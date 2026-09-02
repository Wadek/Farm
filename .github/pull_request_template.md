## Why

## Stack

Base branch (never open a PR from `main`):

## Verify

- [ ] `pytest tests/ -v` locally (paste the log)
- [ ] `frontier hygiene` (advise)
- [ ] `frontier plan` exit 0
- [ ] `frontier apply` exit 0
- [ ] `git push` through the Frontier shim (no `--no-verify`)

Agents do not merge to `main`. Human merges.
