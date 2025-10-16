from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf
import os
from .config import Config
from flask_mail import Mail
from sqlalchemy.exc import IntegrityError

_db = SQLAlchemy()
_login_manager = LoginManager()
_csrf = CSRFProtect()
_mail = Mail()


def get_db():
    return _db


def get_login_manager():
    return _login_manager


def get_csrf():
    return _csrf


def get_mail():
    return _mail


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(os.path.join(app.instance_path, "uploads"), exist_ok=True)

    _db.init_app(app)
    _login_manager.init_app(app)
    _csrf.init_app(app)
    _mail.init_app(app)

    _login_manager.login_view = "auth.login"

    @app.context_processor
    def inject_globals():
        return dict(
            csrf_token=generate_csrf,
            APP_ALLOWED_EXTENSIONS=app.config.get("ALLOWED_EXTENSIONS", []),
            APP_MAX_FILE_SIZE_MB=app.config.get("MAX_FILE_SIZE_MB", 20),
            REGISTRATION_ENABLED=app.config.get("REGISTRATION_ENABLED", True),
        )

    from .auth.routes import auth_bp
    from .notes.routes import notes_bp
    from .drive import drive_bp
    try:
        from .admin.routes import admin_bp
    except Exception:
        admin_bp = None

    app.register_blueprint(auth_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(drive_bp)
    if admin_bp:
        app.register_blueprint(admin_bp)

    with app.app_context():
        from . import models  # noqa: F401
        _db.create_all()
        # Secure bootstrap admin if configured and no users exist
        from .models import User
        if User.query.count() == 0:
            admin_email = os.getenv('ADMIN_EMAIL')
            admin_password = os.getenv('ADMIN_PASSWORD')
            if admin_email and admin_password:
                u = User(email=admin_email.strip().lower(), is_admin=True)
                u.set_password(admin_password)
                _db.session.add(u)
                try:
                    _db.session.commit()
                except IntegrityError:
                    _db.session.rollback()

    return app
