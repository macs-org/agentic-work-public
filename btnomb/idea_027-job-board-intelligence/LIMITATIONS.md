# Limitations and Production Hardening Notes — Job Board Intelligence

This is a compact BTNOMB MVP meant to be easy for reviewers to run and inspect. It demonstrates the core job-board intelligence loop while intentionally keeping production infrastructure small.

## Current MVP boundaries

- Greenhouse and Lever integrations use public board APIs. Additional Workday, Ashby, custom career pages, and ATS-specific scrapers should be added per-domain with robots.txt/rate-limit awareness.
- Public-company entries such as NVIDIA, Apple, Microsoft, Amazon, and Meta are seeded as tracked metadata and extension points; this MVP does not scrape their custom career sites by default.
- Trend detection uses snapshot deltas and rule-based thresholds for spikes, drops, new departments, and new roles. Production should add seasonality, headcount baselines, company-size normalization, source confidence, and duplicate-role detection.
- Role tagging is deterministic keyword tagging. Production should add a maintained taxonomy, richer NLP/LLM classification, normalized locations, remote/hybrid fields, compensation extraction, and quality scoring.
- Email delivery uses SMTP when configured; otherwise it stores a development outbox delivery so reviewers can verify the workflow without credentials. Production should add retries, bounces, unsubscribe management, and deliverability monitoring.
- Webhook delivery records one attempt per signal/subscriber/channel. Production should add signed webhooks, retries, idempotency keys, and dead-letter queues.
- x402 export gating is a payment-requirements surface and demo receipt path, not a full facilitator-backed settlement verifier.
- SQLite is the default local database. Production should use Postgres with migrations, indexes, backups, and a queue/scheduler for polling and digest jobs.
- The dashboard is functional reviewer HTML, not a polished SaaS frontend.
- Tests cover the core product contract with deterministic fixtures; production should add live API smoke tests, integration tests per ATS source, load tests, and alert-delivery tests.

## No secret requirements

The evidence package contains no wallet private keys, API tokens, internal ledger/state files, live SMTP credentials, or live user data. Sample emails, URLs, and x402 receipts are local demo values only.

## Acceptance-upgrade note

Reviewer-facing evidence was refreshed on 2026-05-08 with deterministic sample request/response artifacts, a demo guide, an acceptance checklist, current pytest output, and this limitations file. No new BTNOMB submission URL was sent and no funds were spent.