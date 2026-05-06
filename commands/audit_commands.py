from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_script(script: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=Path(__file__).resolve().parent.parent,
        text=True,
        capture_output=True,
        timeout=60,
    )
    output = (proc.stdout or proc.stderr or '').strip()
    return proc.returncode == 0, output


def _tail_table(output: str, max_lines: int = 18) -> str:
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    if not lines:
        return ''
    head = lines[:4]
    body = lines[4:]
    if len(body) > max_lines:
        body = body[:max_lines] + [f'... {len(lines) - len(head) - max_lines} more lines']
    return '\n'.join(head + body)


def handle_audit_command(text: str) -> str | None:
    raw = (text or '').strip().lower()
    if raw not in {'/audit', '/audit_json', '/health', '/health_json', '/source_health', '/kaynak_saglik'}:
        return None

    if raw in {'/audit', '/audit_json'}:
        ok, output = _run_script('ops/notification_audit.py')
        if not ok:
            return 'HATA: Notification audit failed\n' + output[:1500]
        if raw == '/audit_json':
            return 'Notification audit updated\nreports/notification_audit.json'
        return 'Notification audit\n\n' + _tail_table(output)

    ok, output = _run_script('ops/source_health_report.py')
    if not ok:
        return 'HATA: Source health report failed\n' + output[:1500]
    if raw in {'/health_json'}:
        return 'Source health report updated\nreports/source_health_report.json'
    return 'Source health\n\n' + _tail_table(output)
