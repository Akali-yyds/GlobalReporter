#!/usr/bin/env python3
"""
国家词典生成脚本

从 GeoNames countryInfo.txt + alternateNamesV2.txt 清洗生成 countries.json

数据来源: GeoNames (CC BY 4.0)
"""

import os
import csv
import json
import logging
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(SCRIPT_DIR, "geo_dictionaries", "raw")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "geo_dictionaries")

COUNTRY_FALLBACKS = {
    "CN": {
        "country_name_zh": "中国",
        "aliases": ["中国", "中华人民共和国", "China", "CN", "PRC"],
    },
    "US": {
        "country_name_zh": "美国",
        "aliases": ["美国", "美利坚合众国", "United States", "USA", "US", "America"],
    },
    "GB": {
        "country_name_zh": "英国",
        "aliases": ["英国", "联合王国", "United Kingdom", "UK", "GB", "Britain", "England"],
    },
    "JP": {
        "country_name_zh": "日本",
        "aliases": ["日本", "Japan", "JP"],
    },
}

# GeoNames countryInfo.txt 列定义（TSV格式，#开头行为注释）
# ISO, ISO3, ISO-Numeric, fips, Country, Capital, Area, Population,
# Continent, tld, CurrencyCode, CurrencyName, Phone, PostalCodeFormat,
# PostalCodeRegex, Languages, geonameId, neighbours, EquivalentFipsCode
COUNTRY_INFO_COLUMNS = [
    "iso", "iso3", "iso_numeric", "fips", "country_name", "capital",
    "area_sq_km", "population", "continent", "tld", "currency_code",
    "currency_name", "phone", "postal_code_format", "postal_code_regex",
    "languages", "geoname_id", "neighbours", "equivalent_fips_code"
]

# alternateNamesV2.txt 列定义
# alternateNameId, geonameid, isolanguage, alternate_name,
# isPreferredName, isShortName, isColloquial, isHistoric, from, to
ALT_NAMES_COLUMNS = [
    "alternate_name_id", "geoname_id", "iso_language", "alternate_name",
    "is_preferred", "is_short", "is_colloquial", "is_historic", "from_date", "to_date"
]


