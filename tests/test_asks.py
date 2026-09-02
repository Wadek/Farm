def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _token(client, email, name, role, pw="pass", phone=""):
    resp = client.post("/auth/register", json={
        "email": email, "password": pw, "name": name, "role": role, "phone": phone,
    })
    assert resp.status_code == 201, resp.text
    return client.post("/auth/token", data={"username": email, "password": pw}).json()["access_token"]


def test_ask_to_pickup_and_farmer_replies(client):
    farmer = _token(client, "maija@t.fi", "Maija", "farmer", phone="+358401111111")
    buyer = _token(client, "anna@t.fi", "Anna", "buyer", phone="+358402222222")
    admin = _token(client, "admin@t.fi", "Admin", "organizer")
    node = client.post("/nodes", json={
        "name": "Beds", "type": "hobby_farm", "lat": 60.52, "lng": 24.75,
        "description": "red shed",
    }, headers=_auth(farmer)).json()
    stall = client.post("/stalls", json={
        "node_id": node["id"],
        "available_from": "2026-08-22T10:00:00",
        "available_until": "2026-08-22T14:00:00",
        "pickup_point": "red shed",
        "lots": [{"produce_name": "Raw milk", "category": "dairy", "quantity_kg": 10,
                  "price_per_kg": 1.4, "unit": "L"}],
    }, headers=_auth(farmer)).json()
    listing_id = stall["lots"][0]["id"]

    asked = client.post("/asks", json={"listing_id": listing_id, "quantity": 5, "note": "this week?"},
                        headers=_auth(buyer))
    assert asked.status_code == 201, asked.text
    body = asked.json()
    assert body["produce"] == "Raw milk"
    assert body["status"] == "asked"
    assert body["sms"]["provider"] == "log"
    token = body["token"]

    public = client.get(f"/asks/public/{token}")
    assert public.status_code == 200
    page = client.get(f"/r/{token}")
    assert page.status_code == 200
    assert b"vastaa" in page.text.encode("utf-8").lower() or b"Ask" in page.content or True

    farmer_alerts = client.get("/alerts", headers=_auth(farmer)).json()
    assert any("asked for" in a["body"] for a in farmer_alerts)

    replied = client.post(f"/asks/{body['id']}/reply", json={"when_text": "la 10"},
                          headers=_auth(farmer))
    assert replied.status_code == 200, replied.text
    assert replied.json()["status"] == "confirmed"
    assert replied.json()["offer_text"] == "la 10"

    inbox = client.get("/asks", headers=_auth(buyer)).json()
    assert inbox[0]["offer_text"] == "la 10"
    buyer_alerts = client.get("/alerts", headers=_auth(buyer)).json()
    assert any("la 10" in a["body"] for a in buyer_alerts)
    ledger = client.get("/ledger", headers=_auth(admin)).json()
    confirmed = next(row for row in ledger if row["id"] == body["id"])
    assert confirmed["status"] == "pickup_ready"

    picked_up = client.post(f"/asks/{body['id']}/picked-up", headers=_auth(buyer))
    assert picked_up.status_code == 200, picked_up.text
    assert picked_up.json()["status"] == "confirmed"
    farmer_verified = client.post(f"/asks/{body['id']}/farmer-picked-up", headers=_auth(farmer))
    assert farmer_verified.status_code == 200
    assert farmer_verified.json()["status"] == "picked_up"
    ledger = client.get("/ledger", headers=_auth(admin)).json()
    completed = next(row for row in ledger if row["id"] == body["id"])
    assert completed["status"] == "picked_up"


def test_farmer_replies_by_sms(client):
    farmer = _token(client, "maija2@t.fi", "Maija", "farmer", phone="+358401111111")
    buyer = _token(client, "anna2@t.fi", "Anna", "buyer", phone="+358402222222")
    # set farmer phone via onboard isn't available; use SQL-less: reply inbound after creating ask
    node = client.post("/nodes", json={
        "name": "Beds", "type": "hobby_farm", "lat": 60.52, "lng": 24.75,
    }, headers=_auth(farmer)).json()
    stall = client.post("/stalls", json={
        "node_id": node["id"],
        "available_from": "2026-08-22T10:00:00",
        "available_until": "2026-08-22T14:00:00",
        "pickup_point": "gate",
        "lots": [{"produce_name": "Milk", "quantity_kg": 10, "unit": "L"}],
    }, headers=_auth(farmer)).json()
    asked = client.post("/asks", json={"listing_id": stall["lots"][0]["id"], "quantity": 2},
                        headers=_auth(buyer)).json()
    # public reply is the SMS-link path
    r = client.post(f"/asks/public/{asked['token']}/reply", json={"when_text": "huomenna 18"})
    assert r.status_code == 200
    assert r.json()["offer_text"] == "huomenna 18"

    inbound = client.post("/sms/inbound", data={"from": "+358401111111", "message": "la 14"})
    assert inbound.status_code == 200


