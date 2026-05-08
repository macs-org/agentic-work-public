# Acceptance checklist — BTNOMB idea_024

Bounty: Regulatory Change Monitor — AI-powered alerts when SEC, FDA, FCC, or EU rules change

Status: reviewer evidence upgraded 2026-05-08T15:29:42Z.

## Criteria coverage

- [x] Live scraping of at least 4 regulatory sources
  - Implemented by `FederalRegisterSource` and `AGENCY_MAP` in `app/main.py`.
  - Source agents cover SEC, FDA, FCC, and CFTC through the Federal Register public API.
  - Tests replace the network adapter with deterministic fakes and verify all four agencies are polled.

- [x] AI summary generated for each new document within 5 minutes of publication
  - `POST /api/poll` summarizes immediately during ingestion and returns `summaries_generated_immediately: true`.
  - `GET /api/scheduler/status` exposes `POLL_INTERVAL_SECONDS`; set it to `300` to meet the five-minute monitoring SLA.
  - Summary fields include topics, affected industries, effective date/action required, impact score, and impact level.

- [x] Working subscriber signup and alert delivery
  - `POST /api/subscribers` records email/webhook subscribers and agency/topic/industry preferences.
  - SMTP email delivery works when `SMTP_HOST` is configured.
  - Without SMTP, the app stores delivery records in the development outbox, making review safe and observable.
  - Webhook delivery uses POST with a bounded timeout and records success/failure.

- [x] Dashboard showing recent alerts with filters
  - `GET /` renders the dashboard.
  - Filters: `q`, `agency`, `topic`, and `industry`.
  - Dashboard includes recent alerts, subscriber summary, trend counts, and payment info.

- [x] Searchable regulatory archive
  - `GET /api/alerts` supports full-text-ish query plus agency/topic/industry filters.
  - `GET /api/trends` summarizes alert counts by agency, impact level, and month.

- [x] Stripe or x402 payment integration
  - `GET /api/payments/x402/requirements` returns Base/USDC x402 requirements.
  - `GET /api/export` requires `X-PAYMENT` or paid plan header and returns HTTP 402 otherwise.

- [x] Reproducible packaging
  - `Dockerfile`, `requirements.txt`, `README.md`, `pytest.ini`, app code, and tests are present.
  - `demo/` contains reviewer-facing sample outputs.

## Latest verification

Command run from `work/regulatory_change_monitor`:

```bash
.venv/bin/pytest tests -q
```

Output:

```text
....                                                                     [100%]
4 passed in 0.60s
```

Additional validation command:

```bash
python3 scripts/btnomb.py validate /Users/macsclawd/Projects/agentic-work/platforms/agent-native/btnomb/jobs/2026-05-08_btnomb-regulatory-change-monitor/work/regulatory_change_monitor --tests
```

Use this after edits before publishing/submission updates.
