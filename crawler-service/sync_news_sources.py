#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "api-service"
CRAWLER_ROOT = REPO_ROOT / "crawler-service"

for path in (str(API_ROOT), str(CRAWLER_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.database import SessionLocal
from app.models import NewsSource
from news_crawler.spiders.base import BaseNewsSpider
from scheduler import DEFAULT_SPIDERS

SPIDERS_ROOT = CRAWLER_ROOT / "news_crawler" / "spiders"


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _find_spider_file(spider_name: str) -> Path:
    matches = list(SPIDERS_ROOT.rglob(f"{spider_name}.py"))
    if not matches:
        raise FileNotFoundError(f"Spider file not found for: {spider_name}")
    return matches[0]


def _load_spider_class(spider_name: str) -> type[BaseNewsSpider]:
    spider_file = _find_spider_file(spider_name)
    module_name = f"sync_spider_{spider_name}"
    spec = importlib.util.spec_from_file_location(module_name, spider_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec for: {spider_file}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for _, obj in inspect.getmembers(module, inspect.isclass):
        if not issubclass(obj, BaseNewsSpider) or obj is BaseNewsSpider:
            continue
        if getattr(obj, "name", None) == spider_name:
            return obj

    raise LookupError(f"Spider class not found in: {spider_file}")


def _spider_metadata(spider_name: str) -> dict[str, Any]:
    spider_cls = _load_spider_class(spider_name)
    return {
        "name": getattr(spider_cls, "source_name", spider_name),
        "code": getattr(spider_cls, "source_code", spider_name),
        "base_url": getattr(spider_cls, "source_url", "https://example.com"),
        "country": getattr(spider_cls, "country", "CN"),
        "language": getattr(spider_cls, "language", "zh"),
        "category": getattr(spider_cls, "category", "news"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    created = 0
    updated = 0
    unchanged = 0
    details: list[dict[str, Any]] = []

    try:
        for config in DEFAULT_SPIDERS:
            metadata = _spider_metadata(config.name)
            existing = db.query(NewsSource).filter(NewsSource.code == metadata["code"]).first()
            desired_is_active = bool(config.enabled)

            if existing is None:
                source = NewsSource(
                    name=metadata["name"],
                    code=metadata["code"],
                    base_url=metadata["base_url"],
                    country=metadata["country"],
                    language=metadata["language"],
                    category=metadata["category"],
                    is_active=desired_is_active,
                )
                db.add(source)
                db.flush()
                created += 1
                details.append(
                    {
                        "spider_name": config.name,
                        "action": "create",
                        "code": metadata["code"],
                        "name": metadata["name"],
                        "base_url": metadata["base_url"],
                    }
                )
                continue

            changed_fields: dict[str, dict[str, Any]] = {}
            for field_name, desired_value in (
                ("name", metadata["name"]),
                ("base_url", metadata["base_url"]),
                ("country", metadata["country"]),
                ("language", metadata["language"]),
                ("category", metadata["category"]),
                ("is_active", desired_is_active),
            ):
                current_value = getattr(existing, field_name)
                if current_value != desired_value:
                    changed_fields[field_name] = {"from": current_value, "to": desired_value}
                    setattr(existing, field_name, desired_value)

            if changed_fields:
                updated += 1
                details.append(
                    {
                        "spider_name": config.name,
                        "action": "update",
                        "code": metadata["code"],
                        "changes": changed_fields,
                    }
                )
            else:
                unchanged += 1
                details.append(
                    {
                        "spider_name": config.name,
                        "action": "unchanged",
                        "code": metadata["code"],
                    }
                )

        if args.commit:
            db.commit()
            mode = "commit"
        else:
            db.rollback()
            mode = "dry_run"

        print(
            json.dumps(
                {
                    "mode": mode,
                    "created": created,
                    "updated": updated,
                    "unchanged": unchanged,
                    "details": details,
                },
                ensure_ascii=False,
                indent=2,
                default=_json_default,
            )
        )
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
