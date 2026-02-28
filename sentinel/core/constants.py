"""System-wide constants and NATS subject topology."""

# ── NATS Stream Names ─────────────────────────────────────────
STREAM_RAW = "SENTINEL_RAW"
STREAM_PROCESSED = "SENTINEL_PROCESSED"
STREAM_EVENTS = "SENTINEL_EVENTS"

# ── NATS Subject Patterns ────────────────────────────────────
# Ingestion publishes raw data per source
SUBJECT_RAW = "sentinel.raw.{source}"          # e.g. sentinel.raw.opensky
SUBJECT_RAW_ALL = "sentinel.raw.>"

# Processing publishes normalized + enriched entities
SUBJECT_NORMALIZED = "sentinel.processed.normalized"
SUBJECT_ENRICHED = "sentinel.processed.enriched"
SUBJECT_TRACKED = "sentinel.processed.tracked"
SUBJECT_PROCESSED_ALL = "sentinel.processed.>"

# Events (anomalies, geofence, lifecycle, track)
SUBJECT_EVENT = "sentinel.events.{event_category}"  # e.g. sentinel.events.anomaly
SUBJECT_EVENTS_ALL = "sentinel.events.>"

# ── Consumer Group Names ─────────────────────────────────────
CONSUMER_NORMALIZER = "normalizer"
CONSUMER_ENRICHER = "enricher"
CONSUMER_TRACKER = "tracker"
CONSUMER_STORAGE = "storage"
CONSUMER_EVENT_WRITER = "event-writer"
CONSUMER_LIFECYCLE = "lifecycle"

# ── Redis Key Patterns ───────────────────────────────────────
REDIS_ENTITY_PREFIX = "entity:"                # entity:{source_id}:{entity_type}
REDIS_LIFECYCLE_PREFIX = "lifecycle:"          # lifecycle:{source_id}:{entity_type}
REDIS_GEO_KEY = "sentinel:geo:{entity_type}"  # Geo-indexed positions per type
REDIS_GEO_ALL = "sentinel:geo:all"            # All entities geo-indexed
REDIS_TRACK_PREFIX = "track:"                 # track:{track_id}

# ── Entity Type Constants ────────────────────────────────────
ENTITY_TYPES = ("aircraft", "vessel", "satellite", "earthquake", "weather")

# ── Batch Sizes ──────────────────────────────────────────────
DEFAULT_BATCH_SIZE = 500
DEFAULT_BATCH_FLUSH_INTERVAL_S = 1.0
