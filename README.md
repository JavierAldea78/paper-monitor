# paper-monitor

Paper monitoring workflow for brewing and food science topics.

## Development

Use GitHub Codespaces as the Linux development backend. The intended daily flow is:

```text
VS Code local -> remote/tunnel -> Codespace Linux -> /workspaces/paper-monitor -> Claude Code
```

See:

- [docs/devex-codespaces-claude.md](docs/devex-codespaces-claude.md) for the reusable pattern across projects.
- [docs/devex-codespaces.md](docs/devex-codespaces.md) for the `paper-monitor` specific operating notes.

## Environment variables

All API keys are optional. The script runs without any of them (Semantic Scholar falls back to unauthenticated mode; PubMed uses the public rate limit; Zotero push is skipped).

| Variable | Service | Effect when set |
|---|---|---|
| `S2_API_KEY` | Semantic Scholar | Raises rate limit to 1 req/s; avoids 429 degradation |
| `NCBI_API_KEY` | PubMed / NCBI | Raises rate limit from 3 req/s to 10 req/s |
| `ZOTERO_API_KEY` | Zotero | Enables push of high-score papers to your library |
| `ZOTERO_USER_ID` | Zotero | Required together with `ZOTERO_API_KEY` |

### Local development

```bash
# One-time: copy the example file (already in .gitignore)
cp .env.example .env
# Edit .env and fill in the keys you want, then:
export $(grep -v '^#' .env | xargs)
python scripts/fetch_papers.py
```

### GitHub Actions

Add each key as a repository secret (`Settings → Secrets and variables → Actions`). They are already wired in `.github/workflows/weekly.yml`.

### GitHub Codespaces

Add secrets at `github.com/settings/codespaces`. They are injected automatically into every Codespace — no `.env` file needed.

**Never commit `.env` or any file containing real API key values.**
