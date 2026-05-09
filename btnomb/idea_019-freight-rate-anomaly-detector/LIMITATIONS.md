# Limitations

- The MVP uses public FRED/BLS/BTS series as rate proxies because DAT, IATA, Baltic, and Freightos granular commercial indices often require paid licensing or API credentials.
- SMTP delivery requires environment configuration for actual external email; without credentials the app writes an `.eml` outbox file for safe reviewer verification.
- x402 is implemented as the HTTP/payment-gating interface shape with `X-PAYMENT`; production settlement would wire the header to a facilitator before returning paid exports.
- Vercel/serverless runtime uses `/tmp` SQLite storage. Production should use Postgres for persistence across cold starts.
