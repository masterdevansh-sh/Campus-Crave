"""SQLite database functions for Campus Crave.

The outlet and menu tables already contain the campus menu data. This file
connects the Streamlit screens to those tables and stores users and orders.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent / "campus_food.db"


@contextmanager
def connect_db():
    connection = sqlite3.connect(DB_FILE, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_tables():
    """Create only the account and order tables; keep the existing menu data."""
    with connect_db() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                outlet TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                student_id INTEGER NOT NULL,
                outlet TEXT NOT NULL,
                items_json TEXT NOT NULL,
                total INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Placed',
                qr_token TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                collected_at TEXT,
                pickup_at TEXT,
                FOREIGN KEY (student_id) REFERENCES users(id)
            )"""
        )
        # Add the pickup-time column to older databases without deleting menu data.
        columns = [row["name"] for row in connection.execute("PRAGMA table_info(orders)")]
        if "pickup_at" not in columns:
            connection.execute("ALTER TABLE orders ADD COLUMN pickup_at TEXT")


def get_outlets():
    """Return outlets from the database in a student-friendly order."""
    order = [
        "infinity-kitchens", "quench", "snap-eats", "hoc", "maggi-hotspot",
        "south-indian-pending", "dominos", "subway", "greenox", "monginis",
    ]
    with connect_db() as connection:
        rows = connection.execute(
            f"""SELECT id, name, tagline, category, emoji, accent, location,
                       source_type, source_label, source_url
                FROM outlets
                ORDER BY CASE id {''.join(f' WHEN ? THEN {i}' for i, _ in enumerate(order))} ELSE 99 END""",
            tuple(order),
        ).fetchall()
    return [dict(row) for row in rows]


def get_menu_categories(outlet_id):
    with connect_db() as connection:
        rows = connection.execute(
            """SELECT DISTINCT category FROM menu_items
               WHERE outlet_id = ? ORDER BY category""",
            (outlet_id,),
        ).fetchall()
    return [row["category"] for row in rows]


def get_menu_items(outlet_id, category=None, search_text=""):
    query = "SELECT id, category, name, price FROM menu_items WHERE outlet_id = ?"
    values = [outlet_id]

    if category and category != "All categories":
        query += " AND category = ?"
        values.append(category)

    if search_text.strip():
        query += " AND LOWER(name) LIKE ?"
        values.append("%" + search_text.strip().lower() + "%")

    query += " ORDER BY category, name"

    with connect_db() as connection:
        rows = connection.execute(query, values).fetchall()
    return [dict(row) for row in rows]


def add_user(name, email, password_hash, role, outlet=None):
    try:
        with connect_db() as connection:
            connection.execute(
                """INSERT INTO users (name, email, password_hash, role, outlet)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, email.lower().strip(), password_hash, role, outlet),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def get_user_by_email(email):
    with connect_db() as connection:
        return connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()


def add_order(order_id, student_id, outlet, items_json, total, qr_token, pickup_at, status):
    with connect_db() as connection:
        connection.execute(
            """INSERT INTO orders
               (order_id, student_id, outlet, items_json, total, qr_token, pickup_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (order_id, student_id, outlet, items_json, total, qr_token, pickup_at, status),
        )


def get_student_orders(student_id):
    with connect_db() as connection:
        rows = connection.execute(
            """SELECT order_id, outlet, items_json, total, status, qr_token,
                      created_at, updated_at, collected_at, pickup_at
               FROM orders WHERE student_id = ? ORDER BY created_at DESC""",
            (student_id,),
        ).fetchall()
    return rows


def get_orders_for_outlet(outlet):
    # The outlet filter is enforced in SQL, not just by hiding interface elements.
    with connect_db() as connection:
        rows = connection.execute(
            """SELECT order_id, outlet, items_json, total, status, created_at, updated_at, pickup_at
               FROM orders WHERE outlet = ? AND status != 'Collected'
               ORDER BY COALESCE(pickup_at, created_at) ASC""",
            (outlet,),
        ).fetchall()
    return rows


def get_order_by_id(order_id):
    with connect_db() as connection:
        return connection.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()


def change_order_status(order_id, outlet, old_status, new_status, collected=False):
    """Update an order only when it belongs to the worker's assigned outlet."""
    with connect_db() as connection:
        if collected:
            cursor = connection.execute(
                """UPDATE orders
                   SET status = ?, updated_at = CURRENT_TIMESTAMP,
                       collected_at = CURRENT_TIMESTAMP
                   WHERE order_id = ? AND outlet = ? AND status = ?""",
                (new_status, order_id, outlet, old_status),
            )
        else:
            cursor = connection.execute(
                """UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE order_id = ? AND outlet = ? AND status = ?""",
                (new_status, order_id, outlet, old_status),
            )
    return cursor.rowcount == 1
