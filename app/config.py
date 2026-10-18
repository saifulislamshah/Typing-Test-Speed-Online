"""Single source of truth for names, URLs and test settings.

Rename the product by changing APP_NAME; every page, the manifest, share text and
JSON-LD read it from here.
"""
import os

APP_NAME = "Typing Test Speed Online"
APP_SHORT_NAME = "TypingTest"
SITE_URL = os.environ.get("SITE_URL", "https://typingtestspeedonline.com").rstrip("/")
# PLACEHOLDER: replace with a real, monitored address before launch.
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "hello@typingtestspeedonline.com")
# Vercel Web Analytics: anonymous visitor counts, no cookies. Vercel sets VERCEL=1, and the
# script is served by Vercel from this site's own domain (/_vercel/insights/script.js), so
# the strict CSP ('self') already allows it. Set ANALYTICS=0 to turn it off.
ANALYTICS = os.environ.get("ANALYTICS", "1" if os.environ.get("VERCEL") == "1" else "0") == "1"

LEVELS = ("easy", "medium", "hard")
DEFAULT_LEVEL = "medium"
MODES = ("learn", "speed")
DEFAULT_MODE = "learn"
DURATIONS = (60, 300, 600, 3600)  # seconds; 60 is pre-selected ("Most popular")
DEFAULT_DURATION = 60
CUSTOM_MIN_SECONDS, CUSTOM_MAX_SECONDS = 15, 7200
LONG_TEST_SECONDS = 300  # auto-pause applies from this duration up
IDLE_PAUSE_SECONDS = 30

MAX_SUSTAINED_WPM = 250
MAX_VOCAB_BATCH = 50
MAX_EXCLUDE_IDS = 500
MAX_ANALYZE_BYTES = 3_000_000
MAX_KEYSTROKES = 200_000
