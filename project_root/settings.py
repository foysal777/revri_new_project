import os
from dotenv import load_dotenv 
from pathlib import Path
from dotenv import load_dotenv
from pathlib import Path
from . import ENV
from datetime import timedelta 


BASE_DIR = ENV.BASE_DIR

SECRET_KEY = ENV.SECRET_KEY

DEBUG = ENV.DEBUG

ALLOWED_HOSTS = ENV.ALLOWED_HOSTS

CORS_ALLOWED_ORIGINS = ENV.CORS_ALLOWED_ORIGINS

CORS_ALLOW_HEADERS = ENV.CORS_ALLOW_HEADERS

CSRF_TRUSTED_ORIGINS = ENV.CSRF_TRUSTED_ORIGINS


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "corsheaders",

    'channels',
    'rest_framework',
    "drf_spectacular",
    'rest_framework_simplejwt',
   
    'django_filters',

    'accounts',
    'admin_dashboard',
    'chatsystem',
    'plan',
    'notifiation',
]



MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]



ROOT_URLCONF = 'project_root.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Django 5+ requires a default file storage config for FileField/ImageField.
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

REST_FRAMEWORK = {

    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",

    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.AllowAny',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=30),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=30),
}


ASGI_APPLICATION = 'project_root.asgi.application'
WSGI_APPLICATION = 'project_root.wsgi.application'

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

DATABASES = {
    'default': ENV.DB
}



# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]



EMAIL_BACKEND = ENV.EMAIL_BACKEND 
EMAIL_HOST = ENV.EMAIL_HOST
EMAIL_PORT = ENV.EMAIL_PORT
EMAIL_USE_TLS = ENV.EMAIL_USE_TLS
EMAIL_HOST_USER = ENV.EMAIL_HOST_USER
EMAIL_HOST_PASSWORD = ENV.EMAIL_HOST_PASSWORD

CELERY_BROKER_URL = ENV.REDIS_URL
CELERY_RESULT_BACKEND = ENV.REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [ENV.REDIS_URL],
        }, 
    },
}



LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

USER_TIME_ZONE = 'Asia/Dhaka'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

# Ensure STATIC_URL starts with a leading slash so URLs resolve correctly
STATIC_URL = '/static/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')



OPENAI_API_KEY = ENV.OPENAI_API_KEY
OPENAI_MODEL = ENV.OPENAI_MODEL
OPENAI_EMBEDDING_MODEL = ENV.OPENAI_EMBEDDING_MODEL
VECTOR_STORE_PATH = ENV.VECTOR_STORE_PATH
AI_CHAT_MODEL = ENV.OPENAI_MODEL
AI_EMBEDDING_MODEL = ENV.OPENAI_EMBEDDING_MODEL
AI_VECTOR_STORE_PATH = ENV.VECTOR_STORE_PATH
RAG_TOP_K = ENV.RAG_TOP_K
RAG_MIN_SCORE = ENV.RAG_MIN_SCORE
RAG_CHUNK_SIZE = ENV.RAG_CHUNK_SIZE
RAG_CHUNK_OVERLAP = ENV.RAG_CHUNK_OVERLAP