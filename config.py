# import os
# from dotenv import load_dotenv

# load_dotenv()

# basedir = os.path.abspath(os.path.dirname(__file__))

# class Config:
#     # 1. Environment Detection
#     ENV = os.environ.get('FLASK_ENV', 'production')

#     # 2. Security
#     SECRET_KEY = os.environ.get('SECRET_KEY')
#     if not SECRET_KEY:
#         SECRET_KEY = 'dev-fallback-key-do-not-use-in-prod'

#     # 3. Database
#     SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
#         'sqlite:///' + os.path.join(basedir, 'app.db')
#     SQLALCHEMY_TRACK_MODIFICATIONS = False

#     # 4. Uploads (Local Storage Fallback)
#     # NOTE: This path is used if USE_S3 is False
#     UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
#     ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'} 
#     MAX_CONTENT_LENGTH = 16 * 1024 * 1024

#     # 5. Email Configuration
#     MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
#     MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
#     MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') == 'True'
#     MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
#     MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
#     MAIL_DEFAULT_SENDER = MAIL_USERNAME
#     ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@heritage.com'
#     IT_ADMIN_EMAIL = os.environ.get('IT_ADMIN_EMAIL') or 'it_admin@heritage.com'

#     # 6. Celery Configuration
#     CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
#     CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
#     CELERY_TASK_ALWAYS_EAGER = False

#     # 7. Third Party Integrations
#     IDFY_API_KEY = os.environ.get('IDFY_API_KEY')
#     IDFY_ACCOUNT_ID = os.environ.get('IDFY_ACCOUNT_ID')

#     # 8. AWS S3 Configuration
#     # If this is True, UPLOAD_FOLDER above is ignored
#     USE_S3 = os.environ.get('USE_S3', 'False').lower() == 'true'
    
#     AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
#     AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
#     AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'ap-south-2') 
#     S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # 1. Environment & Security
    ENV = os.environ.get('FLASK_ENV', 'production')
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # --- STRICT PRODUCTION CHECK ---
    if ENV == 'production':
        if not SECRET_KEY:
            raise ValueError("FATAL: SECRET_KEY is missing in production environment.")
    else:
        # Only fallback in dev
        if not SECRET_KEY:
            SECRET_KEY = 'dev-fallback-key-do-not-use-in-prod'

    # 2. Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    if not SQLALCHEMY_DATABASE_URI:
        if ENV == 'production':
             # We can default to SQLite for now per your request, 
             # but normally this should also raise error if you wanted strict Postgres enforcement
             pass 
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 3. File Storage
    USE_S3 = os.environ.get('USE_S3', 'False').lower() == 'true'
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'} 
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # 4. AWS S3 Credentials
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'ap-south-2') 
    S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

    # 5. Email & Notifications
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = MAIL_USERNAME
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@heritage.com'

    # 6. Background Tasks
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
    
    # 7. Integrations
    IDFY_API_KEY = os.environ.get('IDFY_API_KEY')
    IDFY_ACCOUNT_ID = os.environ.get('IDFY_ACCOUNT_ID')