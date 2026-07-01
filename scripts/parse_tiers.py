#!/usr/bin/env python3
"""Step 2.5 — clean tier extraction (deterministic, no LLM).

Renders each pricing page with Playwright, then extracts plan tiers as
{name, price, period} by locating the pricing GRID: the sibling group whose
children each contain both a price and a plan heading. This one generic
heuristic covers most sites; sites it misses get a per-site override in
SELECTORS below (this is the "site-specific selector" maintenance the project
accepts in exchange for zero API cost).

Output: data/tiers.json
"""
import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "data" / "tools.json"
OUT = ROOT / "data" / "tiers.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

# Per-site overrides for sites the generic extractor can't handle (page-builder DOMs).
# id -> {card: css for each plan card, name: css for the plan-name element, words: how
# many leading words of the name to keep}. Verified against the live DOM.
SELECTORS: dict[str, dict] = {
    "teachable": {"card": "div.pricing-green_component", "name": "div[class*=title]", "words": 1},
}

# Override extractor: pull cards by explicit per-site selectors.
OVERRIDE_JS = r"""
(sel) => {
  return [...document.querySelectorAll(sel.card)].map(c => {
    const h = c.querySelector(sel.name) || c;
    const raw = h.textContent.trim().replace(/\s+/g, ' ')
                 .replace(/([a-z])([A-Z])/g, '$1 $2')
                 .split(/\s*(?:Save|\$)/i)[0].trim()
                 .split(' ').slice(0, sel.words || 1).join(' ');
    const cleaned = c.textContent.replace(/save\s*\$\s?\d[\d.,]*/ig, ' ');
    let price = null, period = null, m;
    if ((m = cleaned.match(/\$\s?(\d{1,4})\s*\/?\s*(?:mo|month)/i))) { price = +m[1]; period = 'mo'; }
    else if ((m = cleaned.match(/\$\s?(\d{1,4})/))) { price = +m[1]; }
    return {raw, price, period};
  }).filter(x => x.price != null);
}
"""

# Combined extractor: find the pricing GRID (sibling group with the most price+heading
# cards) so each price stays card-scoped (fixes cross-tier price collisions), then NAME
# each card by matching the seed plan names (fixes add-on/promo/savings name noise).
GENERIC_JS = r"""
(names) => {
  const priceRe = /\$\s?\d{1,4}(?:[.,]\d{2})?/;
  const headSel = 'h1,h2,h3,h4,h5,h6,[class*=name i],[class*=title i],[class*=plan i]';
  const candidates = [];
  document.querySelectorAll('*').forEach(p => {
    const kids = [...p.children];
    if (kids.length < 2 || kids.length > 10) return;
    const cards = kids.filter(k => priceRe.test(k.textContent) && k.querySelector(headSel));
    if (cards.length >= 2) candidates.push([p, cards]);
  });
  // most cards wins; tie-break: the tightest container (least total text) = the grid, not a page wrapper
  candidates.sort((a, b) => b[1].length - a[1].length || a[0].textContent.length - b[0].textContent.length);
  const best = candidates[0];
  if (!best) return [];
  // Return cards in DOM order with card-scoped price + a tentative heading name.
  // Python maps the ordered seed plan names onto these by position (see extract()).
  const out = [];
  for (const card of best[1]) {
    const head = card.querySelector(headSel);
    const raw = head ? head.textContent.trim().replace(/\s+/g, ' ')
                           .replace(/([a-z])([A-Z])/g, '$1 $2')
                           .split(/\s*(?:Save|\$)/i)[0].trim()
                           .split(' ').slice(0, 2).join(' ') : null;
    const cleaned = card.textContent.replace(/save\s*\$\s?\d[\d.,]*/ig, ' ');
    let price = null, period = null, m;
    if ((m = cleaned.match(/\$\s?(\d{1,4})\s*\/?\s*(?:mo|month)/i))) { price = +m[1]; period = 'mo'; }
    else if ((m = cleaned.match(/\$\s?(\d{1,4})\s*\/?\s*(?:yr|year)/i))) { price = +m[1]; period = 'yr'; }
    else if ((m = cleaned.match(/\$\s?(\d{1,4})/))) { price = +m[1]; }
    if (price != null) out.push({raw, price, period});
  }
  return out;
}
"""


def extract(page, tool):
    """Get ordered grid cards, then map seed plan names onto them by position.

    Positional mapping sidesteps DOM name-noise: the grid already yields prices in
    plan order, and the seed lists names in the same order. We trust seed names only
    when the card count matches the seed count (name_source='seed'); otherwise we keep
    the scraped heading and flag it (name_source='scraped') so it's an obvious override
    candidate rather than a silent mislabel.
    """
    if tool["id"] in SELECTORS:
        cards = page.evaluate(OVERRIDE_JS, SELECTORS[tool["id"]])
        out, seen = [], set()  # monthly grid comes first; keep first price per plan name
        for c in cards:
            if c["raw"] in seen:
                continue
            seen.add(c["raw"])
            out.append({"name": c["raw"], "price": c["price"],
                        "period": c["period"], "name_source": "override"})
        return out
    seed = [t["name"] for t in tool.get("pricing_tiers", [])]
    cards = page.evaluate(GENERIC_JS, seed)
    aligned = len(cards) == len(seed) and len(seed) >= 2
    tiers = []
    for i, c in enumerate(cards):
        name = seed[i] if aligned else (c["raw"] or f"Tier {i + 1}")
        tiers.append({"name": name, "price": c["price"], "period": c["period"],
                      "name_source": "seed" if aligned else "scraped"})
    return tiers


def main():
    tools = json.loads(TOOLS.read_text())["tools"]
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for t in tools:
            rec = {"id": t["id"], "name": t["name"], "tiers": [], "status": None}
            page = b.new_page(user_agent=UA)
            try:
                page.goto(t["pricing_page"], wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3500)  # let client-side pricing render
                tiers = extract(page, t)
                rec["tiers"] = tiers
                # Trust only when the grid aligned to the seed (name_source=seed);
                # scraped-name rows are flagged for a per-site selector, not shipped as clean.
                trusted = len(tiers) >= 2 and all(
                    x["name_source"] in ("seed", "override") for x in tiers)
                rec["status"] = "ok" if trusted else "needs_override"
            except Exception as e:
                rec["status"] = f"error: {type(e).__name__}"
            finally:
                page.close()
            results.append(rec)
        b.close()

    stamp = os.environ.get("SCRAPED_AT", "unknown")
    OUT.write_text(json.dumps({"scraped_at": stamp, "results": results},
                              ensure_ascii=False, indent=2))
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"clean tiers for {ok}/{len(results)} -> {OUT}")
    for r in results:
        tiers = ", ".join(f"{x['name']}=${x['price']}/{x['period'] or '?'}" for x in r["tiers"])
        print(f"  {r['id']:14} {r['status']:16} {tiers or '-'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
