"""Clean scheduler for sending scheduled emails with proper timezone handling."""
from __future__ import annotations

import calendar
import datetime
import logging
import re

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from zoneinfo import ZoneInfo

from accounts.enums import UserRole
from plan.enums import PlanType
from plan.models import Plans
from .models import Email
from .enums import RepetedType

logger = logging.getLogger(__name__)
User = get_user_model()


def get_email_timezone(email: Email) -> ZoneInfo:
    """Get timezone for email. Priority: email.user_time_zone → user.time_zone → settings default."""
    tz_name = (
        getattr(email, 'user_time_zone', None) 
        or getattr(email.user, 'time_zone', None) 
        or getattr(settings, 'USER_TIME_ZONE', 'UTC')
    )
    try:
        return ZoneInfo(tz_name)
    except Exception:
        logger.warning(f"Invalid timezone '{tz_name}', using UTC")
        return ZoneInfo('UTC')


def get_scheduled_datetime(email: Email) -> datetime.datetime | None:
    """
    Convert stored local date/time to UTC datetime for comparison.
    Stored values are naive (local time) — we interpret them in the email's timezone.
    """
    if email.set_date is None or email.set_time is None:
        return None

    # Create timezone-aware datetime from local values
    local_tz = get_email_timezone(email)
    local_dt = datetime.datetime.combine(email.set_date, email.set_time)
    local_dt = local_dt.replace(tzinfo=local_tz)
    
    # Convert to UTC for comparison with timezone.now()
    utc_dt = local_dt.astimezone(datetime.timezone.utc)
    
    logger.debug(
        f"Email {email.id}: local={email.set_date} {email.set_time} "
        f"({local_tz}) → UTC={utc_dt}"
    )
    return utc_dt


_get_scheduled_datetime = get_scheduled_datetime

DYNAMIC_EMAIL_FIELDS = {
    'full_name', 'email', 'role', 'plan_name', 'plan_type',
    'price_per_member', 'billing_cycle', 'ai_query_limit', 'badge_label'
}

PLACEHOLDER_PATTERN = re.compile(r'{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}')
ALL_PLACEHOLDERS_PATTERN = re.compile(r'{{\s*(.*?)\s*}}')
VALID_PLACEHOLDER_KEY = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def _get_user_plan(user):
    """Resolve a plan record based on the user's plan type."""
    plan_type = getattr(user, 'plantype', None)
    if not plan_type:
        return None

    try:
        return Plans.objects.filter(plantype=plan_type).order_by('-updated_at').first()
    except Exception as e:
        logger.warning(
            f"Could not resolve plan record for user {getattr(user, 'email', 'unknown')}: {e}"
        )
        return None


def get_plan_users(plan_types: list[str]):
    """Get active users matching the requested plan types."""
    if not plan_types:
        return User.objects.filter(is_active=True)

    try:
        return User.objects.filter(is_active=True, plantype__in=plan_types)
    except Exception:
        logger.warning(f"Could not filter by plan types {plan_types}, using all active users")
        return User.objects.filter(is_active=True)


def _get_plan_price_per_member(user) -> str:
    """Resolve a price-per-member value from the user's plan, if defined."""
    plan = _get_user_plan(user)
    if plan and plan.price is not None:
        return str(plan.price)
    return '0'


def _get_badge_label(plan, plan_type, plan_name):
    """Derive a badge label from plan data or plan type."""
    if plan and plan.name:
        return plan.name

    normalized = plan_type.lower() if isinstance(plan_type, str) else ''
    if 'professional' in normalized:
        return 'Pro'
    if 'paid' in normalized:
        return 'Paid'
    if 'free' in normalized:
        return 'Free'
    return plan_name or 'N/A'


