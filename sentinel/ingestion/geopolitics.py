"""Geopolitical news ingestion connector — mocks or scrapes breaking alerts."""

import asyncio
import random
from datetime import datetime, timezone
import structlog

from sentinel.config import Settings
from sentinel.core.bus import MessageBus
from sentinel.core.events import EventType, SentinelEvent, Severity
from sentinel.core.schemas import Position

log = structlog.get_logger()

# Mocked geopolitical events with realistic Lat/Lon
MOCK_NEWS_FEED = [
    {
        "headline": "Iran-Israel Tensions Escalate Over Airspace Violations",
        "severity": Severity.CRITICAL,
        "lat": 32.4279,
        "lon": 53.6880,
        "source_url": "https://www.reuters.com/world/middle-east/",
        "metadata": {"region": "Middle East", "category": "Conflict"},
    },
    {
        "headline": "Taiwan Strait: Unidentified Naval Movements Tracked",
        "severity": Severity.HIGH,
        "lat": 24.1477,
        "lon": 119.8273,
        "source_url": "https://www.reuters.com/world/asia-pacific/taiwan/",
        "metadata": {"region": "Asia-Pacific", "category": "Military"},
    },
    {
        "headline": "Suez Canal Blockage Warning Issued by Maritime Authority",
        "severity": Severity.HIGH,
        "lat": 30.5852,
        "lon": 32.2654,
        "source_url": "https://www.bloomberg.com/suez-canal",
        "metadata": {"region": "North Africa", "category": "Supply Chain"},
    },
    {
        "headline": "Unusual Submarine Activity Detected near the GIUK Gap",
        "severity": Severity.MEDIUM,
        "lat": 63.0,
        "lon": -15.0,
        "source_url": "https://www.defensenews.com/naval/",
        "metadata": {"region": "North Atlantic", "category": "Military"},
    },
    {
        "headline": "Border Clashes Intensify in the Himalayas",
        "severity": Severity.CRITICAL,
        "lat": 34.3468,
        "lon": 78.2432,
        "source_url": "https://www.reuters.com/world/india/",
        "metadata": {"region": "South Asia", "category": "Conflict"},
    },
]

class GeopoliticsConnector:
    """
    Submits high-priority geopolitical events directly to the Event Bus.
    """
    def __init__(self, bus: MessageBus, settings: Settings) -> None:
        self.bus = bus
        self._settings = settings
        self.name = "geopolitics"

    async def run(self) -> None:
        """Main connector loop for geopolitical events."""
        log.info("geopolitics.started")
        
        while True:
            # Pick a random news event to simulate live polling
            news = random.choice(MOCK_NEWS_FEED)
            
            event = SentinelEvent(
                event_type=EventType.GEOPOLITICAL_NEWS,
                timestamp=datetime.now(timezone.utc),
                severity=news["severity"],
                reason=news["headline"],
                position=Position(latitude=news["lat"], longitude=news["lon"]),
                metadata={
                    "source_url": news["source_url"],
                    **news["metadata"]
                },
                trace_id=f"news-{random.randint(1000, 9999)}"
            )

            try:
                # Publish the event dynamically
                subject = event.nats_subject
                payload = event.serialize()
                await self.bus.publish(subject, payload)
                log.info("geopolitics.event_published", headline=news["headline"])
            except Exception as e:
                log.error("geopolitics.publish_error", error=str(e))
                
            # Random wait between 30 to 90 seconds to simulate breaking news timing
            await asyncio.sleep(random.randint(30, 90))
