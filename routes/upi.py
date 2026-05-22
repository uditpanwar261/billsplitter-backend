"""routes/upi.py — UPI deep-link QR code generation."""
import io
import base64

import qrcode
from flask import Blueprint, request, jsonify

upi_bp = Blueprint("upi", __name__)


def _build_upi_url(upi_id: str, name: str, amount: float, note: str) -> str:
    """Build a standard UPI deep-link URI."""
    return (
        f"upi://pay"
        f"?pa={upi_id}"
        f"&pn={name.replace(' ', '%20')}"
        f"&am={amount:.2f}"
        f"&cu=INR"
        f"&tn={note.replace(' ', '%20')}"
    )


def _generate_qr_base64(data: str) -> str:
    """Render a QR code and return it as a base64-encoded PNG string."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


@upi_bp.route("/upi/qr", methods=["POST"])
def generate_upi_qr():
    data = request.get_json() or {}

    for field in ("upi_id", "name", "amount"):
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    try:
        amount  = float(data["amount"])
        note    = data.get("note", "BillSplitter Payment")
        upi_url = _build_upi_url(data["upi_id"], data["name"], amount, note)
        qr_b64  = _generate_qr_base64(upi_url)

        return jsonify({
            "qr_image": qr_b64,       # base64 PNG — embed as <img src="data:image/png;base64,...">
            "upi_url":  upi_url,       # deep-link — open on Android to launch UPI app
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@upi_bp.route("/upi/validate", methods=["POST"])
def validate_upi():
    """
    Lightweight UPI-ID format validator.
    Real validation requires hitting the NPCI network — this checks the format only.
    """
    data   = request.get_json() or {}
    upi_id = data.get("upi_id", "").strip()

    if not upi_id:
        return jsonify({"error": "upi_id is required"}), 400

    import re
    pattern = r"^[\w.\-]+@[\w]+$"
    valid   = bool(re.match(pattern, upi_id))

    return jsonify({
        "upi_id": upi_id,
        "valid":  valid,
        "message": "Valid UPI ID format" if valid else "Invalid UPI ID format (expected: name@provider)",
    })
