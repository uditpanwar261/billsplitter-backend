from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timezone
import uuid, os, json, qrcode, io, base64
from decimal import Decimal
from collections import defaultdict

app = Flask(__name__)

# ─── CORS ──────────────────────────────────────────────────────────────────────
# In production set CORS_ORIGINS to your Vercel URL.
# Locally this allows VS Code Live Server (5500), python http.server (3000),
# file:// and any other local port you might use.
_cors_origins = os.environ.get("CORS_ORIGINS", "*")
CORS(app, resources={r"/*": {"origins": _cors_origins}},
     supports_credentials=True)

# ─── Config ────────────────────────────────────────────────────────────────────
# Railway injects DATABASE_URL as a MySQL URL.
# Falls back to SQLite for zero-config local dev or Render free tier.
_db_url = os.environ.get('DATABASE_URL', '')
if not _db_url:
    _db_url = 'sqlite:///billsplitter.db'
# Railway MySQL URLs use mysql:// — SQLAlchemy needs mysql+pymysql://
if _db_url.startswith('mysql://'):
    _db_url = _db_url.replace('mysql://', 'mysql+pymysql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')

db = SQLAlchemy(app)


# ─── Models ────────────────────────────────────────────────────────────────────

group_members = db.Table('group_members',
    db.Column('group_id',  db.String(36), db.ForeignKey('groups.id'),  primary_key=True),
    db.Column('member_id', db.String(36), db.ForeignKey('members.id'), primary_key=True),
    db.Column('joined_at', db.DateTime, default=lambda: datetime.now(timezone.utc))
)


class Member(db.Model):
    __tablename__ = 'members'
    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    upi_id     = db.Column(db.String(100))
    avatar_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'email': self.email,
            'upi_id': self.upi_id, 'avatar_url': self.avatar_url,
            'created_at': self.created_at.isoformat()
        }


class Group(db.Model):
    __tablename__ = 'groups'
    id          = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    category    = db.Column(db.String(50), default='general')   # trip / home / food / general
    created_by  = db.Column(db.String(36), db.ForeignKey('members.id'))
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    members     = db.relationship('Member', secondary=group_members, backref='groups', lazy='dynamic')

    def to_dict(self, include_members=False):
        d = {
            'id': self.id, 'name': self.name, 'description': self.description,
            'category': self.category, 'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'member_count': self.members.count()
        }
        if include_members:
            d['members'] = [m.to_dict() for m in self.members]
        return d


class Expense(db.Model):
    __tablename__ = 'expenses'
    id           = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id     = db.Column(db.String(36), db.ForeignKey('groups.id'), nullable=False)
    description  = db.Column(db.String(255), nullable=False)
    amount       = db.Column(db.Numeric(12, 2), nullable=False)
    currency     = db.Column(db.String(3), default='INR')
    paid_by      = db.Column(db.String(36), db.ForeignKey('members.id'), nullable=False)
    split_type   = db.Column(db.String(20), default='equal')  # equal / exact / percent
    split_data   = db.Column(db.Text)   # JSON
    category     = db.Column(db.String(50), default='general')
    date         = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at   = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))
    is_deleted   = db.Column(db.Boolean, default=False)

    payer   = db.relationship('Member', foreign_keys=[paid_by])
    group   = db.relationship('Group', backref='expenses')

    def to_dict(self):
        return {
            'id': self.id, 'group_id': self.group_id, 'description': self.description,
            'amount': float(self.amount), 'currency': self.currency,
            'paid_by': self.paid_by, 'payer_name': self.payer.name if self.payer else None,
            'split_type': self.split_type, 'split_data': json.loads(self.split_data or '{}'),
            'category': self.category, 'date': self.date.isoformat(),
            'created_at': self.created_at.isoformat()
        }


class Settlement(db.Model):
    __tablename__ = 'settlements'
    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id   = db.Column(db.String(36), db.ForeignKey('groups.id'), nullable=False)
    from_id    = db.Column(db.String(36), db.ForeignKey('members.id'), nullable=False)
    to_id      = db.Column(db.String(36), db.ForeignKey('members.id'), nullable=False)
    amount     = db.Column(db.Numeric(12, 2), nullable=False)
    status     = db.Column(db.String(20), default='pending')   # pending / completed
    upi_ref    = db.Column(db.String(100))
    settled_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    payer   = db.relationship('Member', foreign_keys=[from_id])
    payee   = db.relationship('Member', foreign_keys=[to_id])

    def to_dict(self):
        return {
            'id': self.id, 'group_id': self.group_id,
            'from_id': self.from_id, 'from_name': self.payer.name if self.payer else None,
            'to_id': self.to_id,   'to_name':   self.payee.name if self.payee else None,
            'amount': float(self.amount), 'status': self.status,
            'upi_ref': self.upi_ref, 'settled_at': self.settled_at.isoformat() if self.settled_at else None,
            'created_at': self.created_at.isoformat()
        }


