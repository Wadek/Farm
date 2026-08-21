import json
import urllib.parse
import urllib.request

def post(url, data, headers=None, form=False):
    if form:
        body = urllib.parse.urlencode(data).encode()
        hdrs = {"Content-Type": "application/x-www-form-urlencoded"}
    else:
        body = json.dumps(data).encode()
        hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

token = post(
    "http://127.0.0.1:8080/auth/token",
    {"username": "anna@hyvinkaa.fi", "password": "market"},
    form=True,
)["access_token"]
me = json.loads(urllib.request.urlopen(urllib.request.Request(
    "http://127.0.0.1:8080/auth/me",
    headers={"Authorization": "Bearer " + token},
)).read().decode())
print("buyer", me["name"], me["id"])

square = json.loads(urllib.request.urlopen("http://127.0.0.1:8080/square").read().decode())
kale = None
for stall in square["stalls"]:
    for g in stall["goods"]:
        if g["produce_name"].startswith("Lehtikaali"):
            kale = g
print("kale lot", kale["id"], kale["quantity_kg"], "kg")
result = post(
    "http://127.0.0.1:8080/transactions/complete",
    {"listing_id": kale["id"], "buyer_id": me["id"], "quantity_kg": 2.0, "is_walking": False},
    headers={"Authorization": "Bearer " + token},
)
print("trade", result)
ledger = json.loads(urllib.request.urlopen("http://127.0.0.1:8080/ledger").read().decode())
print("ledger", ledger[0])
print("ok")
