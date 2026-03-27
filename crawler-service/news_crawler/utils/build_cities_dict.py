#!/usr/bin/env python3
"""
主要城市词典生成脚本

从 GeoNames cities15000.txt + alternateNamesV2.txt 清洗生成 cities_major.json

数据来源: GeoNames (CC BY 4.0)

筛选策略:
- 全球人口 > 100,000 的城市
- 重点国家 (CN/US/GB/JP) 人口 > 50,000 的城市
- 各国首都无论人口大小都纳入
"""

import os
import json
import logging
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(SCRIPT_DIR, "geo_dictionaries", "raw")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "geo_dictionaries")

# 重点国家（降低人口门槛）
PRIORITY_COUNTRIES = {"CN", "US", "GB", "JP"}
PRIORITY_POP_THRESHOLD = 50_000

# 其他国家的人口门槛
DEFAULT_POP_THRESHOLD = 100_000

DEFAULT_SOURCE_FILE = "cities15000.txt"

# GeoNames cities15000.txt 列定义（TSV格式）
# geonameid, name, asciiname, alternatenames, latitude, longitude,
# feature_class, feature_code, country_code, cc2, admin1_code,
# admin2_code, admin3_code, admin4_code, population, elevation,
# dem, timezone, modification_date
CITY_COLUMNS = [
    "geoname_id", "name", "ascii_name", "alternate_names_inline",
    "latitude", "longitude", "feature_class", "feature_code",
    "country_code", "cc2", "admin1_code", "admin2_code",
    "admin3_code", "admin4_code", "population", "elevation",
    "dem", "timezone", "modification_date"
]


def load_admin1_names(admin1_path: str) -> dict:
    """
    加载 admin1CodesASCII.txt 用于将 admin1_code 映射为名称

    返回: {(country_code, admin1_code): admin1_name}
    """
    mapping = {}

    if not os.path.exists(admin1_path):
        return mapping

    with open(admin1_path, "r", encoding="utf-8") as f:
        for line in f:
            fields = line.strip().split("\t")
            if len(fields) < 2:
                continue
            code_full = fields[0]  # "CN.01"
            name = fields[1]
            parts = code_full.split(".")
            if len(parts) == 2:
                mapping[(parts[0], parts[1])] = name

    return mapping