# ─── Helpers ───────────────────────────────────────────────────────────────────

def compute_balances(group_id):
    """Return net balance dict {member_id: net_amount} for a group."""
    expenses = Expense.query.filter_by(group_id=group_id, is_deleted=False).all()
    balances = defaultdict(Decimal)

    for exp in expenses:
        total  = Decimal(str(exp.amount))
        paid_by = exp.paid_by
        split_data = json.loads(exp.split_data or '{}')
        participants = split_data.get('participants', [])

        if not participants:
            # Fallback: all group members
            members = Group.query.get(group_id).members.all()
            participants = [m.id for m in members]

        if exp.split_type == 'equal':
            share = total / len(participants)
            for pid in participants:
                balances[pid] -= share
            balances[paid_by] += total

        elif exp.split_type == 'exact':
            amounts = split_data.get('amounts', {})
            for pid, amt in amounts.items():
                balances[pid] -= Decimal(str(amt))
            balances[paid_by] += total

        elif exp.split_type == 'percent':
            percents = split_data.get('percents', {})
            for pid, pct in percents.items():
                balances[pid] -= total * Decimal(str(pct)) / 100
            balances[paid_by] += total

    return {k: float(round(v, 2)) for k, v in balances.items()}


def minimize_transactions(balances: dict):
    """Greedy debt-simplification algorithm (Splitwise-style)."""
    creditors, debtors = [], []
    for mid, bal in balances.items():
        if bal > 0.01:
            creditors.append([bal, mid])
        elif bal < -0.01:
            debtors.append([-bal, mid])

    creditors.sort(reverse=True)
    debtors.sort(reverse=True)
    transactions = []

    i, j = 0, 0
    while i < len(creditors) and j < len(debtors):
        credit_amt, creditor = creditors[i]
        debit_amt,  debtor   = debtors[j]
        settled = min(credit_amt, debit_amt)
        transactions.append({
            'from': debtor, 'to': creditor, 'amount': round(settled, 2)
        })
        creditors[i][0] -= settled
        debtors[j][0]   -= settled
        if creditors[i][0] < 0.01: i += 1
        if debtors[j][0]   < 0.01: j += 1

    return transactions


def generate_upi_qr(upi_id, name, amount, note='BillSplitter'):
    """Generate a UPI deep-link QR code and return base64 PNG."""
    upi_url = (
        f"upi://pay?pa={upi_id}&pn={name}&am={amount:.2f}"
        f"&cu=INR&tn={note}"
    )
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode(), upi_url


# ─── Routes: Members ───────────────────────────────────────────────────────────

@app.route('/api/members', methods=['GET'])
def list_members():
    members = Member.query.order_by(Member.name).all()
    return jsonify([m.to_dict() for m in members])


@app.route('/api/members', methods=['POST'])
def create_member():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('email'):
        return jsonify({'error': 'name and email are required'}), 400
    if Member.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 409
    member = Member(
        name=data['name'], email=data['email'],
        upi_id=data.get('upi_id'), avatar_url=data.get('avatar_url')
    )
    db.session.add(member)
    db.session.commit()
    return jsonify(member.to_dict()), 201


@app.route('/api/members/<member_id>', methods=['GET'])
def get_member(member_id):
    m = Member.query.get_or_404(member_id)
    return jsonify(m.to_dict())


@app.route('/api/members/<member_id>', methods=['PUT'])
def update_member(member_id):
    m = Member.query.get_or_404(member_id)
    data = request.get_json()
    for field in ('name', 'email', 'upi_id', 'avatar_url'):
        if field in data:
            setattr(m, field, data[field])
    db.session.commit()
    return jsonify(m.to_dict())


@app.route('/api/members/<member_id>', methods=['DELETE'])
def delete_member(member_id):
    m = Member.query.get_or_404(member_id)
    db.session.delete(m)
    db.session.commit()
    return jsonify({'message': 'Member deleted'}), 200


# ─── Routes: Groups ────────────────────────────────────────────────────────────

@app.route('/api/groups', methods=['GET'])
def list_groups():
    groups = Group.query.order_by(Group.created_at.desc()).all()
    return jsonify([g.to_dict() for g in groups])


