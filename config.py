# import os

# class Config:
#     # Security Key (Keep this secret in production)
#     SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'

#     # Database Configuration (SQLite for local development)
#     basedir = os.path.abspath(os.path.dirname(__file__))
#     SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
#         'sqlite:///' + os.path.join(basedir, 'app.db')
#     SQLALCHEMY_TRACK_MODIFICATIONS = False

#     # File Upload Configuration
#     UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
#     ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
#     MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB Max Upload Size

#     # Mail Config
#     MAIL_SERVER = 'smtp.gmail.com'
#     MAIL_PORT = 587
#     MAIL_USE_TLS = True
#     MAIL_USERNAME = 'raghavkumar.j@heritagefoods.in'
#     MAIL_PASSWORD = 'idne dawk mtei ugic' 
#     MAIL_DEFAULT_SENDER = MAIL_USERNAME






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

    # 3. Uploads (Fixed from our previous step)
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # 4. Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = MAIL_USERNAME

    # 5. Workflow Configuration (New!)
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@heritage.com'
    IT_ADMIN_EMAIL = os.environ.get('IT_ADMIN_EMAIL') or 'it_admin@heritage.com'






#     import os

# class Config:
#     SECRET_KEY = os.environ.get('SECRET_KEY') or 'heritage-foods-production-key'
#     SQLALCHEMY_TRACK_MODIFICATIONS = False
    
#     # Uploads
#     UPLOAD_FOLDER = os.path.join(os.getcwd(), 'app', 'static', 'uploads')
#     ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

#     # Mail Config
#     MAIL_SERVER = 'smtp.gmail.com'
#     MAIL_PORT = 587
#     MAIL_USE_TLS = True
#     MAIL_USERNAME = 'raghavkumar.j@heritagefoods.in'
#     MAIL_PASSWORD = 'idne dawk mtei ugic' 
#     MAIL_DEFAULT_SENDER = MAIL_USERNAME

# class DevelopmentConfig(Config):
#     DEBUG = True
#     SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(os.getcwd(), 'instance', 'heritage_vendor.db')

# class ProductionConfig(Config):
#     DEBUG = False
#     SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
