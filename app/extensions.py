from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from celery import Celery
from flask_wtf.csrf import CSRFProtect  # <--- IMPORT THIS

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
migrate = Migrate()
celery = Celery()
csrf = CSRFProtect()  # <--- INITIALIZE THIS