from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from .. import get_db
from ..models import User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

db = get_db()


def admin_required():
    return current_user.is_authenticated and current_user.is_admin


@admin_bp.before_request
def check_admin():
    if not admin_required():
        return redirect(url_for("notes.index"))


@admin_bp.get("/")
@login_required
def index():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users)


@admin_bp.post("/users")
@login_required
def create_user():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    is_admin = bool(request.form.get("is_admin"))

    if not email or not password:
        flash("Нужны email и пароль", "danger")
        return redirect(url_for("admin.index"))

    user = User(email=email, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
        flash("Пользователь создан", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Email уже существует", "danger")
    return redirect(url_for("admin.index"))


@admin_bp.post("/users/<int:user_id>/quota")
@login_required
def set_quota(user_id: int):
    if not admin_required():
        return redirect(url_for("notes.index"))
    u = User.query.get_or_404(user_id)
    cnt = request.form.get("file_quota_count")
    mb = request.form.get("file_quota_mb")
    u.file_quota_count = int(cnt) if (cnt or '').strip() else None
    u.file_quota_mb = int(mb) if (mb or '').strip() else None
    db.session.commit()
    flash("Квоты обновлены", "success")
    return redirect(url_for("admin.index"))


@admin_bp.post("/users/<int:user_id>/reset")
@login_required
def reset_password(user_id: int):
    if not admin_required():
        return redirect(url_for("notes.index"))
    new_pass = (request.form.get("password") or "").strip()
    if not new_pass:
        flash("Укажите новый пароль", "danger")
        return redirect(url_for("admin.index"))
    u = User.query.get_or_404(user_id)
    u.set_password(new_pass)
    db.session.commit()
    flash("Пароль обновлён", "success")
    return redirect(url_for("admin.index"))


@admin_bp.post("/users/<int:user_id>/delete")
@login_required
def delete_user(user_id: int):
    if not admin_required():
        return redirect(url_for("notes.index"))
    if current_user.id == user_id:
        flash("Нельзя удалить себя", "danger")
        return redirect(url_for("admin.index"))
    u = User.query.get_or_404(user_id)
    db.session.delete(u)
    db.session.commit()
    flash("Пользователь удалён", "success")
    return redirect(url_for("admin.index"))
