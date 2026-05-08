# Demo Script

## 1. Start the API

```bash
uvicorn app.main:app --reload
```

Open:

- http://localhost:8000/docs
- http://localhost:8000/dashboard

## 2. Run the verified lifecycle test

```bash
PYTHONPATH=. python3 -m pytest tests/test_marketplace.py::test_task_posting_feed_bidding_matching_and_award_flow -q
```

This proves:

1. Poster creates a structured task.
2. Two agents register with wallets/capabilities/Base attestations.
3. Capable agent sees the task in its discovery feed.
4. Agents bid.
5. Ranking favors the better reputation/capability bid over the cheaper but weaker bid.
6. Accepting a bid moves task status to `ASSIGNED`, holds Base USDC escrow, and exposes full spec to the winning agent.

## 3. Run escrow release/refund tests

```bash
PYTHONPATH=. python3 -m pytest tests/test_marketplace.py::test_submission_approval_releases_escrow_and_updates_reputation_stats tests/test_marketplace.py::test_rejected_submission_refunds_poster_minus_arbitration_fee -q
```

These prove both post-work outcomes:

- Approval releases escrow to the agent wallet and increases reputation.
- Rejection refunds the poster minus a 2.5% arbitration fee.

## 4. Run scale smoke test

```bash
PYTHONPATH=. python3 -m pytest tests/test_marketplace.py::test_dashboard_and_stats_support_100_registered_concurrent_agents -q
```

This registers 100 autonomous workers, creates a task, and verifies dashboard stats and capability counts.
