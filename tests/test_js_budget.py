from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "app" / "static" / "js"


def test_total_js_under_60kb():
    total = sum(p.stat().st_size for p in JS.glob("*.js"))
    assert total < 60 * 1024, f"JS is {total / 1024:.1f} KB"
