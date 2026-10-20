"""
Ikere-Ekiti pickup points, zones and fare estimation.

IMPORTANT: x/y below are SCHEMATIC map units (shared with the demo app), not GPS.
Replace with real coordinates once the points are surveyed, and swap route_km()
for a haversine or routing-API distance.
"""
import re
from typing import Optional

RATE_PER_KM = 300     # naira per km (proposed pricing model)
SHARE_SEATS = 3       # Share: up to 3 students split the solo fare
MIN_FARE = 300
KM_PER_UNIT = 0.01    # schematic units -> km

ZONES = {
    "A": "BOUESTI Campus Zone",
    "B": "Student Residential Zone",
    "C": "Central Ikere Zone",
    "D": "Ado Road Corridor",
    "E": "Outer Ikere Zone",
}

# code, name, zone, x, y, extra aliases
_P = [
    ("BKR-001", "BOUESTI Main Gate", "A", 70, 70, ["main gate", "bouesti", "gate"]),
    ("BKR-002", "BOUESTI Campus Pickup", "A", 42, 112, ["campus", "campus pickup"]),
    ("BKR-003", "College Area", "A", 118, 118, ["college"]),
    ("BKR-004", "Odo-Oja", "C", 190, 170, []),
    ("BKR-005", "Oke-Osun", "B", 58, 205, []),
    ("BKR-006", "Oke-Idemo", "B", 128, 240, []),
    ("BKR-007", "Uro", "C", 236, 226, []),
    ("BKR-008", "Oke-Ikere", "C", 282, 142, []),
    ("BKR-009", "Ado Road", "D", 304, 262, ["ado"]),
    ("BKR-010", "Ise Road", "E", 110, 345, ["ise"]),
    ("BKR-011", "Afao Road", "D", 230, 312, ["afao"]),
    ("BKR-012", "Odo-Oro", "E", 292, 362, []),
]
PICKUPS = {
    c: {"code": c, "name": n, "zone": z, "x": x, "y": y, "aliases": a}
    for c, n, z, x, y, a in _P
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def pickup_name(code: str) -> str:
    return PICKUPS[code]["name"]


def list_locations() -> str:
    lines = []
    for z, zname in ZONES.items():
        pts = [p for p in PICKUPS.values() if p["zone"] == z]
        if not pts:
            continue
        lines.append(f"*{zname}*")
        for p in pts:
            lines.append(f"{int(p['code'][-3:])}. {p['name']}")
    return "\n".join(lines)


def match_location(text: str) -> Optional[str]:
    """Return a pickup code from a number, code or (loose) name; None if no clear match."""
    t = _norm(text)
    if not t:
        return None
    # number 1-12 or code like "bkr 004"
    m = re.fullmatch(r"(?:bkr )?0*(\d{1,3})", t)
    if m:
        code = f"BKR-{int(m.group(1)):03d}"
        return code if code in PICKUPS else None
    m = re.fullmatch(r"bkr0*(\d{1,3})", t)
    if m:
        code = f"BKR-{int(m.group(1)):03d}"
        return code if code in PICKUPS else None
    # exact name or alias
    for p in PICKUPS.values():
        if t == _norm(p["name"]) or t in [_norm(a) for a in p["aliases"]]:
            return p["code"]
    # unambiguous partial match
    hits = {
        p["code"] for p in PICKUPS.values()
        if len(t) >= 3 and (t in _norm(p["name"]) or _norm(p["name"]) in t)
    }
    return hits.pop() if len(hits) == 1 else None


def _route_km(a: str, b: str) -> float:
    """Elbow route length, matching the demo app's schematic roads."""
    pa, pb = PICKUPS[a], PICKUPS[b]
    return (abs(pb["x"] - pa["x"]) + abs(pb["y"] - pa["y"])) * KM_PER_UNIT


def _round_fare(n: float) -> int:
    return max(MIN_FARE, int(round(n / 50.0)) * 50)


def estimate_fare(pickup: str, dropoff: str) -> tuple[float, dict]:
    """Return (distance_km, {"solo": naira, "share": naira_per_student})."""
    km = round(_route_km(pickup, dropoff), 1)
    solo = _round_fare(km * RATE_PER_KM)
    return km, {"solo": solo, "share": _round_fare(solo / SHARE_SEATS)}
