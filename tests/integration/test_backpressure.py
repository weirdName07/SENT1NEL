"""Integration test — backpressure primitives under load."""

import asyncio
import time

import pytest

from sentinel.core.backpressure import BatchCoalescer, LagMonitor, RateLimiter


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(self):
        """Rate limiter enforces minimum interval between calls."""
        limiter = RateLimiter(interval_s=0.1)

        t0 = time.monotonic()
        await limiter.wait()
        await limiter.wait()
        elapsed = time.monotonic() - t0

        assert elapsed >= 0.09  # Should have waited ~100ms

    @pytest.mark.asyncio
    async def test_rate_limiter_no_delay_on_first_call(self):
        """First call should return immediately."""
        limiter = RateLimiter(interval_s=1.0)
        t0 = time.monotonic()
        await limiter.wait()
        elapsed = time.monotonic() - t0
        assert elapsed < 0.1


class TestBatchCoalescer:
    def test_size_based_flush(self):
        """Batch flushes when size threshold reached."""
        batcher = BatchCoalescer(batch_size=3, flush_interval_s=999)

        assert batcher.add("a") is None
        assert batcher.add("b") is None
        result = batcher.add("c")

        assert result == ["a", "b", "c"]
        assert batcher.pending == 0

    def test_time_based_flush(self):
        """Batch flushes when time interval reached."""
        batcher = BatchCoalescer(batch_size=999, flush_interval_s=0.01)

        batcher.add("a")
        batcher.add("b")
        time.sleep(0.02)
        result = batcher.add("c")

        assert result is not None
        assert len(result) == 3

    def test_manual_flush(self):
        """Manual flush returns all pending items."""
        batcher = BatchCoalescer(batch_size=999)
        batcher.add("x")
        batcher.add("y")

        result = batcher.flush()
        assert result == ["x", "y"]
        assert batcher.pending == 0

    def test_empty_flush(self):
        """Flushing empty batcher returns empty list."""
        batcher = BatchCoalescer()
        result = batcher.flush()
        assert result == []

    def test_should_flush_reports_correctly(self):
        batcher = BatchCoalescer(batch_size=3, flush_interval_s=999)
        assert not batcher.should_flush()
        batcher.add("a")
        assert not batcher.should_flush()  # 1 of 3, no flush needed
        batcher.add("b")
        batcher.add("c")
        # Buffer reached batch_size — should_flush may be True or buffer flushed
        # Actually add() auto-flushes at batch_size, so check pending instead
        # Let's test with time-based: add 1 item, wait for interval
        batcher2 = BatchCoalescer(batch_size=999, flush_interval_s=0.01)
        batcher2.add("x")
        assert not batcher2.should_flush()  # Interval hasn't elapsed
        import time; time.sleep(0.02)
        assert batcher2.should_flush()  # Interval elapsed

    def test_high_throughput(self):
        """Coalescer handles thousands of items correctly."""
        batcher = BatchCoalescer(batch_size=500, flush_interval_s=999)
        flushed = 0
        for i in range(10000):
            result = batcher.add(i)
            if result:
                flushed += len(result)
        # Final flush
        remaining = batcher.flush()
        flushed += len(remaining)
        assert flushed == 10000


class TestLagMonitor:
    def test_records_lag(self):
        monitor = LagMonitor()
        monitor.record_lag("raw", "normalizer", 150)
        assert monitor.total_lag == 150

    def test_multiple_consumers(self):
        monitor = LagMonitor()
        monitor.record_lag("raw", "normalizer", 100)
        monitor.record_lag("events", "writer", 50)
        assert monitor.total_lag == 150

    def test_lag_update(self):
        monitor = LagMonitor()
        monitor.record_lag("raw", "normalizer", 100)
        monitor.record_lag("raw", "normalizer", 50)  # lag decreased
        assert monitor.total_lag == 50


class TestBackpressureStress:
    """Stress tests for backpressure primitives."""

    def test_batcher_rapid_flush_cycles(self):
        """Rapid add→flush cycles don't corrupt state."""
        batcher = BatchCoalescer(batch_size=10)
        total = 0
        for cycle in range(1000):
            for i in range(10):
                result = batcher.add(f"{cycle}:{i}")
                if result:
                    total += len(result)
        remaining = batcher.flush()
        total += len(remaining)
        assert total == 10000

    @pytest.mark.asyncio
    async def test_concurrent_rate_limiters(self):
        """Multiple rate limiters can coexist independently."""
        fast = RateLimiter(interval_s=0.01)
        slow = RateLimiter(interval_s=0.05)

        async def run_fast():
            for _ in range(10):
                await fast.wait()

        async def run_slow():
            for _ in range(3):
                await slow.wait()

        await asyncio.gather(run_fast(), run_slow())
