# RiskRadarAI Workflow

## Development Flow

1. Issue oluşturulur.
2. Branch açılır.
3. Değişiklik yapılır.
4. Test çalıştırılır.
5. PR açılır.
6. Review yapılır.
7. Merge edilir.
8. Roadmap güncellenir.

---

# Branch Strategy

## Main

Production-ready branch.

## Feature Branches

Naming:

feature/<short-name>

Examples:

- feature/runtime-state
- feature/sqlite-audit-log
- feature/router-cleanup

---

# Commit Strategy

Small and traceable commits preferred.

Examples:

- Add runtime state abstraction
- Fix telegram command normalization
- Reduce save_runtime_state I/O

---

# Pull Request Rules

PR must include:

- scope summary
- affected modules
- risk assessment
- test status

---

# Runtime Safety Rules

Before merge:

- tests must pass
- command scopes must be validated
- runtime persistence impact reviewed
- Telegram admin/public boundaries verified

## Branch Workflow
- feature branch -> PR -> CI -> merge
