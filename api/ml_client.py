"""HTTP client for communicating with the ML service."""

import logging

import requests
from flask import current_app

logger = logging.getLogger(__name__)


def _url(path: str) -> str:
    return current_app.config["ML_SERVICE_URL"].rstrip("/") + path


def _timeout() -> int:
    return current_app.config["ML_TIMEOUT_SEC"]


def generate(count: int = 1000) -> dict:
    try:
        r = requests.post(_url("/generate"), json={"count": count}, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        raise RuntimeError(f"ML service /generate failed: {exc}") from exc


def train() -> dict:
    try:
        r = requests.post(_url("/train"), timeout=_timeout())
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        raise RuntimeError(f"ML service /train failed: {exc}") from exc


def predict() -> dict:
    try:
        r = requests.post(_url("/predict"), timeout=_timeout())
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        raise RuntimeError(f"ML service /predict failed: {exc}") from exc
