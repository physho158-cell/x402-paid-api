# BJJ Paid Micro-API (x402, USDC on Base)

A pay-per-call API for AI agents. Agents call an endpoint, receive an HTTP 402 challenge,
pay USDC on Base, retry with the tx hash, and get the data. Payments settle **instantly on-chain**
to the provider wallet. No accounts, no API keys.

## Endpoints
| Route | Price | Returns |
|-------|-------|---------|
| `/v1/citation/check?url=<https-url>` | 0.002 USDC | URL reachability, status, title, bytes |
| `/v1/reports/did-fintech/executive-summary` | 0.005 USDC | Citation-ready research summary (JSON) |
| `/v1/reports/uam-policy/executive-summary` | 0.005 USDC | Citation-ready policy summary (JSON) |
| `/manifest` | free | machine-readable catalog |

Free: `/healthz`, `/manifest`. Payout wallet is set in `app.py` (`RECIPIENT`).

## Deploy (Render, free, ~2 min)
1. Go to https://dashboard.render.com → sign in with GitHub.
2. New → **Web Service** → connect this repository (`physho158-cell/x402-paid-api`).
3. Render auto-reads `render.yaml`. Click **Create**. Wait for "Live".
4. Copy the public URL, e.g. `https://bjj-x402-paid-api.onrender.com`.

## List on PayAPI Market (free, providers keep 100%)
1. Open https://payapi.market/list
2. Paste a PAID route, e.g. `https://bjj-x402-paid-api.onrender.com/v1/citation/check?url=https://example.com`
3. Method GET. The Base wallet auto-fills from your 402. Submit.
4. PayAPI runs automated checks + one settlement test (≤$0.10) → listing goes live → AI agents discover & pay per call.
