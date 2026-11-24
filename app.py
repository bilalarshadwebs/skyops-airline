import io, contextlib
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template
import storage

app = Flask(__name__)
MAX_DUTY = 600

def nid(d):
    d["counter"] += 1
    return d["counter"]

def find(lst, i):
    return next((x for x in lst if x["id"] == int(i)), None)

def err(msg, code=400):
    return jsonify({"error": msg}), code

def log(d, msg):
    d["log"].insert(0, f"{datetime.now():%H:%M:%S} {msg}")
    d["log"] = d["log"][:200]

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/state")
def state():
    return jsonify(storage.load())

@app.post("/api/<kind>")
def create(kind):
    d, b = storage.load(), request.get_json(force=True)
    if kind == "passengers":
        if not b.get("name"): return err("Name is required")
        item = {"id": nid(d), "name": b["name"], "doc_number": b.get("doc_number", ""), "doc_expiry": b.get("doc_expiry", "")}
    elif kind == "aircraft":
        rows, letters = int(b.get("rows", 10)), b.get("letters", "ABCD")
        item = {"id": nid(d), "reg": b["reg"], "type": b["type"], "status": "active",
                "seats": [f"{r}{c}" for r in range(1, rows + 1) for c in letters],
                "cargo_capacity": int(b.get("cargo_capacity", 1000))}
    elif kind == "employees":
        item = {"id": nid(d), "name": b["name"], "role": b["role"], "duty_minutes": 0,
                "quals": [q.strip() for q in b.get("quals", "").split(",") if q.strip()]}
    elif kind == "flights":
        ac = find(d["aircraft"], b["aircraft_id"])
        if not ac or ac["status"] != "active": return err("Aircraft is not serviceable")
        if b["origin"] == b["dest"]: return err("Origin and destination must differ")
        item = {"id": nid(d), "number": b["number"], "origin": b["origin"], "dest": b["dest"],
                "departure": b["departure"], "minutes": int(b.get("minutes", 60)), "aircraft_id": ac["id"],
                "status": "scheduled", "crew": [], "international": bool(b.get("international"))}
    elif kind == "reservations":
        f, p = find(d["flights"], b["flight_id"]), find(d["passengers"], b["passenger_id"])
        if not f or not p: return err("Pick a flight and passenger")
        if f["status"] == "cancelled": return err("Flight is cancelled")
        seat = (b.get("seat") or "").upper() or None
        if seat:
            if seat not in find(d["aircraft"], f["aircraft_id"])["seats"]: return err(f"Seat {seat} does not exist")
            if any(r["flight_id"] == f["id"] and r["seat"] == seat and r["status"] in ("booked", "checked-in", "boarded") for r in d["reservations"]):
                return err(f"Seat {seat} is taken")
        item = {"id": nid(d), "flight_id": f["id"], "passenger_id": p["id"], "seat": seat, "status": "booked", "bags": []}
    elif kind == "cargo":
        f = find(d["flights"], b["flight_id"])
        if not f: return err("Pick a flight")
        item = {"id": nid(d), "awb": b["awb"], "weight": int(b["weight"]), "description": b.get("description", ""),
                "flight_id": f["id"], "kind": b.get("kind", "general"), "status": "accepted"}
    else:
        return err("Unknown type", 404)
    d[kind].append(item)
    log(d, f"Created {kind[:-1] if kind.endswith('s') else kind} #{item['id']}")
    storage.save(d)
    return jsonify(item)

@app.delete("/api/<kind>/<int:i>")
def delete(kind, i):
    d = storage.load()
    if kind not in d or not isinstance(d[kind], list): return err("Unknown type", 404)
    d[kind] = [x for x in d[kind] if x.get("id") != i]
    log(d, f"Deleted {kind} #{i}")
    storage.save(d)
    return jsonify({"ok": True})

