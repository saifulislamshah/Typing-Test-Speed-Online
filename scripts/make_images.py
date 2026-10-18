"""Render favicon PNGs and the Open Graph image with Playwright (no imaging libs).

Usage: python scripts/make_images.py
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import APP_NAME  # noqa: E402

IMG = Path(__file__).resolve().parent.parent / "app" / "static" / "img"
FONTS = (IMG.parent / "fonts").as_uri()

OG = f"""<!doctype html><html><head><style>
@font-face {{ font-family: Inter; src: url('{FONTS}/inter-var-latin.woff2'); font-weight: 100 900; }}
@font-face {{ font-family: SS4; src: url('{FONTS}/source-serif-4-var-latin.woff2'); font-weight: 200 900; }}
body {{ margin: 0; width: 1200px; height: 630px; background: #fbfaf7; font-family: Inter; color: #1b1a19;
  display: flex; flex-direction: column; justify-content: center; padding: 0 88px; box-sizing: border-box; }}
.eyebrow {{ color: #1d4ed8; font-weight: 700; letter-spacing: .14em; font-size: 26px; }}
h1 {{ font-size: 76px; line-height: 1.05; margin: 16px 0 28px; letter-spacing: -0.02em; }}
.card {{ background: #fff; border: 2px solid #e3dfd7; border-radius: 22px; padding: 26px 34px; font-family: SS4; font-size: 34px; max-width: 900px; }}
.card b {{ text-decoration: underline; text-decoration-color: #93b4ff; text-decoration-thickness: 4px; text-underline-offset: 8px; }}
.meta {{ font-family: Inter; font-size: 22px; color: #57534e; margin-top: 10px; }}
.brand {{ position: absolute; right: 88px; top: 60px; font-weight: 750; font-size: 26px; display: flex; gap: 12px; align-items: center; }}
</style></head><body>
<div class="brand"><img src="favicon.svg" width="44" height="44">{APP_NAME}</div>
<div class="eyebrow">TYPING SPEED TEST</div>
<h1>Type faster.<br>Learn new English words.</h1>
<div class="card">Her <b>passion</b> for music shows in every song she writes.<div class="meta">Every sentence teaches you a word - its meaning and how to use it.</div></div>
</body></html>"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1200, "height": 630})
    (IMG / "_og.html").write_text(OG, encoding="utf-8")
    page.goto((IMG / "_og.html").as_uri())
    page.wait_for_timeout(300)
    page.screenshot(path=str(IMG / "og-image.png"))
    (IMG / "_og.html").unlink()
    for size in (32, 192, 512):
        page.set_viewport_size({"width": size, "height": size})
        page.set_content(f'<body style="margin:0;background:transparent"><img src="{(IMG / "favicon.svg").as_uri()}" width="{size}" height="{size}">')
        page.wait_for_timeout(100)
        page.screenshot(path=str(IMG / f"icon-{size}.png"), omit_background=True)
    browser.close()
print("wrote og-image.png, icon-32.png, icon-192.png, icon-512.png")
