# Satokori

Finnish farm-network grocer. Skip the shop. Who has what, when, and where.

Not a till — cash at the gate is not written as a sale.

```
docker compose up -d --build
```

Local: http://127.0.0.1:8791  
Public: https://satokori.com  
Alias: https://satokori.wakalabs.net

## Ship

Frontier is the only path to GitHub. Spec: `D:\wakalabs\frontier\PIPELINE.md`.

1. Feature branch (`frontier/…`). Never commit or push `main`.
2. Clean commit.
3. `frontier hygiene` (advise).
4. `frontier plan` must exit 0.
5. `frontier apply` must exit 0.
6. `git push` through the Frontier shim. Never `--no-verify`.
7. Open a PR into the stack (or into `main`). Human merges. Agents do not merge to `main`.

Tests are not a substitute for plan/apply. Run them verbose:

```
pytest tests/ -v
```

GitHub Actions `verify.yml` re-runs that suite on every PR. It does not replace the local gate.

## REKO

Satokori copies the Facebook REKO ring (not Marketplace classifieds). A producer posts a lot to a shared drop. A customer orders a quantity. The producer confirms. Pay cash or MobilePay at the lot. Farm-gate pickup stays as the other channel: the customer asks, the farmer names a time.

## Phones

The product is the PWA at https://satokori.com. Do not rewrite it as React Native, Flutter, or Expo.

- **iPhone (beta):** Safari → Share → Add to Home Screen. Web Push from iOS 16.4 when opened from that icon. App Store later needs an Apple Developer account and a Mac.
- **Android (Play):** wrap the live PWA as a Trusted Web Activity (PWABuilder / Bubblewrap). Play Console on `wkariniemi@gmail.com`. Store binaries are not in this repo.
- **SDK:** the same host’s OpenAPI plus `X-API-Key` for agents. People sign in with email and password.
