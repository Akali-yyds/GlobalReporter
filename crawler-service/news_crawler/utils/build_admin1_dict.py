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

# 需要生成 admin1 词典的目标国家
TARGET_COUNTRIES = {
    "CN": {"output_file": "china_admin1.json", "country_name": "China", "admin1_type": "Province/Municipality/AR"},
    "US": {"output_file": "usa_admin1.json", "country_name": "United States", "admin1_type": "State/Territory"},
    "GB": {"output_file": "uk_admin1.json", "country_name": "United Kingdom", "admin1_type": "Country/Region"},
    "JP": {"output_file": "japan_admin1.json", "country_name": "Japan", "admin1_type": "Prefecture"},
}

# GeoNames admin1CodesASCII.txt 格式:
# code(CC.admin1_code) \t name \t name_ascii \t geonameId
ADMIN1_COLUMNS = ["code", "name", "name_ascii", "geoname_id"]


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

    logger.info(f"获取到 {len(coords)} 个 admin1 代表坐标")
    return coords


def load_alternate_names_for_admin1(alt_names_path: str, target_ids: set) -> dict:
    """加载 admin1 的中文别名"""
    if not os.path.exists(alt_names_path):
        logger.warning(f"alternateNames 文件不存在: {alt_names_path}")
        return {}

    logger.info(f"正在加载 admin1 别名数据...")
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

            # 只取中文和英文
            if iso_lang not in ("zh", "en", "ja", ""):
                continue

            if geoname_id not in result:
                result[geoname_id] = {"zh": [], "en": [], "ja": [], "aliases": [], "zh_preferred": ""}

            entry = result[geoname_id]

            if iso_lang == "zh":
                if is_preferred and not entry["zh_preferred"]:
                    entry["zh_preferred"] = alt_name
                entry["zh"].append(alt_name)
            elif iso_lang == "en":
                entry["en"].append(alt_name)
            elif iso_lang == "ja":
                entry["ja"].append(alt_name)

            entry["aliases"].append(alt_name)
            match_count += 1

    logger.info(f"别名加载完成: 处理 {line_count:,} 行，匹配 {match_count:,} 条")
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
        aliases = set(admin1.get("aliases", []))
        aliases.add(admin1.get("admin1_name", ""))
        aliases.add(admin1_name_zh)
        admin1["aliases"] = sorted(a for a in aliases if a)


def build_admin1_dicts(skip_alt_names: bool = False):
    """构建各国 admin1 词典主流程"""

    # 1. 解析 admin1CodesASCII.txt
    admin1_path = os.path.join(RAW_DIR, "admin1CodesASCII.txt")
    if not os.path.exists(admin1_path):
        logger.error(f"缺少原始数据文件: {admin1_path}")
        logger.error("请先运行 download_geonames_data.py 下载数据")
        return False

    country_codes = set(TARGET_COUNTRIES.keys())
    admin1_list = parse_admin1_codes(admin1_path, country_codes=country_codes)

    # 2. 加载别名
    if not skip_alt_names:
        alt_names_path = os.path.join(RAW_DIR, "alternateNamesV2.txt")
        if os.path.exists(alt_names_path):
            target_ids = {a["source_id"] for a in admin1_list if a.get("source_id")}
            alt_names = load_alternate_names_for_admin1(alt_names_path, target_ids)

            for admin1 in admin1_list:
                gid = admin1.get("source_id", "")
                if gid in alt_names:
                    entry = alt_names[gid]

                    # 设置中文名
                    if entry.get("zh_preferred"):
                        admin1["admin1_name_zh"] = entry["zh_preferred"]
                    elif entry.get("zh"):
                        admin1["admin1_name_zh"] = entry["zh"][0]

                    # 合并别名
                    all_aliases = set()
                    all_aliases.add(admin1["admin1_name"])
                    if admin1["admin1_name_zh"]:
                        all_aliases.add(admin1["admin1_name_zh"])
                    for n in entry.get("zh", []):
                        all_aliases.add(n)
                    for n in entry.get("en", []):
                        all_aliases.add(n)
                    admin1["aliases"] = sorted(all_aliases)
        else:
            logger.warning("alternateNamesV2.txt 不存在，跳过别名合并")

    apply_cn_admin1_fallback_names(admin1_list)

    # 3. 补充坐标
    cities_path = os.path.join(RAW_DIR, "cities15000.txt")
    if os.path.exists(cities_path):
        coords = load_admin1_coordinates(cities_path, country_codes)
        for admin1 in admin1_list:
            key = (admin1["country_code"], admin1["admin1_code"])
            if key in coords:
                admin1["lat"] = coords[key]["lat"]
                admin1["lng"] = coords[key]["lng"]

    # 4. 按国家分组输出
    for cc, config in TARGET_COUNTRIES.items():
        country_admin1s = [a for a in admin1_list if a["country_code"] == cc]
        country_admin1s.sort(key=lambda a: a["admin1_code"])

        # 设置 admin1_type 和 country_name
        for a in country_admin1s:
            a["admin1_type"] = config["admin1_type"]
            a["country_name"] = config["country_name"]

        output = {
            "version": "1.0",
            "source": "GeoNames (CC BY 4.0)",
            "source_url": "https://download.geonames.org/export/dump/",
            "country_code": cc,
            "country_name": config["country_name"],
            "description": f"{config['country_name']} admin1 词典，基于 GeoNames admin1CodesASCII.txt 清洗生成",
            "total_count": len(country_admin1s),
            "admin1_regions": {a["admin1_code"]: a for a in country_admin1s},
        }

        output_path = os.path.join(OUTPUT_DIR, config["output_file"])
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"生成 {config['output_file']}: {len(country_admin1s)} 条记录")
        zh_count = sum(1 for a in country_admin1s if a.get("admin1_name_zh"))
        coord_count = sum(1 for a in country_admin1s if a.get("lat") is not None)
        logger.info(f"  有中文名: {zh_count}, 有坐标: {coord_count}")

        # 输出前3个示例
        for a in country_admin1s[:3]:
            logger.info(f"  示例: {a['admin1_code']} = {a['admin1_name']} / {a.get('admin1_name_zh', 'N/A')}")

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
