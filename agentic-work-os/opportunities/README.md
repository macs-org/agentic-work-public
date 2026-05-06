# Opportunities

Cross-platform opportunity intake lives here before a job is accepted. Approved job artifacts should move into the platform-local jobs directory:

```text
platforms/{agent-native|human-native}/{platform}/jobs/YYYY-MM-DD_slug/
```

## Layout

```text
opportunities/
├── incoming/       # raw/normalized JSON opportunity records
├── snapshots/      # timestamped copies from discovery runs
├── ranked/         # queue snapshots and daily recommendation reports
├── rejected/       # rejected JSON records kept out of the active queue
├── queue.md        # current deduped/ranked queue
└── README.md
```

## JSON schema

Minimum:

```json
{
  "platform_class": "agent-native",
  "platform": "agentic-market",
  "title": "Paid code review endpoint opportunity",
  "url": "https://example.com/job/123",
  "payout_amount": 50,
  "payout_currency": "USDC"
}
```

Useful optional fields:

- `external_id`
- `description`
- `estimated_usd`
- `deadline`
- `work_type`
- `recommended_process`
- `account_action_required`: `none`, `human approval`, `KYC`, or `unknown`
- scoring dimensions from 0-5: `payout_certainty`, `liquidity`, `task_clarity`, `agent_fit`, `repeatability`, `strategic_value`, `time_to_complete`, `reputation_upside`
- penalties from 0-5: `friction_penalty`, `scam_risk_penalty`
- `expected_model_cost_usd`
- `notes`

## CLI

```bash
# Initialize directories
python3 scripts/aw.py init

# Add a manual opportunity
python3 scripts/aw.py add agent-native agentic-market "Code review x402 service" \
  --payout-amount 50 --payout-currency USDC --estimated-usd 50 \
  --process code-review --url https://example.com/job

# Snapshot, dedupe, lightly score, and update queue
python3 scripts/aw.py discover

# Print daily recommendations
python3 scripts/aw.py recommend --print

# After Mac approves a ranked item, create the platform-local job folder
python3 scripts/aw.py approve 1
```

## Approval policy

Discovery, dedupe, ranking, and recommendation posting are autonomous. Execution can proceed when Mac gives a broad directive such as "pick jobs and do them" or approves a ranked item in `#agentic-work`. Use the dedicated Agentic Work project wallet `0x23bB05603A980C2915FC3B9D5D4a475993b666DE`; wallet use itself does not require approval, but external/job execution decisions should stay within the current directive.

Already-submitted BTNOMB IDs should be downgraded/removed from future recommendations. Check `state/btnomb_submissions.json`, `earnings/ledger.jsonl`, and live BTNOMB `claim-status` before recommending or executing a duplicate.