def load_country_names(countries_json_path: str) -> dict:
    """从已生成的 countries.json 加载国家名称映射"""
    mapping = {}

    if not os.path.exists(countries_json_path):
        return mapping

    with open(countries_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for cc, info in data.get("countries", {}).items():
        mapping[cc] = info.get("country_name", cc)

    return mapping


def parse_cities(
    filepath: str,
    *,
    priority_pop_threshold: int = PRIORITY_POP_THRESHOLD,
    default_pop_threshold: int = DEFAULT_POP_THRESHOLD,
) -> list[dict]:
    """
    解析 GeoNames cities15000.txt

    筛选:
    - 重点国家人口 >= priority_pop_threshold
    - 其他国家人口 >= default_pop_threshold
    - 所有首都 (feature_code == PPLC)
    """
    cities = []

    logger.info(f"正在解析: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            fields = line.strip().split("\t")
            if len(fields) < len(CITY_COLUMNS):
                continue

            row = dict(zip(CITY_COLUMNS, fields))

            country_code = row.get("country_code", "").strip()
            feature_code = row.get("feature_code", "").strip()
            population = _safe_int(row.get("population", "0"))

            # 筛选条件
            is_capital = feature_code == "PPLC"
            is_priority = country_code in PRIORITY_COUNTRIES

            if is_capital:
                pass  # 首都始终纳入
            elif is_priority and population < priority_pop_threshold:
                continue
            elif not is_priority and population < default_pop_threshold:
                continue

            # 从 GeoNames inline alternate names 提取（逗号分隔）
            inline_alts = row.get("alternate_names_inline", "")
            inline_aliases = [n.strip() for n in inline_alts.split(",") if n.strip()] if inline_alts else []

            city = {
                "city_name": row.get("name", "").strip(),
                "city_name_ascii": row.get("ascii_name", "").strip(),
                "city_name_zh": "",  # 稍后从 alternateNames 填充
                "aliases": inline_aliases[:20],  # 限制别名数量
                "country_code": country_code,
                "country_name": "",  # 稍后填充
                "admin1_code": row.get("admin1_code", "").strip(),
                "admin1_name": "",  # 稍后填充
                "lat": _safe_float(row.get("latitude", "")),
                "lng": _safe_float(row.get("longitude", "")),
                "population": population,
                "feature_code": feature_code,
                "is_capital": is_capital,
                "timezone": row.get("timezone", "").strip(),
                "precision_level": "CITY",
                "source": "geonames",
                "source_id": row.get("geoname_id", "").strip(),
            }
            cities.append(city)

    logger.info(f"筛选到 {len(cities)} 个城市")
    logger.info(f"  首都: {sum(1 for c in cities if c['is_capital'])}")
    logger.info(f"  重点国家: {sum(1 for c in cities if c['country_code'] in PRIORITY_COUNTRIES)}")
    logger.info(f"  重点国家人口门槛: {priority_pop_threshold}")
    logger.info(f"  其他国家人口门槛: {default_pop_threshold}")

    return cities


def load_city_alternate_names(alt_names_path: str, target_ids: set) -> dict:
    """加载城市的中文别名"""
    if not os.path.exists(alt_names_path):
        logger.warning(f"alternateNames 文件不存在: {alt_names_path}")
        return {}

    logger.info(f"正在加载城市别名数据...")
    logger.info(f"  目标 geonameId 数量: {len(target_ids)}")

    result = {}
    line_count = 0
    match_count = 0

    with open(alt_names_path, "r", encoding="utf-8") as f:
        for line in f:
            line_count += 1
            if line_count % 5_000_000 == 0:
                logger.info(f"  已处理 {line_count:,} 行，匹配 {match_count:,} 条...")

            fields = line.strip().split("\t")
            if len(fields) < 4:
                continue

            geoname_id = fields[1]
            if geoname_id not in target_ids:
                continue

            iso_lang = fields[2] if len(fields) > 2 else ""
            alt_name = fields[3] if len(fields) > 3 else ""
            is_preferred = fields[4] == "1" if len(fields) > 4 else False

            if not alt_name:
                continue

            if iso_lang not in ("zh", "en"):
                continue

            if geoname_id not in result:
                result[geoname_id] = {"zh": [], "en": [], "zh_preferred": ""}

            entry = result[geoname_id]

            if iso_lang == "zh":
                if is_preferred and not entry["zh_preferred"]:
                    entry["zh_preferred"] = alt_name
                entry["zh"].append(alt_name)
            elif iso_lang == "en":
                entry["en"].append(alt_name)

            match_count += 1

    logger.info(f"别名加载完成: 处理 {line_count:,} 行，匹配 {match_count:,} 条")
    return result


def build_cities_dict(
    skip_alt_names: bool = False,
    *,
    source_filename: str = DEFAULT_SOURCE_FILE,
    priority_pop_threshold: int = PRIORITY_POP_THRESHOLD,
    default_pop_threshold: int = DEFAULT_POP_THRESHOLD,
):
    """构建主要城市词典主流程"""

    # 1. 解析城市源文件
    cities_path = os.path.join(RAW_DIR, source_filename)
    if not os.path.exists(cities_path):
        logger.error(f"缺少原始数据文件: {cities_path}")
        logger.error("请先运行 download_geonames_data.py 下载数据")
        return False

    cities = parse_cities(
        cities_path,
        priority_pop_threshold=priority_pop_threshold,
        default_pop_threshold=default_pop_threshold,
    )

    # 2. 加载中文别名
    if not skip_alt_names:
        alt_names_path = os.path.join(RAW_DIR, "alternateNamesV2.txt")
        if os.path.exists(alt_names_path):
            target_ids = {c["source_id"] for c in cities if c.get("source_id")}
            alt_names = load_city_alternate_names(alt_names_path, target_ids)

            for city in cities:
                gid = city.get("source_id", "")
                if gid in alt_names:
                    entry = alt_names[gid]

                    # 设置中文名
                    if entry.get("zh_preferred"):
                        city["city_name_zh"] = entry["zh_preferred"]
                    elif entry.get("zh"):
                        city["city_name_zh"] = entry["zh"][0]

                    # 合并别名（去重，限制数量）
                    all_aliases = set(city.get("aliases", []))
                    all_aliases.add(city["city_name"])
                    if city["city_name_zh"]:
                        all_aliases.add(city["city_name_zh"])
                    for n in entry.get("zh", []):
                        all_aliases.add(n)
                    for n in entry.get("en", [])[:5]:
                        all_aliases.add(n)
                    city["aliases"] = sorted(all_aliases)[:30]
        else:
            logger.warning("alternateNamesV2.txt 不存在，跳过别名合并")

    # 3. 填充 country_name 和 admin1_name
    countries_json = os.path.join(OUTPUT_DIR, "countries.json")
    country_names = load_country_names(countries_json)

    admin1_path = os.path.join(RAW_DIR, "admin1CodesASCII.txt")
    admin1_names = load_admin1_names(admin1_path)

    for city in cities:
        cc = city["country_code"]
        city["country_name"] = country_names.get(cc, "")
        admin1_key = (cc, city["admin1_code"])
        city["admin1_name"] = admin1_names.get(admin1_key, "")

    # 4. 按人口降序排序
    cities.sort(key=lambda c: c.get("population", 0), reverse=True)

    # 5. 输出
    output = {
        "version": "1.0",
        "source": "GeoNames (CC BY 4.0)",
        "source_url": "https://download.geonames.org/export/dump/",
        "description": f"全球主要城市词典，基于 GeoNames {source_filename} 清洗生成",
        "filter_criteria": {
            "source_filename": source_filename,
            "priority_countries": list(PRIORITY_COUNTRIES),
            "priority_pop_threshold": priority_pop_threshold,
            "default_pop_threshold": default_pop_threshold,
            "capitals_included": True,
        },
        "total_count": len(cities),
        "cities": cities,
    }

    output_path = os.path.join(OUTPUT_DIR, "cities_major.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"城市词典生成完成: {output_path}")
    logger.info(f"  总记录数: {len(cities)}")
    logger.info(f"  有中文名: {sum(1 for c in cities if c.get('city_name_zh'))}")
    logger.info(f"  有坐标: {sum(1 for c in cities if c.get('lat') is not None)}")

    # 按国家统计前10
    from collections import Counter
    cc_dist = Counter(c["country_code"] for c in cities)
    logger.info(f"  城市数前10国家:")
    for cc, count in cc_dist.most_common(10):
        name = country_names.get(cc, cc)
        logger.info(f"    {cc} ({name}): {count}")

    # 输出几个示例
    for city in cities[:5]:
        logger.info(f"  示例: {city['city_name']} / {city.get('city_name_zh', 'N/A')} ({city['country_code']}, pop: {city['population']:,})")

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
    parser = argparse.ArgumentParser(description="从 GeoNames 生成主要城市词典")
    parser.add_argument("--download", action="store_true", help="先下载原始数据再生成")
    parser.add_argument("--skip-alt-names", action="store_true", help="跳过别名处理（加速测试）")
    parser.add_argument("--source-file", default=DEFAULT_SOURCE_FILE, help="城市源文件名，如 cities15000.txt / cities5000.txt")
    parser.add_argument("--priority-pop-threshold", type=int, default=PRIORITY_POP_THRESHOLD, help="重点国家人口门槛")
    parser.add_argument("--default-pop-threshold", type=int, default=DEFAULT_POP_THRESHOLD, help="其他国家人口门槛")
    args = parser.parse_args()

    if args.download:
        from download_geonames_data import download_all
        if not download_all():
            logger.error("数据下载失败，终止生成")
            exit(1)

    build_cities_dict(
        skip_alt_names=args.skip_alt_names,
        source_filename=args.source_file,
        priority_pop_threshold=args.priority_pop_threshold,
        default_pop_threshold=args.default_pop_threshold,
    )