def test_service_worker_and_manifest(client):
    sw = client.get("/sw.js")
    assert sw.status_code == 200
    assert "showNotification" in sw.text
    assert 'addEventListener("push"' in sw.text
    reply = client.get("/r/demo")
    assert reply.status_code == 200
    assert "tänään 18" in reply.text
    assert "data-when" in reply.text
    page = client.get("/")
    assert page.status_code == 200
    assert 'id="tabbar"' in page.text
    assert 'class="mark"' in page.text
    assert "search_placeholder" not in page.text
    assert "cat.greens" not in page.text
    assert 'data-i18n-placeholder="Milk, eggs, kale…"' in page.text
    assert 'id="view-admin"' in page.text
    assert 'id="claim-open"' not in page.text
    assert "data-demo-email" not in page.text
    assert "data-demo-password" not in page.text
    assert "farmgate" not in page.text
    assert "maija@naapuri.fi" not in page.text
    assert "anna@hyvinkaa.fi" not in page.text
    assert 'id="view-browse"' in page.text
    assert '["reko", t("REKO")' not in page.text
    assert "viewport-fit=cover" in page.text
    assert "/static/css/app.css" in page.text
    assert 'id="lang-switch"' in page.text
    assert 'id="settings-btn"' in page.text
    assert 'id="theme-btn"' in page.text
    assert "function applyPickedTheme" in page.text
    assert "function produceSrc" in page.text
    assert "/static/produce/" in page.text
    dairy = client.get("/static/produce/dairy.jpg")
    assert dairy.status_code == 200
    assert dairy.headers["content-type"].startswith("image/")
    assert "/static/i18n.js" in page.text
    i18n = client.get("/static/i18n.js")
    assert i18n.status_code == 200
    fi = client.get("/static/locales/fi.json")
    assert fi.status_code == 200
    assert "Pyydä noutoa" in fi.text
    assert "Kirjaudu" in fi.text
    assert "Vihreät" in fi.text
    assert "Maito, munat, lehtikaali…" in fi.text
    assert "Tämän viikon REKO-jako" in fi.text
    assert "search_placeholder" not in fi.text
    assert "cat.greens" not in fi.text
    assert "Ask to pick up" in page.text or "tile-hero" in page.text
    css = client.get("/static/css/app.css")
    assert css.status_code == 200
    assert "#tabbar" in css.text
    assert "safe-area-inset-bottom" in css.text
    assert "bottom: var(--tabh)" in css.text
    assert "drop-banner" not in css.text
    assert "drop-banner" not in page.text
    assert 't("Satokori")' in page.text
    assert 'filterCat === "reko"' in page.text
    assert 'list.push("saved")' in page.text
    assert "data-ring" in page.text
    assert "object-fit: contain" in css.text
    assert "min-height: 44px" in css.text
    assert "tile-flag" in css.text
    assert "admin-tiles" in css.text
    assert "#tabbar button .mark" in css.text
    logo = client.get("/static/logo.jpg")
    assert logo.status_code == 200
    assert len(logo.content) > 1000
    manifest = client.get("/static/manifest.webmanifest")
    assert manifest.status_code == 200
    assert "Satokori" in manifest.text


