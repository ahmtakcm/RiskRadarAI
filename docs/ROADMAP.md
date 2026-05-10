# RiskRadarAI Roadmap

## Current State

- Scoped Telegram command registry active
- Admin/private command gating active
- UTF Turkish output fixes completed
- Command normalization active
- Telegram command sync active
- 92 tests passing

---

# Phase 4 — Stabilization

## Targets

- Cooldown TOCTOU cleanup
- pending_unofficial_signals refactor
- official_signal_history optimization
- save_runtime_state I/O reduction

## Goal

Runtime stabilization and state consistency.

---

# Phase 5 — Architecture Refactor

## Targets

- RuntimeState abstraction
- SQLite audit/event log
- Router cleanup
- Save debounce
- Worker isolation

## Goal

Long-term maintainability and scalable runtime architecture.
