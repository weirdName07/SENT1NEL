-- Sentinel schema migration 001
-- Creates: entity_states hypertable, events hypertable, geofences, geofence_events

-- ── Extensions ───────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Entity States Hypertable ─────────────────────────────────
CREATE TABLE IF NOT EXISTS entity_states (
    id              UUID DEFAULT gen_random_uuid(),
    entity_type     TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    source          TEXT NOT NULL,

    -- Geospatial (PostGIS)
    position        GEOMETRY(PointZ, 4326),
    accuracy_m      DOUBLE PRECISION,

    -- Kinematics
    speed_mps       DOUBLE PRECISION,
    heading_deg     DOUBLE PRECISION,
    vertical_rate   DOUBLE PRECISION,

    -- Temporal
    observed_at     TIMESTAMPTZ NOT NULL,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Lifecycle
    lifecycle       TEXT NOT NULL DEFAULT 'new',

    -- Intelligence
    confidence      DOUBLE PRECISION DEFAULT 0.5,
    risk_score      DOUBLE PRECISION,
    track_id        UUID,
    observation_count INTEGER DEFAULT 0,
    anomalies       TEXT[],

    -- Flexible metadata
    metadata        JSONB DEFAULT '{}',

    -- Observability
    trace_id        TEXT,

    PRIMARY KEY (id, observed_at)
);

SELECT create_hypertable('entity_states', 'observed_at',
    chunk_time_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Spatial index
CREATE INDEX IF NOT EXISTS idx_entity_position
    ON entity_states USING GIST (position);

-- Source lookups
CREATE INDEX IF NOT EXISTS idx_entity_source
    ON entity_states (source_id, entity_type);

-- Track queries
CREATE INDEX IF NOT EXISTS idx_entity_track
    ON entity_states (track_id, observed_at DESC);

-- Lifecycle queries
CREATE INDEX IF NOT EXISTS idx_entity_lifecycle
    ON entity_states (lifecycle, entity_type, observed_at DESC);

-- Compression
ALTER TABLE entity_states SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'observed_at DESC',
    timescaledb.compress_segmentby = 'source_id, entity_type'
);
SELECT add_compression_policy('entity_states', INTERVAL '24 hours', if_not_exists => TRUE);


-- ── Events Hypertable ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id          UUID DEFAULT gen_random_uuid(),
    event_type  TEXT NOT NULL,
    severity    TEXT NOT NULL DEFAULT 'low',
    timestamp   TIMESTAMPTZ NOT NULL,

    -- Source entity
    entity_id   UUID,
    entity_type TEXT,
    source_id   TEXT,
    track_id    UUID,

    -- Payload
    confidence  DOUBLE PRECISION DEFAULT 0.5,
    reason      TEXT,
    position    GEOMETRY(Point, 4326),

    -- Context
    metadata    JSONB DEFAULT '{}',

    -- Observability
    trace_id    TEXT,

    PRIMARY KEY (id, timestamp)
);

SELECT create_hypertable('events', 'timestamp',
    chunk_time_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_events_type
    ON events (event_type, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_events_entity
    ON events (source_id, entity_type, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_events_severity
    ON events (severity, timestamp DESC);

ALTER TABLE events SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'timestamp DESC',
    timescaledb.compress_segmentby = 'event_type'
);
SELECT add_compression_policy('events', INTERVAL '24 hours', if_not_exists => TRUE);


-- ── Geofence Zones ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS geofences (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    geometry    GEOMETRY(Polygon, 4326) NOT NULL,
    alert_on    TEXT[] DEFAULT ARRAY['ENTER', 'EXIT', 'DWELL'],
    entity_types TEXT[],
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_geofence_geom
    ON geofences USING GIST (geometry);


-- ── Geofence Events ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS geofence_events (
    id            UUID DEFAULT gen_random_uuid(),
    geofence_id   UUID REFERENCES geofences(id),
    entity_type   TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    track_id      UUID,
    event_type    TEXT NOT NULL,
    occurred_at   TIMESTAMPTZ NOT NULL,
    position      GEOMETRY(Point, 4326),
    metadata      JSONB DEFAULT '{}',
    PRIMARY KEY (id, occurred_at)
);

SELECT create_hypertable('geofence_events', 'occurred_at',
    if_not_exists => TRUE
);


-- ── Continuous Aggregates ────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS entity_counts_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', observed_at) AS bucket,
    entity_type,
    source,
    COUNT(DISTINCT source_id) AS unique_entities,
    COUNT(*) AS total_observations
FROM entity_states
GROUP BY bucket, entity_type, source;
