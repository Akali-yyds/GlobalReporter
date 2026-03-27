"""
Comprehensive geographic entity extraction from news text.
Supports countries, provinces/states, major cities — English + Chinese.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class GeoMatch:
    name: str
    geo_key: str  # e.g. "CN_BJ", "US_CA", "US"
    geo_type: str  # "country" | "province" | "city"
    confidence: float
    start_pos: int
    end_pos: int


# ── Country maps ──────────────────────────────────────────────────────────────

# English name → ISO-2
EN_COUNTRY: Dict[str, str] = {
    # Asia
    "china": "CN", "beijing": "CN", "shanghai": "CN", "shenzhen": "CN",
    "guangzhou": "CN", "hong kong": "CN", "hk": "CN", "taiwan": "TW",
    "japan": "JP", "tokyo": "JP", "osaka": "JP", "south korea": "KR",
    "korea": "KR", "seoul": "KR", "busan": "KR", "north korea": "KP",
    "india": "IN", "new delhi": "IN", "mumbai": "IN", "indonesia": "ID",
    "jakarta": "ID", "thailand": "TH", "bangkok": "TH", "vietnam": "VN",
    "hanoi": "VN", "malaysia": "MY", "kuala lumpur": "MY",
    "philippines": "PH", "manila": "PH", "singapore": "SG", "nepal": "NP",
    "pakistan": "PK", "islamabad": "PK", "bangladesh": "BD", "dhaka": "BD",
    # Europe
    "uk": "GB", "united kingdom": "GB", "britain": "GB", "england": "GB",
    "london": "GB", "manchester": "GB", "scotland": "GB", "germany": "DE",
    "berlin": "DE", "munich": "DE", "frankfurt": "DE", "france": "FR",
    "paris": "FR", "marseille": "FR", "russia": "RU", "moscow": "RU",
    "st. petersburg": "RU", "ukraine": "UA", "kyiv": "UA", "kiev": "UA",
    "poland": "PL", "warsaw": "PL", "spain": "ES", "madrid": "ES",
    "barcelona": "ES", "italy": "IT", "rome": "IT", "milan": "IT",
    "netherlands": "NL", "amsterdam": "NL", "belgium": "BE", "brussels": "BE",
    "switzerland": "CH", "zurich": "CH", "austria": "AT", "vienna": "AT",
    "sweden": "SE", "stockholm": "SE", "norway": "NO", "oslo": "NO",
    "denmark": "DK", "copenhagen": "DK", "finland": "FI", "helsinki": "FI",
    "greece": "GR", "athens": "GR", "portugal": "PT", "lisbon": "PT",
    "ireland": "IE", "dublin": "IE", "czech": "CZ", "prague": "CZ",
    "hungary": "HU", "budapest": "HU", "romania": "RO", "bucharest": "RO",
    "bulgaria": "BG", "sofia": "BG", "croatia": "HR", "zagreb": "HR",
    # Americas
    "usa": "US", "united states": "US", "america": "US", "washington": "US",
    "new york": "US", "los angeles": "US", "san francisco": "US",
    "chicago": "US", "boston": "US", "miami": "US", "texas": "US",
    "california": "US", "new york city": "US", "canada": "CA",
    "toronto": "CA", "vancouver": "CA", "mexico": "MX", "mexico city": "MX",
    "brazil": "BR", "rio de janeiro": "BR", "sao paulo": "BR",
    "argentina": "AR", "buenos aires": "AR", "chile": "CL", "santiago": "CL",
    "colombia": "CO", "bogota": "CO", "peru": "PE", "lima": "PE",
    # Middle East
    "israel": "IL", "jerusalem": "IL", "tel aviv": "IL", "iran": "IR",
    "tehran": "IR", "saudi": "SA", "saudi arabia": "SA", "uae": "AE",
    "united arab emirates": "AE", "dubai": "AE", "qatar": "QA", "doha": "QA",
    "iraq": "IQ", "bagdad": "IQ", "syria": "SY", "damascus": "SY",
    "turkey": "TR", "istanbul": "TR", "ankara": "TR", "lebanon": "LB",
    "beirut": "LB", "jordan": "JO", "amman": "JO", "egypt": "EG",
    "cairo": "EG", "pakistan": "PK",
    # Africa
    "south africa": "ZA", "nigeria": "NG", "kenya": "KE", "nairobi": "KE",
    "egypt": "EG", "ethiopia": "ET", "morocco": "MA", "tunisia": "TN",
    "algeria": "DZ", "ghana": "GH", "tanzania": "TZ", "uganda": "UG",
    # Oceania
    "australia": "AU", "sydney": "AU", "melbourne": "AU", "auckland": "NZ",
    "new zealand": "NZ", "fiji": "FJ",
}

# Chinese name → ISO-2
ZH_COUNTRY: Dict[str, str] = {
    # 国家
    "中国": "CN", "北京": "CN", "上海": "CN", "深圳": "CN", "广州": "CN",
    "香港": "CN", "澳门": "CN", "台湾": "TW", "日本": "JP", "东京": "JP",
    "大阪": "JP", "韩国": "KR", "首尔": "KR", "朝鲜": "KP", "印度": "IN",
    "新德里": "IN", "印度尼西亚": "ID", "雅加达": "ID", "泰国": "TH",
    "曼谷": "TH", "越南": "VN", "河内": "VN", "马来西亚": "MY",
    "吉隆坡": "MY", "新加坡": "SG", "菲律宾": "PH", "马尼拉": "PH",
    "巴基斯坦": "PK", "伊斯兰堡": "PK", "孟加拉": "BD", "达卡": "BD",
    # 欧洲
    "英国": "GB", "伦敦": "GB", "曼彻斯特": "GB", "德国": "DE", "柏林": "DE",
    "慕尼黑": "DE", "法兰克福": "DE", "法国": "FR", "巴黎": "FR",
    "马赛": "FR", "俄罗斯": "RU", "莫斯科": "RU", "圣彼得堡": "RU",
    "乌克兰": "UA", "基辅": "UA", "波兰": "PL", "华沙": "PL",
    "西班牙": "ES", "马德里": "ES", "巴塞罗那": "ES", "意大利": "IT",
    "罗马": "IT", "米兰": "IT", "荷兰": "NL", "阿姆斯特丹": "NL",
    "比利时": "BE", "布鲁塞尔": "BE", "瑞士": "CH", "苏黎世": "CH",
    "奥地利": "AT", "维也纳": "AT", "瑞典": "SE", "斯德哥尔摩": "SE",
    "挪威": "NO", "奥斯陆": "NO", "丹麦": "DK", "哥本哈根": "DK",
    "芬兰": "FI", "赫尔辛基": "FI", "希腊": "GR", "雅典": "GR",
    "葡萄牙": "PT", "里斯本": "PT", "爱尔兰": "IE", "都柏林": "IE",
    # 中东
    "以色列": "IL", "耶路撒冷": "IL", "伊朗": "IR", "德黑兰": "IR",
    "沙特": "SA", "沙特阿拉伯": "SA", "阿联酋": "AE", "迪拜": "AE",
    "卡塔尔": "QA", "多哈": "QA", "伊拉克": "IQ", "巴格达": "IQ",
    "叙利亚": "SY", "大马士革": "SY", "土耳其": "TR", "伊斯坦布尔": "TR",
    "安卡拉": "TR", "黎巴嫩": "LB", "贝鲁特": "LB", "约旦": "JO",
    "安曼": "JO", "埃及": "EG", "开罗": "EG",
    # 美洲
    "美国": "US", "华盛顿": "US", "纽约": "US", "洛杉矶": "US",
    "旧金山": "US", "芝加哥": "US", "波士顿": "US", "迈阿密": "US",
    "加州": "US", "得克萨斯": "US", "加拿大": "CA", "多伦多": "CA",
    "温哥华": "CA", "墨西哥": "MX", "巴西": "BR", "里约热内卢": "BR",
    "圣保罗": "BR", "阿根廷": "AR", "布宜诺斯艾利斯": "AR", "智利": "CL",
    "圣地亚哥": "CL", "哥伦比亚": "CO", "波哥大": "CO", "秘鲁": "PE",
    # 非洲
    "南非": "ZA", "尼日利亚": "NG", "肯尼亚": "KE", "内罗毕": "KE",
    "埃及": "EG", "摩洛哥": "MA", "埃塞俄比亚": "ET",
    # 大洋洲
    "澳大利亚": "AU", "悉尼": "AU", "墨尔本": "AU", "新西兰": "NZ",
    "奥克兰": "NZ",
}

# Chinese province/state → ISO-2 (for sub-country granularity)
ZH_PROVINCE: Dict[str, str] = {
    # 中国省份
    "北京": "CN", "上海": "CN", "天津": "CN", "重庆": "CN",
    "河北": "CN", "石家庄": "CN", "山西": "CN", "太原": "CN",
    "辽宁": "CN", "沈阳": "CN", "大连": "CN", "吉林": "CN", "长春": "CN",
    "黑龙江": "CN", "哈尔滨": "CN", "江苏": "CN", "南京": "CN", "苏州": "CN",
    "浙江": "CN", "杭州": "CN", "宁波": "CN", "温州": "CN", "义乌": "CN",
    "安徽": "CN", "合肥": "CN", "福建": "CN", "福州": "CN", "厦门": "CN",
    "泉州": "CN", "江西": "CN", "南昌": "CN", "山东": "CN", "济南": "CN",
    "青岛": "CN", "河南": "CN", "郑州": "CN", "湖北": "CN", "武汉": "CN",
    "湖南": "CN", "长沙": "CN", "广东": "CN", "广州": "CN", "深圳": "CN",
    "东莞": "CN", "佛山": "CN", "珠海": "CN", "海南": "CN", "海口": "CN",
    "四川": "CN", "成都": "CN", "贵州": "CN", "贵阳": "CN", "云南": "CN",
    "昆明": "CN", "陕西": "CN", "西安": "CN", "甘肃": "CN", "兰州": "CN",
    "青海": "CN", "西宁": "CN", "内蒙古": "CN", "呼和浩特": "CN",
    "广西": "CN", "南宁": "CN", "桂林": "CN", "西藏": "CN", "拉萨": "CN",
    "宁夏": "CN", "银川": "CN", "新疆": "CN", "乌鲁木齐": "CN",
    "香港": "CN", "澳门": "CN", "台湾省": "TW",
}

# US state abbreviations and full names → "US"
US_STATES: Dict[str, str] = {
    "california": "US", "texas": "US", "florida": "US", "new york": "US",
    "illinois": "US", "pennsylvania": "US", "ohio": "US", "georgia": "US",
    "michigan": "US", "washington": "US", "arizona": "US", "massachusetts": "US",
    "tennessee": "US", "indiana": "US", "missouri": "US", "maryland": "US",
    "wisconsin": "US", "colorado": "US", "minnesota": "US", "south carolina": "US",
    "alabama": "US", "louisiana": "US", "kentucky": "US", "oregon": "US",
    "oklahoma": "US", "connecticut": "us", "nevada": "US", "utah": "US",
    "iowa": "US", "arkansas": "US", "mississippi": "US", "kansas": "US",
    "new jersey": "US", "nebraska": "US", "idaho": "US", "west virginia": "US",
    "hawaii": "US", "new mexico": "US", "rhode island": "US", "montana": "US",
    "delaware": "US", "south dakota": "US", "north dakota": "US", "alaska": "US",
    "vermont": "US", "wyoming": "US", "maine": "US", "new hampshire": "US",
    "rhode island": "US", "connecticut": "US",
    "ca": "US", "tx": "US", "fl": "US", "ny": "US", "il": "US", "pa": "US",
    "oh": "US", "ga": "US", "mi": "US", "wa": "US", "az": "US", "ma": "US",
    "tn": "US", "in": "US", "mo": "US", "md": "US", "wi": "US", "co": "US",
    "mn": "US", "sc": "US", "al": "US", "la": "US", "ky": "US", "or": "US",
    "ok": "US", "nv": "US", "ut": "US", "ia": "US", "ar": "US", "ms": "US",
    "ks": "US", "nm": "US", "wv": "US", "hi": "US",
}

US_STATE_ABBR = {key for key in US_STATES if len(key) == 2}


class GeoExtractor:
    """
    Extracts geographic entities from news text with country/province/city granularity.
    """

    def extract_countries(self, text: str) -> List[GeoMatch]:
        matches: List[GeoMatch] = []
        text_lower = text.lower()

        for pattern, code in EN_COUNTRY.items():
            if pattern.isascii():
                rx = r'\b' + re.escape(pattern) + r'\b'
                for m in re.finditer(rx, text_lower):
                    matches.append(GeoMatch(
                        name=m.group(),
                        geo_key=code,
                        geo_type="country",
                        confidence=1.0,
                        start_pos=m.start(),
                        end_pos=m.end(),
                    ))
            else:
                for m in re.finditer(re.escape(pattern), text):
                    matches.append(GeoMatch(
                        name=m.group(),
                        geo_key=code,
                        geo_type="country",
                        confidence=1.0,
                        start_pos=m.start(),
                        end_pos=m.end(),
                    ))

        for pattern, code in ZH_COUNTRY.items():
            for m in re.finditer(re.escape(pattern), text):
                matches.append(GeoMatch(
                    name=m.group(),
                    geo_key=code,
                    geo_type="country",
                    confidence=1.0,
                    start_pos=m.start(),
                    end_pos=m.end(),
                ))

        for pattern, code in US_STATES.items():
            source_text = text if pattern in US_STATE_ABBR else text_lower
            source_pattern = pattern.upper() if pattern in US_STATE_ABBR else pattern
            rx = r'\b' + re.escape(source_pattern) + r'\b'
            for m in re.finditer(rx, source_text):
                matches.append(GeoMatch(
                    name=m.group(),
                    geo_key=code,
                    geo_type="country",
                    confidence=0.85,
                    start_pos=m.start(),
                    end_pos=m.end(),
                ))

        return self._dedup(matches)

    def extract_provinces(self, text: str) -> List[GeoMatch]:
        matches: List[GeoMatch] = []
        text_lower = text.lower()

        # Chinese provinces
        for pattern, code in ZH_PROVINCE.items():
            for m in re.finditer(re.escape(pattern), text):
                matches.append(GeoMatch(
                    name=m.group(),
                    geo_key=f"{code}_PROVINCE",
                    geo_type="province",
                    confidence=0.9,
                    start_pos=m.start(),
                    end_pos=m.end(),
                ))

        # English provinces/states
        for pattern, code in US_STATES.items():
            source_text = text if pattern in US_STATE_ABBR else text_lower
            source_pattern = pattern.upper() if pattern in US_STATE_ABBR else pattern
            rx = r'\b' + re.escape(source_pattern) + r'\b'
            for m in re.finditer(rx, source_text):
                matches.append(GeoMatch(
                    name=m.group(),
                    geo_key=f"{code}_STATE",
                    geo_type="province",
                    confidence=0.85,
                    start_pos=m.start(),
                    end_pos=m.end(),
                ))

        return self._dedup(matches)

    def extract_all(self, text: str) -> List[GeoMatch]:
        all_m: List[GeoMatch] = []
        all_m.extend(self.extract_countries(text))
        all_m.extend(self.extract_provinces(text))
        all_m.sort(key=lambda x: (-x.confidence, x.start_pos))
        return all_m

    def get_country_tags(self, text: str) -> List[str]:
        matches = self.extract_countries(text)
        seen: set[str] = set()
        out: List[str] = []
        for m in matches:
            if m.geo_key not in seen:
                seen.add(m.geo_key)
                out.append(m.geo_key)
        return out

    def get_primary_country(self, text: str) -> Optional[str]:
        matches = self.extract_countries(text)
        return matches[0].geo_key if matches else None

    def extract(self, text: str) -> List[Dict]:
        return [
            {
                "name": m.name,
                "geo_key": m.geo_key,
                "type": m.geo_type,
                "confidence": m.confidence,
            }
            for m in self.extract_all(text)
        ]

    @staticmethod
    def _dedup(matches: List[GeoMatch]) -> List[GeoMatch]:
        if not matches:
            return []
        pos_map: Dict[int, List[GeoMatch]] = {}
        for m in matches:
            pos_map.setdefault(m.start_pos, []).append(m)
        result = []
        for pos, ms in pos_map.items():
            best = max(ms, key=lambda x: (x.confidence, x.end_pos - x.start_pos))
            result.append(best)
        result.sort(key=lambda x: x.start_pos)
        return result
