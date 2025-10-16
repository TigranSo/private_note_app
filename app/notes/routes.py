from flask import Blueprint, render_template, request, jsonify, current_app, send_file, abort
from flask_login import login_required, current_user
from sqlalchemy import or_
import os
import mimetypes
import uuid

from .. import get_db
from ..models import Note, Tag, Group, Attachment, DriveFile
from ..security import encrypt_text, decrypt_text

notes_bp = Blueprint("notes", __name__)

db = get_db()


@notes_bp.get("/")
@login_required
def index():
    return render_template("notes/index.html")


@notes_bp.get("/api/groups")
@login_required
def list_groups():
    groups = Group.query.filter_by(user_id=current_user.id).order_by(Group.name.asc()).all()
    return jsonify([{"id": g.id, "name": g.name} for g in groups])


@notes_bp.post("/api/groups")
@login_required
def create_group():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    exists = Group.query.filter_by(user_id=current_user.id, name=name).first()
    if exists:
        return jsonify({"error": "exists"}), 409
    g = Group(user_id=current_user.id, name=name)
    db.session.add(g)
    db.session.commit()
    return jsonify({"id": g.id, "name": g.name}), 201


@notes_bp.patch("/api/groups/<int:group_id>")
@login_required
def rename_group(group_id: int):
    g = Group.query.filter_by(id=group_id, user_id=current_user.id).first_or_404()
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    exists = Group.query.filter(Group.user_id == current_user.id, Group.name == name, Group.id != group_id).first()
    if exists:
        return jsonify({"error": "exists"}), 409
    g.name = name
    db.session.commit()
    return jsonify({"ok": True})


@notes_bp.delete("/api/groups/<int:group_id>")
@login_required
def delete_group(group_id: int):
    g = Group.query.filter_by(id=group_id, user_id=current_user.id).first_or_404()
    db.session.delete(g)
    db.session.commit()
    return jsonify({"ok": True})


@notes_bp.get("/api/notes")
@login_required
def list_notes():
    q = request.args.get("q", "").strip().lower()
    tag = request.args.get("tag")
    group_id = request.args.get("group_id", type=int)
    date = request.args.get("date")  # YYYY-MM-DD

    query = Note.query.filter_by(user_id=current_user.id)
    if group_id:
        query = query.join(Note.groups).filter(Group.id == group_id)
    notes = query.order_by(Note.updated_at.desc()).all()

    result = []
    for n in notes:
        content = decrypt_text(n.content_encrypted)
        if q and (q not in n.title.lower() and q not in content.lower()):
            continue
        if tag and not any(t.name == tag for t in n.tags):
            continue
        if date and n.updated_at.strftime('%Y-%m-%d') != date:
            continue
        result.append({
            "id": n.id,
            "title": n.title,
            "content": content,
            "tags": [t.name for t in n.tags],
            "groups": [ {"id": g.id, "name": g.name} for g in n.groups ],
            "attachments": [ {"id": a.id, "filename": a.filename, "mime_type": a.mime_type, "size": a.size_bytes} for a in n.attachments ],
            "updated_at": n.updated_at.isoformat(),
        })
    return jsonify(result)


@notes_bp.get("/search")
@login_required
def search_page():
    return render_template("search.html")


@notes_bp.get("/api/search")
@login_required
def api_search():
    q = (request.args.get("q") or "").strip().lower()
    notes_out = []
    files_out = []
    if q:
        notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.updated_at.desc()).all()
        for n in notes:
            content = decrypt_text(n.content_encrypted)
            if q in (n.title or '').lower() or q in (content or '').lower():
                notes_out.append({
                    "id": n.id,
                    "title": n.title,
                    "snippet": (content or '')[:180],
                    "updated_at": n.updated_at.isoformat(),
                })
        files = DriveFile.query.filter_by(user_id=current_user.id).order_by(DriveFile.uploaded_at.desc()).all()
        for f in files:
            if q in (f.filename or '').lower():
                files_out.append({
                    "id": f.id,
                    "filename": f.filename,
                    "size": f.size_bytes,
                    "uploaded_at": f.uploaded_at.isoformat(),
                })
    return jsonify({"notes": notes_out, "files": files_out})


