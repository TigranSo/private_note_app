import os
import mimetypes
import uuid
from datetime import datetime, timedelta

from flask import render_template, request, jsonify, current_app, send_file, abort
from flask_login import login_required, current_user

from .. import get_db
from . import drive_bp
from ..models import DriveFile, DriveFolder, drive_file_folders, DriveShare

db = get_db()


def _user_quota_limits():
    if current_user.is_admin:
        return None, None  
    count_limit = current_user.file_quota_count or current_app.config.get("DEFAULT_USER_FILE_QUOTA_COUNT")
    mb_limit = current_user.file_quota_mb or current_app.config.get("DEFAULT_USER_FILE_QUOTA_MB")
    return count_limit, mb_limit


def _user_usage():
    files = DriveFile.query.filter_by(user_id=current_user.id).all()
    total_size = sum((f.size_bytes or 0) for f in files)
    return len(files), total_size


@drive_bp.get("/")
@login_required
def index():
    return render_template("drive/index.html")


@drive_bp.get("/api/files")
@login_required
def list_files():
    q = (request.args.get("q") or "").strip().lower()
    sort = request.args.get('sort', 'date')  
    page = max(1, request.args.get('page', type=int) or 1)
    per_page = max(5, min(100, request.args.get('per_page', type=int) or 20))
    folder_id = request.args.get("folder_id", type=int)
    folders_q = DriveFolder.query.filter_by(user_id=current_user.id, parent_id=folder_id).order_by(DriveFolder.name.asc())
    folders = [{"id": d.id, "name": d.name} for d in folders_q.all()]
    files_q = DriveFile.query.filter_by(user_id=current_user.id)
    if sort == 'name':
        files_q = files_q.order_by(DriveFile.filename.asc())
    elif sort == 'size':
        files_q = files_q.order_by(DriveFile.size_bytes.desc())
    else:
        files_q = files_q.order_by(DriveFile.uploaded_at.desc())
    items = []
    for f in files_q.paginate(page=page, per_page=per_page, error_out=False).items:
        fid = f.folder.id if f.folder else None
        if fid != folder_id:
            continue
        if q and (q not in (f.filename or "").lower()):
            continue
        items.append({
            "id": f.id,
            "filename": f.filename,
            "mime_type": f.mime_type,
            "size": f.size_bytes,
            "uploaded_at": f.uploaded_at.isoformat(),
        })
    used_count, used_bytes = _user_usage()
    count_limit, mb_limit = _user_quota_limits()
    breadcrumbs = []
    cur = DriveFolder.query.get(folder_id) if folder_id else None
    while cur:
        breadcrumbs.append({"id": cur.id, "name": cur.name})
        cur = cur.parent
    breadcrumbs.reverse()
    return jsonify({
        "folders": folders,
        "files": items,
        "usage": {"count": used_count, "bytes": used_bytes},
        "limits": {"count": count_limit, "mb": mb_limit},
        "breadcrumbs": breadcrumbs,
        "pagination": {"page": page, "per_page": per_page}
    })


