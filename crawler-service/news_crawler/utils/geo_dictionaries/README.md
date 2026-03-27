# AiNewser 地理词典数据

## 数据来源

所有词典数据均来自公开数据源，通过清洗脚本标准化生成，**非模型生成**。

### 主数据源：GeoNames

- **官网**: https://www.geonames.org/
- **下载**: https://download.geonames.org/export/dump/
- **许可证**: Creative Commons Attribution 4.0 License
- **使用限制**: 需注明数据来源为 GeoNames

### 使用的原始文件

| 文件 | 说明 | 大小 | 下载地址 |
|------|------|------|----------|
| `countryInfo.txt` | 国家基础信息（ISO代码、名称、首都等） | ~30KB | `download.geonames.org/export/dump/countryInfo.txt` |
| `admin1CodesASCII.txt` | 一级行政区编码与名称 | ~50KB | `download.geonames.org/export/dump/admin1CodesASCII.txt` |
| `cities15000.zip` | 人口>15000的城市 | ~2MB | `download.geonames.org/export/dump/cities15000.zip` |
| `alternateNamesV2.zip` | 多语言别名（含中文） | ~250MB | `download.geonames.org/export/dump/alternateNamesV2.zip` |

## 生成的词典文件

| 文件 | 说明 | 生成脚本 |
|------|------|----------|
| `countries.json` | 全球国家词典 | `build_countries_dict.py` |
| `china_admin1.json` | 中国省级行政区 | `build_admin1_dict.py` |
| `usa_admin1.json` | 美国州级行政区 | `build_admin1_dict.py` |
| `uk_admin1.json` | 英国构成国/地区 | `build_admin1_dict.py` |
| `japan_admin1.json` | 日本都道府县 | `build_admin1_dict.py` |
| `cities_major.json` | 全球主要城市 | `build_cities_dict.py` |

## 字段说明

### countries.json
- `country_code`: ISO 3166-1 alpha-2 国家代码
- `country_name`: 英文国家名称
- `country_name_zh`: 中文国家名称
- `aliases`: 别名列表（含中英文）
- `geojson_key`: GeoJSON匹配键
- `lat` / `lng`: 中心坐标
- `source`: 数据来源标识
- `source_id`: GeoNames geonameId

### admin1 词典
- `country_code`: 所属国家代码
- `country_name`: 所属国家英文名
- `admin1_code`: GeoNames admin1代码
- `admin1_name`: 英文名称
- `admin1_name_zh`: 中文名称
- `admin1_type`: 行政区类型
- `aliases`: 别名列表
- `geojson_key`: GeoJSON匹配键
- `lat` / `lng`: 中心坐标
- `source`: 数据来源标识
- `source_id`: GeoNames geonameId

### cities_major.json
- `city_name`: 英文城市名称
- `city_name_zh`: 中文城市名称
- `aliases`: 别名列表
- `country_code`: 所属国家代码
- `country_name`: 所属国家英文名
- `admin1_code`: 所属admin1代码
- `admin1_name`: 所属admin1名称
- `lat` / `lng`: 坐标
- `population`: 人口数量
- `precision_level`: 精度级别（CITY）
- `source`: 数据来源标识
- `source_id`: GeoNames geonameId

## 生成方式

```bash
# 1. 下载原始数据
python build_countries_dict.py --download

# 2. 生成国家词典
python build_countries_dict.py

# 3. 生成admin1词典
python build_admin1_dict.py

# 4. 生成城市词典
python build_cities_dict.py
```

## 更新时间

- 首次生成: 2026-03-24
- GeoNames 数据快照: 2026-03-24

## raw/ 目录

存放从 GeoNames 下载的原始文件，不纳入版本控制。
