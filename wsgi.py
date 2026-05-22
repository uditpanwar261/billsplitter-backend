"""
wsgi.py — Production entrypoint for Gunicorn.

Usage:
    gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2
"""
from app import app, db

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run()
