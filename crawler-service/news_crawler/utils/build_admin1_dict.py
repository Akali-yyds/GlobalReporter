#!/usr/bin/env python3
"""
Admin1（一级行政区）词典生成脚本

从 GeoNames admin1CodesASCII.txt + alternateNamesV2.txt 清洗生成各国 admin1 词典。

数据来源: GeoNames (CC BY 4.0)

输出文件:
- china_admin1.json
- usa_admin1.json
- uk_admin1.json
- japan_admin1.json
"""

import os
import json
import logging
import argparse
import re
from typing import Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(SCRIPT_DIR, "geo_dictionaries", "raw")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "geo_dictionaries")

CN_ADMIN1_NAME_ZH_BY_CODE = {
    "01": "安徽",
    "02": "浙江",
    "03": "江西",
    "04": "江苏",
    "05": "吉林",
    "06": "青海",
    "07": "福建",
    "08": "黑龙江",
    "09": "河南",
    "10": "河北",
    "11": "湖南",
    "12": "湖北",
    "13": "新疆",
    "14": "西藏",
    "15": "甘肃",
    "16": "广西",
    "18": "贵州",
    "19": "辽宁",
    "20": "内蒙古",
    "21": "宁夏",
    "22": "北京",
    "23": "上海",
    "24": "山西",
    "25": "山东",
    "26": "陕西",
    "28": "天津",
    "29": "云南",
    "30": "广东",
    "31": "海南",
    "32": "四川",
    "33": "重庆",
}

# Focus on the 50 countries that matter most to the current news product instead of all countries.
TOP50_NEWS_COUNTRIES = [
    "CN", "US", "GB", "JP", "IN", "DE", "FR", "IT", "ES", "CA",
    "AU", "BR", "MX", "AR", "CL", "CO", "PE", "VE", "RU", "UA",
    "PL", "NL", "BE", "SE", "NO", "DK", "FI", "CH", "AT", "IE",
    "PT", "TR", "SA", "AE", "IR", "IL", "EG", "ZA", "NG", "ET",
    "KE", "MA", "DZ", "PK", "BD", "ID", "TH", "VN", "KR", "PH",
]

OUTPUT_FILE_OVERRIDES = {
    "CN": "china_admin1.json",
    "US": "usa_admin1.json",
    "GB": "uk_admin1.json",
    "JP": "japan_admin1.json",
}

ADMIN1_TYPE_OVERRIDES = {
    "CN": "Province/Municipality/AR",
    "US": "State/Territory",
    "GB": "Country/Region",
    "JP": "Prefecture",
    "IN": "State/Union Territory",
    "DE": "State",
    "FR": "Region",
    "IT": "Region",
    "ES": "Autonomous Community",
    "CA": "Province/Territory",
    "AU": "State/Territory",
    "BR": "State/Federal District",
    "MX": "State",
    "RU": "Federal Subject",
    "KR": "Province/Metropolitan City",
}

ALT_NAME_LANGUAGES = {
    "", "zh", "en", "ja", "ko", "ru", "ar", "de", "fr", "es", "pt",
    "it", "tr", "fa", "hi", "id", "th", "vi", "uk", "pl", "nl", "sv",
    "da", "fi", "no",
}

EN_ADMIN1_SUFFIXES = [
    " province", " state", " region", " department", " division", " district",
    " governorate", " county", " territory", " prefecture", " canton",
    " autonomous community", " autonomous region", " oblast", " krai",
    " republic", " federal district", " metropolitan city", " special city",
]

ZH_ADMIN1_SUFFIXES = [
    "省", "州", "自治区", "地区", "大区", "行政区", "县", "市", "邦", "郡", "区",
    "直辖市", "特别行政区", "道", "府", "都", "省份",
]

# GeoNames admin1CodesASCII.txt 格式:
# code(CC.admin1_code) \t name \t name_ascii \t geonameId
ADMIN1_COLUMNS = ["code", "name", "name_ascii", "geoname_id"]


def _safe_slug(name: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in name.strip())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "country"


def parse_country_names(filepath: str) -> Dict[str, str]:
    country_names: Dict[str, str] = {}

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            fields = line.split("\t")
            if len(fields) < 5:
                continue

            iso_code = fields[0].strip()
            country_name = fields[4].strip()
            if len(iso_code) == 2 and country_name:
                country_names[iso_code] = country_name

    return country_names


