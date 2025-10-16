from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Table, Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from . import get_db

db = get_db()

note_tags = Table(
    "note_tags",
    db.metadata,
    Column("note_id", Integer, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

note_groups = Table(
    "note_groups",
    db.metadata,
    Column("note_id", Integer, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
)

drive_file_folders = Table(
    "drive_file_folders",
    db.metadata,
    Column("file_id", Integer, ForeignKey("drive_files.id", ondelete="CASCADE"), primary_key=True),
    Column("folder_id", Integer, ForeignKey("drive_folders.id", ondelete="CASCADE"), nullable=False),
)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    name = db.Column(db.String(255), nullable=True)
    avatar_path = db.Column(db.String(512), nullable=True)
    email_verified_at = db.Column(db.DateTime, nullable=True)
    otp_code = db.Column(db.String(8), nullable=True)
    otp_expires_at = db.Column(db.DateTime, nullable=True)
    otp_send_count = db.Column(db.Integer, nullable=True)
    otp_last_sent_at = db.Column(db.DateTime, nullable=True)
    otp_fail_count = db.Column(db.Integer, nullable=True)
    otp_locked_until = db.Column(db.DateTime, nullable=True)
    file_quota_count = db.Column(db.Integer, nullable=True)  
    file_quota_mb = db.Column(db.Integer, nullable=True)    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    notes = relationship("Note", back_populates="user", cascade="all, delete-orphan")
    groups = relationship("Group", back_populates="user", cascade="all, delete-orphan")
    drive_files = relationship("DriveFile", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Note(db.Model):
    __tablename__ = "notes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content_encrypted = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="notes")
    tags = relationship("Tag", secondary=note_tags, back_populates="notes")
    attachments = relationship("Attachment", back_populates="note", cascade="all, delete-orphan")
    groups = relationship("Group", secondary=note_groups, back_populates="notes")


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False, index=True)

    notes = relationship("Note", secondary=note_tags, back_populates="tags")


class Group(db.Model):
    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="groups")
    notes = relationship("Note", secondary=note_groups, back_populates="groups")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_group_user_name"),
    )


class Attachment(db.Model):
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(512), nullable=False)
    mime_type = db.Column(db.String(128), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    note = relationship("Note", back_populates="attachments")


class DriveFile(db.Model):
    __tablename__ = "drive_files"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(512), nullable=False)
    mime_type = db.Column(db.String(128), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="drive_files")
    folder = relationship("DriveFolder", secondary=drive_file_folders, uselist=False, back_populates="files")


class DriveFolder(db.Model):
    __tablename__ = "drive_folders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("drive_folders.id", ondelete="CASCADE"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parent = relationship("DriveFolder", remote_side=[id], backref="children")
    files = relationship("DriveFile", secondary=drive_file_folders, back_populates="folder")

    __table_args__ = (
        UniqueConstraint("user_id", "parent_id", "name", name="uq_drive_folder_user_parent_name"),
    )


class DriveShare(db.Model):
    __tablename__ = "drive_shares"

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey("drive_files.id", ondelete="CASCADE"), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    file = relationship("DriveFile")
