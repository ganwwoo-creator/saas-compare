#!/usr/bin/env python3
"""Step 2 — data collector for the SaaS comparison site.

For each tool in data/tools.json, fetch its public pricing_page and extract the
monthly prices shown. Static fetch (urllib) is tried first; if it yields too few
prices (JS-rendered site), fall back to a headless Playwright render.

Output: data/scraped.json — {id, scraped_at, method, status, prices_found}.
This is the freshness layer that makes the site's data a moat (accurate, current
pricing = exactly what Google 2026 rewards). Tier-name -> price pairing is a later
step; here we reliably capture the price set and flag anything that failed.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "data" / "tools.json"
OUT = ROOT / "data" / "scraped.json"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
# Monthly SaaS prices in this niche sit roughly $9-$999. Filter out noise like $2 (favicon sizes, footnotes).
PRICE_RE = re.compile(r"\$\s?([0-9]{2,4})\b")
MIN_PRICES = 2  # fewer than this from static HTML => treat as JS-rendered, escalate to Playwright


def prices_from_html(html: str) -> list[int]:
    found = {int(m) for m in PRICE_RE.findall(html)}
    # keep plausible monthly SaaS prices; drop absurdly small/large
    return sorted(p for p in found if 9 <= p <= 999)


def fetch_static(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def fetch_rendered(url: str) -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA)
        page.goto(url, wait_until="networkidle", timeout=45000)
        html = page.content()
        browser.close()
        return html


def collect_one(tool: dict) -> dict:
    url = tool["pricing_page"]
    rec = {"id": tool["id"], "name": tool["name"], "method": None,
           "status": None, "prices_found": []}
    try:
        html = fetch_static(url)
        prices = prices_from_html(html)
        rec.update(method="static", prices_found=prices)
        if len(prices) >= MIN_PRICES:
            rec["status"] = "ok"
            return rec
        # too few => JS-rendered, escalate
        html = fetch_rendered(url)
        prices = prices_from_html(html)
        rec.update(method="playwright", prices_found=prices,
                   status="ok" if len(prices) >= MIN_PRICES else "no_prices")
    except Exception as e:  # network/render failure — record, don't crash the run
        rec["status"] = f"error: {type(e).__name__}: {e}"
    return rec


def main() -> int:
    data = json.loads(TOOLS.read_text())
    results = [collect_one(t) for t in data["tools"]]
    # scraped_at is stamped by the caller/CI via env to keep this deterministic;
    # fall back to a placeholder so the file is self-describing.
    import os
    stamp = os.environ.get("SCRAPED_AT", "unknown")
    OUT.write_text(json.dumps({"scraped_at": stamp, "results": results}, indent=2))
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"collected {ok}/{len(results)} ok -> {OUT}")
    for r in results:
        print(f"  {r['id']:14} {r['method'] or '-':10} {r['status']:20} {r['prices_found']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