def build_target_countries() -> dict[str, dict]:
    country_info_path = os.path.join(RAW_DIR, "countryInfo.txt")
    country_names = parse_country_names(country_info_path) if os.path.exists(country_info_path) else {}

    targets: dict[str, dict] = {}
    for country_code in TOP50_NEWS_COUNTRIES:
        country_name = country_names.get(country_code, country_code)
        output_file = OUTPUT_FILE_OVERRIDES.get(country_code, f"{_safe_slug(country_name)}_admin1.json")
        targets[country_code] = {
            "output_file": output_file,
            "country_name": country_name,
            "admin1_type": ADMIN1_TYPE_OVERRIDES.get(country_code, "Admin1"),
        }

    return targets


def _strip_en_admin1_suffixes(name: str) -> str:
    lowered = name.lower().strip()
    for suffix in EN_ADMIN1_SUFFIXES:
        if lowered.endswith(suffix) and len(name) > len(suffix):
            return name[: len(name) - len(suffix)].strip(" ,-/")
    return name.strip()


def _strip_zh_admin1_suffixes(name: str) -> str:
    stripped = name.strip()
    for suffix in ZH_ADMIN1_SUFFIXES:
        if stripped.endswith(suffix) and len(stripped) > len(suffix):
            return stripped[: -len(suffix)].strip()
    return stripped


def _alias_variants(name: str) -> set[str]:
    if not name:
        return set()

    variants = {name.strip()}
    stripped_en = _strip_en_admin1_suffixes(name)
    stripped_zh = _strip_zh_admin1_suffixes(name)
    for value in (stripped_en, stripped_zh):
        if value:
            variants.add(value)

    normalized_space = re.sub(r"\s+", " ", name).strip()
    if normalized_space:
        variants.add(normalized_space)

    return {value for value in variants if value}


def _zh_alias_suffix_variants(name: str, admin1_type: str) -> set[str]:
    stripped = _strip_zh_admin1_suffixes(name)
    if not stripped or stripped == name.strip():
        base = name.strip()
    else:
        base = stripped

    lowered_type = (admin1_type or "").lower()
    variants = {base}
    suffixes: list[str] = []

    if "province" in lowered_type or "region" in lowered_type or "division" in lowered_type or "governorate" in lowered_type:
        suffixes.extend(["省", "地区"])
    if "state" in lowered_type or "territory" in lowered_type or "canton" in lowered_type or "federal subject" in lowered_type:
        suffixes.extend(["州", "邦"])
    if "prefecture" in lowered_type:
        suffixes.extend(["都", "道", "府", "县"])

    for suffix in suffixes:
        variants.add(f"{base}{suffix}")

    return {value for value in variants if value}


def _build_aliases_for_admin1(admin1: dict, entry: dict | None = None) -> list[str]:
    alias_set: set[str] = set()
    admin1_type = admin1.get("admin1_type", "")

    for value in (
        admin1.get("admin1_name", ""),
        admin1.get("admin1_name_ascii", ""),
        admin1.get("admin1_name_zh", ""),
    ):
        alias_set.update(_alias_variants(value))
        if re.search(r"[\u4e00-\u9fff]", value or ""):
            alias_set.update(_zh_alias_suffix_variants(value, admin1_type))

    if entry:
        for key in ("zh", "en", "ja", "ko", "aliases"):
            for value in entry.get(key, []):
                alias_set.update(_alias_variants(value))
                if re.search(r"[\u4e00-\u9fff]", value or ""):
                    alias_set.update(_zh_alias_suffix_variants(value, admin1_type))

    return sorted(alias_set)


