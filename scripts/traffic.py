"""Generate load so the Grafana dashboard has data. Usage: python scripts/traffic.py [base_url] [seconds]"""
import json
import random
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
DURATION = int(sys.argv[2]) if len(sys.argv) > 2 else 60


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return e.code, None


end = time.time() + DURATION
count = 0
while time.time() < end:
    _, item = call("POST", "/items", {"name": f"item-{random.randint(1, 999)}", "quantity": random.randint(0, 50), "price": 9.99})
    call("GET", "/items")
    if item:
        call("GET", f"/items/{item['id']}")
        call("PUT", f"/items/{item['id']}", {"name": item["name"], "quantity": 1, "price": 5})
        if random.random() < 0.5:
            call("DELETE", f"/items/{item['id']}")
    call("GET", "/items/999999")  # 404 on purpose, shows up as client errors
    call("GET", "/health")
    count += 6
    time.sleep(0.2)
print(f"sent about {count} requests")
