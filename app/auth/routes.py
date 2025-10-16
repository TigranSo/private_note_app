from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError
import os
import uuid
import random
from datetime import datetime, timedelta
import mimetypes
from flask_mail import Message

from .. import get_db, get_login_manager, get_mail
from ..models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

db = get_db()
login_manager = get_login_manager()
mail = get_mail()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@auth_bp.get("/login")
def login():
    return render_template("auth/login.html")


@auth_bp.post("/login")
def login_post():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        flash("Неверные учетные данные", "danger")
        return redirect(url_for("auth.login"))

    now = datetime.utcnow()
    if user.otp_locked_until and now < user.otp_locked_until:
        remain = int((user.otp_locked_until - now).total_seconds() // 60) + 1
        flash(f"Аккаунт временно заблокирован для OTP. Подождите ~{remain} мин.", "danger")
        return redirect(url_for("auth.login"))

    window_start = (user.otp_last_sent_at or (now - timedelta(hours=1)))
    if (now - window_start) <= timedelta(hours=1):
        user.otp_send_count = (user.otp_send_count or 0) + 1
    else:
        user.otp_send_count = 1
    user.otp_last_sent_at = now
    if user.otp_send_count > 5 and not current_app.debug:
        flash("Слишком много попыток. Попробуйте позже.", "danger")
        db.session.commit()
        return redirect(url_for("auth.login"))

    code = f"{random.randint(1000, 9999)}"
    user.otp_code = code
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
    db.session.commit()
    try:
        msg = Message(subject="Код входа", recipients=[user.email])
        msg.body = f"Ваш код: {code}. Действителен 10 минут."
        mail.send(msg)
        flash("Мы отправили код подтверждения на вашу почту", "success")
    except Exception:

        flash(f"Код для входа: {code} (почта не настроена)", "warning")
    return redirect(url_for("auth.verify", email=user.email))


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.get("/profile")
@login_required
def profile():
    return render_template("auth/profile.html")


@auth_bp.post("/profile")
@login_required
def update_profile():
    name = (request.form.get("name") or "").strip()
    password = request.form.get("password") or ""
    if name:
        current_user.name = name
    if password:
        current_user.set_password(password)
    if "avatar" in request.files:
        f = request.files["avatar"]
        if f and f.filename:
            uploads_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "avatars")
            os.makedirs(uploads_dir, exist_ok=True)
            ext = os.path.splitext(f.filename)[1]
            safe_name = uuid.uuid4().hex + ext
            path = os.path.join(uploads_dir, safe_name)
            f.save(path)
            current_user.avatar_path = path
    db.session.commit()
    flash("Профиль обновлен", "success")
    return redirect(url_for("auth.profile"))


@auth_bp.get('/avatar/<int:user_id>')
@login_required
def user_avatar(user_id: int):
    u = User.query.get_or_404(user_id)
    if not u.avatar_path or not os.path.exists(u.avatar_path):
        return ("", 404)
    mime = mimetypes.guess_type(u.avatar_path)[0] or 'image/jpeg'
    return send_file(u.avatar_path, mimetype=mime)


@auth_bp.get('/register')
def register():
    if not current_app.config.get('REGISTRATION_ENABLED', True):
        flash('Регистрация отключена. Обратитесь к администратору.', 'warning')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html')


@auth_bp.post('/register')
def register_post():
    if not current_app.config.get('REGISTRATION_ENABLED', True):
        flash('Регистрация отключена. Обратитесь к администратору.', 'warning')
        return redirect(url_for('auth.login'))
    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password') or ''
    if not email or not password:
        flash('Укажите email и пароль', 'danger')
        return redirect(url_for('auth.register'))
    exists = User.query.filter_by(email=email).first()
    if exists:
        flash('Такой email уже зарегистрирован', 'danger')
        return redirect(url_for('auth.register'))
    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash('Аккаунт создан. Выполните вход.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.get('/verify')
def verify():
    email = request.args.get('email', '')
    return render_template('auth/verify.html', email=email)


@auth_bp.post('/verify')
def verify_post():
    email = (request.form.get('email') or '').strip().lower()
    code = (request.form.get('code') or '').strip()
    user = User.query.filter_by(email=email).first()
    if not user or not user.otp_code or not user.otp_expires_at:
        flash('Сессия подтверждения не найдена. Войдите заново.', 'danger')
        return redirect(url_for('auth.login'))
    now = datetime.utcnow()
    if user.otp_locked_until and now < user.otp_locked_until:
        flash('Слишком много неверных кодов. Попробуйте позже.', 'danger')
        return redirect(url_for('auth.verify', email=email))
    if datetime.utcnow() > user.otp_expires_at or code != user.otp_code:
        user.otp_fail_count = (user.otp_fail_count or 0) + 1
        if user.otp_fail_count >= 5 and not current_app.debug:
            user.otp_locked_until = now + timedelta(minutes=15)
            user.otp_fail_count = 0
        db.session.commit()
        flash('Неверный или просроченный код', 'danger')
        return redirect(url_for('auth.verify', email=email))
    user.otp_code = None
    user.otp_expires_at = None
    user.otp_fail_count = 0
    user.otp_locked_until = None
    if not user.email_verified_at:
        user.email_verified_at = datetime.utcnow()
    db.session.commit()
    login_user(user)
    return redirect(url_for('notes.index'))
