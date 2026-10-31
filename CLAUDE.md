## Working rules

- **Lead and delegate.** Before delegating, planning a slice, verifying agent work or logging a round, read `docs/agents/workflow.md`.
- **Git:** commit, push, merge and open pull requests only when the user asks in that turn; each request covers that one action. Leave finished work in the tree and say what changed. The exception is an agent's own branch, in `docs/agents/workflow.md`.
- **Commit messages:** conventional prefix (`feat(web): ...`), one logical piece per commit, no `Co-Authored-By` or other attribution lines.
- **Commit gate:** write a test run to a log and read its exit code before committing. A pipe through `grep` or `head` reports the filter's status, so a red run can look green.
- **Red tests:** a failing test is a defect or a stale description. Fix the code, or amend the test and say why in the commit. Keep every test whose subject still exists, at its original timeout.
- **Dev servers:** the user runs their own and keeps a signed-in browser session on them. Check with `curl`; start or stop theirs only when told to in that turn. An agent that needs a server starts its own on a free port and stops it afterwards.
- **Secrets:** report what kind of value a variable holds, never the value. Record real results only in docs and logs.
- **Live model calls:** test on fake transports by default. Spend a live call only where a real model is the point, and state the planned number of calls first.
- **Product and UI requests:** question the idea before building it. Say what is weak, give ranked suggestions with a recommendation, and let the user overrule.

## Agent skills

### Issue tracker

Issues and specs are tracked in GitHub Issues on `peachoolongtee/anthrobbic`, using the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