@notes_bp.post("/api/notes")
@login_required
def create_note():
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip() or "Без названия"
    content = data.get("content") or ""
    tags = data.get("tags") or []
    groups = data.get("groups") or []  

    note = Note(user_id=current_user.id, title=title, content_encrypted=encrypt_text(content))

    tag_models = []
    for name in tags:
        if isinstance(name, str):
            name = name.strip()
        if not name:
            continue
        tag = Tag.query.filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
        tag_models.append(tag)
    note.tags = tag_models

    group_models = []
    for gname in groups:
        if isinstance(gname, str):
            gname = gname.strip()
        if not gname:
            continue
        g = Group.query.filter_by(user_id=current_user.id, name=gname).first()
        if not g:
            g = Group(user_id=current_user.id, name=gname)
            db.session.add(g)
        group_models.append(g)
    note.groups = group_models

    db.session.add(note)
    db.session.commit()

    return jsonify({"id": note.id}), 201


@notes_bp.patch("/api/notes/<int:note_id>")
@login_required
def update_note(note_id: int):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    data = request.get_json(force=True)

    if "title" in data:
        title = (data.get("title") or "").strip()
        if title:
            note.title = title
    if "content" in data:
        note.content_encrypted = encrypt_text(data.get("content") or "")
    if "tags" in data:
        tags = data.get("tags") or []
        tag_models = []
        for name in tags:
            if isinstance(name, str):
                name = name.strip()
            if not name:
                continue
            tag = Tag.query.filter_by(name=name).first()
            if not tag:
                tag = Tag(name=name)
                db.session.add(tag)
            tag_models.append(tag)
        note.tags = tag_models
    if "groups" in data:
        groups = data.get("groups") or []
        group_models = []
        for gname in groups:
            if isinstance(gname, str):
                gname = gname.strip()
            if not gname:
                continue
            g = Group.query.filter_by(user_id=current_user.id, name=gname).first()
            if not g:
                g = Group(user_id=current_user.id, name=gname)
                db.session.add(g)
            group_models.append(g)
        note.groups = group_models

    db.session.commit()
    return jsonify({"ok": True})


@notes_bp.delete("/api/notes/<int:note_id>")
@login_required
def delete_note(note_id: int):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    db.session.delete(note)
    db.session.commit()
    return jsonify({"ok": True})


@notes_bp.post("/api/notes/<int:note_id>/attachments")
@login_required
def upload_attachment(note_id: int):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    if "file" not in request.files:
        return jsonify({"error": "file required"}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "empty filename"}), 400

    uploads_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(uploads_dir, exist_ok=True)
    ext = os.path.splitext(f.filename)[1]
    safe_name = uuid.uuid4().hex + ext
    stored_path = os.path.join(uploads_dir, safe_name)

    # Constraints
    allowed = set((current_app.config.get("ALLOWED_EXTENSIONS") or []))
    ext_lower = (ext[1:] if ext.startswith('.') else ext).lower()
    if allowed and ext_lower not in allowed:
        return jsonify({"error": "type not allowed"}), 415
    # Save and size check
    f.save(stored_path)
    size_bytes = os.path.getsize(stored_path)
    max_mb = int(current_app.config.get("MAX_FILE_SIZE_MB") or 20)
    if size_bytes > max_mb * 1024 * 1024:
        try:
            os.remove(stored_path)
        except Exception:
            pass
        return jsonify({"error": "file too large"}), 413

    att = Attachment(note_id=note.id, filename=f.filename, stored_path=stored_path, mime_type=f.mimetype, size_bytes=size_bytes)
    db.session.add(att)
    db.session.commit()

    return jsonify({"id": att.id, "filename": att.filename, "mime_type": att.mime_type, "size": att.size_bytes}), 201


@notes_bp.get("/api/attachments/<int:att_id>")
@login_required
def download_attachment(att_id: int):
    att = Attachment.query.get_or_404(att_id)
    if att.note.user_id != current_user.id:
        abort(404)
    mime = att.mime_type or mimetypes.guess_type(att.filename)[0] or "application/octet-stream"
    return send_file(att.stored_path, mimetype=mime, as_attachment=False, download_name=att.filename)


@notes_bp.delete("/api/attachments/<int:att_id>")
@login_required
def delete_attachment(att_id: int):
    att = Attachment.query.get_or_404(att_id)
    if att.note.user_id != current_user.id:
        abort(404)
    try:
        if os.path.exists(att.stored_path):
            os.remove(att.stored_path)
    except Exception:
        pass
    db.session.delete(att)
    db.session.commit()
    return jsonify({"ok": True})
