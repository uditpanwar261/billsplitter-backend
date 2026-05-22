"""routes/groups.py — Group CRUD + member management endpoints."""
from flask import Blueprint, request, jsonify
from models import db, Group, Member

groups_bp = Blueprint("groups", __name__)


@groups_bp.route("/groups", methods=["GET"])
def list_groups():
    groups = Group.query.order_by(Group.created_at.desc()).all()
    return jsonify([g.to_dict() for g in groups])


@groups_bp.route("/groups", methods=["POST"])
def create_group():
    data = request.get_json() or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    g = Group(
        name=data["name"],
        description=data.get("description"),
        category=data.get("category", "general"),
        created_by=data.get("created_by"),
    )
    db.session.add(g)
    for mid in data.get("member_ids", []):
        m = Member.query.get(mid)
        if m:
            g.members.append(m)
    db.session.commit()
    return jsonify(g.to_dict(include_members=True)), 201


@groups_bp.route("/groups/<group_id>", methods=["GET"])
def get_group(group_id):
    return jsonify(Group.query.get_or_404(group_id).to_dict(include_members=True))


@groups_bp.route("/groups/<group_id>", methods=["PUT"])
def update_group(group_id):
    g = Group.query.get_or_404(group_id)
    data = request.get_json() or {}
    for field in ("name", "description", "category"):
        if field in data:
            setattr(g, field, data[field])
    db.session.commit()
    return jsonify(g.to_dict())


@groups_bp.route("/groups/<group_id>", methods=["DELETE"])
def delete_group(group_id):
    g = Group.query.get_or_404(group_id)
    db.session.delete(g)
    db.session.commit()
    return jsonify({"message": "Group deleted"})


@groups_bp.route("/groups/<group_id>/members", methods=["POST"])
def add_member(group_id):
    g = Group.query.get_or_404(group_id)
    data = request.get_json() or {}
    m = Member.query.get_or_404(data.get("member_id", ""))
    if m not in g.members:
        g.members.append(m)
        db.session.commit()
    return jsonify(g.to_dict(include_members=True))


@groups_bp.route("/groups/<group_id>/members/<member_id>", methods=["DELETE"])
def remove_member(group_id, member_id):
    g = Group.query.get_or_404(group_id)
    m = Member.query.get_or_404(member_id)
    if m in g.members:
        g.members.remove(m)
        db.session.commit()
    return jsonify({"message": "Member removed from group"})
