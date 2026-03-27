#!/usr/bin/env python3
"""
地理词典统一加载器

提供统一的词典加载、查询和缓存接口，供 EnhancedGeoProcessor 调用。

功能:
- load_all(): 加载所有词典到内存
- find_country(name): 按名称/别名查找国家
- find_admin1(name, country_code=None): 按名称/别名查找admin1
- find_city(name, country_code=None): 按名称/别名查找城市
- normalize_location(text): 标准化地理名称

设计原则:
- 不硬编码任何具体国家/地区名称
- 所有匹配基于词典数据驱动
- 支持中英文别名匹配
- 首次加载后缓存到内存
"""

import os
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_DIR = os.path.join(SCRIPT_DIR, "geo_dictionaries")


class GeoDictionaryLoader:
    """地理词典加载器"""

    def __init__(self, dict_dir: str = None):
        self._dict_dir = dict_dir or DICT_DIR
        self._loaded = False

        # 原始词典数据
        self._countries_data = {}  # {country_code: {...}}
        self._admin1_data = {}    # {country_code: {admin1_code: {...}}}
        self._cities_data = []    # [{...}, ...]

        # 查找索引（名称 -> 记录列表）
        self._country_index = {}   # {normalized_name: [country_record, ...]}
        self._admin1_index = {}    # {normalized_name: [admin1_record, ...]}
        self._city_index = {}      # {normalized_name: [city_record, ...]}

        # 国家代码反向索引
        self._country_by_code = {}  # {country_code: country_record}

    def load_all(self) -> bool:
        """加载所有词典文件并构建索引"""
        if self._loaded:
            return True

        logger.info("正在加载地理词典...")
        success = True

        # 1. 加载国家词典
        countries_path = os.path.join(self._dict_dir, "countries.json")
        if os.path.exists(countries_path):
            success &= self._load_countries(countries_path)
        else:
            logger.warning(f"国家词典不存在: {countries_path}")

        # 2. 加载 admin1 词典（自动扫描所有 *_admin1.json 文件）
        for filename in os.listdir(self._dict_dir):
            if filename.endswith("_admin1.json"):
                filepath = os.path.join(self._dict_dir, filename)
                success &= self._load_admin1(filepath)

        # 3. 加载城市词典
        cities_path = os.path.join(self._dict_dir, "cities_major.json")
        if os.path.exists(cities_path):
            success &= self._load_cities(cities_path)
        else:
            logger.warning(f"城市词典不存在: {cities_path}")

        self._loaded = True

        logger.info(f"词典加载完成:")
        logger.info(f"  国家: {len(self._countries_data)} 条")
        logger.info(f"  Admin1: {sum(len(v) for v in self._admin1_data.values())} 条 ({len(self._admin1_data)} 个国家)")
        logger.info(f"  城市: {len(self._cities_data)} 条")
        logger.info(f"  索引: 国家 {len(self._country_index)} 条, admin1 {len(self._admin1_index)} 条, 城市 {len(self._city_index)} 条")

        return success

    def _load_countries(self, filepath: str) -> bool:
        """加载国家词典并建立索引"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            countries = data.get("countries", {})
            self._countries_data = countries

            for cc, record in countries.items():
                self._country_by_code[cc] = record

                # 建立名称索引
                names_to_index = set()
                names_to_index.add(record.get("country_name", ""))
                names_to_index.add(record.get("country_name_zh", ""))
                names_to_index.add(cc)  # ISO代码
                for alias in record.get("aliases", []):
                    names_to_index.add(alias)

                for name in names_to_index:
                    if not name:
                        continue
                    key = self._normalize(name)
                    if key not in self._country_index:
                        self._country_index[key] = []
                    self._country_index[key].append(record)

            logger.info(f"  加载国家词典: {len(countries)} 条")
            return True

        except Exception as e:
            logger.error(f"加载国家词典失败: {e}")
            return False

    def _load_admin1(self, filepath: str) -> bool:
        """加载单个国家的 admin1 词典并建立索引"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            country_code = data.get("country_code", "")
            regions = data.get("admin1_regions", {})

            if country_code not in self._admin1_data:
                self._admin1_data[country_code] = {}

            self._admin1_data[country_code].update(regions)

            for admin1_code, record in regions.items():
                names_to_index = set()
                names_to_index.add(record.get("admin1_name", ""))
                names_to_index.add(record.get("admin1_name_ascii", ""))
                names_to_index.add(record.get("admin1_name_zh", ""))
                for alias in record.get("aliases", []):
                    names_to_index.add(alias)

                for name in names_to_index:
                    if not name:
                        continue
                    key = self._normalize(name)
                    if key not in self._admin1_index:
                        self._admin1_index[key] = []
                    self._admin1_index[key].append(record)

            logger.info(f"  加载 admin1 词典 [{country_code}]: {len(regions)} 条 ({os.path.basename(filepath)})")
            return True

        except Exception as e:
            logger.error(f"加载 admin1 词典失败 ({filepath}): {e}")
            return False

    def _load_cities(self, filepath: str) -> bool:
        """加载城市词典并建立索引"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            cities = data.get("cities", [])
            self._cities_data = cities

            for record in cities:
                names_to_index = set()
                names_to_index.add(record.get("city_name", ""))
                names_to_index.add(record.get("city_name_ascii", ""))
                names_to_index.add(record.get("city_name_zh", ""))
                for alias in record.get("aliases", []):
                    names_to_index.add(alias)

                for name in names_to_index:
                    if not name:
                        continue
                    key = self._normalize(name)
                    if key not in self._city_index:
                        self._city_index[key] = []
                    self._city_index[key].append(record)

            logger.info(f"  加载城市词典: {len(cities)} 条")
            return True

        except Exception as e:
            logger.error(f"加载城市词典失败: {e}")
            return False

    # ========== 查询接口 ==========

    def find_country(self, name: str) -> Optional[dict]:
        """
        按名称或别名查找国家

        Args:
            name: 国家名称（中文、英文、ISO代码或别名）

        Returns:
            匹配的国家记录，未找到返回 None
        """
        self._ensure_loaded()
        key = self._normalize(name)
        matches = self._country_index.get(key, [])
        return matches[0] if matches else None

    def find_country_all(self, name: str) -> list[dict]:
        """按名称查找所有匹配的国家（可能有多个）"""
        self._ensure_loaded()
        key = self._normalize(name)
        return self._country_index.get(key, [])

    def find_admin1(self, name: str, country_code: str = None) -> Optional[dict]:
        """
        按名称或别名查找 admin1

        Args:
            name: admin1名称（中文、英文或别名）
            country_code: 可选，限定在特定国家内查找

        Returns:
            匹配的 admin1 记录，未找到返回 None
        """
        self._ensure_loaded()
        key = self._normalize(name)
        matches = self._admin1_index.get(key, [])

        if country_code and matches:
            filtered = [m for m in matches if m.get("country_code") == country_code]
            return filtered[0] if filtered else None

        return matches[0] if matches else None

    def find_admin1_all(self, name: str, country_code: str = None) -> list[dict]:
        """按名称查找所有匹配的 admin1"""
        self._ensure_loaded()
        key = self._normalize(name)
        matches = self._admin1_index.get(key, [])

        if country_code:
            return [m for m in matches if m.get("country_code") == country_code]

        return matches

    def find_city(self, name: str, country_code: str = None) -> Optional[dict]:
        """
        按名称或别名查找城市

        Args:
            name: 城市名称（中文、英文或别名）
            country_code: 可选，限定在特定国家内查找

        Returns:
            匹配的城市记录（优先返回人口最多的），未找到返回 None
        """
        self._ensure_loaded()
        key = self._normalize(name)
        matches = self._city_index.get(key, [])

        if country_code and matches:
            matches = [m for m in matches if m.get("country_code") == country_code]

        if not matches:
            return None

        # 返回人口最多的匹配
        return max(matches, key=lambda m: m.get("population", 0))

    def find_city_all(self, name: str, country_code: str = None) -> list[dict]:
        """按名称查找所有匹配的城市"""
        self._ensure_loaded()
        key = self._normalize(name)
        matches = self._city_index.get(key, [])

        if country_code:
            matches = [m for m in matches if m.get("country_code") == country_code]

        # 按人口降序
        return sorted(matches, key=lambda m: m.get("population", 0), reverse=True)

    def normalize_location(self, text: str) -> dict:
        """
        尝试标准化一段地理文本，按优先级依次匹配 country -> admin1 -> city

        Args:
            text: 地理名称文本

        Returns:
            dict: {
                "matched": bool,
                "match_type": "country" | "admin1" | "city" | None,
                "record": dict | None,
                "input": str
            }
        """
        self._ensure_loaded()

        cleaned = text.strip()
        if not cleaned:
            return {"matched": False, "match_type": None, "record": None, "input": text}

        # 1. 尝试匹配国家
        country = self.find_country(cleaned)
        if country:
            return {
                "matched": True,
                "match_type": "country",
                "record": country,
                "input": text,
            }

        # 2. 尝试匹配 admin1
        admin1 = self.find_admin1(cleaned)
        if admin1:
            return {
                "matched": True,
                "match_type": "admin1",
                "record": admin1,
                "input": text,
            }

        # 3. 尝试匹配城市
        city = self.find_city(cleaned)
        if city:
            return {
                "matched": True,
                "match_type": "city",
                "record": city,
                "input": text,
            }

        # 4. 尝试去除常见后缀后再匹配
        stripped = self._strip_suffixes(cleaned)
        if stripped != cleaned:
            return self.normalize_location(stripped)

        return {"matched": False, "match_type": None, "record": None, "input": text}

    def get_country_by_code(self, country_code: str) -> Optional[dict]:
        """通过ISO代码直接获取国家记录"""
        self._ensure_loaded()
        return self._country_by_code.get(country_code)

    def get_admin1_by_country(self, country_code: str) -> dict:
        """获取某个国家的所有 admin1 记录"""
        self._ensure_loaded()
        return self._admin1_data.get(country_code, {})

    def get_all_countries(self) -> dict:
        """获取所有国家记录"""
        self._ensure_loaded()
        return self._countries_data

    def get_stats(self) -> dict:
        """获取加载统计信息"""
        return {
            "loaded": self._loaded,
            "countries_count": len(self._countries_data),
            "admin1_countries": len(self._admin1_data),
            "admin1_total": sum(len(v) for v in self._admin1_data.values()),
            "cities_count": len(self._cities_data),
            "country_index_size": len(self._country_index),
            "admin1_index_size": len(self._admin1_index),
            "city_index_size": len(self._city_index),
        }

    # ========== 内部方法 ==========

    def _ensure_loaded(self):
        """确保词典已加载"""
        if not self._loaded:
            self.load_all()

    @staticmethod
    def _normalize(name: str) -> str:
        """
        标准化地理名称用于索引匹配

        规则:
        - 转小写（英文）
        - 去除首尾空白
        - 中文保持原样
        """
        if not name:
            return ""
        return name.strip().lower()

    @staticmethod
    def _strip_suffixes(name: str) -> str:
        """
        去除常见的行政区后缀

        支持中文后缀（省、市、区、县等）和英文后缀（Province, State 等）
        """
        # 中文后缀
        zh_suffixes = ["自治区", "特别行政区", "壮族自治区", "维吾尔自治区",
                       "回族自治区", "藏族自治区", "省", "市", "区", "县",
                       "都", "道", "府", "州"]
        for suffix in zh_suffixes:
            if name.endswith(suffix) and len(name) > len(suffix):
                return name[:-len(suffix)]

        # 英文后缀
        en_suffixes = [" province", " state", " prefecture", " county",
                       " region", " territory", " district"]
        name_lower = name.lower()
        for suffix in en_suffixes:
            if name_lower.endswith(suffix) and len(name) > len(suffix):
                return name[:len(name) - len(suffix)]

        return name


# 全局单例
_global_loader = None


def get_loader(dict_dir: str = None) -> GeoDictionaryLoader:
    """获取全局词典加载器单例"""
    global _global_loader
    if _global_loader is None:
        _global_loader = GeoDictionaryLoader(dict_dir)
    return _global_loader


def load_all(dict_dir: str = None) -> GeoDictionaryLoader:
    """加载所有词典并返回加载器"""
    loader = get_loader(dict_dir)
    loader.load_all()
    return loader
