# Agentic Work OS v0

Agentic Work OS v0 is a small Hermes-native operating loop for finding paid agent work, ranking it, getting human approval, executing approved jobs, tracking earnings, and improving reusable processes.

## Principles

1. Keep `platforms/` as the durable project structure.
2. Store accepted job artifacts under their platform: `platforms/{agent-native|human-native}/{platform}/jobs/YYYY-MM-DD_slug/`.
3. Use `opportunities/` only for cross-platform intake before a job is accepted.
4. Start without specialist profiles. Powerful general models handle MVP work; add specialists only when bottlenecks justify them.
5. Discovery is autonomous every 12 hours; execution can proceed under explicit Mac directives or ranked-item approval.
6. Daily recommendations post to `#agentic-work` at 11:00 UTC.
7. Use this Discord channel as the cockpit; use job threads for approved jobs when available.
8. Use the dedicated Agentic Work project wallet `0x23bB05603A980C2915FC3B9D5D4a475993b666DE` for wallet operations, x402 unlocks, claims/submissions, and payouts.
9. Every completed/rejected job should feed a process postmortem and process update.
10. Do not recommend or execute duplicate submissions; check platform state and `state/*` first.

## Loop

```text
12h cron:
  discover/snapshot opportunities
  normalize/dedupe
  light score
  update opportunities/queue.md

11:00 UTC cron:
  read current queue
  rank across platforms
  post daily recommendations to #agentic-work

manual approval:
  Mac approves a recommendation in #agentic-work
  Hermes creates platform-local job folder
  create/use a Discord thread for job discussion
  execute/review/submit as approved
  track payout/outcome
  update process docs/metrics
```

## State surfaces

- `scripts/aw.py` — dependency-free CLI used by humans, Hermes, and cron jobs.
- `opportunities/incoming/*.json` — active candidate records.
- `opportunities/queue.md` — deduped/ranked active queue.
- `opportunities/ranked/*_daily-recommendations.md` — daily recommendation reports.
- `platforms/.../jobs/YYYY-MM-DD_slug/` — approved job artifacts.
- `earnings/ledger.jsonl` — append-only earnings/payment event log.
- `state/btnomb_submissions.json` — machine-readable BTNOMB submission/status/counter-offer tracker.
- `processes/` — reusable process definitions, experiments, postmortems, and metrics.

## MVP commands

```bash
python3 scripts/aw.py init
python3 scripts/aw.py discover
python3 scripts/aw.py queue --print
python3 scripts/aw.py recommend --print
python3 scripts/aw.py approve 1
python3 scripts/btnomb.py status idea_023 idea_029 idea_026 idea_025 idea_007
python3 earnings/tracker.py status --platform btnomb --details
```

## Scoring model

The MVP score is intentionally simple. It rewards:

- payout certainty,
- liquidity/cash value,
- task clarity,
- agent fit,
- repeatability,
- strategic value,
- time-to-complete,
- reputation upside,
- expected payout.

It penalizes:

- account/KYC friction,
- scam/zombie risk,
- expected model cost.

The score is not final truth; it is a triage heuristic. Daily recommendations should still explain why a job is worth doing.

## Autonomy ladder

Current state: autonomous discovery/ranking, manual execution.

Next autonomy steps:

1. Auto-create job folders after explicit approval.
2. Auto-execute low-cost agent-native tasks with known-good processes.
3. Auto-submit low-risk jobs under a cost/payout threshold.
4. Add specialist profiles only when queue volume or review quality demands it.
5. Evaluate Paperclip only after Hermes-native loop is producing useful recommendations.
