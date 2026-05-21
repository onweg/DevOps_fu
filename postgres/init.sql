-- =============================================================================
-- Система обнаружения несанкционированного доступа через сторонние сервисы
-- Database schema
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. access_events
--    Raw API access observations — one row per 5-minute observation window.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS access_events (
    id         SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- ── Auth / Identity ──────────────────────────────────────────────────────
    request_rate_per_min        FLOAT    NOT NULL,
    failed_auth_count           FLOAT    NOT NULL,
    token_age_hours             FLOAT    NOT NULL,
    is_known_service            SMALLINT NOT NULL CHECK (is_known_service    IN (0, 1)),
    service_id                  SMALLINT NOT NULL,
    oauth_scope_count           FLOAT    NOT NULL,
    api_key_age_days            FLOAT    NOT NULL,
    ssl_valid                   SMALLINT NOT NULL CHECK (ssl_valid           IN (0, 1)),

    -- ── Session / Behaviour ──────────────────────────────────────────────────
    session_duration_sec        FLOAT    NOT NULL,
    unique_endpoints_count      FLOAT    NOT NULL,
    concurrent_sessions         SMALLINT NOT NULL,
    off_hours_access            SMALLINT NOT NULL CHECK (off_hours_access    IN (0, 1)),
    permission_escalation_count FLOAT    NOT NULL,
    token_refresh_count         FLOAT    NOT NULL,
    redirect_count              FLOAT    NOT NULL,

    -- ── Network ──────────────────────────────────────────────────────────────
    is_known_ip                 SMALLINT NOT NULL CHECK (is_known_ip         IN (0, 1)),
    ip_change_count             FLOAT    NOT NULL,
    geolocation_anomaly         SMALLINT NOT NULL CHECK (geolocation_anomaly IN (0, 1)),
    response_error_rate         FLOAT    NOT NULL CHECK (response_error_rate BETWEEN 0 AND 1),

    -- ── Data transfer ────────────────────────────────────────────────────────
    data_volume_mb              FLOAT    NOT NULL,
    request_size_avg_bytes      FLOAT    NOT NULL,
    anomaly_score_prev          FLOAT    NOT NULL,

    -- ── Ground truth label ───────────────────────────────────────────────────
    label      SMALLINT    NOT NULL CHECK (label BETWEEN 0 AND 5),
    label_name VARCHAR(30) NOT NULL
);

-- ---------------------------------------------------------------------------
-- 2. threat_detections
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS threat_detections (
    id          SERIAL PRIMARY KEY,
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    event_id INTEGER NOT NULL
        REFERENCES access_events (id) ON DELETE CASCADE,

    gb_label       SMALLINT    NOT NULL,
    gb_label_name  VARCHAR(30) NOT NULL,
    mlp_label      SMALLINT    NOT NULL,
    mlp_label_name VARCHAR(30) NOT NULL,
    km_label       SMALLINT    NOT NULL,
    km_label_name  VARCHAR(30) NOT NULL,

    final_label      SMALLINT    NOT NULL,
    final_label_name VARCHAR(30) NOT NULL,

    confidence      FLOAT   NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),
    model_agreement BOOLEAN NOT NULL DEFAULT FALSE
);

-- ---------------------------------------------------------------------------
-- 3. model_metrics
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_metrics (
    id         SERIAL PRIMARY KEY,
    trained_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    model_name       VARCHAR(30) NOT NULL,
    training_samples INTEGER     NOT NULL,
    test_samples     INTEGER     NOT NULL,

    accuracy        FLOAT NOT NULL,
    precision_macro FLOAT NOT NULL,
    recall_macro    FLOAT NOT NULL,
    f1_macro        FLOAT NOT NULL,

    confusion_matrix JSONB NOT NULL DEFAULT '[]',
    class_report     JSONB NOT NULL DEFAULT '{}'
);

-- ---------------------------------------------------------------------------
-- 4. trusted_services
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trusted_services (
    id          SERIAL PRIMARY KEY,
    added_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    service_name VARCHAR(64) NOT NULL,
    service_id   SMALLINT    NOT NULL,
    service_url  VARCHAR(256),
    description  TEXT,
    is_active    BOOLEAN     NOT NULL DEFAULT TRUE,

    CONSTRAINT uq_service_name UNIQUE (service_name)
);

-- ---------------------------------------------------------------------------
-- 5. activity_logs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activity_logs (
    id         SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    level   VARCHAR(10) NOT NULL
        CHECK (level IN ('INFO', 'WARNING', 'ALERT', 'ERROR')),
    action  VARCHAR(50) NOT NULL,
    message TEXT        NOT NULL,
    details JSONB       NOT NULL DEFAULT '{}'
);

-- ---------------------------------------------------------------------------
-- 6. alerts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alerts (
    id         SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    threat_type VARCHAR(30) NOT NULL,
    severity    VARCHAR(10) NOT NULL
        CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),

    event_id     INTEGER REFERENCES access_events    (id) ON DELETE SET NULL,
    detection_id INTEGER REFERENCES threat_detections (id) ON DELETE SET NULL,

    message    TEXT  NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),

    acknowledged    BOOLEAN                  NOT NULL DEFAULT FALSE,
    acknowledged_at TIMESTAMP WITH TIME ZONE
);

-- =============================================================================
-- Indexes
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_events_label       ON access_events (label);
CREATE INDEX IF NOT EXISTS idx_events_label_name  ON access_events (label_name);
CREATE INDEX IF NOT EXISTS idx_events_created_at  ON access_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_det_event_id  ON threat_detections (event_id);
CREATE INDEX IF NOT EXISTS idx_det_label     ON threat_detections (final_label_name);
CREATE INDEX IF NOT EXISTS idx_det_conf      ON threat_detections (confidence DESC);

CREATE INDEX IF NOT EXISTS idx_metrics_model ON model_metrics (model_name, trained_at DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts (acknowledged, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_level    ON activity_logs (level, created_at DESC);

-- =============================================================================
-- Seed data — trusted third-party services
-- =============================================================================
INSERT INTO trusted_services (service_name, service_id, service_url, description) VALUES
    ('Google OAuth 2.0',  0, 'https://oauth2.googleapis.com',   'Google identity provider'),
    ('GitHub OAuth',      1, 'https://github.com/login/oauth',  'GitHub OAuth integration'),
    ('Stripe API',        2, 'https://api.stripe.com',          'Payment processing'),
    ('SendGrid',          3, 'https://api.sendgrid.com',        'Transactional email'),
    ('Twilio',            4, 'https://api.twilio.com',          'SMS & voice notifications')
ON CONFLICT (service_name) DO NOTHING;

INSERT INTO activity_logs (level, action, message) VALUES
    ('INFO', 'DB_INITIALIZED', 'Database schema created and seed data loaded');
