"""High-density synthetic flight generator — simulates 100k+ moving aircraft globally."""

import asyncio
import math
import random
import time
from typing import Any
from uuid import uuid4

import orjson
import structlog

from sentinel.config import Settings
from sentinel.core.bus import MessageBus
from sentinel.core.constants import SUBJECT_RAW

log = structlog.get_logger()

# Enrichment Data Mocks
AIRLINES = ["Emirates", "Delta Air Lines", "United Airlines", "Lufthansa", "Singapore Airlines", "Qatar Airways", "British Airways", "Air France", "Cathay Pacific", "ANA"]
AIRPORTS = ["JFK", "LHR", "DXB", "HND", "CDG", "FRA", "SIN", "AMS", "ICN", "IST", "SYD", "YYZ", "LAX"]

def generate_initial_state(idx: int) -> dict:
    """Generate a random starting flight state."""
    lat = random.uniform(-60.0, 70.0)
    lon = random.uniform(-180.0, 180.0)
    heading = random.uniform(0.0, 360.0)
    speed = random.uniform(200.0, 280.0) # m/s (approx 400-550 knots)
    alt = random.uniform(8000.0, 12000.0)
    
    origin = random.choice(AIRPORTS)
    dest = random.choice([a for a in AIRPORTS if a != origin])
    airline = random.choice(AIRLINES)
    flight_number = f"{airline[:2].upper()}{random.randint(100, 9999)}"
    
    return {
        "id": f"SYN-{idx}",
        "callsign": flight_number,
        "lat": lat,
        "lon": lon,
        "alt": alt,
        "heading": heading,
        "speed": speed,
        "airline": airline,
        "origin": origin,
        "destination": dest,
    }

class SyntheticFlightsConnector:
    """
    Bypasses BaseConnector to efficiently manage and stream 100,000+ flights.
    """
    def __init__(self, bus: MessageBus, settings: Settings, count: int = 100000) -> None:
        self._bus = bus
        self._settings = settings
        self.name = "synthetic_flights"
        self.entity_type = "aircraft"
        self.count = count
        self.interval_s = 5.0  # Update every 5 seconds
        
        # Pre-allocate 100k flights in memory
        log.info("synthetic.generating_fleet", count=self.count)
        self.fleet = [generate_initial_state(i) for i in range(self.count)]

    def _move_fleet(self, dt: float):
        """Update lat/lon based on heading and speed (simple approximation)."""
        # 1 degree lat is ~111km. 1 m/s = 0.001 km/s.
        for flight in self.fleet:
            # Convert math to move flights
            dist_km = (flight["speed"] * dt) / 1000.0
            
            # Simple flat-earth approximation for speed
            d_lat = (dist_km * math.cos(math.radians(flight["heading"]))) / 111.0
            
            # Adjust lon based on lat scaling
            lat_rad = math.radians(flight["lat"])
            d_lon = (dist_km * math.sin(math.radians(flight["heading"]))) / (111.0 * math.cos(lat_rad) if math.cos(lat_rad) != 0 else 1)
            
            flight["lat"] += d_lat
            flight["lon"] += d_lon
            
            # Wrap around global bounds
            if flight["lat"] > 90.0:
                flight["lat"] = 90.0
                flight["heading"] = (flight["heading"] + 180) % 360
            elif flight["lat"] < -90.0:
                flight["lat"] = -90.0
                flight["heading"] = (flight["heading"] + 180) % 360
                
            if flight["lon"] > 180.0:
                flight["lon"] -= 360.0
            elif flight["lon"] < -180.0:
                flight["lon"] += 360.0

    async def run(self) -> None:
        subject = SUBJECT_RAW.format(source=self.name)
        log.info("synthetic.started", count=self.count)
        
        while True:
            t0 = time.monotonic()
            now = time.time()
            self._move_fleet(self.interval_s)
            
            # Publish in batches to not block the event loop entirely
            batch_size = 5000
            for i in range(0, self.count, batch_size):
                batch = self.fleet[i:i+batch_size]
                
                # We emit raw dictionaries matching normalizer expectations
                # since normalizer reads `source`, `entity_type`, `source_id`, etc.
                for f in batch:
                    raw_record = {
                        "source": self.name,
                        "entity_type": self.entity_type,
                        "source_id": f["id"],
                        "timestamp": now,
                        "latitude": f["lat"],
                        "longitude": f["lon"],
                        "altitude_m": f["alt"],
                        "velocity_mps": f["speed"],
                        "heading": f["heading"],
                        "callsign": f["callsign"],
                        # The normalizer captures unknown keys into metadata
                        "airline": f["airline"],
                        "origin": f["origin"],
                        "destination": f["destination"]
                    }
                    payload = orjson.dumps(raw_record)
                    await self._bus.publish(subject, payload)
                
                # Small yield to let NATS and other tasks breathe
                await asyncio.sleep(0.01)
                
            elapsed = time.monotonic() - t0
            log.info("synthetic.batch_published", count=self.count, elapsed_s=round(elapsed, 2))
            
            # Sleep remainder of the interval
            sleep_time = max(0.1, self.interval_s - elapsed)
            await asyncio.sleep(sleep_time)
