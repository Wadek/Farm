import pytest
from app.services.auth_service import hash_password, verify_password, create_token, decode_token
from app.models.user import UserRole


# --- unit tests ---

def test_password_hash_and_verify():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed)
    assert not verify_password("wrongpassword", hashed)


def test_token_round_trip():
    token = create_token("user-123", UserRole.farmer)
    data = decode_token(token)
    assert data.user_id == "user-123"
    assert data.role == UserRole.farmer


def test_invalid_token_raises():
    with pytest.raises(ValueError):
        decode_token("not.a.valid.token")


def test_tampered_token_raises():
    token = create_token("user-123", UserRole.farmer)
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(ValueError):
        decode_token(tampered)


# --- route integration tests ---

def test_register(client):
    resp = client.post("/auth/register", json={
        "email": "farmer@test.com",
        "password": "securepass",
        "name": "Test Farmer",
        "role": "farmer",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "farmer@test.com"
    assert data["role"] == "farmer"
    assert "password" not in data
    assert "hashed_password" not in data


def test_register_duplicate_email(client):
    payload = {"email": "dup@test.com", "password": "pass", "name": "User", "role": "buyer"}
    client.post("/auth/register", json=payload)
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 409


def test_login_returns_token(client):
    client.post("/auth/register", json={
        "email": "login@test.com", "password": "pass123",
        "name": "Login User", "role": "farmer",
    })
    resp = client.post("/auth/token", data={"username": "login@test.com", "password": "pass123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert resp.json()["token_type"] == "bearer"


def test_login_wrong_password(client):
    client.post("/auth/register", json={
        "email": "wp@test.com", "password": "correct",
        "name": "WP User", "role": "buyer",
    })
    resp = client.post("/auth/token", data={"username": "wp@test.com", "password": "wrong"})
    assert resp.status_code == 401


def test_me_endpoint(client):
    client.post("/auth/register", json={
        "email": "me@test.com", "password": "pass",
        "name": "Me User", "role": "buyer",
    })
    token_resp = client.post("/auth/token", data={"username": "me@test.com", "password": "pass"})
    token = token_resp.json()["access_token"]

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@test.com"


def test_me_without_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_farmer_role_preserved(client):
    client.post("/auth/register", json={
        "email": "farmrole@test.com", "password": "pass",
        "name": "Role Test", "role": "farmer",
    })
    token_resp = client.post("/auth/token", data={"username": "farmrole@test.com", "password": "pass"})
    token = token_resp.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["role"] == "farmer"
