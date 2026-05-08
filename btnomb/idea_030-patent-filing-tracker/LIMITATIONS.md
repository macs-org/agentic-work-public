# Limitations and Production Hardening Notes — Patent Filing Tracker

This is a compact BTNOMB MVP meant to be easy for reviewers to run and inspect. It demonstrates the core patent-intelligence loop while intentionally keeping production infrastructure small.

## Current MVP boundaries

- The live external integration is USPTO PatentsView, which satisfies the acceptance criterion requiring at least USPTO PatentsView. The product overview also mentions EPO OPS; production should add EPO OPS credentials/client support, per-office normalization, and source-specific rate-limit handling.
- Watchlists currently cover company/assignee and keyword entries, matching the explicit acceptance criterion. Production should add first-class inventor, CPC classification, legal-status, jurisdiction, and portfolio-family watchlist types.
- AI summarization is deterministic and rule-based for reviewer reproducibility. Production should add an LLM-backed summarizer with citations, confidence, hallucination checks, and prompt/version tracking.
- Email delivery uses SMTP when configured; otherwise it stores a development outbox delivery so reviewers can verify the workflow without credentials. Production should add retries, bounces, unsubscribe management, and deliverability monitoring.
- Webhook delivery records one attempt per new filing/watchlist/channel. Production should add signed webhooks, retries, idempotency keys, replay protection, and dead-letter queues.
- x402 export gating is a payment-requirements surface and demo receipt path, not a full facilitator-backed settlement verifier.
- SQLite is the default local database. Production should use Postgres with migrations, indexes, backups, retention policies, and a queue/scheduler for daily polling.
- The dashboard is functional reviewer HTML, not a polished SaaS frontend.
- Tests cover the core product contract with deterministic fixtures. Production should add live PatentsView smoke tests, EPO OPS integration tests, load tests, and alert-delivery integration tests.

## No secret requirements

The evidence package contains no wallet private keys, API tokens, internal ledger/state files, live SMTP credentials, or live user data. Sample emails, webhook URLs, and x402 receipts are local demo values only.

## Acceptance-upgrade note

Reviewer-facing evidence was refreshed on 2026-05-08 with deterministic sample request/response artifacts, a demo guide, an acceptance checklist, current pytest output, and this limitations file. No new BTNOMB submission URL was sent and no funds were spent.
