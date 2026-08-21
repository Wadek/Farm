import json
import urllib.request

print("health", urllib.request.urlopen("http://127.0.0.1:8080/health").read().decode())
home = urllib.request.urlopen("http://127.0.0.1:8080/")
body = home.read()
print("home", home.status, home.headers.get("content-type"), "len", len(body))
assert b"Perinnepelto" in body
square = json.loads(urllib.request.urlopen("http://127.0.0.1:8080/square").read().decode())
print("stalls", square["stall_count"], "lots", square["lot_count"], "flares", len(square["flares"]))
for s in square["stalls"]:
    goods = ", ".join(g["produce_name"] for g in s["goods"])
    pickup = (s["pickup_point"] or "")[:48]
    print(" stall", s["farm_name"], s["available_from"], pickup, goods, "matches", s["matched_flares"])
for f in square["flares"]:
    print(" flare", f["buyer_name"], "wants", f["item"], "matches", f["matching_stalls"])
assert square["stall_count"] == 3
assert square["lot_count"] == 8
assert square["flares"][0]["item"] == "Raw milk"
print("ok")
