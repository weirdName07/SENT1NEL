"""Unit tests for the normalizer."""

from sentinel.processing.normalizer import Normalizer


class TestNormalizer:
    def setup_method(self):
        self.normalizer = Normalizer()

    def test_normalize_opensky(self, sample_opensky_raw):
        entity = self.normalizer.normalize(sample_opensky_raw)
        assert entity is not None
        assert entity.entity_type.value == "aircraft"
        assert entity.source_id == "a1b2c3"
        assert entity.position.latitude == 40.7128
        assert entity.position.longitude == -74.0060
        assert entity.velocity.speed_mps == 250.0
        assert entity.metadata["callsign"] == "UAL123"
        assert entity.trace_id.startswith("osky-")

    def test_normalize_usgs(self, sample_usgs_raw):
        entity = self.normalizer.normalize(sample_usgs_raw)
        assert entity is not None
        assert entity.entity_type.value == "earthquake"
        assert entity.source_id == "us7000n123"
        assert entity.confidence == 0.9
        assert entity.metadata["magnitude"] == 5.2

    def test_normalize_vessel(self, sample_vessel_raw):
        entity = self.normalizer.normalize(sample_vessel_raw)
        assert entity is not None
        assert entity.entity_type.value == "vessel"
        assert entity.source_id == "211234567"
        assert entity.metadata["name"] == "EVER GIVEN"

    def test_normalize_unknown_source(self):
        entity = self.normalizer.normalize({"source": "unknown_source"})
        assert entity is None
