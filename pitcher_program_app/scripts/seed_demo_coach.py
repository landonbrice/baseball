"""Create a demo coach account in Supabase Auth + coaches table.

Usage: python -m scripts.seed_demo_coach
Requires SUPABASE_URL and SUPABASE_SERVICE_KEY env vars.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from bot.services.db import get_client

TEAM_ID = "uchicago_baseball"
COACH_EMAIL = os.getenv("DEMO_COACH_EMAIL", "coach@uchicago.example.com")
COACH_NAME = os.getenv("DEMO_COACH_NAME", "Coach Krause")
COACH_ROLE = "head"


def seed():
    client = get_client()

    # Create Supabase Auth user via admin API
    try:
        auth_resp = client.auth.admin.create_user({
            "email": COACH_EMAIL,
            "password": os.getenv("DEMO_COACH_PASSWORD", "changeme2026!"),
            "email_confirm": True,
        })
        supabase_user_id = auth_resp.user.id
        print(f"Created Supabase Auth user: {supabase_user_id}")
    except Exception as e:
        if "already been registered" in str(e).lower() or "duplicate" in str(e).lower():
            # User exists — look up their ID
            users = client.auth.admin.list_users()
            supabase_user_id = None
            for u in users:
                if hasattr(u, 'email') and u.email == COACH_EMAIL:
                    supabase_user_id = u.id
                    break
            if not supabase_user_id:
                print(f"ERROR: Auth user exists but couldn't find ID: {e}")
                return
            print(f"Auth user already exists: {supabase_user_id}")
        else:
            print(f"ERROR creating auth user: {e}")
            return

    # Upsert coaches row
    coach_row = {
        "team_id": TEAM_ID,
        "email": COACH_EMAIL,
        "name": COACH_NAME,
        "role": COACH_ROLE,
        "supabase_user_id": str(supabase_user_id),
    }
    resp = client.table("coaches").upsert(
        coach_row, on_conflict="email"
    ).execute()
    print(f"Upserted coach row: {resp.data}")
    print(f"\nLogin credentials:")
    print(f"  Email: {COACH_EMAIL}")
    print(f"  Password: (set via DEMO_COACH_PASSWORD env var)")


if __name__ == "__main__":
    seed()
