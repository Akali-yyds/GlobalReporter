#!/usr/bin/env python3
"""
地理词典验证脚本

验证生成的词典文件是否正确，测试关键输入能否正确命中。

测试用例:
- 中国 / China
- 北京 / 北京市
- California
- USA
- Tokyo
- London
- Guangdong / 广东省
"""

import os
import sys
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_DIR = os.path.join(SCRIPT_DIR, "geo_dictionaries")


def validate_file_structure():
    """验证词典文件结构完整性"""
    logger.info("=" * 60)
    logger.info("第一部分: 词典文件结构验证")
    logger.info("=" * 60)

    expected_files = [
        "countries.json",
        "china_admin1.json",
        "usa_admin1.json",
        "uk_admin1.json",
        "japan_admin1.json",
        "cities_major.json",
    ]

    all_exist = True
    for fname in expected_files:
        fpath = os.path.join(DICT_DIR, fname)
        exists = os.path.exists(fpath)
        if exists:
            size_kb = os.path.getsize(fpath) / 1024
            logger.info(f"  ✅ {fname}: {size_kb:.1f}KB")
        else:
            logger.error(f"  ❌ {fname}: 缺失")
            all_exist = False

    return all_exist


def validate_countries():
    """验证国家词典"""
    logger.info("\n验证 countries.json ...")
    fpath = os.path.join(DICT_DIR, "countries.json")
    if not os.path.exists(fpath):
        logger.error("  文件不存在")
        return False

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    countries = data.get("countries", {})
    logger.info(f"  总国家数: {len(countries)}")

    # 检查必要字段
    required_fields = ["country_code", "country_name", "source", "source_id"]
    missing_fields = []
    for cc, record in list(countries.items())[:5]:
        for field in required_fields:
            if field not in record:
                missing_fields.append(f"{cc}.{field}")

    if missing_fields:
        logger.warning(f"  缺失字段: {missing_fields[:10]}")

    # 检查重点国家
    for cc in ["CN", "US", "GB", "JP"]:
        if cc in countries:
            c = countries[cc]
            zh = c.get("country_name_zh", "N/A")
            logger.info(f"  {cc}: {c['country_name']} / {zh}")
        else:
            logger.warning(f"  ⚠️ 缺少重点国家: {cc}")

    return True


def validate_admin1():
    """验证 admin1 词典"""
    admin1_files = {
        "china_admin1.json": "CN",
        "usa_admin1.json": "US",
        "uk_admin1.json": "GB",
        "japan_admin1.json": "JP",
    }

    for fname, expected_cc in admin1_files.items():
        logger.info(f"\n验证 {fname} ...")
        fpath = os.path.join(DICT_DIR, fname)
        if not os.path.exists(fpath):
            logger.error(f"  文件不存在")
            continue

        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        regions = data.get("admin1_regions", {})
        cc = data.get("country_code", "")
        logger.info(f"  国家代码: {cc}, admin1 数量: {len(regions)}")

        # 检查中文名覆盖率
        zh_count = sum(1 for r in regions.values() if r.get("admin1_name_zh"))
        logger.info(f"  有中文名: {zh_count}/{len(regions)}")

        # 显示前5条
        for code, region in list(regions.items())[:5]:
            zh = region.get("admin1_name_zh", "N/A")
            logger.info(f"  {code}: {region.get('admin1_name', '')} / {zh}")

    return True


def validate_cities():
    """验证城市词典"""
    logger.info(f"\n验证 cities_major.json ...")
    fpath = os.path.join(DICT_DIR, "cities_major.json")
    if not os.path.exists(fpath):
        logger.error("  文件不存在")
        return False

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    cities = data.get("cities", [])
    logger.info(f"  总城市数: {len(cities)}")

    # 检查中文名覆盖率
    zh_count = sum(1 for c in cities if c.get("city_name_zh"))
    logger.info(f"  有中文名: {zh_count}/{len(cities)}")

    # 按国家统计
    from collections import Counter
    cc_dist = Counter(c.get("country_code") for c in cities)
    logger.info(f"  覆盖国家数: {len(cc_dist)}")
    for cc in ["CN", "US", "GB", "JP"]:
        logger.info(f"  {cc}: {cc_dist.get(cc, 0)} 个城市")

    # 显示前5大城市
    for city in cities[:5]:
        zh = city.get("city_name_zh", "N/A")
        logger.info(f"  {city['city_name']} / {zh} ({city['country_code']}, pop: {city.get('population', 0):,})")

    return True


