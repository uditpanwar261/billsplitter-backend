"""routes/members.py — Member CRUD endpoints."""
from flask import Blueprint, request, jsonify
from models import db, Member

members_bp = Blueprint("members", __name__)


@members_bp.route("/members", methods=["GET"])
def list_members():
    members = Member.query.order_by(Member.name).all()
    return jsonify([m.to_dict() for m in members])


@members_bp.route("/members", methods=["POST"])
def create_member():
    data = request.get_json() or {}
    if not data.get("name") or not data.get("email"):
        return jsonify({"error": "name and email are required"}), 400
    if Member.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 409
    m = Member(
        name=data["name"],
        email=data["email"],
        upi_id=data.get("upi_id"),
        avatar_url=data.get("avatar_url"),
    )
    db.session.add(m)
    db.session.commit()
    return jsonify(m.to_dict()), 201


@members_bp.route("/members/<member_id>", methods=["GET"])
def get_member(member_id):
    return jsonify(Member.query.get_or_404(member_id).to_dict())


@members_bp.route("/members/<member_id>", methods=["PUT"])
def update_member(member_id):
    m = Member.query.get_or_404(member_id)
    data = request.get_json() or {}
    for field in ("name", "email", "upi_id", "avatar_url"):
        if field in data:
            setattr(m, field, data[field])
    db.session.commit()
    return jsonify(m.to_dict())


@members_bp.route("/members/<member_id>", methods=["DELETE"])
def delete_member(member_id):
    m = Member.query.get_or_404(member_id)
    db.session.delete(m)
    db.session.commit()
    return jsonify({"message": "Member deleted"})
