#!/usr/bin/env python3
"""Quick smoke test: run each spider with max_items=3 and report item counts."""
import subprocess
import sys
import json
from pathlib import Path

PYTHON = sys.executable
SPIDERS = [
    "bbc", "ap", "guardian", "reuters", "abc_news", "voa", "cbs_news", "sky_news",
    "pbs_newshour", "euronews", "nbc_news", "fox_news", "times_of_india",
    "aljazeera", "dw", "france24",
    "cna", "scmp", "straits_times", "nhk", "ndtv", "nhk_world",
    "sina", "global_times", "tencent",
    "bilibili_hot",
    "earthquake_usgs", "eonet_events", "disaster_gdacs",
    "nasa_official", "openai_official", "google_blog",
    "nvidia_official", "youtube_blog", "dod_official",
    "github_changelog", "github_openai_releases", "youtube_official",
    "gdelt_doc_global",
]


def test_spider(name: str) -> dict:
    cmd = [
        PYTHON, "-m", "scrapy", "crawl", name,
        "-a", "max_items=3",
        "-s", "LOG_LEVEL=INFO",
        "-s", "CLOSESPIDER_TIMEOUT=30",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=45,
            cwd=Path(__file__).parent,
        )
        stdout = result.stdout + result.stderr
        # Extract item_scraped_count from Scrapy stats dump
        scraped = 0
        for line in stdout.splitlines():
            if "item_scraped_count" in line:
                import re
                m = re.search(r"item_scraped_count['\"]?\s*:\s*(\d+)", line)
                if m:
                    scraped = int(m.group(1))
                    break
        errors = [l for l in stdout.splitlines()
                  if ("ERROR" in l or "no items" in l.lower() or "WARNING" in l)
                  and "item_scraped_count" not in l]
        return {
            "spider": name,
            "exit": result.returncode,
            "scraped": scraped,
            "errors": errors[:3],
            "ok": result.returncode == 0 and scraped > 0,
        }
    except subprocess.TimeoutExpired:
        return {"spider": name, "exit": -1, "scraped": 0, "errors": ["TIMEOUT"], "ok": False}
    except Exception as e:
        return {"spider": name, "exit": -1, "scraped": 0, "errors": [str(e)], "ok": False}


if __name__ == "__main__":
    results = []
    for spider in SPIDERS:
        print(f"  Testing {spider}...", end=" ", flush=True)
        r = test_spider(spider)
        status = "✓" if r["ok"] else "✗"
        print(f"{status}  scraped={r['scraped']}  exit={r['exit']}")
        if r["errors"]:
            for e in r["errors"]:
                print(f"       {e}")
        results.append(r)

    print("\n=== Summary ===")
    ok = [r["spider"] for r in results if r["ok"]]
    fail = [r["spider"] for r in results if not r["ok"]]
    print(f"OK  ({len(ok)}): {', '.join(ok)}")
    print(f"FAIL({len(fail)}): {', '.join(fail)}")
