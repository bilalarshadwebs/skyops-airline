import json, os, threading
PATH = os.path.join(os.path.dirname(__file__), "data.json")
_lock = threading.Lock()
EMPTY = {"airports": [], "aircraft": [], "employees": [], "passengers": [],
         "flights": [], "reservations": [], "cargo": [], "log": [], "counter": 0}

def load():
    if not os.path.exists(PATH):
        save(seed())
    with open(PATH) as f:
        data = json.load(f)
    for k, v in EMPTY.items():
        data.setdefault(k, v if not isinstance(v, list) else [])
    return data

def save(data):
    with _lock:
        tmp = PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, PATH)

def seed():
    seats = [f"{r}{c}" for r in range(1, 11) for c in "ABCD"]
    return {**{k: [] for k in EMPTY if k != "counter"}, "counter": 100,
        "airports": [{"code": "LHE", "name": "Lahore"}, {"code": "KHI", "name": "Karachi"},
                     {"code": "ISB", "name": "Islamabad"}, {"code": "DXB", "name": "Dubai"}],
        "aircraft": [{"id": 1, "reg": "AP-BLA", "type": "A320", "seats": seats, "cargo_capacity": 2000, "status": "active"},
                     {"id": 2, "reg": "AP-BLB", "type": "ATR72", "seats": seats[:28], "cargo_capacity": 800, "status": "active"}],
        "employees": [{"id": 3, "name": "Capt. Ali", "role": "captain", "quals": ["A320"], "duty_minutes": 0},
                      {"id": 4, "name": "F/O Hina", "role": "first officer", "quals": ["A320", "ATR72"], "duty_minutes": 0},
                      {"id": 5, "name": "Sana", "role": "cabin crew", "quals": ["A320"], "duty_minutes": 0}],
        "passengers": [{"id": 6, "name": "Sara Khan", "doc_number": "P123", "doc_expiry": "2030-01-01"},
                       {"id": 7, "name": "Omar Raza", "doc_number": "P456", "doc_expiry": "2025-01-01"}],
        "flights": [{"id": 8, "number": "PK301", "origin": "LHE", "dest": "KHI", "departure": "2026-12-01T08:00",
                     "minutes": 100, "aircraft_id": 1, "status": "scheduled", "crew": [], "international": False}],
        "log": ["Seeded demo data"]}