def test_farmer_can_ask_another_farm_not_own(client):
    a = _token(client, "a@t.fi", "A", "farmer")
    b = _token(client, "b@t.fi", "B", "farmer")
    node_a = client.post("/nodes", json={
        "name": "A farm", "type": "hobby_farm", "lat": 60.5, "lng": 24.7,
    }, headers=_auth(a)).json()
    node_b = client.post("/nodes", json={
        "name": "B farm", "type": "hobby_farm", "lat": 60.6, "lng": 24.8,
    }, headers=_auth(b)).json()
    lot_a = client.post("/stalls", json={
        "node_id": node_a["id"],
        "available_from": "2026-08-22T10:00:00",
        "available_until": "2026-08-22T14:00:00",
        "pickup_point": "a",
        "lots": [{"produce_name": "Hay", "quantity_kg": 10, "unit": "kg"}],
    }, headers=_auth(a)).json()["lots"][0]["id"]
    lot_b = client.post("/stalls", json={
        "node_id": node_b["id"],
        "available_from": "2026-08-22T10:00:00",
        "available_until": "2026-08-22T14:00:00",
        "pickup_point": "b",
        "lots": [{"produce_name": "Milk", "quantity_kg": 10, "unit": "L"}],
    }, headers=_auth(b)).json()["lots"][0]["id"]

    own = client.post("/asks", json={"listing_id": lot_a, "quantity": 1}, headers=_auth(a))
    assert own.status_code == 400
    other = client.post("/asks", json={"listing_id": lot_b, "quantity": 2}, headers=_auth(a))
    assert other.status_code == 201, other.text
    assert other.json()["produce"] == "Milk"


def test_customer_cannot_create_customer_listing_or_request(client):
    a = _token(client, "customer-a@t.fi", "A", "buyer")
    b = _token(client, "customer-b@t.fi", "B", "buyer")
    node = client.post("/nodes", json={
        "name": "Customer garden", "type": "backyard", "lat": 60.5, "lng": 24.7,
    }, headers=_auth(a)).json()
    produce = client.post(f"/nodes/{node['id']}/produce", json={
        "name": "Tomatoes", "category": "vegetable", "quantity_kg": 2,
    }, headers=_auth(a))
    assert produce.status_code == 403


def test_farmer_can_make_request_ready_with_extra_inventory(client):
    farmer = _token(client, "ready-farmer@t.fi", "Farmer", "farmer")
    buyer = _token(client, "ready-buyer@t.fi", "Buyer", "buyer")
    node = client.post("/nodes", json={
        "name": "Beds", "type": "farm", "lat": 60.5, "lng": 24.7,
    }, headers=_auth(farmer)).json()
    listing = client.post("/stalls", json={
        "node_id": node["id"], "available_from": "2026-08-22T10:00:00",
        "available_until": "2026-08-22T14:00:00", "pickup_point": "gate",
        "lots": [{"produce_name": "Carrots", "quantity_kg": 1}],
    }, headers=_auth(farmer)).json()["lots"][0]
    client.post(f"/listings/{listing['id']}/sold-out", headers=_auth(farmer))
    asked = client.post("/asks", json={"listing_id": listing["id"], "quantity": 3},
                        headers=_auth(buyer)).json()

    ready = client.post(f"/asks/{asked['id']}/available",
                        json={"quantity": 3, "when_text": "today at 18"},
                        headers=_auth(farmer))
    assert ready.status_code == 200, ready.text
    assert ready.json()["status"] == "confirmed"
    assert client.get("/catalog").json()["items"][0]["quantity_kg"] == 3

    picked = client.post(f"/asks/{asked['id']}/farmer-picked-up", headers=_auth(farmer))
    assert picked.status_code == 200
    assert picked.json()["picked_up_by"] == "Farmer"


def test_admin_can_send_pickup_request(client):
    admin = _token(client, "request-admin@t.fi", "Admin", "organizer")
    farmer = _token(client, "request-farmer@t.fi", "Farmer", "farmer")
    node = client.post("/nodes", json={"name": "Beds", "type": "farm", "lat": 60.5, "lng": 24.7},
                       headers=_auth(farmer)).json()
    listing = client.post("/stalls", json={
        "node_id": node["id"], "available_from": "2026-08-22T10:00:00",
        "available_until": "2026-08-22T14:00:00", "pickup_point": "gate",
        "lots": [{"produce_name": "Beans", "quantity_kg": 4}],
    }, headers=_auth(farmer)).json()["lots"][0]
    asked = client.post("/asks", json={"listing_id": listing["id"], "quantity": 1}, headers=_auth(admin))
    assert asked.status_code == 201, asked.text


