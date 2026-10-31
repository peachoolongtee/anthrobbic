# Agent work log

The running record of delegated work, so a new session can resume it. Newest round first. Tasks and bugs live on the issue tracker, so this log holds only who did what and what was proven.

An entry is **completed** only when its acceptance criteria are met and the lead has checked the result. Other statuses are **not started**, **in progress** and **blocked**. Record results from real command output, and leave out passwords, keys, tokens and connection strings.

## Round template

```markdown
## Round N: <parent task> (YYYY-MM-DD)

| # | Agent and model | Scope | Branch | Acceptance criteria | Status |
|---|---|---|---|---|---|

### N.1 <role>: <status>

- **Files changed:**
- **Verified by the lead:** what was checked, with the command and its result
- **Not verified:**
- **Findings and remaining work:**
```
