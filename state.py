"""Per-rider conversation state (in memory). Swap for Redis/DB before scaling."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RideState(str, Enum):
    IDLE = "idle"
    AWAITING_PICKUP = "awaiting_pickup"
    AWAITING_DROPOFF = "awaiting_dropoff"
    AWAITING_CONFIRM = "awaiting_confirm"  # rider chooses Solo or Share here
    MATCHED = "matched"
    DRIVER_ARRIVING = "driver_arriving"
    DRIVER_ARRIVED = "driver_arrived"
    IN_TRANSIT = "in_transit"
    COMPLETED = "completed"


@dataclass
class Session:
    state: RideState = RideState.IDLE
    pickup: Optional[str] = None    # pickup code, e.g. "BKR-001"
    dropoff: Optional[str] = None
    mode: Optional[str] = None      # "solo" or "share"
    distance_km: float = 0.0
    fares: dict = field(default_factory=dict)  # {"solo": int, "share": int}
    fare: float = 0.0               # amount the rider pays for the chosen mode
    driver: Optional[dict] = None
    ride_id: int = 0                # bumped on every reset; stops stale background tasks

    def reset(self) -> None:
        self.state = RideState.IDLE
        self.pickup = self.dropoff = self.mode = self.driver = None
        self.distance_km = 0.0
        self.fares = {}
        self.fare = 0.0
        self.ride_id += 1


_sessions: dict[str, Session] = {}


def get_session(phone: str) -> Session:
    return _sessions.setdefault(phone, Session())
