# app/blueprints/payments.py
from flask import Blueprint, request, current_app, jsonify
from models_mongo import make_payment, doc_to_json
from bson import ObjectId

payments_bp = Blueprint('payments', __name__)

@payments_bp.route('', methods=['POST'])
def create_payment():
    payload = request.get_json()
    booking_id = payload.get('booking_id')
    provider = payload.get('provider')
    amount = payload.get('amount', 0.0)
    if not booking_id or not provider:
        return jsonify({'error': 'booking_id and provider required'}), 400
    try:
        booking_oid = ObjectId(booking_id)
    except Exception:
        return jsonify({'error': 'invalid booking_id'}), 400
    pay_doc = make_payment(booking_oid, provider, amount, status='INITIATED', provider_reference=payload.get('provider_reference'))
    current_app.mdb.payments.insert_one(pay_doc)
    # In reality: call provider SDK (Stripe/PayPal), await webhook, then update payment.status and booking.status
    return jsonify(doc_to_json(pay_doc)), 201

# example webhook endpoint for provider callbacks
@payments_bp.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    # provider-specific verification & update logic goes here
    # for example: update payment status and booking.status on success
    return jsonify({'ok': True}), 200