@app.route('/api/groups', methods=['POST'])
def create_group():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'name is required'}), 400
    group = Group(
        name=data['name'], description=data.get('description'),
        category=data.get('category', 'general'), created_by=data.get('created_by')
    )
    db.session.add(group)
    # Add initial members
    for mid in data.get('member_ids', []):
        m = Member.query.get(mid)
        if m:
            group.members.append(m)
    db.session.commit()
    return jsonify(group.to_dict(include_members=True)), 201


@app.route('/api/groups/<group_id>', methods=['GET'])
def get_group(group_id):
    g = Group.query.get_or_404(group_id)
    return jsonify(g.to_dict(include_members=True))


@app.route('/api/groups/<group_id>', methods=['PUT'])
def update_group(group_id):
    g = Group.query.get_or_404(group_id)
    data = request.get_json()
    for field in ('name', 'description', 'category'):
        if field in data:
            setattr(g, field, data[field])
    db.session.commit()
    return jsonify(g.to_dict())


@app.route('/api/groups/<group_id>', methods=['DELETE'])
def delete_group(group_id):
    g = Group.query.get_or_404(group_id)
    db.session.delete(g)
    db.session.commit()
    return jsonify({'message': 'Group deleted'})


@app.route('/api/groups/<group_id>/members', methods=['POST'])
def add_group_member(group_id):
    g = Group.query.get_or_404(group_id)
    data = request.get_json()
    m = Member.query.get_or_404(data['member_id'])
    if m not in g.members:
        g.members.append(m)
        db.session.commit()
    return jsonify(g.to_dict(include_members=True))


@app.route('/api/groups/<group_id>/members/<member_id>', methods=['DELETE'])
def remove_group_member(group_id, member_id):
    g = Group.query.get_or_404(group_id)
    m = Member.query.get_or_404(member_id)
    if m in g.members:
        g.members.remove(m)
        db.session.commit()
    return jsonify({'message': 'Member removed from group'})


# ─── Routes: Expenses ──────────────────────────────────────────────────────────

@app.route('/api/groups/<group_id>/expenses', methods=['GET'])
def list_expenses(group_id):
    Group.query.get_or_404(group_id)
    exps = (Expense.query
            .filter_by(group_id=group_id, is_deleted=False)
            .order_by(Expense.date.desc()).all())
    return jsonify([e.to_dict() for e in exps])


@app.route('/api/groups/<group_id>/expenses', methods=['POST'])
def create_expense(group_id):
    Group.query.get_or_404(group_id)
    data = request.get_json()
    required = ('description', 'amount', 'paid_by')
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'{f} is required'}), 400

    exp = Expense(
        group_id=group_id,
        description=data['description'],
        amount=Decimal(str(data['amount'])),
        currency=data.get('currency', 'INR'),
        paid_by=data['paid_by'],
        split_type=data.get('split_type', 'equal'),
        split_data=json.dumps(data.get('split_data', {})),
        category=data.get('category', 'general'),
        date=datetime.fromisoformat(data['date']) if data.get('date') else datetime.now(timezone.utc)
    )
    db.session.add(exp)
    db.session.commit()
    return jsonify(exp.to_dict()), 201


@app.route('/api/expenses/<expense_id>', methods=['GET'])
def get_expense(expense_id):
    exp = Expense.query.get_or_404(expense_id)
    return jsonify(exp.to_dict())


@app.route('/api/expenses/<expense_id>', methods=['PUT'])
def update_expense(expense_id):
    exp = Expense.query.get_or_404(expense_id)
    data = request.get_json()
    for field in ('description', 'amount', 'currency', 'paid_by', 'split_type', 'category', 'date'):
        if field in data:
            val = data[field]
            if field == 'amount':
                val = Decimal(str(val))
            elif field == 'date':
                val = datetime.fromisoformat(val)
            setattr(exp, field, val)
    if 'split_data' in data:
        exp.split_data = json.dumps(data['split_data'])
    db.session.commit()
    return jsonify(exp.to_dict())


