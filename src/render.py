"""HTML → PDF (Chromium/Playwright) + 페이지 넘침 검사."""
from __future__ import annotations
from pathlib import Path
from playwright.sync_api import sync_playwright

_JS = """() => [...document.querySelectorAll('.page')].map((s, i) => {
  const foot = s.querySelector('.foot, .sfoot');
  const f = foot ? foot.getBoundingClientRect().top : s.getBoundingClientRect().bottom;
  let m = 0;
  s.querySelectorAll('*').forEach(e => {
    if (e.closest('.foot, .sfoot')) return;
    const r = e.getBoundingClientRect();
    if (r.height > 0) m = Math.max(m, r.bottom);
  });
  return [i + 1, Math.round(m), Math.round(f)];
})"""


def html_to_pdf(html: Path, pdf: Path) -> list[tuple[int, int, int]]:
    """returns [(page_no, content_bottom_px, footer_top_px), ...]"""
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(400)
        res = pg.evaluate(_JS)
        pg.pdf(path=str(pdf), format="A4", print_background=True, prefer_css_page_size=True)
        b.close()
    return [tuple(r) for r in res]


def check_overflow(res, expected_pages: int, margin: int):
    bad = [(i, b, m) for i, b, m in res if m - b < margin]
    if len(res) != expected_pages:
        bad.append((0, len(res), expected_pages))
    return bad
