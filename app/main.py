"""FastAPI app: HTML pages, static assets and the small JSON API."""
from __future__ import annotations

import base64
import hashlib
import html
import json
import random
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config
from .analysis import analyze
from .content import FAQ
from .models import AnalyzeRequest, AnalyzeResponse, VocabResponse
from .vocab_store import VocabStore

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
TEMPLATES = BASE / "templates"


def _asset_version() -> str:
    h = hashlib.sha256()
    for p in sorted(STATIC.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(STATIC).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:10]


ASSET_VERSION = _asset_version()
ASSETS = f"/assets/{ASSET_VERSION}"
store = VocabStore()

app = FastAPI(title=config.APP_NAME, docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=500)


class ImmutableStatic(StaticFiles):
    """Assets live under a content-hash path, so they can be cached forever."""

    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp


app.mount(ASSETS, ImmutableStatic(directory=STATIC), name="assets")


# ---------------------------------------------------------------- page rendering
def _faq_html() -> str:
    items = []
    for q, a in FAQ:
        items.append(f'<details class="faq-item"><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>')
    return "\n".join(items)


def _jsonld() -> str:
    data = [
        {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": config.APP_NAME,
            "url": config.SITE_URL + "/",
            "applicationCategory": "EducationalApplication",
            "operatingSystem": "Any",
            "browserRequirements": "Requires JavaScript",
            "inLanguage": "en",
            "isAccessibleForFree": True,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
            "description": "Test your typing speed and learn new English words as you type.",
        },
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in FAQ
            ],
        },
    ]
    return json.dumps(data, separators=(",", ":")).replace("</", "<\\/")


def _client_config() -> str:
    cfg = {
        "appName": config.APP_NAME,
        "siteUrl": config.SITE_URL,
        "levels": config.LEVELS,
        "defaultLevel": config.DEFAULT_LEVEL,
        "defaultMode": config.DEFAULT_MODE,
        "durations": config.DURATIONS,
        "defaultDuration": config.DEFAULT_DURATION,
        "customMin": config.CUSTOM_MIN_SECONDS,
        "customMax": config.CUSTOM_MAX_SECONDS,
        "longTest": config.LONG_TEST_SECONDS,
        "idlePause": config.IDLE_PAUSE_SECONDS,
        "assets": ASSETS,
    }
    return json.dumps(cfg, separators=(",", ":"))


def _fmt(n: int) -> str:
    return f"{n:,}"


PARTIALS = {name: (TEMPLATES / f"_{name}.html").read_text(encoding="utf-8") for name in ("head", "header", "footer")}
NAV = {"test": "/#test", "my-words": "/my-words", "how": "/#how", "faq": "/#faq"}
THEME_SCRIPT = (TEMPLATES / "_theme.js").read_text(encoding="utf-8").strip()
THEME_HASH = base64.b64encode(hashlib.sha256(THEME_SCRIPT.encode()).digest()).decode()
CSP = (
    "default-src 'self'; "
    f"script-src 'self' 'sha256-{THEME_HASH}'; "
    "style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'none'; object-src 'none'; manifest-src 'self'"
)


def render(name: str, *, title: str, description: str, path: str, current: str = "", noindex: bool = False) -> str:
    page = (TEMPLATES / name).read_text(encoding="utf-8")
    header = PARTIALS["header"]
    for key in NAV:
        header = header.replace(f"{{{{CUR_{key}}}}}", ' aria-current="page"' if key == current else "")
    values = {
        "HEAD": PARTIALS["head"],
        "HEADER": header,
        "FOOTER": PARTIALS["footer"],
        "THEME_SCRIPT": THEME_SCRIPT,
        "TITLE": html.escape(title),
        "DESCRIPTION": html.escape(description),
        "CANONICAL": config.SITE_URL + path,
        "ROBOTS": "noindex, follow" if noindex else "index, follow",
        "APP_NAME": html.escape(config.APP_NAME),
        "SITE_URL": config.SITE_URL,
        "CONTACT_EMAIL": html.escape(config.CONTACT_EMAIL),
        "ASSETS": ASSETS,
        "WORD_COUNT": _fmt(store.total_words),
        "SENTENCE_COUNT": _fmt(store.total_sentences),
        "FAQ_HTML": _faq_html(),
        "JSONLD": _jsonld(),
        "CONFIG_JSON": _client_config(),
    }
    # Partials contain placeholders too, so substitute until stable.
    for _ in range(3):
        page = re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: values.get(m.group(1), m.group(0)), page)
    return page


