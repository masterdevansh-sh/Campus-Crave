"""Campus Crave: a small Streamlit app connected to the SQLite menu database."""

import io
import json

import qrcode
import streamlit as st
from datetime import datetime, timedelta


from auth import (
    DEMO_WORKER_PASSWORD,
    create_demo_workers,
    login_user,
    make_worker_email,
    register_student,
)
from database import create_tables, get_menu_categories, get_menu_items, get_outlets
from orders import (
    advance_order,
    calculate_total,
    outlet_orders,
    place_order,
    student_orders,
    verify_collection,
)


st.set_page_config(
    page_title="Campus Crave",
    page_icon="🍔",
    layout="wide",
    initial_sidebar_state="expanded",
)

# A little CSS makes the default Streamlit layout feel more like a food-ordering site.
st.markdown(
    """
    <style>
        .stApp { background: #f5f7f4; }
        .block-container { max-width: 1180px; padding-top: 1.8rem; padding-bottom: 3rem; }
        h1, h2, h3 { color: #20372c; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff;
            border: 1px solid #e4eae4;
            border-radius: 16px;
        }
        .stButton > button {
            border-radius: 10px;
            font-weight: 600;
            min-height: 2.5rem;
        }
        .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
            border-radius: 10px;
        }
        [data-testid="stSidebar"] { background: #edf2ec; }
        .hero {
            padding: 1.5rem 1.7rem;
            border-radius: 18px;
            background: linear-gradient(115deg, #e0eee3, #f5f2e8);
            margin-bottom: 1.2rem;
        }
        .hero small { color: #537260; font-weight: 700; letter-spacing: .08em; }
        .hero h1 { margin: .35rem 0; font-size: 2.1rem; }
        .hero p { color: #58675d; margin: 0; }
        .muted { color: #69766d; font-size: .9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Connect to the packaged menu database and prepare account/order tables.
create_tables()
create_demo_workers()
OUTLETS = get_outlets()
OUTLET_NAMES = [outlet["name"] for outlet in OUTLETS]
OUTLET_BY_NAME = {outlet["name"]: outlet for outlet in OUTLETS}

if "user" not in st.session_state:
    st.session_state.user = None
if "cart" not in st.session_state:
    st.session_state.cart = []
if "cart_outlet" not in st.session_state:
    st.session_state.cart_outlet = None
if "student_page" not in st.session_state:
    st.session_state.student_page = "Explore outlets"
if "menu_outlet_picker" not in st.session_state:
    st.session_state.menu_outlet_picker = "Snap Eats"


def make_qr_image(payload):
    qr = qrcode.QRCode(box_size=7, border=3)
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


def show_order_qr(order):
    payload = order["order_id"] + "|" + order["qr_token"]
    qr_image = make_qr_image(payload)
    image_bytes = io.BytesIO()
    qr_image.save(image_bytes, format="PNG")
    st.image(image_bytes.getvalue(), width=170)
    image_bytes.seek(0)
    st.download_button(
        "Download QR receipt",
        data=image_bytes.getvalue(),
        file_name=order["order_id"] + "_QR.png",
        mime="image/png",
        key="download_" + order["order_id"],
    )
    st.caption("Keep this QR receipt private and show it when collecting your order.")


def show_login_screen():
    st.markdown(
        """
        <div class="hero">
            <small>BENNETT UNIVERSITY · CAMPUS FOOD</small>
            <h1>Campus Crave 🍔</h1>
            <p>Your campus food, all in one place. Sign in to browse menus or manage outlet orders.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    login_tab, register_tab = st.tabs(["Sign in", "Create student account"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email address")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True, type="primary")

        if submitted:
            user = login_user(email, password)
            if user is None:
                st.error("Email or password is incorrect.")
            else:
                st.session_state.user = user
                st.rerun()

    with register_tab:
        st.caption("Student accounts can be created here. Outlet worker accounts are assigned separately.")
        with st.form("register_form"):
            name = st.text_input("Full name")
            email = st.text_input("Email address")
            password = st.text_input("Create password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create account", use_container_width=True, type="primary")

        if submitted:
            if password != confirm_password:
                st.error("The passwords do not match.")
            else:
                success, message = register_student(name, email, password)
                if success:
                    st.success(message)
                else:
                    st.error(message)

    with st.expander("Demo outlet-worker accounts"):
        st.write("For local testing only. Every demo worker password is the same:")
        st.code(DEMO_WORKER_PASSWORD)
        for outlet_name in OUTLET_NAMES:
            st.write(outlet_name + " — " + make_worker_email(outlet_name))


def open_outlet_menu(outlet_name):
    st.session_state.menu_outlet_picker = outlet_name
    st.session_state.student_page = "Menu"


def show_outlet_cards():
    st.markdown(
        """
        <div class="hero">
            <small>EXPLORE BENNETT</small>
            <h1>What are you craving today?</h1>
            <p>Choose an outlet, browse its database menu and add your favourites to the cart.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    search_text = st.text_input("Search outlets", placeholder="Search by outlet name or food type")
    matching_outlets = [
        outlet for outlet in OUTLETS
        if search_text.lower() in (outlet["name"] + " " + (outlet["tagline"] or "")).lower()
    ]

    st.caption(str(len(matching_outlets)) + " outlets")
    columns = st.columns(3)
    for index, outlet in enumerate(matching_outlets):
        with columns[index % 3]:
            with st.container(border=True):
                st.markdown("### " + outlet["emoji"] + "  " + outlet["name"])
                st.caption(outlet["category"] or "Campus outlet")
                st.write(outlet["tagline"] or "Browse the menu")
                item_count = len(get_menu_items(outlet["id"]))
                st.markdown("<p class='muted'>" + str(item_count) + " menu items</p>", unsafe_allow_html=True)
                if outlet["source_type"] == "online_reference":
                    st.caption("Online reference · campus prices need confirmation")
                else:
                    st.caption("Campus menu")
                st.button(
                    "Browse menu  →",
                    key="outlet_" + outlet["id"],
                    use_container_width=True,
                    on_click=open_outlet_menu,
                    args=(outlet["name"],),
                )

    if not matching_outlets:
        st.info("No outlet matches that search.")


def add_item_to_cart(outlet_name, item):
    if st.session_state.cart_outlet not in (None, outlet_name):
        st.error("Your cart already contains items from another outlet. Place that order or clear your cart first.")
        return

    st.session_state.cart_outlet = outlet_name
    existing_item = None
    for cart_item in st.session_state.cart:
        if cart_item["id"] == item["id"]:
            existing_item = cart_item
            break

    if existing_item:
        existing_item["quantity"] += 1
    else:
        st.session_state.cart.append({
            "id": item["id"],
            "name": item["name"],
            "price": item["price"],
            "quantity": 1,
        })

    st.toast(item["name"] + " added to cart")


def show_menu_page():
    st.title("Browse menus")
    selected_outlet_name = st.selectbox(
        "Choose an outlet",
        OUTLET_NAMES,
        key="menu_outlet_picker",
    )
    outlet = OUTLET_BY_NAME[selected_outlet_name]
    st.subheader(outlet["emoji"] + "  " + outlet["name"])
    st.write(outlet["tagline"] or "Explore the menu below.")

    if outlet["source_type"] == "online_reference":
        st.warning(
            "This is an online reference menu, not a verified Bennett campus price list. "
            "You can browse it, but adding items to the cart is disabled until the campus prices are confirmed."
        )
        if outlet["source_url"]:
            st.markdown("[View online reference menu](" + outlet["source_url"] + ")")
    else:
        st.caption("Prices are transcribed from the campus menu supplied for this project. Please confirm any unclear items at the counter.")

    if outlet["id"] == "snap-eats":
        st.info("Snap Eats note: GST applies according to the menu board. The GST rate is not entered here, and MRP/unclear-price items need confirmation at the outlet.")

    st.divider()
    search_text = st.text_input(
        "Search this menu",
        placeholder="For example: burger, coffee, paneer or dosa",
        key="menu_search_" + outlet["id"],
    )
    categories = get_menu_categories(outlet["id"])
    category_options = ["All categories"] + categories
    category = st.selectbox(
        "Filter by category",
        category_options,
        key="menu_category_" + outlet["id"],
    )
    items = get_menu_items(outlet["id"], category, search_text)

    if not items:
        st.info("No matching menu items were found.")
        return

    st.caption(str(len(items)) + " items shown")
    can_order = outlet["source_type"] != "online_reference"
    columns = st.columns(2)
    for index, item in enumerate(items):
        with columns[index % 2]:
            with st.container(border=True):
                st.markdown("**" + item["name"] + "**")
                st.caption(item["category"])
                if item["price"] is None:
                    st.write("Price to confirm")
                    st.button("Unavailable", key="unavailable_" + str(item["id"]), disabled=True, use_container_width=True)
                elif not can_order:
                    st.write("Reference price: ₹" + str(item["price"]))
                    st.button("Ordering disabled", key="ref_" + str(item["id"]), disabled=True, use_container_width=True)
                else:
                    st.write("**₹" + str(item["price"]) + "**")
                    if st.button("Add to cart  +", key="add_" + str(item["id"]), use_container_width=True):
                        add_item_to_cart(outlet["name"], item)


def show_cart_page(user):
    st.title("Your cart")
    if not st.session_state.cart:
        st.info("Your cart is empty. Browse an outlet menu to add food.")
        return

    st.caption("Outlet: " + str(st.session_state.cart_outlet))
    for index, item in enumerate(st.session_state.cart):
        left, middle, right = st.columns([5, 2, 1.5])
        left.write(item["name"] + " × " + str(item["quantity"]))
        middle.write("₹" + str(item["price"] * item["quantity"]))
        if right.button("Remove", key="remove_" + str(index)):
            st.session_state.cart.pop(index)
            if not st.session_state.cart:
                st.session_state.cart_outlet = None
            st.rerun()

    total = calculate_total(st.session_state.cart)
    st.divider()
    st.subheader("Listed-price subtotal: ₹" + str(total))
    st.caption("GST or other charges are not calculated here. Payment is handled directly at the outlet in this prototype.")

    st.subheader("Choose your pickup time")
    pickup_date = st.date_input("Pickup date", value=datetime.now().date())
    pickup_time = st.time_input(
        "Pickup time",
        value=(datetime.now() + timedelta(minutes=20)).time().replace(second=0, microsecond=0),
    )
    pickup_at = datetime.combine(pickup_date, pickup_time).isoformat(timespec="minutes")

    if st.button("Place order", type="primary", use_container_width=True):
        try:
            result = place_order(
                user["id"], st.session_state.cart_outlet,
                st.session_state.cart, pickup_at
            )
        except ValueError as error:
            st.error(str(error))
            return
        st.session_state.cart = []
        st.session_state.cart_outlet = None
        st.success("Order saved! Open My orders to view its receipt.")
        st.write("Order ID: **" + result["order_id"] + "**")
        st.write("Pickup time: **" + result["pickup_at"] + "**")
        if result["status"] == "Scheduled":
            st.info("Your order is scheduled. It will appear in the worker queue 20 minutes before pickup.")
        show_order_qr(result)


def show_student_orders(user):
    st.title("My orders")
    orders = student_orders(user["id"])
    if not orders:
        st.info("You have not placed any orders yet.")
        return

    for order in orders:
        with st.container(border=True):
            st.subheader(order["order_id"] + " · " + order["outlet"])
            st.write("**Status:** " + order["status"])
            st.write("**Listed-price subtotal:** ₹" + str(order["total"]))
            st.caption("Placed: " + str(order["created_at"]))
            st.caption("Pickup: " + str(order["pickup_at"] or "Not specified"))
            for item in json.loads(order["items_json"]):
                st.write("• " + item["name"] + " × " + str(item["quantity"]))
            if order["status"] != "Collected":
                show_order_qr(order)
            else:
                st.success("This order has been collected.")


def show_worker_dashboard(user):
    outlet = user["outlet"]
    st.markdown(
        "<div class='hero'><small>OUTLET STAFF</small><h1>" + outlet + " orders</h1>"
        "<p>Review and update orders assigned to your outlet.</p></div>",
        unsafe_allow_html=True,
    )

    orders = outlet_orders(outlet)
    if not orders:
        st.info("No orders for this outlet yet.")
    else:
        for order in orders:
            with st.container(border=True):
                st.subheader(order["order_id"])
                st.write("**Status:** " + order["status"])
                st.write("**Listed-price subtotal:** ₹" + str(order["total"]))
                st.caption("Placed: " + str(order["created_at"]))
                st.caption("Pickup: " + str(order["pickup_at"] or "Not specified"))
                for item in json.loads(order["items_json"]):
                    st.write("• " + item["name"] + " × " + str(item["quantity"]))

                if order["status"] in ("Placed", "Accepted", "Preparing"):
                    next_label = {
                        "Placed": "Accept order",
                        "Accepted": "Start preparing",
                        "Preparing": "Mark as ready",
                    }[order["status"]]
                    if st.button(next_label, key="advance_" + order["order_id"], type="primary"):
                        changed = advance_order(order["order_id"], outlet, order["status"])
                        if changed:
                            st.success("Order updated.")
                        else:
                            st.error("The order could not be updated. Refresh and try again.")
                        st.rerun()

                elif order["status"] == "Ready":
                    st.write("Scan the student's collection QR.")
                    photo = st.camera_input("Scan QR code", key="camera_" + order["order_id"])
                    qr_text = ""
                    if photo is not None:
                        try:
                            import cv2
                            import numpy as np
                            image_array = np.frombuffer(photo.getvalue(), dtype=np.uint8)
                            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                            qr_text, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
                        except Exception:
                            st.error("QR scanning could not start. Use the manual option below.")

                    with st.expander("Manual verification fallback"):
                        manual_text = st.text_input(
                            "QR content (ORDER_ID|TOKEN)",
                            key="manual_" + order["order_id"],
                        )
                        if manual_text:
                            qr_text = manual_text

                    if qr_text and st.button("Verify and mark collected", key="verify_" + order["order_id"]):
                        success, message = verify_collection(qr_text, outlet)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    elif photo is not None and not qr_text:
                        st.warning("QR not detected. Try again or use manual verification.")


def show_account_page(user):
    st.title("Account")
    st.write("**Name:** " + user["name"])
    st.write("**Email:** " + user["email"])
    st.write("**Account type:** " + user["role"].title())
    if user["role"] == "worker":
        st.write("**Assigned outlet:** " + user["outlet"])


def main():
    user = st.session_state.user
    if user is None:
        show_login_screen()
        return

    st.sidebar.title("Campus Crave 🍔")
    st.sidebar.caption("Bennett campus food ordering")
    st.sidebar.write("Hi, " + user["name"])

    if user["role"] == "student":
        page = st.sidebar.radio(
            "Navigation",
            ["Explore outlets", "Menu", "My cart", "My orders", "Account"],
            key="student_page",
        )
        if page == "Explore outlets":
            show_outlet_cards()
        elif page == "Menu":
            show_menu_page()
        elif page == "My cart":
            show_cart_page(user)
        elif page == "My orders":
            show_student_orders(user)
        else:
            show_account_page(user)
    else:
        page = st.sidebar.radio("Navigation", ["Outlet orders", "Account"])
        if page == "Outlet orders":
            show_worker_dashboard(user)
        else:
            show_account_page(user)

    st.sidebar.divider()
    st.sidebar.caption("Cart items: " + str(sum(item["quantity"] for item in st.session_state.cart)))
    if st.sidebar.button("Log out", use_container_width=True):
        st.session_state.user = None
        st.session_state.cart = []
        st.session_state.cart_outlet = None
        st.rerun()


main()
