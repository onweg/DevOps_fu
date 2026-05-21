import os


class Config:
    MODEL_DIR = os.environ.get("MODEL_DIR", "/app/models")
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    DEBUG     = FLASK_ENV == "development"
