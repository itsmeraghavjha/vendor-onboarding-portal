from flask import Flask
from config import Config
# 1. Added 'migrate' to imports
from .extensions import db, login_manager, mail, migrate, celery
from .models import User
# 2. Added dotenv to load environment variables
from dotenv import load_dotenv
from .celery_utils import init_celery

# 3. Load .env file before app creation
load_dotenv()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Extensions
    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    # 4. Initialize Migrate
    migrate.init_app(app, db) 

    # Initialize Celery
    init_celery(app, celery)
    
    # Configure Login Manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # --- CRITICAL FIX: USER LOADER ---
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register Blueprints
    from .blueprints.main import main_bp
    from .blueprints.auth import auth_bp
    from .blueprints.admin import admin_bp
    from .blueprints.vendor import vendor_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(vendor_bp, url_prefix='/vendor')

    # Create DB Tables
    # Note: With Flask-Migrate, you typically use 'flask db upgrade' instead of this,
    # but keeping it here is fine for development to ensure tables exist.
    with app.app_context():
        db.create_all()

    return app