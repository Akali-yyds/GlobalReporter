"""
Prepare geodata static assets for the API service.

Downloads and preprocesses GeoJSON files for country polygons and admin1 boundaries.
Output is placed in app/static/geodata/ and served via FastAPI StaticFiles.

Usage:
    python prepare_geodata.py               # download all (countries + key admin1)
    python prepare_geodata.py --countries   # country polygons only
    python prepare_geodata.py --admin1 CN   # admin1 for specific country (CN/US/GB/JP)
"""
import argparse
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "app" / "static" / "geodata"
COUNTRIES_DIR = STATIC_DIR / "countries"
ADMIN1_DIR = STATIC_DIR / "admin1"
INDEX_PATH = STATIC_DIR / "geodata_index.json"

# Natural Earth sources (via GitHub CDN — same as react-globe.gl uses)
COUNTRIES_URL = (
    "https://raw.githubusercontent.com/vasturiano/react-globe.gl"
    "/master/example/datasets/ne_110m_admin_0_countries.geojson"
)

# Natural Earth 50m admin1 (province/state boundaries, ~2MB — large countries only)
ADMIN1_50M_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector"
    "/master/geojson/ne_50m_admin_1_states_provinces.geojson"
)
# Natural Earth 10m admin1 (~25MB — comprehensive, fallback for smaller countries)
ADMIN1_10M_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector"
    "/master/geojson/ne_10m_admin_1_states_provinces.geojson"
)

# Admin1 ISO_3166-2 prefix -> output filename
ADMIN1_TARGETS = ["CN", "US", "GB", "JP"]


def download(url: str, dest: Path) -> None:
    print(f"  Downloading {url.split('/')[-1]} ...", end=" ", flush=True)
    urllib.request.urlretrieve(url, dest)
    size_kb = dest.stat().st_size // 1024
    print(f"OK ({size_kb} KB)")


def prepare_countries() -> bool:
    dest = COUNTRIES_DIR / "ne_110m_admin_0_countries.geojson"
    if dest.exists():
        print(f"  countries GeoJSON already present ({dest.stat().st_size // 1024} KB), skipping.")
        return True
    try:
        download(COUNTRIES_URL, dest)
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def _write_country(cc: str, features: list, dest_dir: Path, succeeded: list[str]) -> None:
    """Write a country's admin1 features to a GeoJSON file."""
    out = {"type": "FeatureCollection", "features": features}
    out_path = dest_dir / f"{cc}.geojson"
    with open(out_path, "w", encoding="utf-8") as wf:
        json.dump(out, wf, ensure_ascii=False, separators=(",", ":"))
    size_kb = out_path.stat().st_size // 1024
    print(f"\n    {cc}: {len(features)} features ({size_kb} KB)", end="")
    succeeded.append(cc)


