#!/usr/bin/env python3
"""Step 3 — generate the static comparison site from human-verified curated.json.

Output: site/index.html (comparison table) + site/tools/<id>.html (per tool).
Pure stdlib, no framework. Affiliate links are rel="sponsored nofollow" (correct
SEO disclosure) and point at each program's signup URL — swap in your own ref ID
after you're approved. The "data verified on <date>" badge is the moat signal.
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "curated.json"
TIERS = ROOT / "data" / "tiers.json"  # fresh scrape; prices overlaid onto curated when safe
SITE = ROOT / "site"

CSS = """
:root{--fg:#1a1a2e;--mut:#6b7280;--acc:#3b5bdb;--bg:#f7f8fc;--card:#fff;--line:#e5e7eb}
*{box-sizing:border-box}body{margin:0;font:16px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:var(--fg);background:var(--bg)}
.wrap{max-width:960px;margin:0 auto;padding:32px 20px}
h1{font-size:2rem;margin:.2em 0}h2{margin-top:1.6em}a{color:var(--acc)}
.badge{display:inline-block;background:#e7f5ff;color:#1971c2;border:1px solid #a5d8ff;border-radius:999px;padding:2px 12px;font-size:.85rem;font-weight:600}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;margin:1em 0}
th,td{padding:12px 14px;text-align:left;border-bottom:1px solid var(--line)}
th{background:#f1f3f9;font-size:.85rem;letter-spacing:.02em;text-transform:uppercase;color:var(--mut)}
tr:last-child td{border-bottom:0}
.pay{color:#2b8a3e;font-weight:600}
.btn{display:inline-block;background:var(--acc);color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600}
.mut{color:var(--mut);font-size:.9rem}
footer{margin-top:3em;padding-top:1.2em;border-top:1px solid var(--line);color:var(--mut);font-size:.85rem}
"""


def page(title, body):
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
            f"<body><div class='wrap'>{body}"
            f"<footer><strong>Affiliate disclosure:</strong> some links are affiliate links "
            f"(rel=sponsored). We may earn a commission at no extra cost to you. "
            f"Pricing is auto-collected and human-verified; always confirm on the vendor's site."
            f"</footer></div></body></html>")


def aff_link(tool, label, cls="btn"):
    url = html.escape(tool["affiliate"]["program_url"])
    return f"<a class='{cls}' href='{url}' rel='sponsored nofollow' target='_blank'>{html.escape(label)}</a>"


def paid_tiers(tool):
    return [t for t in tool["tiers"] if t["monthly_usd"] > 0]


def start_price(tool):
    paid = paid_tiers(tool)
    return min(t["monthly_usd"] for t in paid) if paid else 0


def build_index(data):
    rows = []
    for t in sorted(data["tools"], key=start_price):
        sp = start_price(t)
        rows.append(
            f"<tr><td><a href='tools/{t['id']}.html'>{html.escape(t['name'])}</a></td>"
            f"<td>{html.escape(t['category'])}</td>"
            f"<td>${sp}/mo</td><td>{len(t['tiers'])}</td>"
            f"<td class='pay'>{html.escape(t['affiliate']['rate_approx'])}</td>"
            f"<td>{aff_link(t, 'Visit', 'btn')}</td></tr>")
    body = (
        f"<h1>Online Business Builder SaaS — Compared</h1>"
        f"<p><span class='badge'>Pricing verified {html.escape(data['verified_on'])}</span></p>"
        f"<p class='mut'>Funnel, checkout, course &amp; all-in-one platforms, ranked by "
        f"starting price. Data auto-collected and human-checked.</p>"
        f"<table><thead><tr><th>Tool</th><th>Category</th><th>From</th><th>Plans</th>"
        f"<th>Affiliate payout</th><th></th></tr></thead><tbody>{''.join(rows)}</tbody></table>")
    return page("Online Business Builder SaaS — Compared", body)


def build_tool(tool):
    trows = "".join(
        f"<tr><td>{html.escape(t['name'])}</td>"
        f"<td>{'Free' if t['monthly_usd'] == 0 else '$' + str(t['monthly_usd']) + '/mo'}</td></tr>"
        for t in tool["tiers"])
    body = (
        f"<p><a href='../index.html'>&larr; All tools</a></p>"
        f"<h1>{html.escape(tool['name'])}</h1>"
        f"<p class='mut'>{html.escape(tool['category'])} · "
        f"<a href='{html.escape(tool['website'])}' rel='nofollow' target='_blank'>website</a></p>"
        f"<h2>Pricing</h2><table><thead><tr><th>Plan</th><th>Monthly</th></tr></thead>"
        f"<tbody>{trows}</tbody></table>"
        f"<p><strong>Affiliate:</strong> {html.escape(tool['affiliate']['rate_approx'])} "
        f"({html.escape(tool['affiliate']['model'])})</p>"
        f"<p>{aff_link(tool, 'Get ' + tool['name'])}</p>")
    return page(f"{tool['name']} pricing & review", body)


def merge_fresh(data):
    """Overlay fresh scraped prices from tiers.json onto the curated tools — but only
    when the fresh extraction is SAFE for that tool: same tier count as curated and
    plausible, strictly-increasing paid prices. Otherwise keep the human-verified
    curated prices. This is what makes the cron refresh actually update prices without
    letting scrape noise (e.g. samcart's $7/$19) reach the page.
    Returns the freshest verification date to badge.
    """
    if not TIERS.exists():
        return data["verified_on"]
    fresh = {r["id"]: r["tiers"] for r in json.loads(TIERS.read_text())["results"]}
    fresh_date = json.loads(TIERS.read_text()).get("scraped_at", data["verified_on"])
    updated = False
    for tool in data["tools"]:
        ft = fresh.get(tool["id"])
        if not ft or len(ft) != len(tool["tiers"]):
            continue
        prices = [t["price"] for t in ft]
        paid = [p for p in prices if p and p > 0]
        plausible = all(p is not None and 0 <= p <= 2000 for p in prices) and \
            paid == sorted(paid) and len(set(paid)) == len(paid)
        if not plausible:
            continue
        for curated_tier, p in zip(tool["tiers"], prices):
            curated_tier["monthly_usd"] = p
        updated = True
    return fresh_date if updated else data["verified_on"]


def main():
    data = json.loads(DATA.read_text())
    data["verified_on"] = merge_fresh(data)
    (SITE / "tools").mkdir(parents=True, exist_ok=True)
    (SITE / "index.html").write_text(build_index(data))
    for t in data["tools"]:
        (SITE / "tools" / f"{t['id']}.html").write_text(build_tool(t))
    print(f"built site/index.html + {len(data['tools'])} tool pages -> {SITE}")


if __name__ == "__main__":
    main()
