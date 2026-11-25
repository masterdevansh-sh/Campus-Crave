# Campus Crave — restored full-feature version

This build continues the earlier database-connected Campus Crave project. It keeps the original SQLite menu database and all its menu records, outlets, student/worker sign-in, cart, order flow, QR receipts and outlet-specific worker dashboard.

## What is preserved
- Original `campus_food.db` with **10 outlets and 428 menu items**.
- Student registration and login.
- Separate worker accounts assigned to each outlet.
- Outlet browsing and searchable/category-filtered menus.
- Single-outlet cart, checkout and order history.
- QR receipt generation and download.
- Worker order progression: Placed → Accepted → Preparing → Ready → Collected.
- Outlet-specific worker access and server-side order checks.

## Added/fixed
- Scheduled pickup time.
- Orders are marked Scheduled when pickup is more than 20 minutes away.
- Scheduled orders enter the worker queue when the pickup window is within 20 minutes (when that outlet dashboard is refreshed).
- Worker camera QR scanning with manual verification fallback.
- QR image is passed to Streamlit as PNG bytes to avoid the earlier `PilImage` TypeError.
- Database migration adds the pickup time column without replacing the menu tables.

## Windows PowerShell setup
Open this extracted folder in VS Code, then run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

If activation is blocked in PowerShell, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Do **not** run a seed script over the existing database. The menu database is already included.

## Worker demo sign-in
The app creates one demo worker for each outlet at startup.
Password for local demo worker accounts: `CampusDemo123!`
Worker emails follow this pattern: `worker.<outlet-name>@campuscrave.demo` (apostrophes removed; spaces become dots). The exact email for each outlet is shown on the login screen.

Change demo passwords and configure proper worker accounts before real deployment.

## Notes
- Menus from online reference sources remain clearly labelled and ordering stays disabled where campus pricing was not verified.
- This is a local educational prototype. Scheduled order activation occurs when the worker dashboard loads/refreshes; actual timed push notifications require a continuously running background service.
- Camera access in a deployed browser generally requires HTTPS. On local development, test camera permissions in your browser.
- No payment gateway is connected.
