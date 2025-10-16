# Note Private App

## Быстрый старт

1. Создайте виртуальное окружение и установите зависимости:
```
pip install -r requirements.txt
```

2. Создайте `.env` в корне, пример значений:
```
FLASK_ENV=development
SECRET_KEY=change-me

# Database
DATABASE_URL=

# Uploads
UPLOAD_FOLDER=
MAX_CONTENT_LENGTH=20971520

# Encryption
SECURE_ENCRYPTION_KEY=

# Mail (OTP)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=1
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=

# Default quotas
DEFAULT_USER_FILE_QUOTA_COUNT=200
DEFAULT_USER_FILE_QUOTA_MB=500
```

3. Запуск:
```
python __init__.py
```

Если почта не настроена, код OTP будет показан во флеш-сообщении (dev-режим).


