from datetime import datetime, timedelta, timezone

import pytest


class FakeClock:
    def __init__(self):
        self.current_time = 0.0
        self.current_datetime = datetime(2026, 9, 5, 14, 0, tzinfo=timezone.utc)

    def __call__(self) -> float:
        return self.current_time

    def advance(self, seconds: float) -> None:
        self.current_time += seconds
        self.current_datetime += timedelta(seconds=seconds)

    def now(self) -> datetime:
        return self.current_datetime


@pytest.fixture
def fake_clock():
    return FakeClock()
