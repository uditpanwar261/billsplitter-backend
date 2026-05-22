"""
routes/__init__.py
Registers all Blueprint routes onto the Flask app.
"""
from .members     import members_bp
from .groups      import groups_bp
from .expenses    import expenses_bp
from .balances    import balances_bp
from .settlements import settlements_bp
from .upi         import upi_bp


def register_routes(app):
    """Call this once in app.py after creating the Flask app."""
    prefix = "/api"
    app.register_blueprint(members_bp,     url_prefix=prefix)
    app.register_blueprint(groups_bp,      url_prefix=prefix)
    app.register_blueprint(expenses_bp,    url_prefix=prefix)
    app.register_blueprint(balances_bp,    url_prefix=prefix)
    app.register_blueprint(settlements_bp, url_prefix=prefix)
    app.register_blueprint(upi_bp,         url_prefix=prefix)
