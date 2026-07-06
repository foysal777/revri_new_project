from __future__ import annotations

import calendar
import datetime
from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from plan.enums import PlanType
from .models import Email
from notifiation.enums import RepetedType

User = get_user_model()


def _get_scheduled_datetime(email: Email) -> datetime.datetime | None:
    if email.set_date is None or email.set_time is None:
        return None

    set_date_value = email.set_date
    if isinstance(set_date_value, datetime.datetime):
        set_date_value = set_date_value.date()
    # Treat stored set_date/set_time as the user's local date/time. Use
    # the user's timezone (or default) to make a timezone-aware datetime,
    # then convert that instant to UTC for comparison with `now`.
    scheduled_local = datetime.datetime.combine(set_date_value, email.set_time)
    local_tz = _get_email_timezone(email)
    if timezone.is_naive(scheduled_local):
        scheduled_local = scheduled_local.replace(tzinfo=local_tz)
    else:
        scheduled_local = scheduled_local.astimezone(local_tz)

    scheduled = scheduled_local.astimezone(datetime.timezone.utc)
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[EMAIL SCHEDULER] Email ID {email.id}: set_date={email.set_date}, set_time={email.set_time} => scheduled_at={scheduled}")
    
    return scheduled



def _get_plan_users(plan_types: list[str]):
    if not plan_types:
        return User.objects.filter(is_active=True)

    user_fields = {field.name for field in User._meta.get_fields()}
    # If User model actually stores a `plantype` field, query directly.
    if 'plantype' in user_fields:
        return User.objects.filter(is_active=True, plantype__in=plan_types)

    # If there is no plans/relation on the User model, we can't determine
    # plan membership. Fall back to returning all active users so scheduled
    # emails are delivered instead of silently dropping them.
    if 'plans' not in user_fields:
        return User.objects.filter(is_active=True)

    # Otherwise attempt to build recipients from per-user plans relationship.
    candidate_users = []
    for user in User.objects.filter(is_active=True):
        if getattr(user, 'plantype', None) in plan_types:
            candidate_users.append(user.id)
            continue

        if hasattr(user, 'plans'):
            try:
                if any(getattr(plan, 'plantype', None) in plan_types for plan in user.plans.all()):
                    candidate_users.append(user.id)
            except Exception:
                pass

    return User.objects.filter(id__in=candidate_users)



def _get_email_timezone(email: Email) -> ZoneInfo:
    # Priority: explicit timezone set on the Email -> user's profile -> project default
    tz_name = getattr(email, 'user_time_zone', None) or getattr(email.user, 'time_zone', None) or getattr(settings, 'USER_TIME_ZONE', 'UTC')
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo('UTC')


def _advance_repeated_date(email: Email) -> None:
    local_tz = _get_email_timezone(email)
    # Stored values are local; make a tz-aware local datetime to advance
    local_dt = datetime.datetime.combine(email.set_date, email.set_time).replace(tzinfo=local_tz)

    if email.repeated_type == RepetedType.DAILY.value:
        local_dt = local_dt + datetime.timedelta(days=1)
    elif email.repeated_type == RepetedType.WEEKLY.value:
        local_dt = local_dt + datetime.timedelta(weeks=1)
    elif email.repeated_type == RepetedType.MONTHLY.value:
        next_month = local_dt.month + 1
        next_year = local_dt.year
        if next_month > 12:
            next_month = 1
            next_year += 1

        last_day = calendar.monthrange(next_year, next_month)[1]
        next_day = min(local_dt.day, last_day)
        local_dt = local_dt.replace(year=next_year, month=next_month, day=next_day)
    elif email.repeated_type == RepetedType.YEARLY.value:
        try:
            local_dt = local_dt.replace(year=local_dt.year + 1)
        except ValueError:
            local_dt = local_dt.replace(year=local_dt.year + 1, month=2, day=28)
    else:
        email.is_active = False
        return

    next_utc_dt = local_dt.astimezone(datetime.timezone.utc)
    # Persist the next date/time in local values (naive date/time fields).
    email.set_date = local_dt.date()
    email.set_time = local_dt.time().replace(microsecond=0)



def _send_email_to_recipients(email: Email, recipient_emails: list[str]) -> bool:
    import logging
    logger = logging.getLogger(__name__)
    
    if not recipient_emails:
        logger.warning(f"[EMAIL] No recipients to send to for email ID {email.id}")
        return False

    subject = f"Scheduled message from {email.user.full_name or email.user.email}"
    message = email.describe_email or ''

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipient_emails,
            fail_silently=False,
        )
        logger.info(f"[EMAIL] ✓ Sent to {len(recipient_emails)} recipients")
        return True
    except Exception as e:
        logger.error(f"[EMAIL] ✗ Failed to send: {str(e)}")
        return False


@shared_task
def send_scheduled_emails_task() -> int:
    import logging
    logger = logging.getLogger(__name__)
    
    now = timezone.now()
    count = 0
    emails = Email.objects.filter(is_active=True)
    
    logger.info(f"[EMAIL SCHEDULER] Task started. Current time: {now}. Found {emails.count()} active emails.")

    for email in emails:
        scheduled_at = _get_scheduled_datetime(email)
        if scheduled_at is None:
            logger.warning(f"[EMAIL SCHEDULER] Email ID {email.id}: set_date or set_time is None. Skipping.")
            continue
        
        if scheduled_at > now:
            logger.debug(f"[EMAIL SCHEDULER] Email ID {email.id}: Not yet due. scheduled={scheduled_at}, now={now}")
            continue
        
        logger.info(f"[EMAIL SCHEDULER] Email ID {email.id}: DUE! Processing...")
        
        # Handle both list and dict formats for select_audience (for backward compatibility)
        audience = email.select_audience
        if isinstance(audience, dict):
            audience = list(audience.values())
        elif not isinstance(audience, list):
            audience = [audience]
        
        plan_types = [value for value in audience if value in {choice[0] for choice in PlanType.choices()}]
        logger.info(f"[EMAIL SCHEDULER] Email ID {email.id}: Target plan types: {plan_types}")
        
        recipients = _get_plan_users(plan_types)
        recipient_emails = [user.email for user in recipients]
        logger.info(f"[EMAIL SCHEDULER] Email ID {email.id}: Found {len(recipient_emails)} recipients: {recipient_emails}")

        if _send_email_to_recipients(email, recipient_emails):
            count += 1
            logger.info(f"[EMAIL SCHEDULER] Email ID {email.id}: ✓ Sent successfully")
            if email.is_repeated and email.repeated_type:
                _advance_repeated_date(email)
                logger.info(f"[EMAIL SCHEDULER] Email ID {email.id}: Repeated. Next date: {email.set_date}")
            else:
                email.is_active = False
                logger.info(f"[EMAIL SCHEDULER] Email ID {email.id}: Not repeated. Marked inactive.")
            email.save(update_fields=['is_active', 'set_date', 'set_time'])
        else:
            logger.error(f"[EMAIL SCHEDULER] Email ID {email.id}: ✗ Failed to send")
    
    logger.info(f"[EMAIL SCHEDULER] Task completed. Sent {count} emails.")
    return count
