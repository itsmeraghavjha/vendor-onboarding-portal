from flask import Flask
from config import DevelopmentConfig
from .extensions import db, login_manager, mail

def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    from .blueprints.auth import auth_bp
    from .blueprints.main import main_bp
    from .blueprints.admin import admin_bp
    from .blueprints.vendor import vendor_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(vendor_bp)

    with app.app_context():
        db.create_all()

    return app
