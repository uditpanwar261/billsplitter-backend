"""tests/test_expenses.py — Unit tests for expenses + debt reconciliation."""
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_member(client, name, email, upi=None):
    res = client.post(
        "/api/members",
        data=json.dumps({"name": name, "email": email, "upi_id": upi}),
        content_type="application/json",
    )
    assert res.status_code == 201
    return res.get_json()


def make_group(client, name, member_ids):
    res = client.post(
        "/api/groups",
        data=json.dumps({"name": name, "member_ids": member_ids}),
        content_type="application/json",
    )
    assert res.status_code == 201
    return res.get_json()


def make_expense(client, group_id, desc, amount, paid_by, participants, split="equal"):
    res = client.post(
        f"/api/groups/{group_id}/expenses",
        data=json.dumps({
            "description": desc,
            "amount":      amount,
            "paid_by":     paid_by,
            "split_type":  split,
            "split_data":  {"participants": participants},
        }),
        content_type="application/json",
    )
    assert res.status_code == 201
    return res.get_json()


# ── Expense CRUD ──────────────────────────────────────────────────────────────

def test_create_expense(client):
    m  = make_member(client, "Alex", "alex@t.com")
    g  = make_group(client, "TestGroup", [m["id"]])
    e  = make_expense(client, g["id"], "Pizza", 400, m["id"], [m["id"]])
    assert e["amount"]      == 400.0
    assert e["description"] == "Pizza"
    assert e["paid_by"]     == m["id"]


def test_list_expenses(client):
    m = make_member(client, "Alex", "alex@t.com")
    g = make_group(client, "G", [m["id"]])
    make_expense(client, g["id"], "Exp1", 100, m["id"], [m["id"]])
    make_expense(client, g["id"], "Exp2", 200, m["id"], [m["id"]])
    res = client.get(f"/api/groups/{g['id']}/expenses")
    assert res.status_code == 200
    assert len(res.get_json()) == 2


def test_update_expense(client):
    m  = make_member(client, "Alex", "alex@t.com")
    g  = make_group(client, "G", [m["id"]])
    e  = make_expense(client, g["id"], "Pizza", 400, m["id"], [m["id"]])
    res = client.put(
        f"/api/expenses/{e['id']}",
        data=json.dumps({"description": "Biryani", "amount": 500}),
        content_type="application/json",
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["description"] == "Biryani"
    assert body["amount"]      == 500.0


def test_soft_delete_expense(client):
    m  = make_member(client, "Alex", "alex@t.com")
    g  = make_group(client, "G", [m["id"]])
    e  = make_expense(client, g["id"], "Pizza", 400, m["id"], [m["id"]])
    res = client.delete(f"/api/expenses/{e['id']}")
    assert res.status_code == 200
    # Soft-deleted expenses must not appear in group listing
    exps = client.get(f"/api/groups/{g['id']}/expenses").get_json()
    assert all(ex["id"] != e["id"] for ex in exps)


# ── Balance & Debt Reconciliation ─────────────────────────────────────────────

def test_equal_split_balances(client):
    """
    Alex pays ₹300 for 3 people equally.
    Expected: Alex +₹200, Bob -₹100, Carol -₹100
    """
    alex  = make_member(client, "Alex",  "alex@t.com")
    bob   = make_member(client, "Bob",   "bob@t.com")
    carol = make_member(client, "Carol", "carol@t.com")
    g     = make_group(client, "G", [alex["id"], bob["id"], carol["id"]])

    make_expense(
        client, g["id"], "Dinner", 300, alex["id"],
        [alex["id"], bob["id"], carol["id"]]
    )

    res  = client.get(f"/api/groups/{g['id']}/balances")
    assert res.status_code == 200
    bals = {b["member_id"]: b["balance"] for b in res.get_json()}

    assert abs(bals[alex["id"]]  -  200.0) < 0.01
    assert abs(bals[bob["id"]]   - (-100.0)) < 0.01
    assert abs(bals[carol["id"]] - (-100.0)) < 0.01


def test_debt_minimization(client):
    """
    3 members, multiple expenses — suggestions must fully cancel all debts
    and use at most N-1 = 2 transactions.
    """
    alex  = make_member(client, "Alex",  "alex@t.com")
    bob   = make_member(client, "Bob",   "bob@t.com")
    carol = make_member(client, "Carol", "carol@t.com")
    ids   = [alex["id"], bob["id"], carol["id"]]
    g     = make_group(client, "G", ids)

    make_expense(client, g["id"], "Dinner",  300, alex["id"],  ids)
    make_expense(client, g["id"], "Cab",     150, bob["id"],   ids)
    make_expense(client, g["id"], "Hotel",   600, carol["id"], ids)

    suggestions = client.get(
        f"/api/groups/{g['id']}/settlements/suggestions"
    ).get_json()

    assert len(suggestions) <= 2          # at most N-1 transactions

    # Net sum of all suggestion amounts must equal total debt outstanding
    balances = client.get(f"/api/groups/{g['id']}/balances").get_json()
    total_debt = sum(b["balance"] for b in balances if b["balance"] < 0)
    total_sugg = sum(s["amount"] for s in suggestions)
    assert abs(total_sugg + total_debt) < 0.01


def test_settled_expense_excluded_from_balances(client):
    """After a settlement is completed it must be reflected in balances."""
    alex = make_member(client, "Alex", "alex@t.com")
    bob  = make_member(client, "Bob",  "bob@t.com")
    g    = make_group(client, "G", [alex["id"], bob["id"]])

    make_expense(client, g["id"], "Lunch", 200, alex["id"],
                 [alex["id"], bob["id"]])

    # Bob owes Alex ₹100 — record and complete the settlement
    s = client.post(
        f"/api/groups/{g['id']}/settlements",
        data=json.dumps({
            "from_id": bob["id"],
            "to_id":   alex["id"],
            "amount":  100,
        }),
        content_type="application/json",
    ).get_json()

    client.post(f"/api/settlements/{s['id']}/complete",
                data=json.dumps({}), content_type="application/json")

    bals = {b["member_id"]: b["balance"]
            for b in client.get(f"/api/groups/{g['id']}/balances").get_json()}

    assert abs(bals[alex["id"]]) < 0.01
    assert abs(bals[bob["id"]])  < 0.01
