"""
routes/balances.py
Debt reconciliation, per-group balances, and analytics endpoints.

Algorithm: Greedy creditor-debtor matching (Splitwise-style).
  1. Compute net balance per member across all expenses in the group.
  2. Separate members into creditors (balance > 0) and debtors (balance < 0).
  3. Two-pointer greedy pass: pair the largest creditor with the largest debtor,
     settle min(credit, debit), advance whichever side reaches 0.
  Result: at most (N-1) transactions for N members — optimal in practice.
"""
import json
from collections import defaultdict
from decimal import Decimal

from flask import Blueprint, jsonify
from models import Expense, Group, Settlement

balances_bp = Blueprint("balances", __name__)


# ── Core algorithm ────────────────────────────────────────────────────────────

def compute_balances(group_id: str) -> dict:
    """Return {member_id: net_float} for every member in the group."""
    expenses = Expense.query.filter_by(group_id=group_id, is_deleted=False).all()
    balances: dict[str, Decimal] = defaultdict(Decimal)

    for exp in expenses:
        total    = Decimal(str(exp.amount))
        paid_by  = exp.paid_by
        raw      = json.loads(exp.split_data or "{}")
        participants = raw.get("participants", [])

        if not participants:
            # Fall back to all current group members
            participants = [m.id for m in Group.query.get(group_id).members.all()]

        if not participants:
            continue

        if exp.split_type == "equal":
            share = total / len(participants)
            for pid in participants:
                balances[pid] -= share
            balances[paid_by] += total

        elif exp.split_type == "exact":
            amounts = raw.get("amounts", {})
            for pid, amt in amounts.items():
                balances[pid] -= Decimal(str(amt))
            balances[paid_by] += total

        elif exp.split_type == "percent":
            percents = raw.get("percents", {})
            for pid, pct in percents.items():
                balances[pid] -= total * Decimal(str(pct)) / 100
            balances[paid_by] += total

    # Subtract already-completed settlements
    completed = Settlement.query.filter_by(group_id=group_id, status="completed").all()
    for s in completed:
        balances[s.from_id] += Decimal(str(s.amount))
        balances[s.to_id]   -= Decimal(str(s.amount))

    return {k: float(round(v, 2)) for k, v in balances.items()}


def minimize_transactions(balances: dict) -> list:
    """
    Greedy algorithm: return the minimum list of (from, to, amount) transfers
    that settle all debts.
    """
    creditors, debtors = [], []
    for mid, bal in balances.items():
        if bal > 0.01:
            creditors.append([bal, mid])
        elif bal < -0.01:
            debtors.append([-bal, mid])

    creditors.sort(reverse=True)
    debtors.sort(reverse=True)
    transactions = []

    i = j = 0
    while i < len(creditors) and j < len(debtors):
        credit_amt, creditor = creditors[i]
        debit_amt,  debtor   = debtors[j]
        settled = round(min(credit_amt, debit_amt), 2)
        transactions.append({"from": debtor, "to": creditor, "amount": settled})
        creditors[i][0] -= settled
        debtors[j][0]   -= settled
        if creditors[i][0] < 0.01:
            i += 1
        if debtors[j][0] < 0.01:
            j += 1

    return transactions


# ── Routes ────────────────────────────────────────────────────────────────────

@balances_bp.route("/groups/<group_id>/balances", methods=["GET"])
def group_balances(group_id):
    g = Group.query.get_or_404(group_id)
    balances = compute_balances(group_id)
    members  = {m.id: m.name for m in g.members}

    result = [
        {
            "member_id":   mid,
            "member_name": members.get(mid, "Unknown"),
            "balance":     bal,
            "status":      "owed" if bal > 0 else ("owes" if bal < 0 else "settled"),
        }
        for mid, bal in balances.items()
    ]
    return jsonify(result)


@balances_bp.route("/groups/<group_id>/settlements/suggestions", methods=["GET"])
def settlement_suggestions(group_id):
    g        = Group.query.get_or_404(group_id)
    balances = compute_balances(group_id)
    txns     = minimize_transactions(balances)
    members  = {m.id: m for m in g.members}

    enriched = []
    for t in txns:
        fm = members.get(t["from"])
        tm = members.get(t["to"])
        enriched.append({
            "from_id":   t["from"],
            "from_name": fm.name   if fm else "Unknown",
            "to_id":     t["to"],
            "to_name":   tm.name   if tm else "Unknown",
            "amount":    t["amount"],
            "upi_id":    tm.upi_id if tm else None,
        })
    return jsonify(enriched)


@balances_bp.route("/groups/<group_id>/analytics", methods=["GET"])
def group_analytics(group_id):
    g    = Group.query.get_or_404(group_id)
    exps = Expense.query.filter_by(group_id=group_id, is_deleted=False).all()

    total      = sum(float(e.amount) for e in exps)
    by_cat     = defaultdict(float)
    by_member  = defaultdict(float)

    for e in exps:
        by_cat[e.category or "general"] += float(e.amount)
        by_member[e.paid_by]            += float(e.amount)

    member_names = {m.id: m.name for m in g.members}

    return jsonify({
        "total_expenses":  total,
        "expense_count":   len(exps),
        "member_count":    g.members.count(),
        "by_category":     dict(by_cat),
        "by_member":       {member_names.get(k, k): v for k, v in by_member.items()},
    })
