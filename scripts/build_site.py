#!/usr/bin/env python3
"""Step 3 — generate the static comparison site from human-verified curated.json.

Output: site/index.html (comparison table) + site/tools/<id>.html (per tool).
Pure stdlib, no framework. Affiliate links are rel="sponsored nofollow" (correct
SEO disclosure) and point at each program's signup URL — swap in your own ref ID
after you're approved. The "data verified on <date>" badge is the moat signal.
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "curated.json"
TIERS = ROOT / "data" / "tiers.json"  # fresh scrape; prices overlaid onto curated when safe
CONTENT = ROOT / "content"  # guide article fragments (Korean, target real search demand)
SITE = ROOT / "site"
BASE_URL = "https://ganwwoo-creator.github.io/saas-compare"

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
.btn{display:inline-block;background:var(--acc);color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600;white-space:nowrap}
.mut{color:var(--mut);font-size:.9rem}
.free{display:inline-block;background:#ebfbee;color:#2b8a3e;border:1px solid #b2f2bb;border-radius:999px;padding:1px 10px;font-size:.8rem;font-weight:600;margin-left:6px}
.callout{background:#fff9db;border:1px solid #ffe066;border-radius:12px;padding:14px 18px;margin:1em 0}
.guides{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:6px 18px;margin:1em 0}
.guides li{margin:.5em 0}
article h2{margin-top:1.8em}article h3{margin-top:1.3em}
footer{margin-top:3em;padding-top:1.2em;border-top:1px solid var(--line);color:var(--mut);font-size:.85rem}
"""


def page(title, body):
    return (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<meta name='google-site-verification' "
            f"content='7LufQyBjdjB0oki2FLN222vLHq7l7K1CoA_L5jmdlHA'>"
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
            f"<body><div class='wrap'>{body}"
            f"<footer><strong>제휴 안내:</strong> 일부 링크는 제휴 링크입니다. "
            f"링크를 통해 가입하셔도 추가 비용은 없으며, 저희가 소정의 수수료를 받을 수 있습니다. "
            f"가격은 자동 수집 후 사람이 확인한 것으로, 최종 가격은 각 공식 사이트에서 꼭 확인하세요."
            f"</footer></div></body></html>")


def aff_link(tool, label, cls="btn"):
    url = html.escape(tool["affiliate"]["program_url"])
    return f"<a class='{cls}' href='{url}' rel='sponsored nofollow' target='_blank'>{html.escape(label)}</a>"


def paid_tiers(tool):
    return [t for t in tool["tiers"] if t["monthly_usd"] > 0]


def start_price(tool):
    paid = paid_tiers(tool)
    return min(t["monthly_usd"] for t in paid) if paid else 0


CATEGORY_KO = {"all-in-one": "올인원", "funnel": "판매 퍼널", "course": "온라인 강의",
               "email": "이메일", "checkout": "결제", "website": "홈페이지"}


def has_free(tool):
    return any(x["monthly_usd"] == 0 for x in tool["tiers"])


def build_index(data, guides):
    rows = []
    for t in sorted(data["tools"], key=start_price):
        sp = start_price(t)
        cat = CATEGORY_KO.get(t["category"], t["category"])
        free = "<span class='free'>무료 시작</span>" if has_free(t) else ""
        rows.append(
            f"<tr><td><a href='tools/{t['id']}.html'>{html.escape(t['name'])}</a>{free}"
            f"<div class='mut'>{html.escape(t.get('desc_ko', ''))}</div></td>"
            f"<td>{html.escape(cat)}</td>"
            f"<td>{'무료~' if has_free(t) else ''}월 ${sp}</td>"
            f"<td>{aff_link(t, '보러가기', 'btn')}</td></tr>")
    free_tools = [t for t in data["tools"] if has_free(t)]
    free_names = ", ".join(
        f"<a href='tools/{t['id']}.html'>{html.escape(t['name'])}</a>" for t in free_tools)
    guide_links = "".join(
        f"<li><a href='guides/{g['slug']}.html'>{html.escape(g['title'])}</a></li>" for g in guides)
    body = (
        f"<h1>온라인 강의·홈페이지 제작 도구 가격 비교</h1>"
        f"<p><span class='badge'>가격 확인일 {html.escape(data['verified_on'])}</span></p>"
        f"<p class='mut'>온라인 강의 판매, 홈페이지·판매 페이지 제작, 이메일 마케팅 도구를 "
        f"시작 가격이 싼 순서로 정리했습니다. 가격은 자동으로 매주 갱신됩니다.</p>"
        f"<div class='callout'>💡 <strong>돈 안 들이고 시작하고 싶다면:</strong> {free_names}"
        f" — 무료 플랜으로 먼저 써 보고, 필요할 때만 유료로 올리면 됩니다.</div>"
        f"<table><thead><tr><th>도구</th><th>종류</th><th>시작 가격</th>"
        f"<th></th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
        f"<h2>가이드</h2><div class='guides'><ul>{guide_links}</ul></div>"
        f"<h2>참고하세요</h2>"
        f"<p class='mut'>모두 해외 서비스라 화면은 기본 영어이고, 결제에는 해외 결제가 되는 "
        f"카드(비자·마스터 등)가 필요합니다. 표시 가격은 달러(USD)이며 대부분 연 단위 결제 기준 "
        f"월 환산 가격입니다.</p>")
    return page("온라인 강의·홈페이지 제작 도구 가격 비교 (2026)", body)


