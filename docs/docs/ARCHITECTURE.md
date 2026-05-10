# RiskRadarAI Architecture

## Overview

RiskRadarAI is a modular Telegram-based risk intelligence and alert platform.

System responsibilities:

- Multi-source ingestion
- Risk/event parsing
- AI-assisted enrichment
- Notification policy evaluation
- Telegram delivery
- Runtime governance
- Auditability

---

# Core Layers

## Fetchers

Responsible for collecting raw data from:

- RSS
- Official sources
- Social sources
- Economic feeds

---

## Parsers

Normalize source-specific content into internal event structures.

---

## Enrichers

Enhance parsed content using:

- AI summarization
- Text hygiene
- Deduplication
- Metadata enrichment

---

## Rules & Policies

Responsible for:

- notification policies
- score thresholds
- official verification logic
- digest/runtime suppression

---

## Services

Operational runtime services:

- Telegram bot
- command registry
- runtime state
- scheduling
- persistence

---

# Current Runtime Model

Current runtime uses file-based persistence and modular workers.

Known limitations:

- runtime state fragmentation
- save_runtime_state excessive I/O
- cooldown synchronization complexity

---

# Planned Architecture Migration

## Phase 4

Stabilization and state consistency improvements.

## Phase 5

Migration targets:

- RuntimeState abstraction
- SQLite audit/event log
- router cleanup
- save debounce
- worker isolation

Goal:
Long-term maintainability and scalable runtime governance.
