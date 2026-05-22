"""
models.py — SQLAlchemy ORM models for BillSplitter.
Imported by app.py and routes/*.py.
"""
import uuid
import json
from datetime import datetime, timezone
from decimal import Decimal

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ── Many-to-many: Group ↔ Member ─────────────────────────────────────────────
group_members = db.Table(
    "group_members",
    db.Column("group_id",  db.String(36), db.ForeignKey("groups.id"),  primary_key=True),
    db.Column("member_id", db.String(36), db.ForeignKey("members.id"), primary_key=True),
    db.Column("joined_at", db.DateTime,   default=lambda: datetime.now(timezone.utc)),
)


# ── Member ────────────────────────────────────────────────────────────────────
class Member(db.Model):
    __tablename__ = "members"

    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    upi_id     = db.Column(db.String(100))
    avatar_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id":         self.id,
            "name":       self.name,
            "email":      self.email,
            "upi_id":     self.upi_id,
            "avatar_url": self.avatar_url,
            "created_at": self.created_at.isoformat(),
        }


# ── Group ─────────────────────────────────────────────────────────────────────
class Group(db.Model):
    __tablename__ = "groups"

    id          = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    category    = db.Column(db.String(50), default="general")  # trip/home/food/general
    created_by  = db.Column(db.String(36), db.ForeignKey("members.id"))
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    members  = db.relationship("Member", secondary=group_members, backref="groups", lazy="dynamic")
    creator  = db.relationship("Member", foreign_keys=[created_by])

    def to_dict(self, include_members=False):
        d = {
            "id":           self.id,
            "name":         self.name,
            "description":  self.description,
            "category":     self.category,
            "created_by":   self.created_by,
            "created_at":   self.created_at.isoformat(),
            "member_count": self.members.count(),
        }
        if include_members:
            d["members"] = [m.to_dict() for m in self.members]
        return d


# ── Expense ───────────────────────────────────────────────────────────────────
class Expense(db.Model):
    __tablename__ = "expenses"

    id          = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id    = db.Column(db.String(36), db.ForeignKey("groups.id"), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount      = db.Column(db.Numeric(12, 2), nullable=False)
    currency    = db.Column(db.String(3), default="INR")
    paid_by     = db.Column(db.String(36), db.ForeignKey("members.id"), nullable=False)
    split_type  = db.Column(db.String(20), default="equal")   # equal / exact / percent
    split_data  = db.Column(db.Text)                           # JSON blob
    category    = db.Column(db.String(50), default="general")
    date        = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))
    is_deleted  = db.Column(db.Boolean, default=False)

    payer = db.relationship("Member", foreign_keys=[paid_by])
    group = db.relationship("Group", backref="expenses")

    def to_dict(self):
        return {
            "id":          self.id,
            "group_id":    self.group_id,
            "description": self.description,
            "amount":      float(self.amount),
            "currency":    self.currency,
            "paid_by":     self.paid_by,
            "payer_name":  self.payer.name if self.payer else None,
            "split_type":  self.split_type,
            "split_data":  json.loads(self.split_data or "{}"),
            "category":    self.category,
            "date":        self.date.isoformat(),
            "created_at":  self.created_at.isoformat(),
        }


# ── Settlement ────────────────────────────────────────────────────────────────
class Settlement(db.Model):
    __tablename__ = "settlements"

    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id   = db.Column(db.String(36), db.ForeignKey("groups.id"),  nullable=False)
    from_id    = db.Column(db.String(36), db.ForeignKey("members.id"), nullable=False)
    to_id      = db.Column(db.String(36), db.ForeignKey("members.id"), nullable=False)
    amount     = db.Column(db.Numeric(12, 2), nullable=False)
    status     = db.Column(db.String(20), default="pending")   # pending / completed
    upi_ref    = db.Column(db.String(100))
    settled_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    payer = db.relationship("Member", foreign_keys=[from_id])
    payee = db.relationship("Member", foreign_keys=[to_id])

    def to_dict(self):
        return {
            "id":          self.id,
            "group_id":    self.group_id,
            "from_id":     self.from_id,
            "from_name":   self.payer.name if self.payer else None,
            "to_id":       self.to_id,
            "to_name":     self.payee.name if self.payee else None,
            "amount":      float(self.amount),
            "status":      self.status,
            "upi_ref":     self.upi_ref,
            "settled_at":  self.settled_at.isoformat() if self.settled_at else None,
            "created_at":  self.created_at.isoformat(),
        }