PAGES = {
    "/": ("index.html", "Typing Speed Test Online - Type Faster & Learn English Words",
          "Test your typing speed and learn new English words as you type. See each word's meaning and "
          "real example sentences. Free, no sign-up.", "test"),
    "/my-words": ("my-words.html", f"My Words - Your Saved Vocabulary | {config.APP_NAME}",
                  "Review the English words you saved during typing tests, with meanings, pronunciation and "
                  "example sentences. Practice them again for free.", "my-words"),
    "/privacy": ("privacy.html", f"Privacy Policy | {config.APP_NAME}",
                 "No account, no tracking: your typing results and saved words stay in your own browser.", ""),
    "/terms": ("terms.html", f"Terms of Use | {config.APP_NAME}",
               "Simple terms for using this free typing speed test and vocabulary trainer.", ""),
}
RENDERED = {path: render(t, title=ti, description=d, path=path, current=c) for path, (t, ti, d, c) in PAGES.items()}
NOT_FOUND = render("404.html", title=f"Page not found | {config.APP_NAME}",
                   description="This page does not exist.", path="/404", noindex=True)


@app.middleware("http")
async def headers_and_limits(request: Request, call_next):
    if request.url.path == "/api/analyze":
        length = request.headers.get("content-length")
        if length and int(length) > config.MAX_ANALYZE_BYTES:
            return JSONResponse({"detail": "Payload too large"}, status_code=413)
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if resp.headers.get("content-type", "").startswith("text/html"):
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["Cache-Control"] = "no-cache"
    return resp


def _page(path: str):
    def handler() -> HTMLResponse:
        return HTMLResponse(RENDERED[path])
    return handler


for _path in PAGES:
    app.add_api_route(_path, _page(_path), methods=["GET", "HEAD"], response_class=HTMLResponse, include_in_schema=False)


@app.exception_handler(404)
async def not_found(request: Request, exc):
    if request.url.path.startswith("/api/"):
        detail = getattr(exc, "detail", "Not found")
        return JSONResponse({"detail": detail}, status_code=404)
    return HTMLResponse(NOT_FOUND, status_code=404)


# ---------------------------------------------------------------- root files
@app.get("/robots.txt", include_in_schema=False)
def robots() -> PlainTextResponse:
    return PlainTextResponse(f"User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: {config.SITE_URL}/sitemap.xml\n")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap() -> Response:
    urls = "".join(f"<url><loc>{config.SITE_URL}{p}</loc></url>" for p in PAGES)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    return Response(xml, media_type="application/xml")


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest() -> JSONResponse:
    return JSONResponse({
        "name": config.APP_NAME,
        "short_name": config.APP_SHORT_NAME,
        "start_url": "/",
        "display": "standalone",
        "background_color": "#fbfaf7",
        "theme_color": "#1d4ed8",
        "icons": [
            {"src": f"{ASSETS}/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": f"{ASSETS}/img/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": f"{ASSETS}/img/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
    }, media_type="application/manifest+json")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response((STATIC / "img" / "icon-32.png").read_bytes(), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/og-image.png", include_in_schema=False)
def og_image() -> Response:
    """Stable (unversioned) URL for social previews."""
    return Response((STATIC / "img" / "og-image.png").read_bytes(), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


# ---------------------------------------------------------------- API
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "words": store.total_words}


@app.get("/api/vocab", response_model=VocabResponse)
def vocab(
    level: str = Query(config.DEFAULT_LEVEL, pattern="^(easy|medium|hard)$"),
    count: int = Query(20, ge=1, le=config.MAX_VOCAB_BATCH),
    seed: int | None = Query(None, ge=0, lt=2**31),
    cursor: int = Query(0, ge=0),
    exclude: str = Query("", max_length=config.MAX_EXCLUDE_IDS * 40),
):
    if seed is None:
        seed = random.randrange(2**31)
    ids = {x for x in exclude.split(",") if x}
    if len(ids) > config.MAX_EXCLUDE_IDS:
        raise HTTPException(422, f"exclude accepts at most {config.MAX_EXCLUDE_IDS} ids")
    words, nxt, total = store.sample(level, count, seed, cursor, ids)
    body = {"level": level, "seed": seed, "cursor": cursor, "next_cursor": nxt, "total": total, "words": words}
    return JSONResponse(body, headers={"Cache-Control": "public, max-age=3600"})


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze_endpoint(req: AnalyzeRequest) -> dict:
    return analyze(req.words, req.keystrokes, req.duration_ms, req.pauses)
