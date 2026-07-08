# Showcase deployment — Mac Mini + Cloudflare Tunnel

Stand up the platform on a Mac Mini and expose it at `example.com` with
real chapter subdomains, for a next-day demo. Cloudflare terminates TLS at its
edge, so **no Caddy / no certificates to manage** — a tunnel forwards HTTPS to
a local gunicorn.

```
browser ──https──▶ Cloudflare edge ──tunnel──▶ cloudflared ──http──▶ gunicorn 127.0.0.1:8000
  example.com            (TLS here)                              (Django, showcase settings)
  delhi.example.com
  bangalore.example.com
  goa.example.com
```

**Domain scheme.** The root directory lives at the **apex** and chapters are
**one level** under it (`delhi.example.com`). One level is the deepest
that Cloudflare's **free** Universal SSL wildcard (`*.example.com`)
covers — a nested scheme like `bangalore.null.example.com` would need the
paid Advanced Certificate Manager, so it is deliberately avoided here.

> **Heads-up — this temporarily takes over your apex.** Routing
> `example.com` through the tunnel replaces whatever your apex shows today
> with the null root directory, for the duration of the demo. Removing the
> apex route (or stopping the tunnel) restores it instantly. If you'd rather
> keep your personal homepage live, skip the apex route below and enter the
> demo at `bangalore.example.com` instead (you just lose the
> root-directory page). We route **only** the apex + three named city
> subdomains — no
> wildcard — so any *other* subdomains you already use are untouched.

Prereqs: Docker Desktop (running), the repo's `venv`, and `example.com` on
Cloudflare.

---

## Part 1 — Cloudflare Tunnel (one-time, interactive)

```bash
brew install cloudflared
cloudflared tunnel login                 # opens a browser; pick example.com
cloudflared tunnel create null-showcase  # note the Tunnel ID it prints
```

Create `~/.cloudflared/config.yml` (substitute the Tunnel ID and your macOS
user). We list the hostnames **explicitly** — no wildcard — so only these four
are served by the app:

```yaml
tunnel: <TUNNEL-ID>
credentials-file: /Users/<you>/.cloudflared/<TUNNEL-ID>.json
ingress:
  - hostname: "example.com"            # root directory (omit this line to keep your apex page)
    service: http://127.0.0.1:8000
  - hostname: "delhi.example.com"
    service: http://127.0.0.1:8000
  - hostname: "bangalore.example.com"
    service: http://127.0.0.1:8000
  - hostname: "goa.example.com"
    service: http://127.0.0.1:8000
  - service: http_status:404
```

Point DNS at the tunnel (one per hostname; drop the apex line to keep your
personal homepage):

```bash
cloudflared tunnel route dns null-showcase example.com
cloudflared tunnel route dns null-showcase delhi.example.com
cloudflared tunnel route dns null-showcase bangalore.example.com
cloudflared tunnel route dns null-showcase goa.example.com
```

Each command adds a **proxied (orange-cloud) CNAME** to
`<TUNNEL-ID>.cfargotunnel.com`; you can also add them by hand in **DNS → Add
record**. The orange cloud is what puts the free Universal SSL cert in front.

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

Open **https://example.com** (root directory) and
**https://bangalore.example.com** (the populated Bangalore chapter). Done.

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
| `lead@example.com` | Bangalore chapter lead → `/leads/...` |
| `speaker@example.com` | speaker with past sessions |
| `member1@example.com` … `member6@example.com` | attendees |

Chapters: **delhi**, **bangalore**, **goa** (`<sub>.<ROOT_DOMAIN>`).
**Bangalore** is the populated demo chapter — its events are wired for
**check-in**, **waitlist**, **invite-only approval**, and a **just-ended**
event. Delhi and Goa are empty shells (routable, no content). Re-home the demo
by changing `PRIMARY_CHAPTER` at the top of `scripts/seed_rev3_data.py` and
re-seeding.

### Suggested tour
1. `https://example.com` — root directory: three chapters + collective
   stats (Part 0 architecture).
2. `https://bangalore.example.com` — chapter homepage, upcoming events,
   archives.
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
