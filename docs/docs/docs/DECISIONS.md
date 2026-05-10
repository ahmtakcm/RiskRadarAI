# RiskRadarAI Decisions

This document tracks important engineering and architecture decisions.

---

# 2026-05 — Scoped Telegram Command Registry

## Decision

Telegram commands are managed through a centralized scoped registry.

## Reason

Previous command handling caused:

- duplicated aliases
- inconsistent visibility
- admin/public confusion
- command drift

## Result

- centralized command governance
- public/admin separation
- Telegram sync consistency

---

# 2026-05 — Admin Private Command Gating

## Decision

Sensitive commands are restricted to admin private chat scope.

## Reason

Operational/runtime commands must not be exposed publicly.

Examples:

- digest forcing
- runtime operations
- maintenance commands

## Result

Reduced operational risk.

---

# 2026-05 — Runtime Architecture Refactor Planning

## Decision

Move toward RuntimeState + SQLite-backed audit/event persistence.

## Reason

Current file-based persistence introduces:

- excessive I/O
- synchronization complexity
- fragmented runtime state

## Planned Outcome

- scalable runtime governance
- auditability
- cleaner runtime lifecycle
