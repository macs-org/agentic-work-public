# On-Chain Wallet Intelligence

Autonomous on-chain wallet intelligence SaaS MVP for BTNOMB idea_021.

It monitors curated and custom wallets on Ethereum/Base, parses transactions into human-readable events, generates AI-style context with conviction scores, sends real-time alerts by email/Telegram/webhook, and exposes a wallet activity dashboard plus x402-gated export.

## Acceptance criteria coverage

- **50+ wallet monitoring:** app seeds 50 wallet profiles with tier/source metadata and supports custom watchlists.
- **Ethereum/Base live polling:** `POST /api/poll` queries configurable JSON-RPC endpoints (`ETHEREUM_RPC_URL`, `BASE_RPC_URL`) and scans recent blocks for watched addresses.
- **Swap/transfer parsing:** native transfers, ERC20 transfers, common swap selectors, LP selectors, NFT and generic contract interactions are normalized.
- **AI context:** every alert includes a context sentence, likely intent, and conviction score based on wallet tier, value, chain and method.
- **Real-time delivery:** email via SMTP, Telegram via bot token/chat id, webhook via HTTP POST. Without credentials, email/Telegram delivery is stored as a dev outbox record.
- **Dashboard:** `GET /` shows wallet profiles, activity feed, filters and signal severity.
- **Custom watchlist:** `POST /api/watchlists` adds subscriber-specific wallets.
- **x402 payment integration:** `GET /api/payments/x402/requirements`; `GET /api/export` requires `X-PAYMENT` or paid plan header.

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000.

## Docker

```bash
docker build -t onchain-wallet-intelligence .
docker run -p 8000:8000 -v wallet-intel-data:/data onchain-wallet-intelligence
```

## API examples

```bash
curl -X POST http://localhost:8000/api/subscribers -H 'content-type: application/json'   -d '{"email":"alerts@example.com","telegram_chat_id":"123","webhook_url":"https://example.com/hook"}'

curl -X POST http://localhost:8000/api/watchlists -H 'content-type: application/json'   -d '{"subscriber_id":1,"address":"0x000000000000000000000000000000000000dEaD","label":"burn wallet"}'

curl -X POST 'http://localhost:8000/api/poll?chains=base,ethereum&blocks=2'
curl 'http://localhost:8000/api/alerts?chain=base&min_score=60'
curl http://localhost:8000/api/export -H 'X-PAYMENT: demo-receipt'
```

## Environment

- `WALLET_INTEL_DB`: SQLite path, default `/tmp/onchain_wallet_intelligence.db`
- `ETHEREUM_RPC_URL`: default `https://ethereum-rpc.publicnode.com`
- `BASE_RPC_URL`: default `https://base-rpc.publicnode.com`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`: optional email settings
- `TELEGRAM_BOT_TOKEN`: optional Telegram bot token
- `X402_PAY_TO`: wallet receiving x402 payments

## Tests

```bash
pytest tests -q
```
