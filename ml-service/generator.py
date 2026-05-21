"""
Synthetic access-event data generator.

Each record represents a 5-minute observation window of API access activity
from a third-party service integration. Feature distributions are calibrated
to reflect how each attack type actually manifests in observable access patterns.

Class distribution:
  30%  normal              — most access is legitimate
  14%  credential_stuffing — stolen credential lists
  14%  token_theft         — OAuth/API token compromised
  14%  api_abuse           — legitimate service abusing rate limits
  14%  brute_force         — systematic password attacks
  14%  oauth_hijack        — OAuth flow manipulation
"""

import logging

import numpy as np
import psycopg2.extras

import db
from features import FEATURE_COLUMNS, LABEL_NAMES

logger = logging.getLogger(__name__)

_WEIGHTS = [0.30, 0.14, 0.14, 0.14, 0.14, 0.14]


def generate(count: int) -> dict:
    rng  = np.random.default_rng()
    rows = _build_all_rows(count, rng)
    rng.shuffle(rows)

    conn = db.get_db()
    _bulk_insert(conn, rows)

    total_row = db.fetchone("SELECT COUNT(*) AS cnt FROM access_events")
    total = total_row["cnt"] if total_row else len(rows)

    logger.info("Generated %d records (DB total: %d)", len(rows), total)
    return {"generated": len(rows), "total": int(total)}


def _build_all_rows(count: int, rng: np.random.Generator) -> list:
    ns = [max(1, round(count * w)) for w in _WEIGHTS]
    ns[-1] += count - sum(ns)

    rows = []
    generators = [_normal, _credential_stuffing, _token_theft,
                  _api_abuse, _brute_force, _oauth_hijack]
    for label, (gen_fn, n) in enumerate(zip(generators, ns)):
        for _ in range(n):
            row = gen_fn(rng)
            row["label"]      = label
            row["label_name"] = LABEL_NAMES[label]
            rows.append(row)
    return rows


def _clip(val: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, val)))


# ─────────────────────────────────────────────────────────────────────────────
# Per-class generators
# ─────────────────────────────────────────────────────────────────────────────

def _normal(rng: np.random.Generator) -> dict:
    """
    Legitimate third-party service access.
    Low error rate, known IP, known service, normal request volume.
    """
    return {
        "request_rate_per_min":        _clip(rng.normal(15, 8),   1,   50),
        "failed_auth_count":           int(rng.choice([0, 1, 2], p=[0.70, 0.20, 0.10])),
        "token_age_hours":             _clip(rng.normal(168, 100), 1,  720),
        "is_known_service":            1,
        "service_id":                  int(rng.integers(0, 10)),
        "oauth_scope_count":           int(rng.choice([2, 3, 4, 5], p=[0.30, 0.40, 0.20, 0.10])),
        "api_key_age_days":            _clip(rng.normal(90, 60),   1,  365),
        "ssl_valid":                   1,
        "session_duration_sec":        _clip(rng.normal(300, 150), 10,  900),
        "unique_endpoints_count":      _clip(rng.normal(5, 3),      1,   15),
        "concurrent_sessions":         int(rng.choice([1, 2], p=[0.90, 0.10])),
        "off_hours_access":            int(rng.choice([0, 1], p=[0.80, 0.20])),
        "permission_escalation_count": 0,
        "token_refresh_count":         int(rng.choice([0, 1, 2], p=[0.60, 0.30, 0.10])),
        "redirect_count":              int(rng.choice([1, 2, 3], p=[0.60, 0.30, 0.10])),
        "is_known_ip":                 1,
        "ip_change_count":             0,
        "geolocation_anomaly":         0,
        "response_error_rate":         _clip(rng.normal(0.03, 0.02), 0.0, 0.10),
        "data_volume_mb":              _clip(rng.normal(5, 4),        0.1, 20),
        "request_size_avg_bytes":      _clip(rng.normal(512, 200),    100, 1500),
        "anomaly_score_prev":          _clip(rng.normal(0.05, 0.03),  0.0, 0.20),
    }