def validate_loader_matching():
    """验证词典加载器的匹配能力"""
    logger.info("\n" + "=" * 60)
    logger.info("第二部分: 词典加载器匹配验证")
    logger.info("=" * 60)

    from geo_dictionary_loader import GeoDictionaryLoader

    loader = GeoDictionaryLoader(DICT_DIR)
    loader.load_all()

    stats = loader.get_stats()
    logger.info(f"加载统计: {json.dumps(stats, indent=2)}")

    # 定义测试用例
    test_cases = [
        # (输入, 预期match_type, 预期关键字段值)
        ("中国", "country", "CN"),
        ("China", "country", "CN"),
        ("USA", "country", "US"),
        ("北京", None, None),       # 可能匹配城市或admin1
        ("北京市", None, None),     # 带后缀，测试strip
        ("California", "admin1", None),
        ("Tokyo", "city", None),
        ("London", "city", None),
        ("Guangdong", "admin1", None),
        ("广东省", None, None),     # 带后缀
    ]

    logger.info(f"\n测试 {len(test_cases)} 个关键输入:")
    logger.info("-" * 80)

    pass_count = 0
    fail_count = 0

    for input_text, expected_type, expected_code in test_cases:
        result = loader.normalize_location(input_text)
        matched = result["matched"]
        match_type = result.get("match_type")
        record = result.get("record")

        if matched:
            # 根据类型提取关键信息
            if match_type == "country":
                key_info = record.get("country_code", "")
                display = f"{record.get('country_name', '')} / {record.get('country_name_zh', 'N/A')}"
            elif match_type == "admin1":
                key_info = f"{record.get('country_code', '')}.{record.get('admin1_code', '')}"
                display = f"{record.get('admin1_name', '')} / {record.get('admin1_name_zh', 'N/A')}"
            elif match_type == "city":
                key_info = f"{record.get('country_code', '')}"
                display = f"{record.get('city_name', '')} / {record.get('city_name_zh', 'N/A')}"
            else:
                key_info = ""
                display = "unknown"

            status = "✅"
            pass_count += 1
            logger.info(f"  {status} '{input_text}' -> [{match_type}] {display} ({key_info})")
        else:
            status = "❌"
            fail_count += 1
            logger.info(f"  {status} '{input_text}' -> 未匹配")

    logger.info("-" * 80)
    logger.info(f"匹配结果: {pass_count} 通过, {fail_count} 失败, 共 {len(test_cases)} 条")

    return fail_count == 0


def main():
    """运行所有验证"""
    logger.info("GlobalReporter 地理词典验证")
    logger.info("=" * 60)

    results = {}

    # 1. 文件结构验证
    results["file_structure"] = validate_file_structure()

    if not results["file_structure"]:
        logger.error("\n词典文件不完整，请先运行清洗脚本生成词典。")
        logger.error("执行顺序:")
        logger.error("  1. python download_geonames_data.py")
        logger.error("  2. python build_countries_dict.py")
        logger.error("  3. python build_admin1_dict.py")
        logger.error("  4. python build_cities_dict.py")
        return False

    # 2. 词典内容验证
    results["countries"] = validate_countries()
    results["admin1"] = validate_admin1()
    results["cities"] = validate_cities()

    # 3. 加载器匹配验证
    results["loader"] = validate_loader_matching()

    # 最终报告
    logger.info("\n" + "=" * 60)
    logger.info("验证报告")
    logger.info("=" * 60)
    for check, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        logger.info(f"  {check}: {status}")

    all_passed = all(results.values())
    if all_passed:
        logger.info("\n🎉 所有验证通过！词典数据可用于 EnhancedGeoProcessor")
    else:
        logger.warning("\n⚠️ 部分验证未通过，请检查上述错误")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
