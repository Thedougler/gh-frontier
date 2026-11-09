# gh-frontier

A [`gh` CLI extension](https://cli.github.com/manual/gh_extension) that answers
"which issue next?" — the unblocked frontier of a repository's open issues,
ordered by priority and dependency position, using GitHub's native issue
dependencies. One paginated GraphQL query fetches everything (no per-issue
REST loop); all ordering is local.

## Install

```sh
gh extension install Thedougler/gh-frontier
```

Requires `gh` ≥ 2.94 (native issue dependencies) and an authenticated `gh`.

## Usage

```sh
gh frontier next --repo Thedougler/avtt -n 10   # the next 10 unblocked ready-for-agent issues
gh frontier next --priority P0 --json           # machine-readable P0 frontier
gh frontier order --exclude-label needs-info    # all matching issues, topological blocked-by order
gh frontier show 780                            # one issue's blockers, blocks, depth, unblocks
```

`next` — open issues with **no open blocker**, in the repo's rule order:
highest priority first (`P0`…`P3`; an issue with no priority label counts as
`P2`), then lowest number. Default label `ready-for-agent`.

`order` — all matching issues, blocked ones included, in topological order of
the blocked-by edges; ties broken by `--sort`. Dependency cycles are an error
(exit 4) listing the cycle and a fix.

`show N` — an issue's open/closed blockers, what it blocks, dependency depth
(longest open-blocker chain) and transitive `unblocks` count.

### Flags

| Flag | Meaning |
| ---- | ------- |
| `--label` (repeatable, ANDed) | Required labels. `next` defaults to `ready-for-agent`; `order` has no default. |
| `--exclude-label` (repeatable) | Skip issues carrying any of these. |
| `--unassigned` | Only issues with no assignee. |
| `--priority Px` (repeatable) | Only these priority labels. |
| `--priority-labels P0,P1,P2,P3` | Priority labels in rank order. |
| `--default-priority P2` | Priority for issues carrying none. |
| `--sort KEYS` | Comma list, applied in order: `priority`, `number`/`oldest`, `newest`, `updated`, `unblocks` (transitive downstream count, desc), `depth` (blocker-chain length). Default `priority,number`. |
| `--repo OWNER/NAME` | Repository; defaults to the current repo like `gh`. |
| `--json` | Stable JSON array (`number`, `title`, `priority`, `labels`, `assignees`, `blocked_by_open`, `blocked_by_closed`, `blocks`, `unblocks`, `depth`, `created_at`, `updated_at`, `parent`, `url`). |
| `--limit N` / `-n` / `--all` | Output is bounded at 20 by default; the trailer line names the flag to see all. |

### Exit codes

`0` success · `1` runtime/API failure · `2` usage error · `3` issue not found ·
`4` dependency cycle. Errors print a `fix:` line on stderr.

## Tests

```sh
uv run --with pytest pytest -q
```

Hermetic: ordering, filtering, topo and cycle logic run against fixture JSON,
no network.

## Performance

Timing is dominated by `gh api graphql --paginate` process startup, ~1 s per
100 open issues. ~150 issues ≈ 2 pages ≈ 2–3 s; avtt's 395 open issues (4
pages) takes ~5 s.

## Docs

Docs: Context7 /websites/github_en_graphql — `ctx7 docs /websites/github_en_graphql "Issue blockedBy blocking"`
Docs: Context7 /websites/cli_github_manual — `ctx7 docs /websites/cli_github_manual "gh extension"`
