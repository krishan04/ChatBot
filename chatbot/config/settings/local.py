from .base import *  # noqa

DEBUG = True

INSTALLED_APPS += ["django_extensions"]  # noqa

# Relax CORS locally
CORS_ALLOW_ALL_ORIGINS = True

# Show emails in console locally
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"