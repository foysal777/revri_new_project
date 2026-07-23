import csv
import io
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class UserManagementEndpointsTests(APITestCase):

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            password='Password123!',
            full_name='Admin User',
            userole='admin',
            is_verified=True,
            is_staff=True,
        )
        self.normal_user = User.objects.create_user(
            email='john@example.com',
            password='Password123!',
            full_name='John Doe',
            userole='normal',
            is_verified=True,
        )

    def test_export_users_csv(self):
        url = reverse('export-users-csv')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="users_export.csv"', response['Content-Disposition'])

        content = response.content.decode('utf-8')
        lines = [line for line in content.splitlines() if line]
        self.assertGreaterEqual(len(lines), 3)  # Header + at least 2 users

        header = lines[0].split(',')
        self.assertEqual(header[0], 'ID')
        self.assertEqual(header[1], 'Email')

        self.assertIn('admin@example.com', content)
        self.assertIn('john@example.com', content)

    def test_get_user_detail(self):
        url = reverse('admin-user-detail', kwargs={'pk': self.normal_user.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'john@example.com')
        self.assertEqual(response.data['full_name'], 'John Doe')

    def test_update_user_detail(self):
        url = reverse('admin-user-detail', kwargs={'pk': self.normal_user.id})
        payload = {
            'full_name': 'John Updated',
            'plantype': 'builder',
            'is_verified': True,
        }
        response = self.client.patch(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.normal_user.refresh_from_db()
        self.assertEqual(self.normal_user.full_name, 'John Updated')
        self.assertEqual(self.normal_user.plantype, 'builder')

    def test_delete_user(self):
        url = reverse('admin-user-detail', kwargs={'pk': self.normal_user.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.normal_user.id).exists())
