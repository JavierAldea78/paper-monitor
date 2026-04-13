#!/usr/bin/env python3
"""
Send HTML newsletter with top papers via Gmail SMTP.
Required env vars: GMAIL_USER, GMAIL_APP_PASSWORD, NEWSLETTER_TO
Optional env vars: PAGES_URL
"""

import json
import os
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

REPO_ROOT   = Path(__file__).parent.parent
PAPERS_JSON = REPO_ROOT / "papers.json"

GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
NEWSLETTER_TO      = os.environ["NEWSLETTER_TO"]   # comma-separated addresses
PAGES_URL          = os.environ.get("PAGES_URL", "https://javieraldea78.github.io/paper-monitor/")

DOMAIN_COLORS = {
    "NOLO":    "#0ea5e9",
    "Quality": "#10b981",
    "BSG":     "#f59e0b",
    "Biotech": "#8b5cf6",
    "Process": "#ef4444",
}

# ── HTML builder ───────────────────────────────────────────────────────────────

def badge(text: str, color: str) -> str:
    return (f'<span style="background:{color};color:#fff;padding:2px 8px;'
            f'border-radius:12px;font-size:11px;font-weight:600;">{text}</span>')


def paper_row(p: dict) -> str:
    color   = DOMAIN_COLORS.get(p.get("domain",""), "#64748b")
    doi_lnk = (f'<a href="{p["doi_url"]}" style="color:#3b82f6;">'
               f'{p["doi"][:40]}…</a>' if p.get("doi_url") else "—")
    score   = p.get("score", 0)
    score_color = "#10b981" if score >= 60 else ("#f59e0b" if score >= 40 else "#64748b")
    return f"""
        <tr>
          <td style="padding:10px 8px;border-bottom:1px solid #1e293b;vertical-align:top;width:60%;">
            <strong style="color:#f1f5f9;font-size:13px;">{p['title'][:120]}</strong><br>
            <span style="color:#94a3b8;font-size:11px;">
              {p.get('authors','')} &bull; {p.get('journal','')} &bull; {p.get('year','')}
            </span><br>
            <span style="margin-top:4px;display:inline-block;">
              {badge(p.get('domain',''), color)}
            </span>
          </td>
          <td style="padding:10px 8px;border-bottom:1px solid #1e293b;text-align:center;width:10%;">
            <span style="color:{score_color};font-weight:700;font-size:15px;">{score}</span>
          </td>
          <td style="padding:10px 8px;border-bottom:1px solid #1e293b;width:30%;font-size:11px;">
            {doi_lnk}
          </td>
        </tr>"""


def build_html(papers: list[dict], today: str) -> str:
    top = papers[:60]  # cap at 60 papers in email

    # Group by domain, sorted by score within each
    by_domain: dict[str, list] = {}
    for p in top:
        by_domain.setdefault(p.get("domain", "General"), []).append(p)

    sections = ""
    for domain in sorted(by_domain):
        color = DOMAIN_COLORS.get(domain, "#64748b")
        rows  = "".join(paper_row(p) for p in by_domain[domain][:15])
        sections += f"""
        <h2 style="color:#f1f5f9;margin:32px 0 8px;padding-bottom:6px;
                   border-bottom:2px solid {color};">{domain}</h2>
        <table style="width:100%;border-collapse:collapse;">
          <thead>
            <tr style="background:#1e293b;">
              <th style="padding:8px;text-align:left;color:#94a3b8;font-size:11px;font-weight:600;">TITLE</th>
              <th style="padding:8px;text-align:center;color:#94a3b8;font-size:11px;font-weight:600;">SCORE</th>
              <th style="padding:8px;text-align:left;color:#94a3b8;font-size:11px;font-weight:600;">DOI</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:800px;margin:0 auto;padding:24px;">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1e3a5f,#1e293b);
                padding:32px;border-radius:12px;margin-bottom:32px;
                border:1px solid #334155;">
      <div style="display:flex;align-items:center;gap:12px;">
        <div style="width:40px;height:40px;background:#3b82f6;border-radius:8px;
                    display:flex;align-items:center;justify-content:center;
                    font-size:20px;">&#128270;</div>
        <div>
          <h1 style="color:#f1f5f9;margin:0;font-size:22px;font-weight:700;">Tech Vigilance</h1>
          <p style="color:#94a3b8;margin:4px 0 0;font-size:13px;">
            Weekly digest &bull; {today} &bull; {len(papers)} papers found
          </p>
        </div>
      </div>
    </div>

    <!-- Body -->
    {sections}

    <!-- Footer -->
    <div style="margin-top:40px;padding:20px;border-top:1px solid #334155;text-align:center;">
      <a href="{PAGES_URL}" style="display:inline-block;background:#3b82f6;color:#fff;
               padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:13px;">
        Open Dashboard &#8599;
      </a>
      <p style="color:#475569;font-size:11px;margin-top:16px;">
        Sources: PubMed &bull; Semantic Scholar &bull; Europe PMC &bull; Last {90} days
      </p>
    </div>

  </div>
</body>
</html>"""

# ── Send ───────────────────────────────────────────────────────────────────────

def main():
    today   = datetime.date.today().isoformat()
    papers  = json.loads(PAPERS_JSON.read_text(encoding="utf-8"))

    if not papers:
        print("No papers in papers.json — skipping newsletter.")
        return

    recipients = [r.strip() for r in NEWSLETTER_TO.split(",") if r.strip()]
    html       = build_html(papers, today)

    msg              = MIMEMultipart("alternative")
    msg["Subject"]   = f"Tech Vigilance — {today} ({len(papers)} papers)"
    msg["From"]      = GMAIL_USER
    msg["To"]        = ", ".join(recipients)
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_USER, recipients, msg.as_string())

    print(f"Newsletter sent → {recipients}  ({today}, {len(papers)} papers)")


if __name__ == "__main__":
    main()