def prepare_admin1(target_countries: list[str]) -> list[str]:
    """Download and split admin1 GeoJSON by country code."""
    raw_path = ADMIN1_DIR / "_ne_50m_admin1_raw.geojson"
    succeeded: list[str] = []

    # Check if any target is already prepared
    missing = [cc for cc in target_countries if not (ADMIN1_DIR / f"{cc}.geojson").exists()]
    if not missing:
        print(f"  All admin1 targets already present: {target_countries}")
        return target_countries

    # Download the 50m file (smaller, covers large countries)
    if not raw_path.exists():
        try:
            download(ADMIN1_50M_URL, raw_path)
        except Exception as e:
            print(f"  ERROR downloading admin1 50m: {e}")
            return succeeded

    def _cc_matches(feat: dict, cc: str) -> bool:
        p = feat.get("properties") or {}
        if p.get("iso_a2", "").upper() == cc:
            return True
        iso2_pref = str(p.get("iso_3166_2", "")).split("-")[0].upper()
        if iso2_pref == cc:
            return True
        hasc_pref = str(p.get("code_hasc", "")).split(".")[0].upper()
        if hasc_pref == cc:
            return True
        return False

    print(f"  Splitting admin1 by country from 50m: {missing} ...", end=" ", flush=True)
    with open(raw_path, encoding="utf-8") as f:
        data = json.load(f)
    features_50m = data.get("features", [])

    still_missing: list[str] = []
    for cc in missing:
        country_features = [f for f in features_50m if _cc_matches(f, cc)]
        if not country_features:
            still_missing.append(cc)
            continue
        _write_country(cc, country_features, ADMIN1_DIR, succeeded)

    # For countries not in ne_50m, try ne_10m (slower but comprehensive)
    if still_missing:
        print(f"\n  Countries not in 50m, trying 10m for: {still_missing}")
        raw_10m = ADMIN1_DIR / "_ne_10m_admin1_raw.geojson"
        if not raw_10m.exists():
            try:
                download(ADMIN1_10M_URL, raw_10m)
            except Exception as e:
                print(f"  ERROR downloading admin1 10m: {e}")
                return succeeded
        with open(raw_10m, encoding="utf-8") as f:
            features_10m = json.load(f).get("features", [])
        for cc in still_missing:
            country_features = [f for f in features_10m if _cc_matches(f, cc)]
            if not country_features:
                print(f"  WARNING: no admin1 features found for {cc} in 10m either")
                continue
            _write_country(cc, country_features, ADMIN1_DIR, succeeded)

    print(" done.")
    return succeeded


def update_index(countries_ok: bool, admin1_ready: list[str]) -> None:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8")) if INDEX_PATH.exists() else {}
    index.setdefault("layers", {})
    index["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    index["layers"]["countries"] = {
        "file": "countries/ne_110m_admin_0_countries.geojson",
        "url": "/static/geodata/countries/ne_110m_admin_0_countries.geojson",
        "description": "Natural Earth 110m country polygons",
        "id_property": "ISO_A3",
        "name_property": "NAME",
        "ready": countries_ok,
    }
    index["layers"]["admin1"] = {
        "available_countries": sorted(admin1_ready),
        "url_pattern": "/static/geodata/admin1/{country_code}.geojson",
        "description": "Admin1 (province/state) boundaries per country",
        "id_property": "iso_3166_2",
        "name_property": "name",
        "ready": len(admin1_ready) > 0,
    }
    INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  geodata_index.json updated.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare geodata static assets")
    parser.add_argument("--countries", action="store_true", help="Download country GeoJSON only")
    parser.add_argument("--admin1", nargs="*", metavar="CC", help="Prepare admin1 for country codes (default: CN US GB JP)")
    args = parser.parse_args()

    COUNTRIES_DIR.mkdir(parents=True, exist_ok=True)
    ADMIN1_DIR.mkdir(parents=True, exist_ok=True)

    do_countries = args.countries or (args.admin1 is None)
    admin1_targets = args.admin1 if args.admin1 is not None else ([] if args.countries else ADMIN1_TARGETS)

    countries_ok = False
    admin1_ready: list[str] = []

    if do_countries:
        print("=== Preparing country polygons ===")
        countries_ok = prepare_countries()

    if admin1_targets:
        print(f"=== Preparing admin1 boundaries for {admin1_targets} ===")
        admin1_ready = prepare_admin1(admin1_targets)

    print("=== Updating geodata index ===")
    # Re-read current index to preserve existing ready state
    current = json.loads(INDEX_PATH.read_text(encoding="utf-8")) if INDEX_PATH.exists() else {}
    existing_ok = current.get("layers", {}).get("countries", {}).get("ready", False)
    existing_admin1 = current.get("layers", {}).get("admin1", {}).get("available_countries", [])
    update_index(
        countries_ok=countries_ok or existing_ok,
        admin1_ready=sorted(set(admin1_ready) | set(existing_admin1)),
    )

    print("\nDone. Run `python prepare_geodata.py` again at any time to refresh.")


if __name__ == "__main__":
    main()
