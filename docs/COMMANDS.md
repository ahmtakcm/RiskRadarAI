# RiskRadarAI Commands

## Command Governance

RiskRadarAI Telegram commands are managed through a scoped command registry.

## Current Rules

- Public/group commands are restricted to the public allowlist.
- Admin/private commands are gated.
- `/command@BotUsername` format is normalized.
- Telegram `setMyCommands` sync uses the registry.
- Sensitive commands such as `/digest_now` are admin-private only.

## Current Command Areas

- Health
- Audit
- Profiles
- Sources
- Watch
- Manual scan
- Digest/admin operations

## Maintenance Rules

- Do not add commands directly into handlers without registry update.
- Do not expose admin commands to group/public scope.
- Keep command aliases minimal and documented.
- Remove legacy aliases after migration.