@app.post("/api/reservations/<int:i>/<action>")
def reservation_action(i, action):
    d = storage.load()
    r = find(d["reservations"], i)
    if not r: return err("Not found", 404)
    f, p = find(d["flights"], r["flight_id"]), find(d["passengers"], r["passenger_id"])
    if action == "checkin":
        if r["status"] != "booked": return err("Only booked reservations can check in")
        if not r["seat"]: return err("Assign a seat first")
        dep = f["departure"][:10]
        if not p["doc_expiry"] or p["doc_expiry"] <= dep: return err("No valid travel document for this date")
        r["status"] = "checked-in"
    elif action == "board":
        if r["status"] != "checked-in": return err("Passenger must be checked in")
        r["status"] = "boarded"
    elif action == "bag":
        if r["status"] not in ("booked", "checked-in"): return err("Cannot add bags now")
        w = int(request.get_json(force=True).get("weight", 20))
        if w > 32: return err("Bag over 32kg limit")
        r["bags"].append({"tag": f"BG{nid(d)}", "weight": w, "status": "accepted"})
    elif action == "cancel":
        r["status"] = "cancelled"
    else:
        return err("Unknown action")
    log(d, f"Reservation #{i}: {action} -> {r['status']}")
    storage.save(d)
    return jsonify(r)

@app.post("/api/flights/<int:i>/<action>")
def flight_action(i, action):
    d, b = storage.load(), request.get_json(silent=True) or {}
    f = find(d["flights"], i)
    if not f: return err("Not found", 404)
    ac = find(d["aircraft"], f["aircraft_id"])
    if action == "crew":
        e = find(d["employees"], b["employee_id"])
        if e["id"] in f["crew"]: return err("Already assigned")
        if ac["type"] not in e["quals"]: return err(f"{e['name']} is not qualified for {ac['type']}")
        if e["duty_minutes"] + f["minutes"] > MAX_DUTY: return err(f"{e['name']} would exceed {MAX_DUTY} duty minutes")
        e["duty_minutes"] += f["minutes"]
        f["crew"].append(e["id"])
    elif action == "delay":
        m = int(b.get("minutes", 60))
        f["departure"] = (datetime.fromisoformat(f["departure"]) + timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M")
        f["status"] = "delayed"
    elif action == "cancel":
        f["status"] = "cancelled"
        for r in d["reservations"]:
            if r["flight_id"] == i and r["status"] in ("booked", "checked-in"):
                r["status"] = "needs rebooking"
    elif action == "divert":
        f["dest"], f["status"] = b["airport"], "diverted"
    elif action == "depart":
        f["status"] = "departed"
    else:
        return err("Unknown action")
    log(d, f"Flight {f['number']}: {action}")
    storage.save(d)
    return jsonify(f)

@app.get("/api/report")
def report():
    d = storage.load()
    out = []
    for f in d["flights"]:
        ac = find(d["aircraft"], f["aircraft_id"]) or {"seats": [], "cargo_capacity": 0}
        res = [r for r in d["reservations"] if r["flight_id"] == f["id"] and r["status"] != "cancelled"]
        cargo = sum(c["weight"] for c in d["cargo"] if c["flight_id"] == f["id"])
        bags = sum(bg["weight"] for r in res for bg in r["bags"])
        roles = [find(d["employees"], c)["role"] for c in f["crew"] if find(d["employees"], c)]
        gaps = [x for x in ("captain", "first officer") if x not in roles]
        out.append({"number": f["number"], "status": f["status"], "pax": len(res), "capacity": len(ac["seats"]),
                    "load_kg": cargo + bags, "cargo_capacity": ac["cargo_capacity"],
                    "overweight": cargo + bags > ac["cargo_capacity"], "crew_gaps": gaps})
    return jsonify(out)

@app.post("/api/reset")
def reset():
    storage.save(storage.seed())
    return jsonify({"ok": True})

@app.get("/api/demo")
def demo():
    import airline_model
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try: airline_model.main()
        except Exception as e: print("ERROR:", e)
    return jsonify({"output": buf.getvalue()})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
