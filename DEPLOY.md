# 🚀 BillSplitter — Deployment Guide
### Get a fully functional live link for your resume in ~15 minutes

---

## Architecture

```
Frontend (HTML/JS)          Backend (Flask/Python)        Database
─────────────────          ──────────────────────        ────────
  Vercel (free)    ──────▶   Railway (free trial)  ────▶  MySQL on Railway
  your-app.vercel.app        your-app.railway.app          auto-provisioned
```

---

## PART 1 — Deploy Backend on Railway (Flask + MySQL)

### Step 1: Push backend to GitHub

```bash
cd billsplitter-backend

git init
git add .
git commit -m "feat: BillSplitter Flask API"

# Create a new repo on github.com called "billsplitter-backend"
# then run:
git remote add origin https://github.com/YOUR_USERNAME/billsplitter-backend.git
git branch -M main
git push -u origin main
```

---

### Step 2: Create Railway account

1. Go to **https://railway.app** → Sign up with GitHub (free, no credit card for trial)
2. Click **"New Project"**

---

### Step 3: Add MySQL database

1. Inside your project click **"+ Add a service"** → **"Database"** → **"MySQL"**
2. Railway provisions a MySQL instance instantly
3. Click on the MySQL service → **"Variables"** tab
4. Copy the value of **`MYSQL_URL`** — you'll need it shortly

---

### Step 4: Deploy the Flask app

1. Click **"+ Add a service"** → **"GitHub Repo"**
2. Select **`billsplitter-backend`**
3. Railway auto-detects Python and runs `gunicorn` via `Procfile` ✓

---

### Step 5: Set environment variables

In the Flask service → **"Variables"** tab, add:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Paste the `MYSQL_URL` from Step 3 |
| `SECRET_KEY` | Any long random string e.g. `x9k2m...` |
| `CORS_ORIGINS` | `*` (or your Vercel URL later) |
| `FLASK_ENV` | `production` |

Click **"Deploy"** → wait ~90 seconds.

---

### Step 6: Get your backend URL

1. Flask service → **"Settings"** tab → **"Networking"** → **"Generate Domain"**
2. You'll get a URL like: `https://billsplitter-backend-production.up.railway.app`
3. **Test it:** open `https://YOUR-URL.up.railway.app/api/health` in your browser
   - You should see: `{"status": "ok", "version": "1.0.0"}`

✅ Backend is live!

---

## PART 2 — Deploy Frontend on Vercel (HTML/JS)

### Step 7: Update the API URL in index.html

Open `billsplitter-frontend/index.html` and find this line:

```html
window.BS_API_BASE = window.location.hostname === 'localhost'
  ? 'http://localhost:5000/api'
  : 'https://YOUR-APP.up.railway.app/api';  // ← replace after Railway deploy
```

Change `YOUR-APP` to your actual Railway subdomain:

```html
window.BS_API_BASE = window.location.hostname === 'localhost'
  ? 'http://localhost:5000/api'
  : 'https://billsplitter-backend-production.up.railway.app/api';
```

---

### Step 8: Push frontend to GitHub

```bash
cd billsplitter-frontend

git init
git add .
git commit -m "feat: BillSplitter frontend"

# Create a new repo on github.com called "billsplitter-frontend"
git remote add origin https://github.com/YOUR_USERNAME/billsplitter-frontend.git
git branch -M main
git push -u origin main
```

---

### Step 9: Deploy to Vercel

1. Go to **https://vercel.com** → Sign up with GitHub (completely free, no credit card)
2. Click **"Add New Project"** → import **`billsplitter-frontend`**
3. Settings:
   - **Framework Preset:** Other
   - **Build Command:** *(leave blank)*
   - **Output Directory:** `.`
4. Click **"Deploy"** → done in ~10 seconds

You'll get a URL like: `https://billsplitter-frontend.vercel.app`

✅ Frontend is live!

---

### Step 10: Update CORS on Railway (optional but recommended)

In Railway → Flask service → Variables:

```
CORS_ORIGINS = https://billsplitter-frontend.vercel.app
```

Redeploy the backend (Railway auto-redeploys on variable changes).

---

## PART 3 — Test your live app

Open `https://billsplitter-frontend.vercel.app` in your browser:

1. Click **"Try demo"** — works instantly, no backend needed
2. Click **"Register"** → create a real account → data saves to Railway MySQL
3. Create a group, add expenses, view balances, generate UPI QR

---

## PART 4 — Resume Link

Add this to your resume / portfolio:

```
BillSplitter  |  Live: https://billsplitter-frontend.vercel.app
              |  Code: https://github.com/YOUR_USERNAME/billsplitter-backend
              |        https://github.com/YOUR_USERNAME/billsplitter-frontend

Tech: Python · Flask · MySQL · REST API · UPI integration · HTML/CSS/JS
```

Or for a single link, combine both repos into a monorepo:

```
https://github.com/YOUR_USERNAME/billsplitter
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `/api/health` returns 502 | Check Railway logs — likely a missing `DATABASE_URL` |
| CORS error in browser | Set `CORS_ORIGINS=*` in Railway variables |
| SQLite instead of MySQL | Ensure `DATABASE_URL` is set in Railway variables |
| Vercel shows blank page | Check browser console — usually a wrong `BS_API_BASE` URL |
| UPI QR not showing | Normal on desktop — UPI deep-links only open apps on Android |
| Railway app sleeps | Free tier sleeps after inactivity — first load takes ~5s to wake |

---

## Optional: Custom domain (free via Freenom or Cloudflare)

1. Get a free domain at https://www.cloudflare.com/products/registrar/
2. In Vercel → your project → **"Domains"** → add your domain
3. Add Vercel's CNAME to your DNS provider
4. Done — your app is now at `https://billsplitter.yourdomain.com`

---

## Cost summary

| Service | Cost |
|---|---|
| Vercel (frontend) | **Free forever** |
| Railway (backend + MySQL) | **Free** ($5 trial, then ~$0.50–$2/mo for light use) |
| Custom domain | Free (Cloudflare) or ~$1/yr |

Total for a resume project: **$0 to keep it live for months.**

---

*Deploy time: ~15 minutes · Live link ready for recruiters ✓*
