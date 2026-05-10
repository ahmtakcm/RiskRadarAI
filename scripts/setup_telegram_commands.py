"""
Synchronise Telegram bot command list with the command registry.

Usage:
    python scripts/setup_telegram_commands.py

What it does:
    1. Reads TELEGRAM_ADMIN_USER_IDS from environment.
    2. Calls setMyCommands with default scope → public commands only.
    3. For each admin user ID, calls setMyCommands with chat scope
       → public + admin commands.

This script is intended to be run on deploy, not at every boot.
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Ensure project root is on sys.path so commands.registry can be imported
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

from commands.registry import admin_payload, public_payload

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN bulunamadı. Set BOT_TOKEN or TELEGRAM_BOT_TOKEN in .env")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def _set_commands(payload: list[dict], scope: dict | None = None) -> dict:
    """Call setMyCommands with given payload and optional scope.

    Returns the JSON response dict.
    """
    body: dict = {"commands": payload}
    if scope is not None:
        body["scope"] = scope

    r = requests.post(
        f"{API_URL}/setMyCommands",
        json=body,
        timeout=20,
    )
    data = r.json()
    print(f"[setMyCommands] scope={scope.get('type') if scope else 'default'} | "
          f"status={r.status_code} | ok={data.get('ok')} | "
          f"cmd_count={len(payload)}")
    return data


def main() -> int:
    errors = 0

    # --- Step 1: Set default scope (all chats) with public commands only ---
    print("--- Setting default scope: public commands ---")
    result = _set_commands(public_payload())
    if not result.get("ok"):
        print(f"  ERROR: {result.get('description', 'unknown')}")
        errors += 1

    # --- Step 2: Set per-admin chat scope with all commands ---
    admin_ids_raw = os.getenv("TELEGRAM_ADMIN_USER_IDS", "")
    admin_ids = [x.strip() for x in admin_ids_raw.split(",") if x.strip()]

    if not admin_ids:
        print("--- No TELEGRAM_ADMIN_USER_IDS set; skipping admin chat scope ---")
    else:
        full_payload = admin_payload()
        print(f"--- Setting admin chat scopes for {len(admin_ids)} admin(s) ---")
        for aid in admin_ids:
            try:
                chat_id = int(aid)
            except ValueError:
                print(f"  ERROR: invalid admin user ID: {aid!r}")
                errors += 1
                continue

            result = _set_commands(full_payload, scope={"type": "chat", "chat_id": chat_id})
            if not result.get("ok"):
                print(f"  ERROR for chat_id={chat_id}: {result.get('description', 'unknown')}")
                errors += 1

    if errors:
        print(f"\nCompleted with {errors} error(s).")
        return 1

    print("\nAll command scopes synced successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())