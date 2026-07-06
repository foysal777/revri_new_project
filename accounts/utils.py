import random
from django.core.mail import send_mail
from django.conf import settings

def generate_otp():
    return str(random.randint(1000, 9999))

def send_otp_email(email, otp):
    subject = 'Your Verification OTP'
    message = f'Your OTP for verification is: {otp}'
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [email],
        fail_silently=False,
    )
