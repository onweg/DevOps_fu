import os


class Config:
    DATABASE_URL   = os.environ.get("DATABASE_URL", "")
    ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://ml-service:5001")
    ML_TIMEOUT_SEC = int(os.environ.get("ML_TIMEOUT_SEC", "120"))
    FLASK_ENV      = os.environ.get("FLASK_ENV", "development")
    DEBUG          = FLASK_ENV == "development"
