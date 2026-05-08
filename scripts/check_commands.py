from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from commands.profile_commands import handle_profile_command


COMMANDS = [
    "/menu",
    "/komutlar",
    "/yardim",
    "/health",
    "/source_health",
    "/kaynak_saglik",
    "/profiles",
    "/profile_status",
    "/profil_liste",
    "/profil_durum",
    "/watch",
    "/watch_liste",
    "/tara",
    "✅ Sağlık",
    "📚 Profiller",
    "📡 Kaynaklar",
    "👁 Watch",
    "🔎 Tara",
    "📋 Menü",
]


def main() -> int:
    bad = []

    for command in COMMANDS:
        try:
            reply = handle_profile_command(command)
        except Exception as exc:
            bad.append((command, f"EXCEPTION: {exc}"))
            continue

        if not reply or not str(reply).strip():
            bad.append((command, "EMPTY_REPLY"))

    if bad:
        print("COMMAND_CHECK_FAIL")
        for command, reason in bad:
            print(f"- {command}: {reason}")
        return 1

    print(f"COMMAND_CHECK_OK count={len(COMMANDS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
