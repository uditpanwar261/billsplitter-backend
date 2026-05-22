"""tests/test_upi.py — Tests for UPI QR generation and validation."""
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


def test_generate_qr_success(client):
    res = client.post(
        "/api/upi/qr",
        data=json.dumps({
            "upi_id": "alex@upi",
            "name":   "Alex Kumar",
            "amount": 250.00,
            "note":   "BillSplitter Settlement",
        }),
        content_type="application/json",
    )
    assert res.status_code == 200
    body = res.get_json()
    assert "qr_image" in body
    assert "upi_url"  in body
    assert body["upi_url"].startswith("upi://pay")
    assert "pa=alex@upi" in body["upi_url"]
    assert "am=250.00"   in body["upi_url"]
    assert "cu=INR"      in body["upi_url"]


def test_generate_qr_missing_fields(client):
    res = client.post(
        "/api/upi/qr",
        data=json.dumps({"upi_id": "alex@upi"}),   # missing name + amount
        content_type="application/json",
    )
    assert res.status_code == 400


def test_validate_upi_valid(client):
    res = client.post(
        "/api/upi/validate",
        data=json.dumps({"upi_id": "john.doe@okicici"}),
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.get_json()["valid"] is True


def test_validate_upi_invalid(client):
    res = client.post(
        "/api/upi/validate",
        data=json.dumps({"upi_id": "not-a-valid-upi"}),
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.get_json()["valid"] is False


def test_validate_upi_missing(client):
    res = client.post(
        "/api/upi/validate",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert res.status_code == 400
