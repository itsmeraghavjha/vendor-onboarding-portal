from flask import Flask, flash, redirect, url_for, request
from config import Config
# 1. Add 'csrf' to the imports
from .extensions import db, login_manager, mail, migrate, celery, csrf, limiter
from .models import User
from dotenv import load_dotenv
from .celery_utils import init_celery
from werkzeug.exceptions import RequestEntityTooLarge

load_dotenv()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Extensions
    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # --- REGISTER LIMITER ---
    limiter.init_app(app)
    
    # 2. IMPORTANT: Initialize CSRF Protection
    csrf.init_app(app) 

    # Initialize Celery
    init_celery(app, celery)
    
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register Blueprints
    from .blueprints.main import main_bp
    from .blueprints.auth import auth_bp
    from .blueprints.admin import admin_bp
    from .blueprints.vendor import vendor_bp
    from .blueprints.masters import masters_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(vendor_bp, url_prefix='/vendor')
    app.register_blueprint(masters_bp, url_prefix='/admin/masters')

    

    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(e):
        flash("File upload error: One of your files is larger than 16MB.", "error")
        if request.referrer:
            return redirect(request.referrer)
        return redirect(request.url)

    with app.app_context():
        db.create_all()

    

    return app