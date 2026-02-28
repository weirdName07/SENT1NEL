"""Enricher — metadata enrichment, confidence scoring, staleness detection."""

from __future__ import annotations

import structlog

from sentinel.core.schemas import EntityLifecycle, EntityState, EntityType

log = structlog.get_logger()


class Enricher:
    """
    Enriches normalized EntityState with:
    - Confidence adjustment based on data quality signals
    - Metadata augmentation
    - Risk score placeholder
    """

    def enrich(self, entity: EntityState) -> EntityState:
        """Apply enrichment pipeline to an entity."""
        entity = self._adjust_confidence(entity)
        entity = self._set_risk_placeholder(entity)
        return entity

    def _adjust_confidence(self, entity: EntityState) -> EntityState:
        """
        Adjust confidence based on data quality signals.

        Factors:
        - Position accuracy if available
        - Source reliability
        - Staleness
        - Completeness of fields
        """
        confidence = entity.confidence

        # Penalize missing velocity data
        if entity.velocity is None or entity.velocity.speed_mps is None:
            confidence *= 0.8

        # Penalize missing altitude for aircraft/satellites
        if entity.entity_type in (EntityType.AIRCRAFT, EntityType.SATELLITE):
            if entity.position.altitude_m is None:
                confidence *= 0.7

        # Reward high-quality positions
        if entity.position.accuracy_m is not None:
            if entity.position.accuracy_m < 100:
                confidence = min(1.0, confidence * 1.1)
            elif entity.position.accuracy_m > 10000:
                confidence *= 0.6

        # Source-specific adjustments
        if entity.source == "usgs":
            confidence = max(confidence, 0.85)  # Authoritative source
        elif entity.source == "celestrak":
            confidence *= 0.9  # Propagated positions degrade

        entity.confidence = round(max(0.0, min(1.0, confidence)), 3)
        return entity

    def _set_risk_placeholder(self, entity: EntityState) -> EntityState:
        """
        Placeholder risk score logic.
        Real implementation would use ML models, context, etc.
        """
        # For now, risk is None (explicitly not computed)
        # This placeholder ensures the field exists and future systems can populate it
        return entity