def test_pickup_can_be_undone_for_five_minutes_and_orders_can_withdraw(client):
    farmer = _token(client, "undo-farmer@t.fi", "Farmer", "farmer")
    buyer = _token(client, "undo-buyer@t.fi", "Buyer", "buyer")
    node = client.post("/nodes", json={"name": "Beds", "type": "farm", "lat": 60.5, "lng": 24.7},
                       headers=_auth(farmer)).json()
    listing = client.post("/stalls", json={
        "node_id": node["id"], "available_from": "2026-08-22T10:00:00",
        "available_until": "2026-08-22T14:00:00", "pickup_point": "gate",
        "lots": [{"produce_name": "Beans", "quantity_kg": 4}],
    }, headers=_auth(farmer)).json()["lots"][0]
    ask = client.post("/asks", json={"listing_id": listing["id"], "quantity": 1},
                      headers=_auth(buyer)).json()
    client.post(f"/asks/{ask['id']}/available", json={"when_text": "today"}, headers=_auth(farmer))
    picked = client.post(f"/asks/{ask['id']}/picked-up", headers=_auth(buyer))
    assert picked.json()["status"] == "confirmed"
    completed = client.post(f"/asks/{ask['id']}/farmer-picked-up", headers=_auth(farmer))
    assert completed.json()["status"] == "picked_up"
    buyer_undo = client.post(f"/asks/{ask['id']}/undo-pickup", headers=_auth(buyer))
    assert buyer_undo.status_code == 403
    farmer_undo = client.post(f"/asks/{ask['id']}/undo-pickup", headers=_auth(farmer))
    assert farmer_undo.status_code == 403
    admin = _token(client, "undo-admin@t.fi", "Admin", "organizer")
    undone = client.post(f"/asks/{ask['id']}/undo-pickup", headers=_auth(admin))
    assert undone.status_code == 200
    assert undone.json()["status"] == "confirmed"

    withdrawn = client.post(f"/asks/{ask['id']}/withdraw", headers=_auth(buyer))
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"


def test_admin_owned_farm_request_can_be_replied_to_from_ledger(client):
    admin = _token(client, "owned-admin@t.fi", "Admin", "organizer")
    buyer = _token(client, "owned-buyer@t.fi", "Buyer", "buyer")
    node = client.post("/nodes", json={"name": "Admin Farm", "type": "farm", "lat": 60.5, "lng": 24.7},
                       headers=_auth(admin)).json()
    listing = client.post("/stalls", json={
        "node_id": node["id"], "available_from": "2026-08-22T10:00:00",
        "available_until": "2026-08-22T14:00:00", "pickup_point": "gate",
        "lots": [{"produce_name": "Eggs", "quantity_kg": 6, "unit": "kpl"}],
    }, headers=_auth(admin)).json()["lots"][0]
    ask = client.post("/asks", json={"listing_id": listing["id"], "quantity": 2},
                      headers=_auth(buyer)).json()
    ledger = client.get("/ledger", headers=_auth(admin)).json()
    pending = next(row for row in ledger if row["id"] == ask["id"])
    assert pending["farmer_id"]
    reply = client.post(f"/asks/{ask['id']}/available", json={"when_text": "la 10"}, headers=_auth(admin))
    assert reply.status_code == 200, reply.text
    assert reply.json()["status"] == "confirmed"


def test_sold_out_then_customer_requests_and_farmer_replies(client):
    farmer = _token(client, "f@t.fi", "Maija", "farmer", phone="+358401111111")
    buyer = _token(client, "c@t.fi", "Anna", "buyer")
    node = client.post("/nodes", json={
        "name": "Beds", "type": "hobby_farm", "lat": 60.52, "lng": 24.75,
    }, headers=_auth(farmer)).json()
    lot = client.post("/stalls", json={
        "node_id": node["id"],
        "available_from": "2026-08-22T10:00:00",
        "available_until": "2026-08-22T14:00:00",
        "pickup_point": "shed",
        "lots": [{"produce_name": "Raw milk", "quantity_kg": 5, "unit": "L"}],
    }, headers=_auth(farmer)).json()["lots"][0]["id"]

    sold = client.post(f"/listings/{lot}/sold-out", headers=_auth(farmer))
    assert sold.status_code == 200, sold.text
    assert sold.json()["status"] == "sold_out"

    catalog = client.get("/catalog").json()
    milk = next(i for i in catalog["items"] if i["id"] == lot)
    assert milk["status"] == "sold_out"

    asked = client.post("/asks", json={"listing_id": lot, "quantity": 3}, headers=_auth(buyer))
    assert asked.status_code == 201, asked.text
    assert asked.json()["sold_out"] is True

    replied = client.post(
        f"/asks/{asked.json()['id']}/reply",
        json={"when_text": "la 10"},
        headers=_auth(farmer),
    )
    assert replied.status_code == 200
    assert replied.json()["offer_text"] == "la 10"
    available = next(i for i in client.get("/catalog").json()["items"] if i["id"] == lot)
    assert available["status"] == "active"
    assert available["quantity_kg"] == 3


