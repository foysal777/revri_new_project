
import os
import environ
from dotenv import load_dotenv


load_dotenv()


BASE_DIR = os.path.abspath('.')


env = environ.Env(
    DEBUG=(bool, False),
    DATABASE_URL=(str, f'sqlite:///{BASE_DIR}/db.sqlite3'),
)

DB = env.db('DATABASE_URL')


SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env("ALLOWED_HOSTS").split(",")
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS").split(",")

EMAIL_BACKEND = env("EMAIL_BACKEND")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env.int("EMAIL_PORT")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="postmaster@revboostai.net")

_csrf = env("CSRF_TRUSTED_ORIGINS", default="")

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CORS_ALLOW_HEADERS = env.list("CORS_ALLOW_HEADERS", default=[
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "ngrok-skip-browser-warning",
])

STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET")

PAYMENT_SUCCESS_URL=env("PAYMENT_SUCCESS_URL")
PAYMENT_CANCEL_URL=env("PAYMENT_CANCEL_URL")

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")



OPENAI_API_KEY=env("OPENAI_API_KEY")
OPENAI_MODEL=env("OPENAI_MODEL")
OPENAI_EMBEDDING_MODEL=env("OPENAI_EMBEDDING_MODEL")

VECTOR_STORE_PATH=env("VECTOR_STORE_PATH")

RAG_TOP_K=env.int("RAG_TOP_K")
RAG_MIN_SCORE=env.float("RAG_MIN_SCORE")
RAG_CHUNK_SIZE=env.int("RAG_CHUNK_SIZE")
RAG_CHUNK_OVERLAP=env.int("RAG_CHUNK_OVERLAP")