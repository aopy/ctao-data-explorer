# Security Notes

- **Secrets**: never commit; load from environment/secret stores; rotate immediately if exposure is suspected
- **Cookies**: set `COOKIE_SECURE=true` on HTTPS; consider `SameSite=None` only when needed (e.g., cross-site auth)
- **CORS**: restrict origins to the expected hostnames
- **Auth**: prefer short‑lived access tokens; store refresh tokens securely (encrypted at rest)
- **Headers**: add `Content-Security-Policy`, `X-Frame-Options`, `Referrer-Policy`
