"""routes/settlements.py — Settlement record & completion endpoints."""
from datetime import datetime, timezone
from decimal import Decimal

from flask import Blueprint, request, jsonify
from models import db, Settlement, Group

settlements_bp = Blueprint("settlements", __name__)


@settlements_bp.route("/groups/<group_id>/settlements", methods=["GET"])
def list_settlements(group_id):
    Group.query.get_or_404(group_id)
    settlements = (
        Settlement.query
        .filter_by(group_id=group_id)
        .order_by(Settlement.created_at.desc())
        .all()
    )
    return jsonify([s.to_dict() for s in settlements])


@settlements_bp.route("/groups/<group_id>/settlements", methods=["POST"])
def create_settlement(group_id):
    Group.query.get_or_404(group_id)
    data = request.get_json() or {}

    for field in ("from_id", "to_id", "amount"):
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    s = Settlement(
        group_id=group_id,
        from_id=data["from_id"],
        to_id=data["to_id"],
        amount=Decimal(str(data["amount"])),
        upi_ref=data.get("upi_ref"),
    )
    db.session.add(s)
    db.session.commit()
    return jsonify(s.to_dict()), 201


@settlements_bp.route("/settlements/<settlement_id>", methods=["GET"])
def get_settlement(settlement_id):
    return jsonify(Settlement.query.get_or_404(settlement_id).to_dict())


@settlements_bp.route("/settlements/<settlement_id>/complete", methods=["POST"])
def complete_settlement(settlement_id):
    s    = Settlement.query.get_or_404(settlement_id)
    data = request.get_json() or {}

    s.status     = "completed"
    s.upi_ref    = data.get("upi_ref", s.upi_ref)
    s.settled_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(s.to_dict())


@settlements_bp.route("/settlements/<settlement_id>", methods=["DELETE"])
def delete_settlement(settlement_id):
    s = Settlement.query.get_or_404(settlement_id)
    db.session.delete(s)
    db.session.commit()
    return jsonify({"message": "Settlement deleted"})
