"""Prometheus metric definitions — single source of truth for all Sentinel metrics."""

from prometheus_client import Counter, Gauge, Histogram

# ── Ingestion ─────────────────────────────────────────────────

ingested_total = Counter(
    "sentinel_ingested_total",
    "Total entities ingested",
    ["source", "entity_type"],
)

ingestion_latency = Histogram(
    "sentinel_ingestion_latency_seconds",
    "Time from source observation to NATS publish",
    ["source"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

ingestion_errors = Counter(
    "sentinel_ingestion_errors_total",
    "Ingestion errors by source",
    ["source", "error_type"],
)

# ── Processing ────────────────────────────────────────────────

processing_latency = Histogram(
    "sentinel_processing_latency_seconds",
    "Per-stage processing latency",
    ["stage"],
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5),
)

# ── End-to-End ────────────────────────────────────────────────

e2e_latency = Histogram(
    "sentinel_e2e_latency_seconds",
    "Source observation time to stored in DB",
    ["source"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# ── Track Stitching ──────────────────────────────────────────

track_associations = Counter(
    "sentinel_track_associations_total",
    "Track association outcomes",
    ["method"],  # "exact_match", "kalman", "new_track"
)

active_tracks = Gauge(
    "sentinel_track_active_count",
    "Currently active tracks",
    ["entity_type"],
)

# ── Lifecycle ─────────────────────────────────────────────────

lifecycle_transitions = Counter(
    "sentinel_lifecycle_transitions_total",
    "Entity lifecycle state transitions",
    ["from_state", "to_state"],
)

# ── Anomaly Detection ────────────────────────────────────────

anomalies_detected = Counter(
    "sentinel_anomalies_detected_total",
    "Anomalies detected by type and entity type",
    ["entity_type", "anomaly_type"],
)

# ── Events ────────────────────────────────────────────────────

events_emitted = Counter(
    "sentinel_events_emitted_total",
    "Events emitted to event bus",
    ["event_type"],
)

# ── Database ──────────────────────────────────────────────────

db_write_latency = Histogram(
    "sentinel_db_write_latency_seconds",
    "TimescaleDB batch write latency",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

db_write_batch_size = Histogram(
    "sentinel_db_write_batch_size",
    "Number of rows per batch insert",
    buckets=(1, 10, 50, 100, 250, 500, 1000),
)

# ── Redis ─────────────────────────────────────────────────────

redis_keys = Gauge(
    "sentinel_redis_keys_total",
    "Total keys in Redis hot cache",
)

# ── Errors ────────────────────────────────────────────────────

errors_total = Counter(
    "sentinel_errors_total",
    "Total errors by component",
    ["component", "error_type"],
)