@drive_bp.post("/api/files")
@login_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "file required"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "empty filename"}), 400

    used_count, used_bytes = _user_usage()
    count_limit, mb_limit = _user_quota_limits()
    if count_limit is not None and used_count >= count_limit:
        return jsonify({"error": "count quota exceeded"}), 403

    uploads_root = current_app.config["UPLOAD_FOLDER"]
    user_dir = os.path.join(uploads_root, "drive", str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    ext = os.path.splitext(f.filename)[1]
    safe_name = uuid.uuid4().hex + ext
    stored_path = os.path.join(user_dir, safe_name)
    ext = os.path.splitext(f.filename)[1]
    allowed = set((current_app.config.get("ALLOWED_EXTENSIONS") or []))
    ext_lower = (ext[1:] if ext.startswith('.') else ext).lower()
    if allowed and ext_lower not in allowed:
        return jsonify({"error": "type not allowed"}), 415
    f.save(stored_path)
    size_bytes = os.path.getsize(stored_path)
    max_mb = int(current_app.config.get("MAX_FILE_SIZE_MB") or 20)
    if size_bytes > max_mb * 1024 * 1024:
        try:
            os.remove(stored_path)
        except Exception:
            pass
        return jsonify({"error": "file too large"}), 413

    if mb_limit is not None:
        new_total_mb = (used_bytes + size_bytes) / (1024 * 1024)
        if new_total_mb > mb_limit:
            try:
                os.remove(stored_path)
            except Exception:
                pass
            return jsonify({"error": "size quota exceeded"}), 403

    df = DriveFile(
        user_id=current_user.id,
        filename=f.filename,
        stored_path=stored_path,
        mime_type=f.mimetype,
        size_bytes=size_bytes,
        uploaded_at=datetime.utcnow(),
    )
    db.session.add(df)
    folder_id = request.args.get("folder_id", type=int)
    if folder_id:
        folder = DriveFolder.query.filter_by(id=folder_id, user_id=current_user.id).first()
        if folder:
            db.session.flush()
            db.session.execute(drive_file_folders.insert().values(file_id=df.id, folder_id=folder.id))
    db.session.commit()
    return jsonify({"id": df.id, "filename": df.filename, "mime_type": df.mime_type, "size": df.size_bytes}), 201


@drive_bp.get("/api/files/<int:file_id>")
@login_required
def download_file(file_id: int):
    f = DriveFile.query.get_or_404(file_id)
    if f.user_id != current_user.id and not current_user.is_admin:
        abort(404)
    mime = f.mime_type or mimetypes.guess_type(f.filename)[0] or "application/octet-stream"
    return send_file(f.stored_path, mimetype=mime, as_attachment=False, download_name=f.filename)


@drive_bp.get('/s/<token>')
def shared_download(token: str):
    share = DriveShare.query.filter_by(token=token).first_or_404()
    if datetime.utcnow() > share.expires_at:
        abort(410)
    f = share.file
    mime = f.mime_type or mimetypes.guess_type(f.filename)[0] or "application/octet-stream"
    return send_file(f.stored_path, mimetype=mime, as_attachment=False, download_name=f.filename)


@drive_bp.delete("/api/files/<int:file_id>")
@login_required
def delete_file(file_id: int):
    f = DriveFile.query.get_or_404(file_id)
    if f.user_id != current_user.id and not current_user.is_admin:
        abort(404)
    try:
        if os.path.exists(f.stored_path):
            os.remove(f.stored_path)
    except Exception:
        pass
    db.session.delete(f)
    db.session.commit()
    return jsonify({"ok": True})


@drive_bp.patch('/api/files/<int:file_id>')
@login_required
def rename_file(file_id: int):
    f = DriveFile.query.get_or_404(file_id)
    if f.user_id != current_user.id:
        abort(404)
    data = request.get_json(force=True)
    newname = (data.get('filename') or '').strip()
    if not newname:
        return jsonify({'error': 'filename required'}), 400
    f.filename = newname
    db.session.commit()
    return jsonify({'ok': True})


@drive_bp.post('/api/files/<int:file_id>/share')
@login_required
def share_file(file_id: int):
    f = DriveFile.query.get_or_404(file_id)
    if f.user_id != current_user.id:
        abort(404)
    data = request.get_json(force=True)
    minutes = max(1, min(10080, int(data.get('minutes') or 60)))
    token = uuid.uuid4().hex
    share = DriveShare(file_id=f.id, token=token, expires_at=datetime.utcnow() + timedelta(minutes=minutes), created_by=current_user.id)
    db.session.add(share)
    db.session.commit()
    return jsonify({'url': f"/drive/s/{token}", 'expires_at': share.expires_at.isoformat()})


@drive_bp.post('/api/folders')
@login_required
def create_folder():
    data = request.get_json(force=True)
    name = (data.get('name') or '').strip()
    parent_id = data.get('parent_id')
    if not name:
        return jsonify({'error': 'name required'}), 400
    parent = None
    if parent_id is not None:
        parent = DriveFolder.query.filter_by(id=parent_id, user_id=current_user.id).first_or_404()
    folder = DriveFolder(user_id=current_user.id, name=name, parent=parent)
    db.session.add(folder)
    db.session.commit()
    return jsonify({'id': folder.id, 'name': folder.name}), 201


@drive_bp.patch('/api/folders/<int:folder_id>')
@login_required
def rename_folder(folder_id: int):
    folder = DriveFolder.query.filter_by(id=folder_id, user_id=current_user.id).first_or_404()
    data = request.get_json(force=True)
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    folder.name = name
    db.session.commit()
    return jsonify({'ok': True})


@drive_bp.delete('/api/folders/<int:folder_id>')
@login_required
def delete_folder(folder_id: int):
    folder = DriveFolder.query.filter_by(id=folder_id, user_id=current_user.id).first_or_404()
    if folder.children:
        return jsonify({'error': 'folder not empty'}), 400
    if folder.files:
        return jsonify({'error': 'move files out before delete'}), 400
    db.session.delete(folder)
    db.session.commit()
    return jsonify({'ok': True})


@drive_bp.patch('/api/files/<int:file_id>/move')
@login_required
def move_file(file_id: int):
    f = DriveFile.query.get_or_404(file_id)
    if f.user_id != current_user.id:
        abort(404)
    data = request.get_json(force=True)
    dest_id = data.get('folder_id')
    db.session.execute(drive_file_folders.delete().where(drive_file_folders.c.file_id == f.id))
    if dest_id:
        dest = DriveFolder.query.filter_by(id=dest_id, user_id=current_user.id).first_or_404()
        db.session.execute(drive_file_folders.insert().values(file_id=f.id, folder_id=dest.id))
    db.session.commit()
    return jsonify({'ok': True})


