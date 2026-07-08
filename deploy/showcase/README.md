# Showcase deployment — Mac Mini + Cloudflare Tunnel

Stand up the platform on a Mac Mini and expose it at your Cloudflare domain,
with real chapter subdomains, for a next-day demo. Cloudflare terminates TLS
at its edge, so **no Caddy / no certificates to manage** — a tunnel forwards
`https://<domain>` and `https://*.<domain>` to a local gunicorn.

```
browser ──https──▶ Cloudflare edge ──tunnel──▶ cloudflared ──http──▶ gunicorn 127.0.0.1:8000
  example.com            (TLS here)                                    (Django, showcase settings)
  delhi.example.com
  bangalore.example.com
```

Prereqs: Docker Desktop (running), the repo's `venv`, and a domain on
Cloudflare. **Use your zone apex as the root** (`example.com`) so chapters are
one level deep (`delhi.example.com`) and covered by free Universal SSL — see
the note in `env.showcase.example`.

---

## Part 1 — Cloudflare Tunnel (one-time, interactive)

```bash
brew install cloudflared
cloudflared tunnel login                 # opens a browser; pick your domain/zone
cloudflared tunnel create null-showcase  # note the Tunnel ID it prints
```

Create `~/.cloudflared/config.yml` (substitute the Tunnel ID, your macOS user,
and your domain):

```yaml
tunnel: <TUNNEL-ID>
credentials-file: /Users/<you>/.cloudflared/<TUNNEL-ID>.json
ingress:
  - hostname: "example.com"
    service: http://127.0.0.1:8000
  - hostname: "*.example.com"
    service: http://127.0.0.1:8000
  - service: http_status:404
```

Point DNS at the tunnel (apex + wildcard):

```bash
cloudflared tunnel route dns null-showcase example.com
cloudflared tunnel route dns null-showcase "*.example.com"
```

If the wildcard route errors, add it by hand in the Cloudflare dashboard:
**DNS → Add record → CNAME, name `*`, target `<TUNNEL-ID>.cfargotunnel.com`,
Proxied (orange cloud)**.

In the dashboard: **SSL/TLS → Overview → Full**, and **Edge Certificates →
Always Use HTTPS → On**.

---

## Part 2 — Run the app (repeat per showcase / after a reboot)

```bash
cd <repo>
source venv/bin/activate
pip install gunicorn                       # one-time; NOT `pip install -r requirements.txt`
                                           # (that builds mysqlclient, which fails on macOS;
                                           #  the venv already uses the PyMySQL shim)

cp deploy/showcase/env.showcase.example deploy/showcase/.env.showcase
# edit .env.showcase: set ROOT_DOMAIN, SITE_BASE_URL, the three *_DOMAIN vars,
# and a long random DJANGO_SECRET_KEY (e.g. `python -c "import secrets;print(secrets.token_urlsafe(50))"`)

set -a; source deploy/showcase/.env.showcase; set +a
./scripts/run_showcase.sh                  # brings up db+redis, migrates, collectstatic,
                                           # seeds demo data, then runs gunicorn (leave it running)
```

In a second terminal:

```bash
cloudflared tunnel run null-showcase       # leave running
```

Open **https://example.com** (root directory) and **https://delhi.example.com**
(Delhi chapter). Done.

### Keep it alive across reboots (optional)

Install the tunnel as a launch service so it restarts automatically:
`sudo cloudflared service install`. Run the app under `tmux`/`screen`, or wrap
`run_showcase.sh` in a `launchd` plist.

---

## Demo logins & content (from the seed script)

All passwords are `password`.

| Login | Role |
|---|---|
| `admin@example.com` | superuser → `/admin` |
| `lead@example.com` | Delhi chapter lead → `/leads/...` |
| `speaker@example.com` | speaker with past sessions |
| `member1@example.com` … `member6@example.com` | attendees |

Chapters: **delhi**, **bangalore**, **goa** (`<sub>.<ROOT_DOMAIN>`).
Delhi has demo events wired for **check-in**, **waitlist**, **invite-only
approval**, and a **just-ended** event.

### Suggested tour
1. `https://example.com` — root directory: three chapters + collective stats
   (Part 0 architecture).
2. `https://delhi.example.com` — chapter homepage, upcoming events, archives.
3. Log in as `member1@…`, RSVP to the **waitlist** event → see the waitlist
   position; the confirmation email prints in the gunicorn log.
4. Log in as `lead@…` → `/leads/events` → the **invite-only approval queue**,
   the **check-in scanner/kiosk**, CSV export.
5. `admin@…` → `/admin` — full Django admin, audit log, all resources.

---

## Notes / gotchas

- **Settings:** `config.settings.showcase` (inherits prod; TLS-at-edge tweaks,
  cross-subdomain shared login, inline Celery, console email). It is exercised
  only here — the 202-test suite runs under `config.settings.test`.
- **Email** prints to the gunicorn log by default. Set `MAILGUN_API_KEY` (+
  `MAILGUN_SENDER_DOMAIN`) in the env to send real mail.
- **2FA** is off for a frictionless demo. Set `REQUIRE_2FA_FOR_PRIVILEGED=1`
  to showcase TOTP enrolment on admin/lead accounts.
- **reCAPTCHA** uses Google's public test keys (they always pass; the widget
  shows a "for testing" note). Set `RECAPTCHA_PUBLIC_KEY`/`_PRIVATE_KEY` for
  real keys.
- **Media** (uploaded images) is served off local disk by Django. Fine for a
  demo; wire S3 (`AWS_STORAGE_BUCKET_NAME`) for real traffic.
- This is a **demo** posture, not a hardened production deploy (single host,
  seeded data, relaxed HSTS/2FA). Don't leave it exposed long-term as-is.
```
