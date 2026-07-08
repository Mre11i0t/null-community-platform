# Documentation

Project documentation for the **null-community-platform** — a Django rewrite of
the null.community *swachalit* platform, with a multi-tenant chapter-sites
architecture.

| Doc | What it covers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Multi-tenant host routing, app layout, settings layering, background jobs |
| [FEATURES.md](FEATURES.md) | Full feature catalogue by audience (Guest / Member / Leader / Admin / API) |
| [DATA_MODEL.md](DATA_MODEL.md) | Core domain models, fields, and relationships |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Local setup, seed data, management commands, running tests |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production + Mac-Mini/Cloudflare showcase deploy, environment variables |
| [UPGRADING.md](UPGRADING.md) | Keeping the codebase alive: dependency/Django/Python upgrades, migration paths |
| [ROADMAP.md](ROADMAP.md) | Deliberately-deferred features and improvement ideas |
| [rev3-delivery-audit.md](rev3-delivery-audit.md) | Adversarial audit of the Rev 3 "delivered" claim + the fixes it produced |

> **Note on domains.** Docs use `example.com` and `sub.example.com` as
> placeholders. Substitute your own `ROOT_DOMAIN`; nothing in the tracked
> codebase hardcodes a real deployment domain (the live `.env` is gitignored).

---

*Made with [Claude Code](https://claude.com/claude-code).*