@app.route('/api/expenses/<expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    exp = Expense.query.get_or_404(expense_id)
    exp.is_deleted = True
    db.session.commit()
    return jsonify({'message': 'Expense deleted'})


# ─── Routes: Balances & Debt Reconciliation ────────────────────────────────────

@app.route('/api/groups/<group_id>/balances', methods=['GET'])
def group_balances(group_id):
    g = Group.query.get_or_404(group_id)
    balances = compute_balances(group_id)
    members  = {m.id: m.name for m in g.members}
    result   = [
        {'member_id': mid, 'member_name': members.get(mid, 'Unknown'),
         'balance': bal, 'status': 'owed' if bal > 0 else ('owes' if bal < 0 else 'settled')}
        for mid, bal in balances.items()
    ]
    return jsonify(result)


@app.route('/api/groups/<group_id>/settlements/suggestions', methods=['GET'])
def settlement_suggestions(group_id):
    g = Group.query.get_or_404(group_id)
    balances = compute_balances(group_id)
    txns     = minimize_transactions(balances)
    members  = {m.id: m for m in g.members}
    enriched = []
    for t in txns:
        fm = members.get(t['from'])
        tm = members.get(t['to'])
        enriched.append({
            'from_id':   t['from'],
            'from_name': fm.name if fm else 'Unknown',
            'to_id':     t['to'],
            'to_name':   tm.name if tm else 'Unknown',
            'amount':    t['amount'],
            'upi_id':    tm.upi_id if tm else None
        })
    return jsonify(enriched)


# ─── Routes: Settlements ───────────────────────────────────────────────────────

@app.route('/api/groups/<group_id>/settlements', methods=['GET'])
def list_settlements(group_id):
    settlements = Settlement.query.filter_by(group_id=group_id).order_by(Settlement.created_at.desc()).all()
    return jsonify([s.to_dict() for s in settlements])


@app.route('/api/groups/<group_id>/settlements', methods=['POST'])
def create_settlement(group_id):
    data = request.get_json()
    s = Settlement(
        group_id=group_id, from_id=data['from_id'],
        to_id=data['to_id'], amount=Decimal(str(data['amount'])),
        upi_ref=data.get('upi_ref')
    )
    db.session.add(s)
    db.session.commit()
    return jsonify(s.to_dict()), 201


@app.route('/api/settlements/<settlement_id>/complete', methods=['POST'])
def complete_settlement(settlement_id):
    s = Settlement.query.get_or_404(settlement_id)
    data = request.get_json() or {}
    s.status     = 'completed'
    s.upi_ref    = data.get('upi_ref', s.upi_ref)
    s.settled_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(s.to_dict())


# ─── Routes: UPI QR ────────────────────────────────────────────────────────────

@app.route('/api/upi/qr', methods=['POST'])
def get_upi_qr():
    data = request.get_json()
    required = ('upi_id', 'name', 'amount')
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'{f} is required'}), 400
    try:
        qr_b64, upi_url = generate_upi_qr(
            data['upi_id'], data['name'],
            float(data['amount']), data.get('note', 'BillSplitter Payment')
        )
        return jsonify({'qr_image': qr_b64, 'upi_url': upi_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Routes: Analytics ─────────────────────────────────────────────────────────

@app.route('/api/groups/<group_id>/analytics', methods=['GET'])
def group_analytics(group_id):
    g    = Group.query.get_or_404(group_id)
    exps = Expense.query.filter_by(group_id=group_id, is_deleted=False).all()
    total   = sum(float(e.amount) for e in exps)
    by_cat  = defaultdict(float)
    by_mem  = defaultdict(float)
    for e in exps:
        by_cat[e.category]  += float(e.amount)
        by_mem[e.paid_by]   += float(e.amount)
    members = {m.id: m.name for m in g.members}
    return jsonify({
        'total_expenses':    total,
        'expense_count':     len(exps),
        'by_category':       dict(by_cat),
        'by_member':         {members.get(k, k): v for k, v in by_mem.items()},
        'member_count':      g.members.count()
    })


@app.route('/', methods=['GET'])
def index():
    """Root route — confirms server is running and lists available endpoints."""
    return jsonify({
        'app':     'BillSplitter API',
        'version': '1.0.0',
        'status':  'running',
        'docs':    'Use /api/health to verify, then connect your frontend.',
        'endpoints': {
            'health':      'GET  /api/health',
            'members':     'GET  /api/members',
            'groups':      'GET  /api/groups',
            'expenses':    'GET  /api/groups/<id>/expenses',
            'balances':    'GET  /api/groups/<id>/balances',
            'settlements': 'GET  /api/groups/<id>/settlements/suggestions',
            'upi_qr':      'POST /api/upi/qr',
            'analytics':   'GET  /api/groups/<id>/analytics',
        }
    })


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '1.0.0'})


# ─── Init ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port  = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    print(f"\n✅ BillSplitter API running on http://localhost:{port}")
    print(f"   Test it: http://localhost:{port}/api/health\n")
    app.run(host='0.0.0.0', port=port, debug=debug)


# ─── Auto-create tables on first import (for Gunicorn workers) ────────────────
with app.app_context():
    db.create_all()