def _build_email_context(user):
    """Build the full substitution context for an individual user."""
    plan = _get_user_plan(user)
    plan_type_raw = getattr(user, 'plantype', None)
    plan_name = plan.name if plan and plan.name else (plan_type_raw.replace('_', ' ').title() if plan_type_raw else 'N/A')
    plan_type = plan_type_raw.replace('_', ' ').title() if plan_type_raw else 'N/A'
    badge_label = _get_badge_label(plan, plan_type_raw or '', plan_name)

    role_value = getattr(user, 'userole', None)
    if role_value not in {UserRole.ADMIN.value, UserRole.NORMAL.value}:
        role_value = 'N/A'

    return {
        'full_name': user.full_name or 'Valued User',
        'email': user.email or 'N/A',
        'role': role_value,
        'plan_name': plan_name,
        'plan_type': plan_type,
        'price_per_member': _get_plan_price_per_member(user) or '0',
        'billing_cycle': 'N/A',
        'ai_query_limit': '0',
        'badge_label': badge_label,
    }


def _validate_placeholders(template: str) -> None:
    """Validate that every placeholder in the template is supported."""
    placeholders = ALL_PLACEHOLDERS_PATTERN.findall(template)
    for raw_key in placeholders:
        if not VALID_PLACEHOLDER_KEY.match(raw_key):
            raise ValueError(f"Unsupported placeholder format: '{{{{{raw_key}}}}}'")
        if raw_key not in DYNAMIC_EMAIL_FIELDS:
            raise ValueError(f"Unsupported placeholder: '{{{{{raw_key}}}}}'")


def _substitute_placeholders(template: str, context: dict) -> tuple[str, int, list[str]]:
    """Replace variables in the template with the user's context values."""
    _validate_placeholders(template)
    fallback_fields: set[str] = set()

    def replace(match):
        key = match.group(1)
        value = context.get(key, '')
        if key in {'full_name', 'email', 'role'} and not str(value).strip():
            fallback_fields.add(key)
        if key in {'plan_name', 'plan_type', 'billing_cycle', 'badge_label'} and value in {'N/A', ''}:
            fallback_fields.add(key)
        if key in {'price_per_member', 'ai_query_limit'} and value in {'0', '', None}:
            fallback_fields.add(key)

        return str(value)

    result, substitutions = PLACEHOLDER_PATTERN.subn(replace, template)
    unresolved = ALL_PLACEHOLDERS_PATTERN.findall(result)
    if unresolved:
        raise ValueError(f"Unresolved placeholders remain: {unresolved}")

    return result, substitutions, sorted(fallback_fields)


def _format_send_log(recipient_full_name, recipient_email, segment_name, status, substitution_count, fallback_fields):
    fallback_text = ', '.join(fallback_fields) if fallback_fields else 'none'
    return (
        f"To: {recipient_full_name} <{recipient_email}> | "
        f"Segment: {segment_name} | "
        f"Status: {status} | "
        f"Replaced: {substitution_count} | "
        f"Fallbacks: {fallback_text}"
    )


def advance_repeated_date(email: Email) -> None:
    """Advance email date for next occurrence (DAILY/WEEKLY/MONTHLY/YEARLY)."""
    local_tz = get_email_timezone(email)
    local_dt = datetime.datetime.combine(email.set_date, email.set_time).replace(tzinfo=local_tz)
    
    if email.repeated_type == RepetedType.DAILY.value:
        local_dt += datetime.timedelta(days=1)
    elif email.repeated_type == RepetedType.WEEKLY.value:
        local_dt += datetime.timedelta(weeks=1)
    elif email.repeated_type == RepetedType.MONTHLY.value:
        # Move to same day next month (or last day if month is shorter)
        next_month = local_dt.month + 1 if local_dt.month < 12 else 1
        next_year = local_dt.year if local_dt.month < 12 else local_dt.year + 1
        last_day = calendar.monthrange(next_year, next_month)[1]
        day = min(local_dt.day, last_day)
        local_dt = local_dt.replace(year=next_year, month=next_month, day=day)
    elif email.repeated_type == RepetedType.YEARLY.value:
        try:
            local_dt = local_dt.replace(year=local_dt.year + 1)
        except ValueError:  # Feb 29 in leap year
            local_dt = local_dt.replace(year=local_dt.year + 1, month=2, day=28)
    else:
        email.is_active = False
        return
    
    # Store back as naive local values
    email.set_date = local_dt.date()
    email.set_time = local_dt.time().replace(microsecond=0)


