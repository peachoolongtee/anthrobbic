# Agent workflow

How work runs in this repo: the main session is the lead, and subagents build.

## Roles

The lead architects, writes specs and acceptance criteria, reviews, and integrates. Implementation goes to subagents, because the user's budget and attention are spent on the lead and its judgement is wanted on design and merges. The lead codes directly only for a change too small to be worth a brief.

| Work | Agent | `model` |
|---|---|---|
| Backend, logic, infrastructure | `implementer` | `sonnet` |
| UI | `frontend-engineer` | `sonnet` |
| Architecture, before anything crossing modules, APIs or data models | `architect` | `opus` |
| Independent proof that a slice works | `verifier` | `sonnet`, or `opus` for money, auth or security |
| Diff review | `code-reviewer`, `design-reviewer` | `sonnet`, or `opus` for cross-cutting review |
| Hard debugging, forensic audits, statistics, red teaming | `general-purpose` | `opus` |
| Searches and lookups | `Explore` | `haiku` |

Pass `model` on every Agent call and in every Workflow script, capped at `opus`. Choose the tier by whether extra reasoning could change the result. For a decision that is expensive to reverse, run specialist, then a separate `opus` reviewer, and the lead reconciles any disagreement.

## Running a round

1. **Slice.** Cut the work into vertical slices that each end in working software, with one owner per feature on one branch. Tasks and bugs live on the issue tracker. Work needing several tickets gets a `/wayfinder` map.
2. **Log.** Add the round to `docs/agents/work-log.md`.
3. **Delegate.** Send each agent a brief with every field below. Run independent agents in parallel, and give any two that write code separate files.
4. **Check.** Accept a report only after reading the diff and its evidence. Run or spawn the checks a claim rests on.
5. **Close.** Update the log with real results, then hand back to the user with what changed and what is unverified.

## Delegation brief

- **Objective and context:** what done means and why it matters.
- **Scope:** the files it may change, and what it must leave alone.
- **Constraints:** the rules from `CLAUDE.md` that bear on this task.
- **Acceptance criteria:** each one checkable.
- **Dependencies:** what it needs from other agents.
- **Report back:** work completed, files changed, the exact commands run and their results, issues, remaining work.

## Agent branches

Each writing agent uses `isolation: "worktree"` and its own branch cut from the latest integration branch, which is `main` until the user names another. One task per branch. It commits as it goes on that branch, so work survives a crash. Keep worktrees out of the scratchpad: macOS clears untouched files under `/private/tmp` after a few days, and this has destroyed worktrees before.

Agent branches stay local until the user asks for a push. The lead merges them into the integration branch with `--no-ff`, when the user asks. If work needs another agent's unmerged work, land that first.

## Test gates

- **During development:** the feature's own tests, typecheck, lint and unit tests.
- **At integration and release checkpoints:** the full suites, plus one review pass.
- **Rigorous independent verification at every step:** anything touching money, authority, auth or security.

The test budget is a real constraint. On one project about 70% of agent time went to running tests and 11% to writing code, because each sequential wave paid for its own full gate.

## Handoffs

Keep the written record to the work log and the tracker. Write a handoff document only when work moves to another machine or a new session needs what those two lack.
