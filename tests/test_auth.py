"""Auth flow tests: register, duplicate guard, login, protected routes."""


def test_register_and_login(client):
    r = client.post("/auth/register", json={"email": "x@y.com", "password": "pass123"})
    assert r.status_code == 201
    assert r.json()["email"] == "x@y.com"

    r = client.post("/auth/login", data={"username": "x@y.com", "password": "pass123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_duplicate_email_rejected(client):
    client.post("/auth/register", json={"email": "d@y.com", "password": "pass123"})
    r = client.post("/auth/register", json={"email": "d@y.com", "password": "pass123"})
    assert r.status_code == 400


def test_wrong_password_rejected(client):
    client.post("/auth/register", json={"email": "w@y.com", "password": "pass123"})
    r = client.post("/auth/login", data={"username": "w@y.com", "password": "nope"})
    assert r.status_code == 401


def test_protected_route_requires_token(client):
    r = client.get("/documents")
    assert r.status_code == 401