def parse_country_info(filepath: str) -> list[dict]:
    """解析 GeoNames countryInfo.txt 文件"""
    countries = []

    logger.info(f"正在解析: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过注释行和空行
            if not line or line.startswith("#"):
                continue

            fields = line.split("\t")
            if len(fields) < 17:  # need at least through geoname_id (index 16)
                continue

            row = dict(zip(COUNTRY_INFO_COLUMNS, fields))

            # 跳过无效记录
            iso_code = row.get("iso", "").strip()
            if not iso_code or len(iso_code) != 2:
                continue

            country = {
                "country_code": iso_code,
                "country_name": row.get("country_name", "").strip(),
                "country_name_zh": "",  # 稍后从 alternateNames 填充
                "aliases": [],
                "capital": row.get("capital", "").strip(),
                "population": _safe_int(row.get("population", "0")),
                "continent": row.get("continent", "").strip(),
                "geojson_key": iso_code,  # 默认用ISO代码作为GeoJSON匹配键
                "lat": None,  # 稍后从城市数据补充，或用国家中心
                "lng": None,
                "source": "geonames",
                "source_id": row.get("geoname_id", "").strip(),
            }
            countries.append(country)

    logger.info(f"解析到 {len(countries)} 个国家记录")
    return countries


def load_alternate_names(filepath: str, target_geoname_ids: set, languages: set = None) -> dict:
    """
    从 alternateNamesV2.txt 加载指定 geonameId 的别名

    Args:
        filepath: alternateNamesV2.txt 文件路径
        target_geoname_ids: 需要加载别名的 geonameId 集合
        languages: 需要的语言代码集合，如 {'zh', 'en'}，None 表示所有

    Returns:
        dict: {geoname_id: {"zh": [names], "en": [names], "aliases": [all_names]}}
    """
    if not os.path.exists(filepath):
        logger.warning(f"alternateNames 文件不存在: {filepath}")
        return {}

    logger.info(f"正在加载别名数据: {filepath}")
    logger.info(f"  目标 geonameId 数量: {len(target_geoname_ids)}")

    result = {}
    line_count = 0
    match_count = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line_count += 1
            if line_count % 5_000_000 == 0:
                logger.info(f"  已处理 {line_count:,} 行，匹配 {match_count:,} 条...")

            fields = line.strip().split("\t")
            if len(fields) < 4:
                continue

            geoname_id = fields[1]
            if geoname_id not in target_geoname_ids:
                continue

            iso_lang = fields[2] if len(fields) > 2 else ""
            alt_name = fields[3] if len(fields) > 3 else ""
            is_preferred = fields[4] == "1" if len(fields) > 4 else False

            if not alt_name:
                continue

            # 过滤语言
            if languages and iso_lang not in languages:
                continue

            if geoname_id not in result:
                result[geoname_id] = {"zh": [], "en": [], "aliases": [], "zh_preferred": ""}

            entry = result[geoname_id]

            if iso_lang == "zh":
                if is_preferred and not entry["zh_preferred"]:
                    entry["zh_preferred"] = alt_name
                entry["zh"].append(alt_name)
            elif iso_lang == "en":
                entry["en"].append(alt_name)

            entry["aliases"].append(alt_name)
            match_count += 1

    logger.info(f"别名加载完成: 处理 {line_count:,} 行，匹配 {match_count:,} 条，覆盖 {len(result)} 个实体")
    return result


def merge_country_aliases(countries: list[dict], alt_names: dict) -> list[dict]:
    """将 alternateNames 中的别名合并到国家记录中"""
    merged_count = 0

    for country in countries:
        geoname_id = country.get("source_id", "")
        if geoname_id in alt_names:
            entry = alt_names[geoname_id]

            # 设置中文名称（优先使用preferred name）
            if entry.get("zh_preferred"):
                country["country_name_zh"] = entry["zh_preferred"]
            elif entry.get("zh"):
                country["country_name_zh"] = entry["zh"][0]

            # 合并别名（去重）
            all_aliases = set()
            all_aliases.add(country["country_name"])  # 英文名
            if country["country_name_zh"]:
                all_aliases.add(country["country_name_zh"])  # 中文名
            for name in entry.get("zh", []):
                all_aliases.add(name)
            for name in entry.get("en", []):
                all_aliases.add(name)

            country["aliases"] = sorted(all_aliases)
            merged_count += 1

    logger.info(f"合并别名: {merged_count}/{len(countries)} 个国家有别名数据")
    return countries


def apply_country_fallbacks(countries: list[dict]) -> list[dict]:
    for country in countries:
        country_code = country.get("country_code", "")
        fallback = COUNTRY_FALLBACKS.get(country_code)
        if not fallback:
            continue

        if not country.get("country_name_zh") and fallback.get("country_name_zh"):
            country["country_name_zh"] = fallback["country_name_zh"]

        aliases = set(country.get("aliases", []))
        aliases.add(country.get("country_name", ""))
        if country.get("country_name_zh"):
            aliases.add(country["country_name_zh"])
        aliases.add(country_code)
        for alias in fallback.get("aliases", []):
            aliases.add(alias)
        country["aliases"] = sorted(a for a in aliases if a)

    return countries


def load_country_coordinates(cities_filepath: str) -> dict:
    """
    从 cities15000.txt 中提取各国首都坐标作为国家代表坐标

    GeoNames cities15000.txt 列: geonameid, name, asciiname, alternatenames,
    latitude, longitude, feature_class, feature_code, country_code, cc2,
    admin1_code, admin2_code, admin3_code, admin4_code, population,
    elevation, dem, timezone, modification_date
    """
    coords = {}

    if not os.path.exists(cities_filepath):
        logger.warning(f"城市文件不存在，跳过坐标加载: {cities_filepath}")
        return coords

    logger.info(f"正在从城市数据中提取国家首都坐标...")

    with open(cities_filepath, "r", encoding="utf-8") as f:
        for line in f:
            fields = line.strip().split("\t")
            if len(fields) < 9:
                continue

            feature_code = fields[7] if len(fields) > 7 else ""
            country_code = fields[8] if len(fields) > 8 else ""

            # PPLC = capital of a political entity
            if feature_code == "PPLC" and country_code:
                lat = _safe_float(fields[4])
                lng = _safe_float(fields[5])
                if lat is not None and lng is not None:
                    coords[country_code] = {"lat": lat, "lng": lng}

    logger.info(f"获取到 {len(coords)} 个国家的首都坐标")
    return coords


def build_countries_dict(skip_alt_names: bool = False):
    """构建国家词典主流程"""

    # 1. 解析 countryInfo.txt
    country_info_path = os.path.join(RAW_DIR, "countryInfo.txt")
    if not os.path.exists(country_info_path):
        logger.error(f"缺少原始数据文件: {country_info_path}")
        logger.error("请先运行 download_geonames_data.py 下载数据")
        return False

    countries = parse_country_info(country_info_path)

    # 2. 加载别名（如果有 alternateNamesV2.txt）
    if not skip_alt_names:
        alt_names_path = os.path.join(RAW_DIR, "alternateNamesV2.txt")
        if os.path.exists(alt_names_path):
            target_ids = {c["source_id"] for c in countries if c.get("source_id")}
            alt_names = load_alternate_names(alt_names_path, target_ids, languages={"zh", "en"})
            countries = merge_country_aliases(countries, alt_names)
        else:
            logger.warning("alternateNamesV2.txt 不存在，跳过别名合并")

    # 3. 补充国家坐标（从城市数据中取首都坐标）
    cities_path = os.path.join(RAW_DIR, "cities15000.txt")
    if os.path.exists(cities_path):
        coords = load_country_coordinates(cities_path)
        for country in countries:
            cc = country["country_code"]
            if cc in coords:
                country["lat"] = coords[cc]["lat"]
                country["lng"] = coords[cc]["lng"]

    countries = apply_country_fallbacks(countries)

    # 4. 排序并输出
    countries.sort(key=lambda c: c["country_code"])

    output = {
        "version": "1.0",
        "source": "GeoNames (CC BY 4.0)",
        "source_url": "https://download.geonames.org/export/dump/",
        "description": "全球国家词典，基于GeoNames countryInfo.txt清洗生成",
        "total_count": len(countries),
        "countries": {c["country_code"]: c for c in countries},
    }

    output_path = os.path.join(OUTPUT_DIR, "countries.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"国家词典生成完成: {output_path}")
    logger.info(f"  总记录数: {len(countries)}")
    logger.info(f"  有中文名: {sum(1 for c in countries if c.get('country_name_zh'))}")
    logger.info(f"  有坐标: {sum(1 for c in countries if c.get('lat') is not None)}")

    # 输出几个示例
    for cc in ["CN", "US", "GB", "JP"]:
        if cc in output["countries"]:
            c = output["countries"][cc]
            logger.info(f"  示例 [{cc}]: {c['country_name']} / {c.get('country_name_zh', 'N/A')}")

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
    parser = argparse.ArgumentParser(description="从 GeoNames 生成国家词典")
    parser.add_argument("--download", action="store_true", help="先下载原始数据再生成")
    parser.add_argument("--skip-alt-names", action="store_true", help="跳过别名处理（加速测试）")
    args = parser.parse_args()

    if args.download:
        from download_geonames_data import download_all
        if not download_all():
            logger.error("数据下载失败，终止生成")
            exit(1)

    build_countries_dict(skip_alt_names=args.skip_alt_names)
