import os
from dotenv import load_dotenv

load_dotenv()

APP_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(APP_DIR, os.pardir))
INSTANCE_DIR = os.path.join(PROJECT_ROOT, "instance")
DEFAULT_DB_PATH = os.path.join(INSTANCE_DIR, "app.db")
DEFAULT_DB_URI = "sqlite:///" + DEFAULT_DB_PATH.replace("\\", "/")
DEFAULT_UPLOADS = os.path.join(INSTANCE_DIR, "uploads")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or DEFAULT_DB_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER") or DEFAULT_UPLOADS
    SECURE_ENCRYPTION_KEY = os.getenv("SECURE_ENCRYPTION_KEY")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
    ALLOWED_EXTENSIONS = (os.getenv("ALLOWED_EXTENSIONS",
        "jpg,jpeg,png,gif,webp,pdf,txt,md,doc,docx,xls,xlsx,ppt,pptx,mp3,wav,ogg,mp4,mov,webm,zip,rar,7z"
    )).split(',')
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "1") == "1"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", os.getenv("MAIL_USERNAME", "no-reply@example.com"))
    DEFAULT_USER_FILE_QUOTA_COUNT = int(os.getenv("DEFAULT_USER_FILE_QUOTA_COUNT", "200"))
    DEFAULT_USER_FILE_QUOTA_MB = int(os.getenv("DEFAULT_USER_FILE_QUOTA_MB", "500"))
    REGISTRATION_ENABLED = os.getenv("REGISTRATION_ENABLED", "1") == "1"
