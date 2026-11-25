"""Order creation, pickup scheduling, status changes and QR verification."""

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta

from database import (
    add_order, change_order_status, get_order_by_id,
    get_orders_for_outlet, get_student_orders,
)

STATUS_STEPS = {
    "Placed": "Accepted",
    "Accepted": "Preparing",
    "Preparing": "Ready",
}


def calculate_total(cart):
    total = 0
    for item in cart:
        total += item["price"] * item["quantity"]
    return total


def place_order(student_id, outlet, cart, pickup_at=None):
    if not cart:
        raise ValueError("Your cart is empty.")

    if pickup_at is None:
        pickup = datetime.now() + timedelta(minutes=10)
    else:
        pickup = datetime.fromisoformat(pickup_at)

    if pickup < datetime.now() + timedelta(minutes=10):
        raise ValueError("Choose a pickup time at least 10 minutes from now.")

    order_id = "CC" + uuid.uuid4().hex[:8].upper()
    qr_token = secrets.token_urlsafe(12)
    items_json = json.dumps(cart)
    total = calculate_total(cart)

    # Orders further away stay Scheduled until they enter the 20-minute window.
    status = "Placed" if pickup <= datetime.now() + timedelta(minutes=20) else "Scheduled"
    add_order(order_id, student_id, outlet, items_json, total, qr_token,
              pickup.isoformat(timespec="minutes"), status)
    return {
        "order_id": order_id,
        "qr_token": qr_token,
        "total": total,
        "pickup_at": pickup.isoformat(timespec="minutes"),
        "status": status,
    }


def student_orders(student_id):
    return get_student_orders(student_id)


def outlet_orders(outlet):
    # Activate scheduled orders when their pickup time is within 20 minutes.
    from database import connect_db
    with connect_db() as connection:
        connection.execute(
            """UPDATE orders SET status='Placed', updated_at=CURRENT_TIMESTAMP
               WHERE outlet=? AND status='Scheduled'
               AND datetime(pickup_at) <= datetime('now','localtime','+20 minutes')""",
            (outlet,),
        )
    return get_orders_for_outlet(outlet)


def advance_order(order_id, outlet, current_status):
    next_status = STATUS_STEPS.get(current_status)
    if next_status is None:
        return False
    return change_order_status(order_id, outlet, current_status, next_status)


def verify_collection(qr_text, worker_outlet):
    parts = qr_text.strip().split("|", 1)
    if len(parts) != 2:
        return False, "QR content is not recognised."

    order_id, entered_token = parts[0].strip(), parts[1].strip()
    order = get_order_by_id(order_id)

    if order is None:
        return False, "Order not found."
    if order["outlet"] != worker_outlet:
        return False, "This order belongs to a different outlet."
    if order["status"] != "Ready":
        return False, "Only orders marked Ready can be collected."

    saved_hash = hashlib.sha256(order["qr_token"].encode("utf-8")).hexdigest()
    entered_hash = hashlib.sha256(entered_token.encode("utf-8")).hexdigest()
    if not secrets.compare_digest(saved_hash, entered_hash):
        return False, "QR verification failed."

    changed = change_order_status(
        order_id, worker_outlet, "Ready", "Collected", collected=True
    )
    if not changed:
        return False, "The order status changed. Refresh and try again."
    return True, "Order verified and marked as Collected."
