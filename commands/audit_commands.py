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


def handle_audit_command(text: str) -> str | None:
    raw = (text or "").strip().lower()
    if raw not in {"/health", "/source_health", "/kaynak_saglik"}:
        return None

    ok, output = _run_script("ops/source_health_report.py")
    if not ok:
        return "❌ Sağlık raporu üretilemedi\n" + output[:1200]

    return _source_health_summary(output, only_issues=raw in {"/source_health", "/kaynak_saglik"})
