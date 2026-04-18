def _register_and_token(client, email="farmer@test.com"):
    client.post("/auth/register", json={
        "email": email, "password": "pass", "name": "Farmer", "role": "farmer"
    })
    resp = client.post("/auth/token", data={"username": email, "password": "pass"})
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- API key CRUD ---

def test_create_api_key(client):
    token = _register_and_token(client)
    resp = client.post("/auth/api-keys", json={"label": "my phone"},
                       headers=_auth(token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["key"].startswith("farm_")
    assert data["prefix"] in data["key"]
    assert "note" in data


def test_api_key_auth(client):
    token = _register_and_token(client)
    key_resp = client.post("/auth/api-keys", json={"label": "test"},
                           headers=_auth(token))
    api_key = key_resp.json()["key"]

    resp = client.get("/auth/me", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    assert resp.json()["email"] == "farmer@test.com"


def test_invalid_api_key_rejected(client):
    resp = client.get("/auth/me", headers={"X-API-Key": "farm_bad_key"})
    assert resp.status_code == 401


def test_list_api_keys(client):
    token = _register_and_token(client)
    client.post("/auth/api-keys", json={"label": "a"}, headers=_auth(token))
    client.post("/auth/api-keys", json={"label": "b"}, headers=_auth(token))
    resp = client.get("/auth/api-keys", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_revoke_api_key(client):
    token = _register_and_token(client)
    key_resp = client.post("/auth/api-keys", json={"label": "test"},
                           headers=_auth(token))
    key_id = key_resp.json()["id"]
    api_key = key_resp.json()["key"]

    client.delete(f"/auth/api-keys/{key_id}", headers=_auth(token))

    resp = client.get("/auth/me", headers={"X-API-Key": api_key})
    assert resp.status_code == 401


# --- Discovery endpoints ---

def test_ai_plugin_manifest(client):
    resp = client.get("/.well-known/ai-plugin.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name_for_model"] == "farm_network"
    assert "openapi" in data["api"]["url"]


def test_mcp_manifest(client):
    resp = client.get("/.well-known/mcp.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "farm_network"
    assert "onboarding" in data


# --- Agent card ---

def test_agent_card(client):
    token = _register_and_token(client)
    resp = client.get("/me/agent-card", headers=_auth(token))
    assert resp.status_code == 200
    card = resp.json()["card"]
    assert "Farm Network" in card
    assert "X-API-Key" in card
    assert "farmer" in card


def test_agent_card_includes_nodes(client):
    token = _register_and_token(client)
    client.post("/nodes", json={
        "name": "Test Farm", "type": "farm", "lat": 60.5522, "lng": 24.7050
    }, headers=_auth(token))
    resp = client.get("/me/agent-card", headers=_auth(token))
    assert "Test Farm" in resp.json()["card"]
