import os

class Config:
    # Security Key (Keep this secret in production)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'

    # Database Configuration (SQLite for local development)
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File Upload Configuration
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB Max Upload Size

    # Mail Config
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'raghavkumar.j@heritagefoods.in'
    MAIL_PASSWORD = 'idne dawk mtei ugic' 
    MAIL_DEFAULT_SENDER = MAIL_USERNAME













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
