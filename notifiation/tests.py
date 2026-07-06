import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from notifiation.enums import RepetedType
from notifiation.models import Email
from notifiation.tasks import _advance_repeated_date, _get_scheduled_datetime, send_scheduled_emails_task

User = get_user_model()


class EmailRepeatTaskTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='user@example.com',
            password='testpassword',
            plantype='paid',
        )

    def test_get_scheduled_datetime_handles_datetime_field_value(self):
        set_date = timezone.make_aware(datetime.datetime(2026, 7, 1, 1, 2, 3))
        email = Email(user=self.user, set_date=set_date, set_time=datetime.time(9, 0))

        scheduled = _get_scheduled_datetime(email)

        self.assertEqual(scheduled.date(), set_date.date())
        self.assertEqual(scheduled.time(), datetime.time(9, 0))

    def test_advance_repeated_date_monthly_rolls_over_end_of_month(self):
        set_date = timezone.make_aware(datetime.datetime(2026, 1, 31, 8, 0))
        email = Email(user=self.user, set_date=set_date, set_time=datetime.time(9, 0), is_repeated=True, repeated_type=RepetedType.MONTHLY.value)

        _advance_repeated_date(email)

        self.assertEqual(email.set_date.year, 2026)
        self.assertEqual(email.set_date.month, 2)
        self.assertEqual(email.set_date.day, 28)

    def test_advance_repeated_date_yearly_handles_feb_29_non_leap_year(self):
        set_date = timezone.make_aware(datetime.datetime(2024, 2, 29, 8, 0))
        email = Email(user=self.user, set_date=set_date, set_time=datetime.time(9, 0), is_repeated=True, repeated_type=RepetedType.YEARLY.value)

        _advance_repeated_date(email)

        self.assertEqual(email.set_date.year, 2025)
        self.assertEqual(email.set_date.month, 2)
        self.assertEqual(email.set_date.day, 28)

    @patch('notifiation.tasks.send_mail')
    def test_send_scheduled_emails_task_advances_repeated_email(self, mock_send_mail):
        email = Email.objects.create(
            user=self.user,
            set_date=timezone.make_aware(datetime.datetime(2026, 1, 31, 0, 0)),
            set_time=datetime.time(9, 0),
            select_audience=[],
            is_repeated=True,
            repeated_type=RepetedType.MONTHLY.value,
            describe_email='Test repeat email',
            is_active=True,
        )

        count = send_scheduled_emails_task()

        email.refresh_from_db()

        self.assertEqual(count, 1)
        self.assertTrue(mock_send_mail.called)
        self.assertEqual(email.set_date.month, 2)
        self.assertEqual(email.set_date.day, 28)
        self.assertTrue(email.is_active)

    @patch('notifiation.tasks.send_mail')
    def test_send_scheduled_emails_task_personalizes_per_user(self, mock_send_mail):
        user1 = User.objects.create_user(
            email='alice@example.com',
            password='testpassword',
            full_name='Alice',
            userole='normal',
            plantype='free',
        )
        user2 = User.objects.create_user(
            email='bob@example.com',
            password='testpassword',
            full_name='Bob',
            userole='admin',
            plantype='professional',
        )

        send_time = timezone.now() - datetime.timedelta(minutes=5)
        email = Email.objects.create(
            user=self.user,
            set_date=send_time.date(),
            set_time=send_time.time(),
            select_audience=['free', 'professional'],
            describe_email=(
                'Hello {{full_name}}, your email is {{email}}. '
                'Plan: {{plan_name}} ({{badge_label}}). '
                'Billing: {{billing_cycle}}. AI limit: {{ai_query_limit}}'
            ),
            is_active=True,
        )

        count = send_scheduled_emails_task()

        self.assertEqual(count, 2)
        self.assertEqual(mock_send_mail.call_count, 2)

        bodies = [call.args[1] for call in mock_send_mail.call_args_list]
        self.assertIn(
            'Hello Alice, your email is alice@example.com. Plan: Free (Free). Billing: N/A. AI limit: 0',
            bodies,
        )
        self.assertIn(
            'Hello Bob, your email is bob@example.com. Plan: Professional (Pro). Billing: N/A. AI limit: 0',
            bodies,
        )

    @patch('notifiation.tasks.send_mail')
    def test_send_scheduled_emails_task_falls_back_to_n_a_and_zero(self, mock_send_mail):
        user = User.objects.create_user(
            email='fallback@example.com',
            password='testpassword',
            full_name='',
            userole='',
            plantype='free',
        )

        send_time = timezone.now() - datetime.timedelta(minutes=5)
        email = Email.objects.create(
            user=self.user,
            set_date=send_time.date(),
            set_time=send_time.time(),
            select_audience=['free'],
            describe_email=(
                'Hi {{full_name}}, your email is {{email}}. '
                'Role: {{role}}. Plan: {{plan_name}} ({{badge_label}}). '
                'Type: {{plan_type}}. Price: {{price_per_member}}. '
                'Billing: {{billing_cycle}}. AI: {{ai_query_limit}}.'
            ),
            is_active=True,
        )

        count = send_scheduled_emails_task()

        self.assertEqual(count, 1)
        self.assertEqual(mock_send_mail.call_count, 1)

        body = mock_send_mail.call_args_list[0].args[1]
        self.assertIn('Hi Valued User, your email is fallback@example.com.', body)
        self.assertIn('Role: N/A.', body)
        self.assertIn('Plan: Free (Free).', body)
        self.assertIn('Type: Free.', body)
        self.assertIn('Price: 0.', body)
        self.assertIn('Billing: N/A.', body)
        self.assertIn('AI: 0.', body)

    @patch('notifiation.tasks.send_mail')
    def test_send_scheduled_emails_task_rejects_invalid_placeholder(self, mock_send_mail):
        user = User.objects.create_user(
            email='placeholder@example.com',
            password='testpassword',
            full_name='Placeholder User',
            userole='normal',
            plantype='free',
        )

        send_time = timezone.now() - datetime.timedelta(minutes=5)
        email = Email.objects.create(
            user=self.user,
            set_date=send_time.date(),
            set_time=send_time.time(),
            select_audience=['free'],
            describe_email='Hello {{full_name}}, your special token is {{token}}.',
            is_active=True,
        )

        count = send_scheduled_emails_task()

        self.assertEqual(count, 0)
        self.assertEqual(mock_send_mail.call_count, 0)
        email.refresh_from_db()
        self.assertFalse(email.is_active)
