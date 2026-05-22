"""routes/expenses.py — Expense CRUD endpoints."""
import json
from datetime import datetime, timezone
from decimal import Decimal

from flask import Blueprint, request, jsonify
from models import db, Expense, Group

expenses_bp = Blueprint("expenses", __name__)


@expenses_bp.route("/groups/<group_id>/expenses", methods=["GET"])
def list_expenses(group_id):
    Group.query.get_or_404(group_id)
    exps = (
        Expense.query
        .filter_by(group_id=group_id, is_deleted=False)
        .order_by(Expense.date.desc())
        .all()
    )
    return jsonify([e.to_dict() for e in exps])


@expenses_bp.route("/groups/<group_id>/expenses", methods=["POST"])
def create_expense(group_id):
    Group.query.get_or_404(group_id)
    data = request.get_json() or {}

    for field in ("description", "amount", "paid_by"):
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    date_val = datetime.now(timezone.utc)
    if data.get("date"):
        try:
            date_val = datetime.fromisoformat(data["date"])
        except ValueError:
            return jsonify({"error": "Invalid date format. Use ISO 8601."}), 400

    exp = Expense(
        group_id=group_id,
        description=data["description"],
        amount=Decimal(str(data["amount"])),
        currency=data.get("currency", "INR"),
        paid_by=data["paid_by"],
        split_type=data.get("split_type", "equal"),
        split_data=json.dumps(data.get("split_data", {})),
        category=data.get("category", "general"),
        date=date_val,
    )
    db.session.add(exp)
    db.session.commit()
    return jsonify(exp.to_dict()), 201


@expenses_bp.route("/expenses/<expense_id>", methods=["GET"])
def get_expense(expense_id):
    return jsonify(Expense.query.get_or_404(expense_id).to_dict())


@expenses_bp.route("/expenses/<expense_id>", methods=["PUT"])
def update_expense(expense_id):
    exp = Expense.query.get_or_404(expense_id)
    data = request.get_json() or {}

    if "description" in data:
        exp.description = data["description"]
    if "amount" in data:
        exp.amount = Decimal(str(data["amount"]))
    if "currency" in data:
        exp.currency = data["currency"]
    if "paid_by" in data:
        exp.paid_by = data["paid_by"]
    if "split_type" in data:
        exp.split_type = data["split_type"]
    if "split_data" in data:
        exp.split_data = json.dumps(data["split_data"])
    if "category" in data:
        exp.category = data["category"]
    if "date" in data:
        try:
            exp.date = datetime.fromisoformat(data["date"])
        except ValueError:
            return jsonify({"error": "Invalid date format. Use ISO 8601."}), 400

    db.session.commit()
    return jsonify(exp.to_dict())


@expenses_bp.route("/expenses/<expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    exp = Expense.query.get_or_404(expense_id)
    exp.is_deleted = True          # soft delete — keeps history intact
    db.session.commit()
    return jsonify({"message": "Expense deleted"})
