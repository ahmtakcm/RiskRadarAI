# CLINE Workflow Rules

## Before any code changes (Act mode)
1. Run `git status` to check the working tree.
2. If there are uncommitted user changes, **stop and report them** to the user before proceeding.

## Before risky or multi-file edits
- Create a checkpoint commit, or ask the user for explicit permission.

## After each completed task
1. **Run tests** – execute the project test suite.
2. **Show changed files** – list which files were modified.
3. **Show diff summary** – provide an overview of what changed.
4. **Commit** – if tests pass, commit with a clear and descriptive message.

## Destructive commands
- Never run `git reset --hard`, `git clean -fd`, `git push --force`, or similar destructive operations **unless explicitly requested** by the user.

## Commit style
- Keep commits **small and focused**. Each commit should represent a single logical change.