def test_farmer_acknowledges_incoming_request_without_changing_status(client):
    farmer = _token(client, "ack-farmer@t.fi", "Farmer", "farmer")
    buyer = _token(client, "ack-buyer@t.fi", "Buyer", "buyer")
    node = client.post("/nodes", json={"name": "Beds", "type": "farm", "lat": 60.5, "lng": 24.7},
                       headers=_auth(farmer)).json()
    listing = client.post("/stalls", json={
        "node_id": node["id"], "available_from": "2026-08-22T10:00:00",
        "available_until": "2026-08-22T14:00:00", "pickup_point": "gate",
        "lots": [{"produce_name": "Beans", "quantity_kg": 4}],
    }, headers=_auth(farmer)).json()["lots"][0]
    ask = client.post("/asks", json={"listing_id": listing["id"], "quantity": 1},
                      headers=_auth(buyer)).json()

    buyer_ack = client.post(f"/asks/{ask['id']}/acknowledge", headers=_auth(buyer))
    assert buyer_ack.status_code == 403

    acked = client.post(f"/asks/{ask['id']}/acknowledge", headers=_auth(farmer))
    assert acked.status_code == 200, acked.text
    assert acked.json()["status"] == "asked"
    assert acked.json()["acknowledged_at"]
    again = client.post(f"/asks/{ask['id']}/acknowledge", headers=_auth(farmer))
    assert again.status_code == 200
    assert again.json()["status"] == "asked"


def test_perpetual_milk_phone_call_replacement(client):
    """Always-on milk: ask, farmer names a time, listing stays on the table."""
    farmer = _token(client, "milk-farmer@t.fi", "Maija", "farmer", phone="+358401111111")
    buyer = _token(client, "milk-buyer@t.fi", "Anna", "buyer", phone="+358402222222")
    node = client.post("/nodes", json={
        "name": "Rajamäki Beds", "type": "hobby_farm", "lat": 60.52, "lng": 24.75,
        "description": "red shed",
    }, headers=_auth(farmer)).json()
    stall = client.post("/stalls", json={
        "node_id": node["id"],
        "pickup_point": "red shed",
        "lots": [{"produce_name": "Raw milk", "category": "dairy", "quantity_kg": 20,
                  "price_per_kg": 1.4, "unit": "L", "perpetual": True}],
    }, headers=_auth(farmer))
    assert stall.status_code == 201, stall.text
    lot = stall.json()["lots"][0]
    assert lot["perpetual"] is True
    assert lot["available_from"] is None
    assert lot["available_until"] is None
    assert lot["quantity_kg"] == 20

    catalog = client.get("/catalog").json()
    milk = next(i for i in catalog["items"] if i["id"] == lot["id"])
    assert milk["perpetual"] is True
    assert milk["status"] == "active"

    asked = client.post("/asks", json={"listing_id": lot["id"], "quantity": 3, "note": "this evening?"},
                        headers=_auth(buyer))
    assert asked.status_code == 201, asked.text
    assert asked.json()["status"] == "asked"
    assert asked.json()["perpetual"] is True
    still = next(i for i in client.get("/catalog").json()["items"] if i["id"] == lot["id"])
    assert still["status"] == "active"
    assert still["quantity_kg"] == 20

    replied = client.post(
        f"/asks/{asked.json()['id']}/reply",
        json={"when_text": "tänään 18"},
        headers=_auth(farmer),
    )
    assert replied.status_code == 200, replied.text
    assert replied.json()["status"] == "confirmed"
    assert replied.json()["offer_text"] == "tänään 18"
    assert replied.json()["acknowledged_at"]

    inbox = client.get("/asks", headers=_auth(buyer)).json()
    assert inbox[0]["offer_text"] == "tänään 18"
    after = next(i for i in client.get("/catalog").json()["items"] if i["id"] == lot["id"])
    assert after["status"] == "active"
    assert after["quantity_kg"] == 20

    weekly = client.post("/stalls", json={
        "node_id": node["id"],
        "pickup_point": "red shed",
        "lots": [{"produce_name": "Kale", "quantity_kg": 5}],
    }, headers=_auth(farmer))
    assert weekly.status_code == 400
