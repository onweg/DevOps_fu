"""
Single source of truth for feature column order and label mappings.

IMPORTANT: The order of FEATURE_COLUMNS is fixed once the first model is trained.
Changing the order invalidates all saved .pkl files — retrain required.
"""

FEATURE_COLUMNS = [
    # ── Auth / Identity (8) ───────────────────────────────────────────────────
    "request_rate_per_min",        # requests per minute in the observation window
    "failed_auth_count",           # failed authentication attempts in 5-min window
    "token_age_hours",             # OAuth/API token age in hours
    "is_known_service",            # 1 if third-party service is in trusted whitelist
    "service_id",                  # encoded third-party service identifier (0–9)
    "oauth_scope_count",           # number of OAuth scopes requested
    "api_key_age_days",            # age of API key in days
    "ssl_valid",                   # 1 if SSL certificate is valid, else 0

    # ── Session / Behaviour (7) ───────────────────────────────────────────────
    "session_duration_sec",        # session duration in seconds
    "unique_endpoints_count",      # distinct API endpoints accessed
    "concurrent_sessions",         # concurrent sessions with the same credentials
    "off_hours_access",            # 1 if access is outside business hours (09:00–18:00)
    "permission_escalation_count", # attempts to access restricted/admin endpoints
    "token_refresh_count",         # token refresh operations in the window
    "redirect_count",              # OAuth redirect hops in the window

    # ── Network (4) ───────────────────────────────────────────────────────────
    "is_known_ip",                 # 1 if source IP is in the trusted IP list
    "ip_change_count",             # number of source IP changes during the session
    "geolocation_anomaly",         # 1 if access originates from an unusual location
    "response_error_rate",         # fraction of 4xx/5xx responses (0.0–1.0)

    # ── Data transfer (3) ─────────────────────────────────────────────────────
    "data_volume_mb",              # total data transferred in MB
    "request_size_avg_bytes",      # average request payload size in bytes
    "anomaly_score_prev",          # anomaly score from the previous observation window
]

LABEL_NAMES = {
    0: "normal",
    1: "credential_stuffing",
    2: "token_theft",
    3: "api_abuse",
    4: "brute_force",
    5: "oauth_hijack",
}

LABEL_IDS = {v: k for k, v in LABEL_NAMES.items()}