def _credential_stuffing(rng: np.random.Generator) -> dict:
    """
    Attacker iterates a list of stolen username/password pairs.

    Key indicators:
      - request_rate_per_min 100–1000  (bot-speed requests)
      - failed_auth_count 20–300       (nearly all attempts fail)
      - response_error_rate 0.6–0.99   (overwhelmingly 401/403)
      - unique_endpoints_count 1–2     (only targeting /login or /token)
      - concurrent_sessions 5–50       (distributed botnet)
      - ip_change_count 3–30           (rotating proxies)
    """
    return {
        "request_rate_per_min":        _clip(rng.normal(500, 200),  100, 1000),
        "failed_auth_count":           _clip(rng.normal(100, 40),    20,  300),
        "token_age_hours":             _clip(rng.normal(0.5, 0.3),    0,    2),
        "is_known_service":            int(rng.choice([0, 1], p=[0.50, 0.50])),
        "service_id":                  int(rng.integers(0, 10)),
        "oauth_scope_count":           int(rng.choice([1, 2], p=[0.70, 0.30])),
        "api_key_age_days":            _clip(rng.normal(1, 1),        0,    5),
        "ssl_valid":                   int(rng.choice([0, 1], p=[0.30, 0.70])),
        "session_duration_sec":        _clip(rng.normal(600, 200),   60, 1200),
        "unique_endpoints_count":      _clip(rng.normal(1.5, 0.5),    1,    3),
        "concurrent_sessions":         _clip(rng.normal(20, 10),      5,   50),
        "off_hours_access":            int(rng.choice([0, 1], p=[0.30, 0.70])),
        "permission_escalation_count": 0,
        "token_refresh_count":         0,
        "redirect_count":              0,
        "is_known_ip":                 int(rng.choice([0, 1], p=[0.70, 0.30])),
        "ip_change_count":             _clip(rng.normal(10, 5),       3,   30),
        "geolocation_anomaly":         int(rng.choice([0, 1], p=[0.40, 0.60])),
        "response_error_rate":         _clip(rng.normal(0.85, 0.08),  0.60, 0.99),
        "data_volume_mb":              _clip(rng.normal(0.5, 0.3),    0.1,   2),
        "request_size_avg_bytes":      _clip(rng.normal(200, 80),    50,  500),
        "anomaly_score_prev":          _clip(rng.normal(0.70, 0.15),  0.4,  1.0),
    }


def _token_theft(rng: np.random.Generator) -> dict:
    """
    Attacker uses a stolen OAuth/API token from a legitimate user.
    Auth succeeds (valid token) but behaviour is anomalous.

    Key indicators:
      - is_known_ip = 0               (different IP from the original owner)
      - geolocation_anomaly = 1       (impossible travel)
      - data_volume_mb 50–400         (data exfiltration)
      - unique_endpoints_count 8–40   (mapping the API surface)
      - token_age_hours 100–2000      (old stolen token)
      - permission_escalation_count 1–15
    """
    return {
        "request_rate_per_min":        _clip(rng.normal(20, 10),     5,   60),
        "failed_auth_count":           int(rng.choice([0, 1], p=[0.90, 0.10])),
        "token_age_hours":             _clip(rng.normal(500, 200),  100, 2000),
        "is_known_service":            int(rng.choice([0, 1], p=[0.30, 0.70])),
        "service_id":                  int(rng.integers(0, 10)),
        "oauth_scope_count":           _clip(rng.normal(8, 3),       5,   15),
        "api_key_age_days":            _clip(rng.normal(200, 100),  30,  500),
        "ssl_valid":                   1,
        "session_duration_sec":        _clip(rng.normal(1800, 600), 300, 3600),
        "unique_endpoints_count":      _clip(rng.normal(20, 8),      8,   40),
        "concurrent_sessions":         int(rng.choice([1, 2, 3], p=[0.50, 0.30, 0.20])),
        "off_hours_access":            int(rng.choice([0, 1], p=[0.30, 0.70])),
        "permission_escalation_count": _clip(rng.normal(5, 3),       1,   15),
        "token_refresh_count":         _clip(rng.normal(10, 5),      3,   25),
        "redirect_count":              int(rng.choice([1, 2], p=[0.70, 0.30])),
        "is_known_ip":                 0,
        "ip_change_count":             _clip(rng.normal(5, 3),       2,   15),
        "geolocation_anomaly":         1,
        "response_error_rate":         _clip(rng.normal(0.15, 0.08), 0.05, 0.40),
        "data_volume_mb":              _clip(rng.normal(150, 60),   50,  400),
        "request_size_avg_bytes":      _clip(rng.normal(800, 300),  300, 2000),
        "anomaly_score_prev":          _clip(rng.normal(0.50, 0.15), 0.2,  0.8),
    }


