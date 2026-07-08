#!/usr/bin/env bash
# Publish the docs/ set to the repo's GitHub Wiki.
#
# PREREQUISITE: the wiki must exist first. GitHub only enables wikis on
# public repos (or private repos on a paid plan), and the wiki's git repo
# doesn't exist until its first page is created in the web UI:
#   repo → Wiki tab → "Create the first page" → save.
# After that, run this script to publish every doc as a wiki page.
#
# Usage: ./scripts/publish_wiki.sh <github-owner/repo>
#   e.g. ./scripts/publish_wiki.sh Mre11i0t/null-community-platform
set -euo pipefail
REPO_SLUG="${1:?usage: publish_wiki.sh <owner/repo>}"
SRC="$(cd "$(dirname "$0")/.." && pwd)/docs"
WORK="$(mktemp -d)"

echo "==> Cloning wiki for $REPO_SLUG"
git clone "https://github.com/${REPO_SLUG}.wiki.git" "$WORK"

echo "==> Copying docs → wiki pages"
# GitHub wiki page name = filename without extension; keep it simple.
cp "$SRC/ARCHITECTURE.md"        "$WORK/Architecture.md"
cp "$SRC/FEATURES.md"            "$WORK/Features.md"
cp "$SRC/DATA_MODEL.md"          "$WORK/Data-Model.md"
cp "$SRC/DEVELOPMENT.md"         "$WORK/Development.md"
cp "$SRC/DEPLOYMENT.md"          "$WORK/Deployment.md"
cp "$SRC/UPGRADING.md"           "$WORK/Upgrading.md"
cp "$SRC/ROADMAP.md"             "$WORK/Roadmap.md"
[ -f "$SRC/rev3-delivery-audit.md" ] && cp "$SRC/rev3-delivery-audit.md" "$WORK/Rev3-Delivery-Audit.md"

cat > "$WORK/Home.md" <<'MD'
# null Community Platform — Wiki

A Django rewrite of the null.community **swachalit** platform, with a
multi-tenant chapter-sites architecture.

- [[Architecture]] — host routing, app layout, settings, background jobs
- [[Features]] — full feature catalogue by audience
- [[Data-Model]] — core domain models and relationships
- [[Development]] — local setup, seed data, tests
- [[Deployment]] — production + showcase deploy, env vars
- [[Upgrading]] — keeping the codebase alive: Django/Python/deps upgrades
- [[Roadmap]] — deferred features + improvement ideas
- [[Rev3-Delivery-Audit]] — the adversarial delivery audit

---

*Made with [Claude Code](https://claude.com/claude-code).*
MD

cd "$WORK"
git add -A
git -c user.email=noreply@claude.com -c user.name="Claude Code" commit -q -m "Publish documentation to wiki" || { echo "  nothing to publish"; exit 0; }
git push origin HEAD 2>&1 | tail -2
echo "==> Wiki published: https://github.com/${REPO_SLUG}/wiki"
rm -rf "$WORK"
