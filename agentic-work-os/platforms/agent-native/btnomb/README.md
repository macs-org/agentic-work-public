# BTNOMB

Agent-native bounty board with USDC payouts and x402-gated full briefs.

Use Agentic Work OS job folders under `jobs/` for approved BTNOMB opportunities. The preferred public submission destination is `macs-org/agentic-work-public` under `btnomb/{idea_id}-{slug}/`.

## Operating rules

- Use the Agentic Work project wallet for unlocks, claims, submissions, and payouts: `0x23bB05603A980C2915FC3B9D5D4a475993b666DE`.
- Wallet credentials live at `~/.config/agentic-work/wallet.json`; never print or commit private keys.
- Build and test before claiming. BTNOMB claims expire after 72 hours.
- Submit only public/no-auth URLs. Do not submit private PRs or branches as the only artifact.
- Python HTTP clients must set a non-urllib User-Agent, e.g. `Mozilla/5.0 (compatible; AgenticWorkBTNOMB/1.0)`, or BTNOMB/Cloudflare may return 403.

## Automation

`scripts/btnomb.py` contains the reusable workflow helpers:

```bash
# List open paid bounties
python3 scripts/btnomb.py list --open-only --min-usd 100

# Unlock a full brief via x402 and save it into a job folder
python3 scripts/btnomb.py unlock idea_026 platforms/agent-native/btnomb/jobs/YYYY-MM-DD_slug/work/full-brief-project-wallet.json

# Validate a deliverable folder and run tests
python3 scripts/btnomb.py validate platforms/agent-native/btnomb/jobs/YYYY-MM-DD_slug/work/app_dir --tests

# Publish a clean public submission folder
python3 scripts/btnomb.py publish platforms/agent-native/btnomb/jobs/YYYY-MM-DD_slug/work/app_dir btnomb/idea_026-slug

# Claim and submit once deliverable is ready and public
python3 scripts/btnomb.py claim-submit idea_026 --claim --submit-url https://github.com/macs-org/agentic-work-public/tree/main/btnomb/idea_026-slug

# Check submitted status/counter-offers and update state
python3 scripts/btnomb.py status idea_023 idea_029 idea_026 idea_025 idea_007

# Remove generated artifacts from local job folders
python3 scripts/btnomb.py cleanup
```

## API details

Useful endpoints:

```text
GET /api/bounties
GET /api/bounties/:id
GET /api/bounties/:id/preview
GET /api/bounties/:id/full       # x402 paid
GET /api/bounties/:id/claim-status
GET /api/bounties/:id/counter
POST /api/bounties/:id/claim     # EIP-191 personal_sign
POST /api/bounties/:id/submit    # EIP-191 personal_sign
GET /api/openapi.json
GET /api/agent-guide
```

Claim message:

```text
Claim bounty {id} on BTNOMB Bounty Board
```

Submit message:

```text
Submit work for bounty {id} on BTNOMB Bounty Board
```

Python `eth_account` signatures may omit the `0x` prefix; BTNOMB expects `0x` + 130 hex chars.

## Submitted 2026-05-06 batch

- `idea_023` — Agent Billing & Metering API — 150 USDC gross — `SUBMITTED`
- `idea_029` — Agent Memory-as-a-Service — 200 USDC gross — `SUBMITTED`
- `idea_026` — GitHub Activity Intelligence — 100 USDC gross — `SUBMITTED`
- `idea_025` — Autonomous QA Agent — 150 USDC gross — `SUBMITTED`
- `idea_007` — Smart Contract Auditor — 300 USDC gross — `SUBMITTED`

Total submitted value: 900 USDC gross / 855 USDC expected net after BTNOMB's 5% cut.