def _api_abuse(rng: np.random.Generator) -> dict:
    """
    Legitimate third-party service abusing API rate limits / scraping data.
    Credentials are valid; the attack is volumetric.

    Key indicators:
      - request_rate_per_min 100–600  (sustained high volume)
      - is_known_service = 1          (known service, abusing limits)
      - is_known_ip = 1               (same IP, not hiding)
      - data_volume_mb 100–1000       (bulk data extraction)
      - unique_endpoints_count 10–50  (broad API surface crawl)
    """
    return {
        "request_rate_per_min":        _clip(rng.normal(300, 100),  100,  600),
        "failed_auth_count":           int(rng.choice([0, 1, 2], p=[0.60, 0.30, 0.10])),
        "token_age_hours":             _clip(rng.normal(48, 24),      1,  200),
        "is_known_service":            1,
        "service_id":                  int(rng.integers(0, 10)),
        "oauth_scope_count":           _clip(rng.normal(4, 2),        1,   10),
        "api_key_age_days":            _clip(rng.normal(30, 20),      1,  180),
        "ssl_valid":                   1,
        "session_duration_sec":        _clip(rng.normal(3600, 1000), 1800, 7200),
        "unique_endpoints_count":      _clip(rng.normal(25, 8),      10,   50),
        "concurrent_sessions":         _clip(rng.normal(8, 4),        3,   20),
        "off_hours_access":            int(rng.choice([0, 1], p=[0.50, 0.50])),
        "permission_escalation_count": _clip(rng.normal(2, 2),        0,    8),
        "token_refresh_count":         _clip(rng.normal(5, 3),        1,   15),
        "redirect_count":              int(rng.choice([1, 2, 3], p=[0.50, 0.30, 0.20])),
        "is_known_ip":                 1,
        "ip_change_count":             int(rng.choice([0, 1], p=[0.80, 0.20])),
        "geolocation_anomaly":         0,
        "response_error_rate":         _clip(rng.normal(0.20, 0.10),  0.05, 0.50),
        "data_volume_mb":              _clip(rng.normal(500, 200),   100, 1000),
        "request_size_avg_bytes":      _clip(rng.normal(2000, 800),  500, 5000),
        "anomaly_score_prev":          _clip(rng.normal(0.40, 0.15),  0.1,  0.7),
    }


def _brute_force(rng: np.random.Generator) -> dict:
    """
    Systematic password attack against a single endpoint.
    Higher failed_auth and error_rate than credential_stuffing;
    lower request volume but more focused.

    Key indicators:
      - failed_auth_count 50–500      (highest of all classes)
      - response_error_rate 0.8–1.0   (almost every request fails)
      - unique_endpoints_count 1      (only /login or /token)
      - token_refresh_count = 0       (never successfully gets a token)
      - data_volume_mb 0.05–0.5       (tiny — only auth requests)
    """
    return {
        "request_rate_per_min":        _clip(rng.normal(100, 40),   30,  300),
        "failed_auth_count":           _clip(rng.normal(200, 80),   50,  500),
        "token_age_hours":             _clip(rng.normal(0.1, 0.1),   0,  0.5),
        "is_known_service":            int(rng.choice([0, 1], p=[0.40, 0.60])),
        "service_id":                  int(rng.integers(0, 10)),
        "oauth_scope_count":           1,
        "api_key_age_days":            _clip(rng.normal(0.5, 0.5),   0,    2),
        "ssl_valid":                   int(rng.choice([0, 1], p=[0.40, 0.60])),
        "session_duration_sec":        _clip(rng.normal(900, 300),  300, 1800),
        "unique_endpoints_count":      int(rng.choice([1, 2], p=[0.90, 0.10])),
        "concurrent_sessions":         _clip(rng.normal(3, 2),       1,   10),
        "off_hours_access":            int(rng.choice([0, 1], p=[0.40, 0.60])),
        "permission_escalation_count": 0,
        "token_refresh_count":         0,
        "redirect_count":              0,
        "is_known_ip":                 int(rng.choice([0, 1], p=[0.60, 0.40])),
        "ip_change_count":             _clip(rng.normal(5, 3),       1,   15),
        "geolocation_anomaly":         int(rng.choice([0, 1], p=[0.50, 0.50])),
        "response_error_rate":         _clip(rng.normal(0.95, 0.04), 0.80, 1.0),
        "data_volume_mb":              _clip(rng.normal(0.2, 0.1),  0.05, 0.5),
        "request_size_avg_bytes":      _clip(rng.normal(150, 50),   50,  300),
        "anomaly_score_prev":          _clip(rng.normal(0.60, 0.20), 0.3,  1.0),
    }


