# 💸 BillSplitter

> A production-ready shared expense management app with UPI payment integration, Splitwise-style debt reconciliation, and a mobile-first UI.

---

##  Live Backend url -> billsplitter-backend-production-7a67.up.railway.app

## Table of Contents
1. [Features](#features)
2. [Tech Stack](#tech-stack)
3. [Quick Start](#quick-start)
4. [API Reference](#api-reference)
5. [Debt Reconciliation Algorithm](#debt-reconciliation-algorithm)
6. [UPI Integration](#upi-integration)
7. [Database Schema](#database-schema)
8. [Deployment](#deployment)
9. [Git Workflow](#git-workflow)

---

## Features

| Feature | Description |
|---|---|
| 👥 Group & member management | Create groups, add/remove members |
| 💳 Expense CRUD | Equal / exact / percentage splits |
| 🧮 Debt reconciliation | Greedy minimise-transactions algorithm |
| 📲 UPI QR generation | Deep-link QR for instant in-app payment |
| 📊 Analytics | Spend by category, member, and day |
| ✅ Settlement tracking | Mark debts as paid, track UPI refs |

---

## Tech Stack

- **Backend**: Python 3.11 + Flask 3.x
- **Database**: MySQL 8.0 via SQLAlchemy ORM
- **Payments**: UPI deep-link (`upi://pay`) + QR via `qrcode`
- **DevOps**: Docker Compose, Gunicorn
- **Testing**: Postman collection (included)

---

## Quick Start

### Prerequisites
- Docker & Docker Compose  **or**  Python 3.11 + MySQL 8

### Option A — Docker (recommended)

```bash
git clone https://github.com/yourname/billsplitter.git
cd billsplitter
docker-compose up --build
```

API available at `http://localhost:5000/api`

### Option B — Local

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create DB
mysql -u root -p -e "CREATE DATABASE billsplitter;"

# Set env vars
export DATABASE_URL="mysql+pymysql://root:password@localhost/billsplitter"
export SECRET_KEY="your-secret-key"

python app.py
```

---

## API Reference

Base URL: `http://localhost:5000/api`

### Health
```
GET /health
```

---

### Members

| Method | Endpoint | Description |
|---|---|---|
| GET | `/members` | List all members |
| POST | `/members` | Create member |
| GET | `/members/:id` | Get member |
| PUT | `/members/:id` | Update member |
| DELETE | `/members/:id` | Delete member |

**Create member body:**
```json
{
  "name": "Alex Kumar",
  "email": "alex@example.com",
  "upi_id": "alex@upi"
}
```

---

### Groups

| Method | Endpoint | Description |
|---|---|---|
| GET | `/groups` | List all groups |
| POST | `/groups` | Create group |
| GET | `/groups/:id` | Get group with members |
| PUT | `/groups/:id` | Update group |
| DELETE | `/groups/:id` | Delete group |
| POST | `/groups/:id/members` | Add member to group |
| DELETE | `/groups/:id/members/:mid` | Remove member |

**Create group body:**
```json
{
  "name": "Goa Trip 2025",
  "description": "Beach vacation",
  "category": "trip",
  "member_ids": ["uuid1", "uuid2"]
}
```

---

### Expenses

| Method | Endpoint | Description |
|---|---|---|
| GET | `/groups/:id/expenses` | List group expenses |
| POST | `/groups/:id/expenses` | Create expense |
| GET | `/expenses/:id` | Get expense |
| PUT | `/expenses/:id` | Update expense |
| DELETE | `/expenses/:id` | Soft-delete expense |

**Create expense — equal split:**
```json
{
  "description": "Hotel deposit",
  "amount": 4800,
  "paid_by": "member-uuid",
  "split_type": "equal",
  "category": "accommodation",
  "split_data": {
    "participants": ["uuid1", "uuid2", "uuid3"]
  }
}
```

**Create expense — exact split:**
```json
{
  "description": "Custom meal",
  "amount": 1000,
  "paid_by": "member-uuid",
  "split_type": "exact",
  "split_data": {
    "amounts": { "uuid1": 400, "uuid2": 350, "uuid3": 250 }
  }
}
```

**Create expense — percentage split:**
```json
{
  "split_type": "percent",
  "split_data": {
    "percents": { "uuid1": 50, "uuid2": 30, "uuid3": 20 }
  }
}
```

---

### Balances & Reconciliation

```
GET  /groups/:id/balances              → per-member net balance
GET  /groups/:id/settlements/suggestions → minimised transaction list
GET  /groups/:id/analytics             → totals, by category, by member
```

**Balances response:**
```json
[
  { "member_id": "...", "member_name": "Alex", "balance": 3678.00, "status": "owed" },
  { "member_id": "...", "member_name": "Sarah", "balance": -2523.00, "status": "owes" }
]
```

**Settlement suggestions response:**
```json
[
  {
    "from_id": "...", "from_name": "Sarah",
    "to_id": "...",   "to_name": "Alex",
    "amount": 2353.00, "upi_id": "alex@upi"
  }
]
```

---

### Settlements

| Method | Endpoint | Description |
|---|---|---|
| GET | `/groups/:id/settlements` | List settlements |
| POST | `/groups/:id/settlements` | Record settlement |
| POST | `/settlements/:id/complete` | Mark as paid |

---

### UPI QR

```
POST /upi/qr
```
Body:
```json
{
  "upi_id": "alex@upi",
  "name": "Alex Kumar",
  "amount": 2353.00,
  "note": "BillSplitter Settlement"
}
```
Response:
```json
{
  "qr_image": "<base64-png>",
  "upi_url": "upi://pay?pa=alex@upi&pn=Alex+Kumar&am=2353.00&cu=INR&tn=BillSplitter+Settlement"
}
```

---

## Debt Reconciliation Algorithm

BillSplitter uses a **greedy creditor-debtor matching** algorithm (same approach as Splitwise) that minimises the number of transactions needed to settle a group.

```
1. Compute net balance for each member
   balance[member] = (total paid by member) - (total owed by member)

2. Separate into:
   creditors (balance > 0)  — they are owed money
   debtors   (balance < 0)  — they owe money

3. Sort both lists descending by absolute amount

4. Two-pointer greedy pass:
   settled = min(largest_credit, largest_debt)
   → Record transaction: debtor pays creditor `settled`
   → Reduce both balances by `settled`
   → Advance pointer for whichever side reaches 0

Result: at most (N-1) transactions for N members,
        typically far fewer (optimal in practice).
```

Example — 4 members, 5 expenses → reduced from 10 possible transfers to **2 transfers**.

---

## UPI Integration

UPI payments use the standard **deep-link URI scheme**:

```
upi://pay?pa=<vpa>&pn=<name>&am=<amount>&cu=INR&tn=<note>
```

- `pa` — payee VPA (Virtual Payment Address), e.g. `name@upi`
- `pn` — payee display name
- `am` — amount in INR
- `tn` — transaction note

On Android, this URI opens the user's default UPI app (GPay, PhonePe, Paytm, etc.).  
The API also generates a **QR code** encoding the same URI so users can scan with any UPI app.

---

## Database Schema

```
members        (id, name, email, upi_id, avatar_url, created_at)
groups         (id, name, description, category, created_by, created_at)
group_members  (group_id, member_id, joined_at)   ← many-to-many
expenses       (id, group_id, description, amount, currency,
                paid_by, split_type, split_data JSON,
                category, date, created_at, is_deleted)
settlements    (id, group_id, from_id, to_id, amount,
                status, upi_ref, settled_at, created_at)
```

---

## Deployment

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | sqlite:///dev.db | MySQL connection string |
| `SECRET_KEY` | dev-secret | Flask secret (change in prod!) |

### Production with Gunicorn

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

---

## Git Workflow

```bash
git init
git add .
git commit -m "feat: initial BillSplitter backend"

# Feature branches
git checkout -b feature/upi-qr
git checkout -b feature/analytics
git checkout -b fix/debt-rounding

# Merge via PR on GitHub
```

---

## Postman Testing

Import `BillSplitter.postman_collection.json` into Postman.

1. Create a member → copy `id` → set `{{member_id}}`
2. Create a group → copy `id` → set `{{group_id}}`
3. Add member to group
4. Create expenses
5. Check `/balances` and `/settlements/suggestions`
6. Generate UPI QR


---

*Built with Flask · MySQL · UPI · ❤️*