def parse_admin1_codes(filepath: str, country_codes: set = None) -> list[dict]:
    """
    解析 GeoNames admin1CodesASCII.txt

    每行格式: CC.ADMIN1CODE \t Name \t NameASCII \t GeonameId
    """
    admin1_list = []

    logger.info(f"正在解析: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            fields = line.split("\t")
            if len(fields) < 4:
                continue

            code_full = fields[0]  # 如 "CN.01"
            parts = code_full.split(".")
            if len(parts) != 2:
                continue

            country_code = parts[0]
            admin1_code = parts[1]

            # 过滤目标国家
            if country_codes and country_code not in country_codes:
                continue

            admin1 = {
                "country_code": country_code,
                "admin1_code": admin1_code,
                "admin1_code_full": code_full,
                "admin1_name": fields[1].strip(),
                "admin1_name_ascii": fields[2].strip(),
                "admin1_name_zh": "",  # 稍后从 alternateNames 填充
                "admin1_type": "",
                "aliases": [],
                "geojson_key": f"{country_code}.{admin1_code}",
                "lat": None,
                "lng": None,
                "source": "geonames",
                "source_id": fields[3].strip(),
            }
            admin1_list.append(admin1)

    logger.info(f"解析到 {len(admin1_list)} 条 admin1 记录")
    if country_codes:
        for cc in country_codes:
            count = sum(1 for a in admin1_list if a["country_code"] == cc)
            logger.info(f"  {cc}: {count} 条")

    return admin1_list


def load_admin1_coordinates(cities_filepath: str, country_codes: set) -> dict:
    """
    从 cities15000.txt 中提取各 admin1 的最大城市坐标作为代表坐标

    返回: {(country_code, admin1_code): {"lat": float, "lng": float, "city": str}}
    """
    coords = {}  # (cc, admin1_code) -> {"lat", "lng", "pop", "city"}

    if not os.path.exists(cities_filepath):
        logger.warning(f"城市文件不存在: {cities_filepath}")
        return coords

    logger.info("正在从城市数据中提取 admin1 代表坐标...")

    with open(cities_filepath, "r", encoding="utf-8") as f:
        for line in f:
            fields = line.strip().split("\t")
            if len(fields) < 15:
                continue

            country_code = fields[8] if len(fields) > 8 else ""
            if country_code not in country_codes:
                continue

            admin1_code = fields[10] if len(fields) > 10 else ""
            if not admin1_code:
                continue

            population = _safe_int(fields[14])
            lat = _safe_float(fields[4])
            lng = _safe_float(fields[5])
            city_name = fields[1]

            key = (country_code, admin1_code)

            # 取人口最多的城市作为代表坐标
            if key not in coords or population > coords[key]["pop"]:
                coords[key] = {
                    "lat": lat,
                    "lng": lng,
                    "pop": population,
                    "city": city_name,
                }

    logger.info("Loaded representative coordinates for %s admin1 regions", len(coords))
    return coords

def load_alternate_names_for_admin1(alt_names_path: str, target_ids: set) -> dict:
    """Load multilingual alternate names for target admin1 records."""
    if not os.path.exists(alt_names_path):
        logger.warning("alternateNames file is missing: %s", alt_names_path)
        return {}

    logger.info("Loading admin1 alternate names...")
    logger.info("  target geonameIds: %s", len(target_ids))

    result = {}
    line_count = 0
    match_count = 0

    with open(alt_names_path, "r", encoding="utf-8") as f:
        for line in f:
            line_count += 1
            if line_count % 5_000_000 == 0:
                logger.info("  processed %s lines, matched %s aliases...", f"{line_count:,}", f"{match_count:,}")

            fields = line.strip().split("	")
            if len(fields) < 4:
                continue

            geoname_id = fields[1]
            if geoname_id not in target_ids:
                continue

            iso_lang = fields[2] if len(fields) > 2 else ""
            alt_name = fields[3] if len(fields) > 3 else ""
            is_preferred = fields[4] == "1" if len(fields) > 4 else False

            if not alt_name or iso_lang not in ALT_NAME_LANGUAGES:
                continue

            if geoname_id not in result:
                result[geoname_id] = {
                    "zh": [],
                    "en": [],
                    "ja": [],
                    "ko": [],
                    "aliases": [],
                    "zh_preferred": "",
                }

            entry = result[geoname_id]

            if iso_lang == "zh":
                if is_preferred and not entry["zh_preferred"]:
                    entry["zh_preferred"] = alt_name
                entry["zh"].append(alt_name)
            elif iso_lang == "en":
                entry["en"].append(alt_name)
            elif iso_lang == "ja":
                entry["ja"].append(alt_name)
            elif iso_lang == "ko":
                entry["ko"].append(alt_name)

            entry["aliases"].append(alt_name)
            match_count += 1

    logger.info(
        "Alternate-name loading complete: processed %s lines, matched %s aliases across %s admin1 records",
        f"{line_count:,}",
        f"{match_count:,}",
        len(result),
    )
    return result


def apply_cn_admin1_fallback_names(admin1_list: list[dict]):
    for admin1 in admin1_list:
        if admin1.get("country_code") != "CN":
            continue
        if admin1.get("admin1_name_zh"):
            continue
        admin1_name_zh = CN_ADMIN1_NAME_ZH_BY_CODE.get(admin1.get("admin1_code", ""))
        if not admin1_name_zh:
            continue
        admin1["admin1_name_zh"] = admin1_name_zh


def build_admin1_dicts(skip_alt_names: bool = False):
    """Build admin1 dictionaries for the selected top-50 news countries."""
    target_countries = build_target_countries()

    admin1_path = os.path.join(RAW_DIR, "admin1CodesASCII.txt")
    if not os.path.exists(admin1_path):
        logger.error("Missing raw admin1 source file: %s", admin1_path)
        logger.error("Run download_geonames_data.py first")
        return False

    country_codes = set(target_countries.keys())
    admin1_list = parse_admin1_codes(admin1_path, country_codes=country_codes)

    alt_names = {}
    if not skip_alt_names:
        alt_names_path = os.path.join(RAW_DIR, "alternateNamesV2.txt")
        if os.path.exists(alt_names_path):
            target_ids = {a["source_id"] for a in admin1_list if a.get("source_id")}
            alt_names = load_alternate_names_for_admin1(alt_names_path, target_ids)

            for admin1 in admin1_list:
                entry = alt_names.get(admin1.get("source_id", ""))
                if not entry:
                    continue
                if entry.get("zh_preferred"):
                    admin1["admin1_name_zh"] = entry["zh_preferred"]
                elif entry.get("zh"):
                    admin1["admin1_name_zh"] = entry["zh"][0]
        else:
            logger.warning("alternateNamesV2.txt is missing, skipping multilingual alias merge")

    apply_cn_admin1_fallback_names(admin1_list)
    for admin1 in admin1_list:
        config = target_countries[admin1["country_code"]]
        admin1["admin1_type"] = config["admin1_type"]
        admin1["country_name"] = config["country_name"]
    for admin1 in admin1_list:
        admin1["aliases"] = _build_aliases_for_admin1(admin1, alt_names.get(admin1.get("source_id", "")))

    cities_path = os.path.join(RAW_DIR, "cities15000.txt")
    if os.path.exists(cities_path):
        coords = load_admin1_coordinates(cities_path, country_codes)
        for admin1 in admin1_list:
            key = (admin1["country_code"], admin1["admin1_code"])
            if key in coords:
                admin1["lat"] = coords[key]["lat"]
                admin1["lng"] = coords[key]["lng"]

    for cc, config in target_countries.items():
        country_admin1s = [a for a in admin1_list if a["country_code"] == cc]
        country_admin1s.sort(key=lambda a: a["admin1_code"])

        output = {
            "version": "1.1",
            "source": "GeoNames (CC BY 4.0)",
            "source_url": "https://download.geonames.org/export/dump/",
            "country_code": cc,
            "country_name": config["country_name"],
            "description": f"{config['country_name']} admin1 dictionary generated from GeoNames admin1CodesASCII.txt",
            "total_count": len(country_admin1s),
            "admin1_regions": {a["admin1_code"]: a for a in country_admin1s},
        }

        output_path = os.path.join(OUTPUT_DIR, config["output_file"])
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        zh_count = sum(1 for a in country_admin1s if a.get("admin1_name_zh"))
        coord_count = sum(1 for a in country_admin1s if a.get("lat") is not None)
        logger.info(
            "Generated %s: %s records | zh=%s | coords=%s",
            config["output_file"],
            len(country_admin1s),
            zh_count,
            coord_count,
        )

    return True


def _safe_int(val: str) -> int:
    try:
        return int(val.strip())
    except (ValueError, TypeError):
        return 0


def _safe_float(val: str):
    try:
        return round(float(val.strip()), 6)
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从 GeoNames 生成 admin1 词典")
    parser.add_argument("--download", action="store_true", help="先下载原始数据再生成")
    parser.add_argument("--skip-alt-names", action="store_true", help="跳过别名处理（加速测试）")
    args = parser.parse_args()

    if args.download:
        from download_geonames_data import download_all
        if not download_all():
            logger.error("数据下载失败，终止生成")
            exit(1)

    build_admin1_dicts(skip_alt_names=args.skip_alt_names)
