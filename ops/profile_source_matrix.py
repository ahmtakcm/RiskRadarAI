from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from config.paths import PROFILES_DIR, USER_INPUTS_DIR
from source_selectors.profile_loader import load_config_for_profile
from source_selectors.feed_selector import select_feeds


REPORT_PATH = Path("reports/profile_source_matrix.json")


KNOWN_PROFILE_IDS = [
    "resmi_aciklamalar",
    "ekonomi",
    "saglik",
    "dunya",
    "turkiye",
    "yerel",
    "osint",
    "analiz",
    "tum_profiller",
]


def _existing_profiles() -> set[str]:
    return {p.stem for p in PROFILES_DIR.glob("*.json")}


def _active_profiles_from_state() -> list[str]:
    path = USER_INPUTS_DIR / "profile_state.json"
    if not path.exists():
        return []
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
        return [str(x) for x in blob.get("active_profiles", []) if str(x).strip()]
    except Exception:
        return []


def build_matrix(profiles: list[str]) -> dict:
    rows: dict[str, dict] = {}
    duplicate_counter = Counter()

    for profile_id in profiles:
        cfg = load_config_for_profile(profile_id, active_profile_names=[profile_id])
        official = select_feeds(cfg, mode="official_only")
        social = select_feeds(cfg, mode="social_only")
        osint = select_feeds(cfg, mode="osint_only")
        analysis = select_feeds(cfg, mode="analysis_only")
        all_feeds = select_feeds(cfg, mode="all")

        names = [f.get("name") for f in all_feeds if f.get("name")]
        duplicate_counter.update(names)

        rows[profile_id] = {
            "official_shared_count": len(official),
            "social_count": len(social),
            "osint_count": len(osint),
            "analysis_count": len(analysis),
            "total_dedup_count": len(all_feeds),
            "selected_sources": names,
        }

    duplicates = sorted([name for name, c in duplicate_counter.items() if c > 1])
    warnings: list[str] = []

    for profile_id, row in rows.items():
        if row["total_dedup_count"] == 0:
            warnings.append(f"zero-source profile: {profile_id}")

    if duplicates:
        warnings.append(f"duplicate source_id across profiles: {len(duplicates)}")

    return {
        "profiles": profiles,
        "rows": rows,
        "summary": {
            "active_profiles_from_state": _active_profiles_from_state(),
            "duplicate_source_ids": duplicates[:200],
        },
        "warnings": warnings,
    }


def _render_text(matrix: dict) -> str:
    rows = matrix.get("rows", {}) or {}
    lines = ["=== Profile Source Matrix ===", ""]

    active = matrix.get("summary", {}).get("active_profiles_from_state") or []
    if active:
        lines.append("Active/enabled (runtime state): " + ", ".join(active))
        lines.append("")

    for profile_id, row in rows.items():
        lines.append(f"[{profile_id}] total={row.get('total_dedup_count')}")
        lines.append(f"  shared_official={row.get('official_shared_count')} social={row.get('social_count')} osint={row.get('osint_count')} analysis={row.get('analysis_count')}")
        if not row.get("selected_sources"):
            lines.append("  WARNING: zero sources selected")
        lines.append("")

    warns = matrix.get("warnings") or []
    if warns:
        lines.append("Warnings:")
        lines.extend([f"- {w}" for w in warns])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Write JSON to reports/profile_source_matrix.json")
    parser.add_argument("--profile", action="append", default=[], help="Limit to specific profile_id (repeatable)")
    args = parser.parse_args(argv)

    existing = _existing_profiles()
    profiles = [p for p in KNOWN_PROFILE_IDS if p in existing]
    if args.profile:
        wanted = [p for p in args.profile if p in existing]
        profiles = wanted

    matrix = build_matrix(profiles)
    print(_render_text(matrix))

    if args.json:
        REPORT_PATH.parent.mkdir(exist_ok=True)
        REPORT_PATH.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

