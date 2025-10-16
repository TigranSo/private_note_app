from flask import Blueprint

drive_bp = Blueprint("drive", __name__, url_prefix="/drive")

from . import routes  # noqa: E402,F401



