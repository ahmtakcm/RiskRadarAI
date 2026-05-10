from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _run_script(script: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    output = (proc.stdout or proc.stderr or "").strip()
    return proc.returncode == 0, output


def _table_rows(output: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in output.splitlines():
        line = line.rstrip()
        if not line or line.startswith(("Source health report", "active_profile=", "mode ", "----")):
            continue
        parts = [p for p in line.split(" ") if p]
        if len(parts) >= 6:
            rows.append(parts)
    return rows


def _source_health_summary(output: str, *, only_issues: bool) -> str:
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    total = 0
    issues: list[str] = []
    unknown = 0

    for line in lines:
        if line.startswith("active_profile="):
            for bit in line.split():
                if bit.startswith("total="):
                    try:
                        total = int(bit.split("=", 1)[1])
                    except Exception:
                        pass

        if line.startswith(("official_", "social_", "osint_", "analysis_")):
            cols = [x for x in line.split("  ") if x.strip()]
            compact = " ".join(line.split())
            if " unknown " in f" {compact} ":
                unknown += 1
            if any(x in compact.lower() for x in ("error", "fail", "timeout", "dns", "cooldown")):
                issues.append(compact)

    if only_issues:
        if not issues:
            return (
                "🟢 Kaynak sorunu görünmüyor.\n\n"
                f"Toplam kaynak: {total or 'bilinmiyor'}\n"
                f"Durumu henüz ölçülmemiş: {unknown}"
            )
        return "⚠️ Sorunlu kaynaklar:\n" + "\n".join(f"- {x}" for x in issues[:20])

    return (
        "🟢 RiskRadarAI çalışıyor\n\n"
        f"Kaynak toplamı: {total or 'bilinmiyor'}\n"
        f"Durumu henüz ölçülmemiş: {unknown}\n"
        f"Sorunlu kaynak: {len(issues)}\n\n"
        "Detay için: /source_health"
    )


def _notification_audit_summary(output: str, *, as_json: bool) -> str:
    if as_json:
        report = ROOT / "reports" / "notification_audit.json"
        if report.exists():
            try:
                import json
                data = json.loads(report.read_text(encoding="utf-8"))
                counts = data.get("counts", {})
                return (
                    "🧾 Notification audit JSON üretildi\n"
                    f"Dosya: reports/notification_audit.json\n"
                    f"Toplam: {counts.get('total', 'bilinmiyor')} | official={counts.get('official_only', 0)} social={counts.get('social_only', 0)} osint={counts.get('osint_only', 0)} analysis={counts.get('analysis_only', 0)}"
                )
            except Exception:
                pass
        return "🧾 Notification audit JSON üretildi: reports/notification_audit.json"

    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    header = next((line for line in lines if line.startswith("active_profile=")), "")
    lane_counts = {}
    for line in lines:
        if line.startswith(("official_", "social_", "osint_", "analysis_", "calendar")):
            compact = " ".join(line.split())
            parts = compact.split()
            if len(parts) >= 5:
                lane = parts[4]
                lane_counts[lane] = lane_counts.get(lane, 0) + 1
    lane_text = "\n".join(f"- {k}: {v}" for k, v in sorted(lane_counts.items())) or "- lane özeti üretilemedi"
    return f"🧾 Notification audit\n{header}\n\nLane özeti:\n{lane_text}\n\nDetay: /audit_json"


def handle_audit_command(text: str) -> str | None:
    raw = (text or "").strip().lower()
    if raw in {"/audit", "/audit_json"}:
        ok, output = _run_script("ops/notification_audit.py")
        if not ok:
            return "❌ Denetim raporu üretilemedi\n" + output[:1200]
        return _notification_audit_summary(output, as_json=raw == "/audit_json")

    if raw not in {"/health", "/source_health", "/kaynak_saglik"}:
        return None

    ok, output = _run_script("ops/source_health_report.py")
    if not ok:
        return "❌ Sağlık raporu üretilemedi\n" + output[:1200]

    return _source_health_summary(output, only_issues=raw in {"/source_health", "/kaynak_saglik"})
