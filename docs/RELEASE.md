# RiskRadarAI Release Governance

## Purpose

This document defines release, versioning, tagging, and rollback standards for RiskRadarAI.

---

# Versioning

RiskRadarAI follows semantic versioning:

MAJOR.MINOR.PATCH

Examples:

- 1.0.0
- 1.1.0
- 1.1.1

## Version Meaning

- MAJOR: breaking architecture/runtime changes
- MINOR: new features or major improvements
- PATCH: bug fixes, small hardening changes, documentation updates

---

# Release Flow

1. Complete work on feature branch.
2. Open pull request.
3. CI must pass.
4. Merge into main.
5. Verify main branch CI.
6. Create release tag.
7. Write release notes.
8. Deploy if required.
9. Monitor runtime logs.

---

# Tag Format

Use:

vMAJOR.MINOR.PATCH

Examples:

- v1.0.0
- v1.1.0
- v1.1.1

---

# Release Notes Must Include

- Summary
- Changed areas
- Tests
- Deployment notes
- Rollback notes
- Known risks

---

# Rollback Strategy

Rollback must identify:

- previous stable commit
- previous stable tag
- runtime state impact
- config compatibility
- deployment command

---

# Current Baseline

Current stable governance baseline includes:

- Codespaces
- Devcontainer
- CI
- pytest
- PR workflow
- protected main
- CODEOWNERS
- documentation standard