def build_tool(tool):
    trows = "".join(
        f"<tr><td>{html.escape(t['name'])}</td>"
        f"<td>{'무료' if t['monthly_usd'] == 0 else '월 $' + str(t['monthly_usd'])}</td></tr>"
        for t in tool["tiers"])
    cat = CATEGORY_KO.get(tool["category"], tool["category"])
    body = (
        f"<p><a href='../index.html'>&larr; 전체 비교표로</a></p>"
        f"<h1>{html.escape(tool['name'])} 가격 정리</h1>"
        f"<p class='mut'>{html.escape(cat)} · "
        f"<a href='{html.escape(tool['website'])}' rel='nofollow' target='_blank'>공식 사이트</a></p>"
        f"<p>{html.escape(tool.get('desc_ko', ''))}</p>"
        f"<h2>요금제</h2><table><thead><tr><th>플랜</th><th>가격</th></tr></thead>"
        f"<tbody>{trows}</tbody></table>"
        f"<p class='mut'>달러(USD) 기준이며 대부분 연 단위 결제 시 월 환산 가격입니다. "
        f"해외 결제 가능한 카드가 필요합니다.</p>"
        f"<p>{aff_link(tool, tool['name'] + ' 시작하기')}</p>")
    return page(f"{tool['name']} 가격·요금제 정리 (2026)", body)


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


def render_guides(data):
    """Render content/*.html fragments into site/guides/.

    Fragments may embed live-data tokens so guide articles never show stale prices
    (the weekly cron refreshes them together with the table):
      {{PRICE:tool-id:TierName}} -> "월 $17" / "무료"
      {{AFF:tool-id:라벨}}        -> affiliate button
      {{LINK:tool-id}}           -> link to the tool page
    First <h1> in the fragment is used as the page title.
    """
    tools = {t["id"]: t for t in data["tools"]}

    def price_tok(m):
        t = tools[m.group(1)]
        tier = next((x for x in t["tiers"] if x["name"] == m.group(2)), None)
        if tier is None:
            return "가격 확인 필요"
        return "무료" if tier["monthly_usd"] == 0 else f"월 ${tier['monthly_usd']}"

    guides = []
    if not CONTENT.exists():
        return guides
    (SITE / "guides").mkdir(parents=True, exist_ok=True)
    for frag in sorted(CONTENT.glob("*.html")):
        body = frag.read_text()
        body = re.sub(r"\{\{PRICE:([\w.-]+):([^}]+)\}\}", price_tok, body)
        body = re.sub(r"\{\{AFF:([\w.-]+):([^}]+)\}\}",
                      lambda m: aff_link(tools[m.group(1)], m.group(2)), body)
        body = re.sub(r"\{\{LINK:([\w.-]+)\}\}",
                      lambda m: f"<a href='../tools/{m.group(1)}.html'>"
                                f"{html.escape(tools[m.group(1)]['name'])}</a>", body)
        title_m = re.search(r"<h1>(.*?)</h1>", body)
        title = re.sub(r"<[^>]+>", "", title_m.group(1)) if title_m else frag.stem
        nav = "<p><a href='../index.html'>&larr; 가격 비교표로</a></p>"
        (SITE / "guides" / f"{frag.stem}.html").write_text(
            page(title, f"{nav}<article>{body}</article>"))
        guides.append({"slug": frag.stem, "title": title})
    return guides


def write_seo_files(data, guides):
    """sitemap.xml + robots.txt so Google/Naver can discover every page."""
    urls = ([f"{BASE_URL}/"]
            + [f"{BASE_URL}/tools/{t['id']}.html" for t in data["tools"]]
            + [f"{BASE_URL}/guides/{g['slug']}.html" for g in guides])
    lastmod = data["verified_on"]
    entries = "\n".join(
        f"  <url><loc>{u}</loc><lastmod>{lastmod}</lastmod></url>" for u in urls)
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n</urlset>\n")
    (SITE / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n")


def main():
    data = json.loads(DATA.read_text())
    data["verified_on"] = merge_fresh(data)
    (SITE / "tools").mkdir(parents=True, exist_ok=True)
    guides = render_guides(data)
    (SITE / "index.html").write_text(build_index(data, guides))
    for t in data["tools"]:
        (SITE / "tools" / f"{t['id']}.html").write_text(build_tool(t))
    write_seo_files(data, guides)
    print(f"built site/index.html + {len(data['tools'])} tool pages "
          f"+ {len(guides)} guides + sitemap.xml/robots.txt -> {SITE}")


if __name__ == "__main__":
    main()
