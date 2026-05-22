"""tests/test_members.py — Unit tests for /api/members endpoints."""
import json
import pytest
from app import app as flask_app
from models import db


@pytest.fixture
def client():
    flask_app.config["TESTING"]               = True
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with flask_app.app_context():
        db.create_all()
        yield flask_app.test_client()
        db.drop_all()


def _post_member(client, name="Alex", email="alex@test.com", upi="alex@upi"):
    return client.post(
        "/api/members",
        data=json.dumps({"name": name, "email": email, "upi_id": upi}),
        content_type="application/json",
    )


# ── CREATE ────────────────────────────────────────────────────────────────────

def test_create_member(client):
    res = _post_member(client)
    assert res.status_code == 201
    body = res.get_json()
    assert body["name"]   == "Alex"
    assert body["email"]  == "alex@test.com"
    assert body["upi_id"] == "alex@upi"
    assert "id" in body


def test_create_member_missing_fields(client):
    res = client.post(
        "/api/members",
        data=json.dumps({"name": "No Email"}),
        content_type="application/json",
    )
    assert res.status_code == 400


def test_create_member_duplicate_email(client):
    _post_member(client)
    res = _post_member(client)          # same email
    assert res.status_code == 409


# ── READ ──────────────────────────────────────────────────────────────────────

def test_list_members_empty(client):
    res = client.get("/api/members")
    assert res.status_code == 200
    assert res.get_json() == []


def test_list_members(client):
    _post_member(client, "Alex", "alex@test.com")
    _post_member(client, "Sarah", "sarah@test.com")
    res = client.get("/api/members")
    assert res.status_code == 200
    assert len(res.get_json()) == 2


def test_get_member(client):
    created = _post_member(client).get_json()
    res     = client.get(f"/api/members/{created['id']}")
    assert res.status_code == 200
    assert res.get_json()["id"] == created["id"]


def test_get_member_not_found(client):
    res = client.get("/api/members/nonexistent-id")
    assert res.status_code == 404


# ── UPDATE ────────────────────────────────────────────────────────────────────

def test_update_member(client):
    mid = _post_member(client).get_json()["id"]
    res = client.put(
        f"/api/members/{mid}",
        data=json.dumps({"upi_id": "newalex@okaxis"}),
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.get_json()["upi_id"] == "newalex@okaxis"


# ── DELETE ────────────────────────────────────────────────────────────────────

def test_delete_member(client):
    mid = _post_member(client).get_json()["id"]
    res = client.delete(f"/api/members/{mid}")
    assert res.status_code == 200
    assert client.get(f"/api/members/{mid}").status_code == 404
