import os
from dotenv import load_dotenv

# Load the .env file immediately
load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # 1. Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-fallback-key'

    # 2. Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 3. Uploads
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'} 
    
    # Keep your size limit, it's perfect
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # 4. Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = MAIL_USERNAME
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@heritage.com'
    IT_ADMIN_EMAIL = os.environ.get('IT_ADMIN_EMAIL') or 'it_admin@heritage.com'

    # 6. Celery Configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
    CELERY_TASK_ALWAYS_EAGER = False