def _oauth_hijack(rng: np.random.Generator) -> dict:
    """
    OAuth authorization flow manipulation (open redirects, CSRF, token injection).

    Key indicators:
      - redirect_count 3–20           (attacker injects extra redirect hops)
      - token_refresh_count 8–40      (constant token rotation to avoid expiry)
      - oauth_scope_count 5–20        (requesting excessive permissions)
      - permission_escalation_count 3–20
      - ssl_valid = 0 (often)         (attacker's callback uses HTTP)
      - session_duration_sec 30–300   (quick in-and-out attack window)
    """
    return {
        "request_rate_per_min":        _clip(rng.normal(20, 10),     5,   50),
        "failed_auth_count":           int(rng.choice([0, 1], p=[0.80, 0.20])),
        "token_age_hours":             _clip(rng.normal(2, 1),       0.1,   8),
        "is_known_service":            int(rng.choice([0, 1], p=[0.60, 0.40])),
        "service_id":                  int(rng.integers(0, 10)),
        "oauth_scope_count":           _clip(rng.normal(12, 4),      5,   20),
        "api_key_age_days":            _clip(rng.normal(1, 1),       0,    5),
        "ssl_valid":                   int(rng.choice([0, 1], p=[0.50, 0.50])),
        "session_duration_sec":        _clip(rng.normal(120, 60),   30,  300),
        "unique_endpoints_count":      _clip(rng.normal(3, 2),       1,    8),
        "concurrent_sessions":         int(rng.choice([1, 2], p=[0.70, 0.30])),
        "off_hours_access":            int(rng.choice([0, 1], p=[0.50, 0.50])),
        "permission_escalation_count": _clip(rng.normal(8, 4),       3,   20),
        "token_refresh_count":         _clip(rng.normal(20, 8),      8,   40),
        "redirect_count":              _clip(rng.normal(8, 4),       3,   20),
        "is_known_ip":                 int(rng.choice([0, 1], p=[0.60, 0.40])),
        "ip_change_count":             _clip(rng.normal(3, 2),       1,   10),
        "geolocation_anomaly":         int(rng.choice([0, 1], p=[0.40, 0.60])),
        "response_error_rate":         _clip(rng.normal(0.10, 0.05), 0.02, 0.30),
        "data_volume_mb":              _clip(rng.normal(10, 5),      1,   30),
        "request_size_avg_bytes":      _clip(rng.normal(600, 200),  200, 1500),
        "anomaly_score_prev":          _clip(rng.normal(0.30, 0.15), 0.1,  0.6),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Database insertion
# ─────────────────────────────────────────────────────────────────────────────

def _bulk_insert(conn, rows: list) -> None:
    if not rows:
        return

    cols   = FEATURE_COLUMNS + ["label", "label_name"]
    values = [[row[c] for c in cols] for row in rows]
    sql    = f"INSERT INTO access_events ({', '.join(cols)}) VALUES %s"

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, values, page_size=500)
    conn.commit()
