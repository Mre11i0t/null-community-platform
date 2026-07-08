# Adding the CI workflows

Three GitHub Actions workflows are prepared in `.github/workflows/` in your
local working tree but were **not pushed**, because the `gh` token used for the
initial push lacks the `workflow` OAuth scope. GitHub refuses to accept commits
that touch `.github/workflows/` without it.

The files (already written, ready to go):

- `.github/workflows/ci.yml` — pytest + migrations check + prod deploy-check (MySQL/Redis services)
- `.github/workflows/codeql.yml` — weekly Python security analysis
- `.github/workflows/secrets-scan.yml` — gitleaks on every push/PR

## To add them (pick one)

### Option A — grant the scope, then commit + push (recommended)

```bash
gh auth refresh -s workflow        # opens a browser to approve the workflow scope
cd <repo>
git add .github/workflows/
git commit -m "ci: add test, CodeQL, and secret-scan workflows"
git push origin main
```

### Option B — add them via the GitHub web UI

For each file, GitHub → your repo → **Add file → Create new file**, paste the
path (e.g. `.github/workflows/ci.yml`) and the contents from your local copy,
commit. The web UI runs as *you*, so the workflow scope isn't an issue.

Once pushed, CI runs on every push/PR to `main`.

---

*Made with [Claude Code](https://claude.com/claude-code).*
