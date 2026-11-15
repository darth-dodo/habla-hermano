"""Seed a demo account from the shell. The data lives in src/services/demo_seed.py.

Needs the TARGET environment's settings in the shell, because encrypted
fields (translations, display name) must use that environment's key:
    SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, SECRET_KEY, ENCRYPTION_SALT
    DEMO_PASSWORD   (only needed when the user does not exist yet)

Usage (on the Render shell the env is already set):
    make seed-demo EMAIL=demo@example.com          # dry run
    make seed-demo EMAIL=demo@example.com YES=1    # write

In the browser instead: sign in with an email listed in DEMO_ADMIN_EMAILS and open /demo.
Each write first deletes the demo user's rows in the seeded tables, so runs
never duplicate. The streak counts days ending today: re-run on demo day.
"""

import argparse
import os
import sys
from datetime import UTC, datetime
from typing import Any

from src.config import get_settings
from src.db.client import get_supabase_admin
from src.services.demo_seed import build_rows, seed_user


def find_or_create_user(admin: Any, email: str) -> str:
    """Return the demo user's ID, creating a confirmed account if missing."""
    page = 1
    while users := admin.auth.admin.list_users(page=page, per_page=200):
        for user in users:
            if (user.email or "").lower() == email.lower():
                return str(user.id)
        page += 1
    password = os.environ.get("DEMO_PASSWORD")
    if not password:
        sys.exit("User does not exist. Set DEMO_PASSWORD to create it.")
    created = admin.auth.admin.create_user(
        {"email": email, "password": password, "email_confirm": True}
    )
    return str(created.user.id)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--email", required=True, help="the demo account's email")
    parser.add_argument("--yes", action="store_true", help="write (default is a dry run)")
    args = parser.parse_args()

    settings = get_settings()
    if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY and settings.ENCRYPTION_SALT):
        sys.exit(
            "Set SUPABASE_URL, SUPABASE_SERVICE_KEY, SECRET_KEY and ENCRYPTION_SALT for the target env."
        )

    now = datetime.now(UTC)
    rows = build_rows("<demo-user-id>", now)
    host = settings.SUPABASE_URL.split("//")[-1].split(".")[0]
    print(f"Target Supabase project: {host}")
    print(f"Demo account: {args.email}")
    for table, items in rows.items():
        print(f"  {table}: {len(items)} rows")
    due = sum(1 for v in rows["vocabulary"] if v["next_review_at"] <= now.isoformat())
    print(f"  words due for review now: {due}; streak: 9 days")
    if not args.yes:
        print("Dry run. Re-run with --yes to write.")
        return

    admin = get_supabase_admin()
    for table, count in seed_user(admin, find_or_create_user(admin, args.email)).items():
        print(f"Wrote {count} rows to {table}")
    print("Done. Sign in as the demo user and open /progress to check.")


if __name__ == "__main__":
    main()