_advance_repeated_date = advance_repeated_date

@shared_task(bind=True, max_retries=3)
def send_scheduled_emails_task(self) -> int:
    """
    Main scheduler task: check all active emails and send those that are due.
    Runs every 1-2 minutes via Celery beat.
    """
    now_utc = timezone.now()
    count = 0
    
    logger.info(f"🔄 Scheduler started at {now_utc}")
    
    active_emails = Email.objects.filter(is_active=True)
    logger.info(f"   Found {active_emails.count()} active emails")
    
    for email in active_emails:
        try:
            scheduled_utc = get_scheduled_datetime(email)
            
            if scheduled_utc is None:
                logger.warning(f"   Email {email.id}: missing set_date or set_time, skipping")
                continue
            
            if scheduled_utc > now_utc:
                logger.debug(f"   Email {email.id}: not yet due (due at {scheduled_utc})")
                continue
            
            # Email is due — process it
            logger.info(f"   Email {email.id}: ⏰ DUE — sending...")
            
            # Get plan types and resolve recipient users
            audience = email.select_audience or []
            if isinstance(audience, dict):
                audience = list(audience.values())
            elif not isinstance(audience, list):
                audience = [audience]

            plan_types = [v for v in audience if v in {c[0] for c in PlanType.choices()}]
            recipient_users = get_plan_users(plan_types)

            if not recipient_users.exists():
                logger.warning(f"   Email {email.id}: no recipients found, marking inactive")
                email.is_active = False
                email.save(update_fields=['is_active'])
                continue

            subject = f"Scheduled message from {email.user.full_name or email.user.email}"
            template = email.describe_email or ""
            sent_any = False
            segment_name = ','.join(plan_types) if plan_types else 'all'

            for recipient in recipient_users.order_by('id').iterator():
                try:
                    context = _build_email_context(recipient)
                    body, substitutions, fallback_fields = _substitute_placeholders(template, context)

                    send_mail(
                        subject,
                        body,
                        settings.DEFAULT_FROM_EMAIL,
                        [recipient.email],
                        fail_silently=False,
                    )
                    sent_any = True
                    count += 1
                    logger.info(_format_send_log(
                        recipient_full_name=context['full_name'],
                        recipient_email=recipient.email,
                        segment_name=segment_name,
                        status='Sent ✓',
                        substitution_count=substitutions,
                        fallback_fields=fallback_fields,
                    ))
                except ValueError as substitution_error:
                    logger.error(
                        f"   Email {email.id}: ❌ Failed to personalize email for {recipient.email}: {substitution_error}"
                    )
                except Exception as e:
                    logger.error(_format_send_log(
                        recipient_full_name=context.get('full_name', recipient.email),
                        recipient_email=recipient.email,
                        segment_name=segment_name,
                        status='Failed ✗',
                        substitution_count=substitutions if 'substitutions' in locals() else 0,
                        fallback_fields=fallback_fields if 'fallback_fields' in locals() else [],
                    ))
                    logger.error(f"   Email {email.id}: ❌ Send failed for {recipient.email}: {e}")
                    raise self.retry(exc=e, countdown=60, max_retries=3)

            if not sent_any:
                logger.warning(f"   Email {email.id}: no personalized emails were sent")
                email.is_active = False
                email.save(update_fields=['is_active'])
                continue
            
            # Handle repetition
            if email.is_repeated and email.repeated_type:
                advance_repeated_date(email)
                logger.info(f"   Email {email.id}: 🔁 Repeated — next: {email.set_date} {email.set_time}")
            else:
                email.is_active = False
                logger.info(f"   Email {email.id}: 🛑 Not repeated — marked inactive")
            
            email.save(update_fields=['is_active', 'set_date', 'set_time'])
            
        except Exception as e:
            logger.error(f"   Email {email.id}: 💥 Unexpected error: {e}", exc_info=True)
            continue
    
    logger.info(f"✅ Scheduler completed — sent {count} email(s)")
    return count
