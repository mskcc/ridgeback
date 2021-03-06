"""
Django settings for ridgeback project.

Generated by 'django-admin startproject' using Django 2.2.6.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '3gpghwoqas_6ei_efvb%)5s&lwgs#o99c9(ovmi=1od*e6ezvw'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = os.environ.get('RIDGEBACK_ALLOWED_HOSTS', 'localhost').split(',')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'toil_orchestrator.apps.ToilOrchestratorConfig',
    'rest_framework',
    'drf_yasg'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ridgeback.urls'

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

WSGI_APPLICATION = 'ridgeback.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

DB_NAME = os.environ['RIDGEBACK_DB_NAME']
DB_USERNAME = os.environ['RIDGEBACK_DB_USERNAME']
DB_PASSWORD = os.environ['RIDGEBACK_DB_PASSWORD']
DB_HOST = os.environ.get('RIDGEBACK_DB_URL', 'localhost')
DB_PORT = os.environ.get('RIDGEBACK_DB_PORT', 5432)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': DB_NAME,
        'USER': DB_USERNAME,
        'PASSWORD': DB_PASSWORD,
        'HOST': DB_HOST,
        'PORT': DB_PORT
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

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

REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    # 'DEFAULT_PERMISSION_CLASSES': (
    #     'rest_framework.permissions.IsAuthenticated',
    # ),
    # 'DEFAULT_AUTHENTICATION_CLASSES': (
    #     'rest_framework_jwt.authentication.JSONWebTokenAuthentication',
    #     'rest_framework.authentication.SessionAuthentication',
    #     'rest_framework.authentication.BasicAuthentication',
    # ),
}

# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/New_York'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/

LOGIN_URL='/admin/login/'
LOGOUT_URL='/admin/logout/'

SWAGGER_SETTINGS = {
    'VALIDATOR_URL':None
}


CORS_ORIGIN_ALLOW_ALL = True

# Celery settings

RABBITMQ_USERNAME = os.environ.get('RIDGEBACK_RABBITMQ_USERNAME', 'guest')
RABBITMQ_PASSWORD = os.environ.get('RIDGEBACK_RABBITMQ_PASSWORD', 'guest')
RABBITMQ_URL = os.environ.get('RIDGEBACK_RABBITMQ_URL', 'localhost')

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'amqp://%s:%s@%s/' % (RABBITMQ_USERNAME, RABBITMQ_PASSWORD, RABBITMQ_URL) )
RIDGEBACK_DEFAULT_QUEUE = os.environ.get(
    'RIDGEBACK_DEFAULT_QUEUE', 'ridgeback_default_queue')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

#Logging

LOG_PATH = os.environ.get('RIDGEBACK_LOG_PATH', 'ridgeback-server.log')

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
        "file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_PATH,
            "maxBytes": 209715200,
            "backupCount": 10
        }
    },
    "loggers": {
        "django_auth_ldap": {
            "level": "DEBUG", "handlers": ["console"]
        },
        "django": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": True,
        },
    },
}

# Toil settings

TOIL_JOB_STORE_ROOT = os.environ['RIDGEBACK_TOIL_JOB_STORE_ROOT']
TOIL_WORK_DIR_ROOT = os.environ['RIDGEBACK_TOIL_WORK_DIR_ROOT']
TOIL_TMP_DIR_ROOT = os.environ['RIDGEBACK_TOIL_TMP_DIR_ROOT']
LSF_WALLTIME = os.environ['RIDGEBACK_LSF_WALLTIME']
LSF_SLA = os.environ['RIDGEBACK_LSF_SLA']
CWLTOIL = os.environ.get('RIDGEBACK_TOIL', 'cwltoil')


# Cleanup periods

CLEANUP_COMPLETED_JOBS = os.environ.get('RIDGEBACK_CLEANUP_COMPLETED_JOBS', 30)
CLEANUP_FAILED_JOBS = os.environ.get('RIDGEBACK_CLEANUP_FAILED_JOBS', 30)

STATIC_ROOT = 'ridgeback_staticfiles'
STATIC_URL = '/static/'
