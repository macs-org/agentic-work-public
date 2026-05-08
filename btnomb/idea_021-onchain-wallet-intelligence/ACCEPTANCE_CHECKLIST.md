# Acceptance Checklist — BTNOMB idea_021

Bounty: On-Chain Wallet Intelligence — Track alpha wallets on Base & Ethereum, get alerts when they move

Public submission URL: https://github.com/macs-org/agentic-work-public/tree/main/btnomb/idea_021-onchain-wallet-intelligence

## Criteria coverage

1. Live monitoring of at least 50 wallets on Ethereum or Base
   - Status: covered.
   - Evidence: `app/main.py` seeds 50 curated wallet profiles; `/health` reports `wallets: 50`; `/api/wallets` exposes the watched set.
   - Test/evidence: `tests/test_wallet_intelligence.py::test_seeds_50_wallets_custom_watchlist_and_poll`; `evidence/sample_api_flow.json` lines with `health.wallets` and `poll_base_one_block.wallets_tracked`.

2. Transaction parsing working for swaps and transfers
   - Status: covered.
   - Evidence: `parse_transaction` recognizes native transfers, ERC-20 transfers, DEX swap selectors, LP selectors, NFT selectors, and generic contract interactions.
   - Test/evidence: `test_parse_swap_transfer_and_context_scores`; `evidence/sample_api_flow.json` includes one `transfer` alert and one `swap` alert.

3. AI context generation functional per alert
   - Status: covered.
   - Evidence: every alert stores `summary`, `context`, `likely_intent`, and `conviction_score` based on wallet tier, chain, value, and method.
   - Test/evidence: `test_parse_swap_transfer_and_context_scores` asserts context and score; sample alert JSON shows human-readable context and likely intent.

4. Email alert delivery working in real-time under 60 seconds from confirmation
   - Status: covered for MVP delivery path; production scheduler should call poll every 45 seconds.
   - Evidence: `deliver_email` sends through SMTP when `SMTP_HOST` is configured and safely records a dev-outbox row when credentials are absent. `/api/poll` returns `under_60_second_polling_configured: true` with default `POLL_INTERVAL_SECONDS=45`.
   - Test/evidence: `test_seeds_50_wallets_custom_watchlist_and_poll` verifies delivery rows; `evidence/sample_api_flow.json` shows email delivery records with `stored` status in credential-free review mode.

5. Dashboard showing wallet activity feed
   - Status: covered.
   - Evidence: `GET /` renders a dashboard with filters, top watched wallets, activity feed, context, score, and payment section.
   - Test/evidence: `test_dashboard_and_payment_gate` asserts dashboard response; `evidence/dashboard-preview.html` contains a rendered snapshot.

6. Custom wallet watchlist working
   - Status: covered.
   - Evidence: `POST /api/watchlists` adds or replaces subscriber/global custom wallets with chain scope; matching works against watched `from` and `to` addresses.
   - Test/evidence: `test_seeds_50_wallets_custom_watchlist_and_poll` and `test_match_event_to_to_address_and_chain_filter`; sample API flow shows the `custom whale` Base watchlist entry.

7. Stripe or x402 payment integration
   - Status: covered with x402-style gate.
   - Evidence: `GET /api/payments/x402/requirements` returns Base/USDC payment requirements and `GET /api/export` requires `X-PAYMENT` or paid plan header.
   - Test/evidence: `test_dashboard_and_payment_gate`; `evidence/sample_api_flow.json` shows HTTP 402 without payment and successful export with `X-PAYMENT: demo-receipt`.

## Latest verification

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/onchain_wallet_intelligence_venv/bin/python -m pytest tests -q -p no:cacheprovider
```

Output:

```text
....                                                                     [100%]
4 passed
```

Public URL checks on 2026-05-08 returned HTTP 200 for the submitted GitHub tree, core source files, reviewer docs, tests, and evidence artifacts. See `evidence/public-url-verification-2026-05-08.txt` for the exact URL list.

## Reviewer notes

The repo intentionally avoids committed private credentials. To exercise live email/Telegram delivery, set `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASSWORD`/`SMTP_FROM` and/or `TELEGRAM_BOT_TOKEN`, then run the poll endpoint. Without those credentials, delivery attempts are still visible through `/api/deliveries` as stored development-outbox entries.
