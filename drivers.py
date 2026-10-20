"""Driver matching. Mock pool for the pilot; replace with real driver availability."""
import random

DRIVERS = [
    {"name": "Emeka O.", "vehicle": "Toyota Corolla", "plate": "EKT-482-KJ"},
    {"name": "Segun A.", "vehicle": "Honda Accord", "plate": "EKT-117-AB"},
    {"name": "Yusuf M.", "vehicle": "Toyota Camry", "plate": "EKT-905-RT"},
]


def find_available_driver() -> dict:
    return random.choice(DRIVERS)
