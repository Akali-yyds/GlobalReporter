可以。下面我给你一份**适合直接放进项目仓库的完整 TODO 清单**，已经结合了你当前项目现状：

* 项目：**AiNewser**
* 当前状态：**P0 ~ P3 已完成；P4 / P5 / P8 / P9 正在推进**
* 已落地能力：**多层地理建模、词典与提取链路、热点聚合 API、静态 geodata、前端国家 -> admin1 钻取**
* 当前重点：**真实 crawler 链路联调、历史回填抽样验证、前端交互打磨与收口**

---

# AiNewser 完整 TODO 清单

## 项目阶段总览

* [x] P0 - 地理建模与迁移准备
* [x] P1 - 数据库迁移与字段增强
* [x] P2 - 地理词典与标准化基础设施
* [x] P3 - 地区提取模块重构
* [ ] P4 - 数据回填与质量验证
* [ ] P5 - 爬虫源稳定化与数据质量增强
* [ ] P6 - API 服务升级（核心能力已落地，待收口）
* [ ] P7 - 地理数据与静态资源体系（主体已落地，待城市点位）
* [ ] P8 - 前端多层地球展示（国家 -> admin1 已打通）
* [ ] P9 - 钻取交互与详情联动（基础链路已打通）
* [ ] P10 - 性能优化
* [ ] P11 - 调度、监控与运维
* [ ] P12 - 测试、验收与文档完善

---

# P0 - 地理建模与迁移准备（已完成）

## 目标

确定地理建模方向，避免后续返工。

## TODO

* [x] 明确地理展示分层：`country / admin1 / city`
* [x] 明确 `precision_level` 枚举设计
* [x] 明确 `display_mode` 枚举设计
* [x] 明确 `geo_entities` 与 `event_geo_mappings` 职责边界
* [x] 评估是否需要 `geo_hierarchies`
* [x] 评估是否需要 PostGIS
* [x] 明确前端 polygon / point / list_only 规则
* [x] 输出地理升级方案文档

## 验收

* [x] 数据建模方案定稿
* [x] TODO 顺序明确
* [x] 开发可进入迁移阶段

---

# P1 - 数据库迁移与字段增强（已完成）

## 目标

为后续地区提取与多层地图展示打好字段基础。

## TODO

* [x] 创建 Alembic 迁移文件
* [x] 为 `geo_entities` 增加字段：

  * [x] `country_code`
  * [x] `country_name`
  * [x] `admin1_code`
  * [x] `admin1_name`
  * [x] `admin2_code`
  * [x] `admin2_name`
  * [x] `city_name`
  * [x] `district_name`
  * [x] `lat`
  * [x] `lng`
  * [x] `precision_level`
  * [x] `geojson_key`
  * [x] `display_mode`
* [x] 为 `event_geo_mappings` 增加字段：

  * [x] `matched_text`
  * [x] `confidence`
  * [x] `relevance_score`
  * [x] `extraction_method`
  * [x] `is_primary`
* [x] 创建必要索引
* [x] 执行迁移
* [x] 验证迁移结果
* [x] 更新 SQLAlchemy 模型
* [x] 执行数据回填检查

## 验收

* [x] 数据库迁移成功
* [x] 模型与数据库一致
* [x] 索引建立完成

---

# P2 - 地理词典与标准化基础设施（已完成）

## 目标

建立基于公开数据源清洗生成的标准化地理词典，为地区提取模块提供可靠输入。

## TODO

### P2.1 数据源选型

* [x] 确定国家词典数据源

  * [x] 优先评估 GeoNames `countryInfo.txt`
  * [x] 确认许可证与使用限制
* [x] 确定 admin1 词典数据源

  * [x] GeoNames `admin1CodesASCII.txt`
  * [ ] 补充别名来源
* [x] 确定城市词典数据源

  * [x] 先采用 GeoNames `cities15000`
  * [x] 在脚本中支持切换到 `cities5000`
* [x] 确定边界 GeoJSON 数据源

  * [x] 全球国家：Natural Earth 110m
  * [x] admin1：Natural Earth 50m 优先，10m 兜底
* [ ] 记录每类数据的来源、许可证、更新时间（GeoNames 已记录，GeoJSON 说明仍待补齐）

### P2.2 目录与原始数据管理

* [x] 创建目录：

  * [x] `crawler-service/news_crawler/utils/geo_dictionaries/`
  * [x] `crawler-service/news_crawler/utils/geo_dictionaries/raw/`
  * [ ] `crawler-service/news_crawler/utils/geo_dictionaries/aliases/`
* [x] 创建 `geo_dictionaries/README.md`
* [x] 约定原始文件命名规则
* [x] 约定生成文件命名规则

### P2.3 统一字段结构定义

* [x] 定义 `countries.json` 输出格式
* [x] 定义 `china_admin1.json` 输出格式
* [x] 定义 `usa_admin1.json` 输出格式
* [x] 定义 `uk_admin1.json` 输出格式
* [x] 定义 `japan_admin1.json` 输出格式
* [x] 定义 `cities_major.json` 输出格式
* [x] 明确通用字段：

  * [x] `source`
  * [x] `source_id`
  * [x] `aliases`
  * [x] `lat`
  * [x] `lng`

### P2.4 清洗脚本

* [x] 创建 `build_countries_dict.py`
* [x] 创建 `build_admin1_dict.py`
* [x] 创建 `build_cities_dict.py`
* [x] 实现国家数据清洗逻辑
* [x] 实现 admin1 数据清洗逻辑
* [x] 实现城市数据清洗逻辑
* [x] 去重与标准化
* [x] 输出 JSON
* [x] 补充国家 fallback 别名（`中国` / `USA` / `英国` / `日本`）
* [x] 补充中国 admin1 中文 fallback
* [ ] 合并多语言别名（等待 `alternateNamesV2.txt`）

### P2.5 词典加载器

* [x] 创建 `geo_dictionary_loader.py`
* [x] 实现：

  * [x] `load_all()`
  * [x] `find_country(name)`
  * [x] `find_admin1(name, country_code=None)`
  * [x] `find_city(name, country_code=None)`
  * [x] `normalize_location(text)`
* [x] 构建内存索引
* [x] 支持中英文别名匹配
* [x] 支持缓存

### P2.6 最小验证

* [x] 编写词典验证脚本
* [x] 验证以下输入能正确命中：

  * [x] 中国
  * [x] 北京
  * [x] 北京市
  * [x] China
  * [x] USA
  * [x] California
  * [x] Tokyo
  * [x] London
  * [x] 广东省
* [x] 输出验证结果报告

## 验收

* [x] 词典文件生成成功
* [x] 加载器可用
* [x] 重点国家与主要城市可命中
* [ ] 数据来源可追溯（词典已可追溯，GeoJSON 文档仍待补充）

---

# P3 - 地区提取模块重构（已完成，待联调收尾）

## 目标

把 `geo_extractor` 升级成可批量处理、可解释、可评分的地理提取模块。

## TODO

### P3.1 核心模块设计

* [x] 创建 `enhanced_geo_processor.py`
* [x] 创建 `location_matcher.py`
* [x] 保留旧 `geo_extractor.py` 作为过渡或兼容层
* [x] 定义提取结果数据结构

### P3.2 文本处理

* [ ] 标题清洗
* [ ] 摘要清洗
* [ ] 正文清洗
* [ ] 中英文分词/切词策略确认
* [ ] 标题 / 摘要 / 正文权重规则确定

### P3.3 地名候选提取

* [x] 词典匹配
* [x] 正则匹配
* [x] 多语言别名匹配
* [x] 行政后缀识别（省、市、州、县、区等）

### P3.4 分层识别

* [x] 国家识别
* [x] admin1 识别
* [ ] admin2 识别（先预留）
* [x] 城市识别
* [x] 点位提取支持

### P3.5 消歧与评分

* [x] 重名地名消歧
* [x] 上下文国家推断
* [x] 标题优先级打分
* [x] 多候选置信度排序
* [x] 生成 `confidence`
* [x] 生成 `is_primary`

### P3.6 输出标准化结构

* [x] 输出 country 结果
* [x] 输出 admin1 结果
* [x] 输出 city 结果
* [x] 输出 `precision_level`
* [x] 输出 `display_mode`
* [x] 输出 `matched_text`
* [x] 输出 `lat/lng`

### P3.7 集成到 Pipeline

* [x] 改造 `GeoExtractionPipeline`
* [x] 将标准化结果写入数据库
* [x] 增加兜底逻辑
* [x] 增加异常日志

## 验收

* [x] 新闻可提取出结构化地理结果
* [x] 一条新闻可支持多个地理结果
* [x] 可标记主地区
* [x] 结果可直接供 API 使用

### 当前剩余风险

* [x] 已完成真实 PostgreSQL rollback smoke：`api-service/validate_geo_ingest_smoke.py` 可正常连接、入库、接口回读并事务回滚
* [ ] 仍需补一轮真实 crawler 调度链路联调，确认 `GeoExtractionPipeline -> /api/news/ingest -> /api/news/events/{id}` 在实跑路径上稳定
* [x] 已补充真实环境 smoke 脚本：`api-service/validate_geo_ingest_smoke.py`（默认事务回滚，不留脏数据）
* [ ] `api-service/app/crawler_runner.py` 的 scope spider 列表、`crawler-service/scheduler.py` 的 `DEFAULT_SPIDERS`、以及 `news_sources` 注册口径仍需统一
* [ ] admin1 词典覆盖仍依赖当前已生成国家集合，部分非重点国家可能只能先落到 country / city

---

# P4 - 数据回填与质量验证（进行中）

## 目标

验证地理提取效果，建立反馈闭环。

## TODO

* [x] 编写历史新闻地理回填脚本
* [x] 补充质量概览脚本（`api-service/geo_quality_overview.py`）
* [x] 已跑一轮历史事件地理回填并生成结果样例（见 `backfill_result.json`）
* [x] 质量概览已输出覆盖率、`event_level` 分布、可疑样例（见 `quality_result.json`）
* [x] 已根据样例收紧误判：过滤连续 Title Case 人名片段中的单词级城市候选（如 `Mason`）
* [x] 修复复合连字符误判：`Mar-a-Lago` 中的 `Lago` 被识别为错误城市（regex `?` 改 `*`）
* [ ] 对现有新闻重新执行地理提取
* [ ] 抽样 100~300 条新闻人工验证
* [ ] 统计国家级命中率
* [ ] 统计 admin1 级命中率
* [ ] 统计 city 级命中率
* [ ] 统计误判类型
* [ ] 输出质量评估报告
* [ ] 根据误判结果调整规则和词典

## 验收

* [ ] 国家级准确率达到目标
* [ ] admin1 提取可用
* [ ] 常见错误有可解释原因
* [x] 已进入 API 开发阶段

---

# P5 - 爬虫源稳定化与数据质量增强（进行中）

## 目标

提升各新闻源的可用性和结构化质量。

## TODO

### P5.1 新闻源维护

* [x] 新增新闻源审计脚本：`crawler-service/source_audit.py`
* [x] 新增 `news_sources` 同步脚本：`crawler-service/sync_news_sources.py`
* [x] 修复 `crawler-service/scheduler.py` 中 `crawl_jobs` 状态更新误用 `source_id` 的问题
* [x] 梳理当前默认调度源：`sina / global_times / tencent / cnn / ap / bbc / guardian / reuters / aljazeera / dw / france24 / cna / scmp / nhk / ndtv`
* [ ] 将 `sync_news_sources.py --commit` 应用到真实库并回归 `source_audit.py`
* [ ] 对默认调度源逐个做实跑验证与解析回归
* [x] 统一 `api-service/app/crawler_runner.py` 的 scope spider 列表与 `scheduler.DEFAULT_SPIDERS`
* [ ] 修复解析失效 spider
* [ ] 增加字段完整性校验

### P5.2 采集质量

* [ ] 标题提取稳定化
* [ ] 摘要提取稳定化
* [x] 发布时间标准化（base.py + news_ingest.py 均支持 RFC 2822 / ISO 8601 / 时间戳）
* [ ] 正文抽取质量提升
* [ ] 来源名称标准化

### P5.3 去重与事件聚合

* [x] 优化 URL 去重（`_normalize_url`：去 tracking 参数、路径末斜杠）
* [x] 优化标题归一化（去来源后缀如 `- BBC News`、去标点）
* [x] 优化事件合并逻辑（热度累加、main_country 保留、is_primary 标记）
* [ ] 提升多来源同事件聚合效果

### P5.4 任务与失败处理

* [x] 爬虫任务日志增强（结构化输出 scraped/dropped/elapsed）
* [x] 失败重试策略（`_run_scrapy_with_retry`，非致命错误自动重试一次）
* [ ] 单源重跑能力
* [ ] 异常报警预留

## 验收

* [ ] 默认调度源可稳定抓取
* [ ] 结构化字段完整率可接受
* [ ] 事件聚合基本可用

---

# P6 - API 服务升级（进行中）

## 目标

提供适合前端分层地球展示与详情联动的数据接口。

## TODO

### P6.1 地理热点接口

* [x] 新增 `hotspots.py` 路由（替代 geo_layers.py）
* [x] 实现 `GET /api/hotspots/countries`
* [x] 实现 `GET /api/hotspots/admin1/{country_code}`
* [x] 实现 `GET /api/globe/regions/{geo_key}/news`（已存在于 globe.py）
* [x] 实现 `GET /api/news/events/{event_id}` geo-mappings（已嵌入事件详情）

### P6.2 现有接口升级

* [x] 升级 `GET /api/news/hot`：新增 `level` + `min_heat` 参数
* [x] 升级 `GET /api/globe/hotspots`：已支持 `scope / limit / min_heat`
* [x] 兼容旧前端结构（未破坏现有字段）
* [x] 支持 `scope / limit / min_heat / level`

### P6.3 服务层

* [x] 新增 `geo_service.py`
* [x] 实现国家级热点聚合（`get_country_hotspots`）
* [x] 实现 admin1 热点聚合（`get_admin1_hotspots`）
* [x] 实现城市点位聚合（`get_city_hotspots` + `/api/hotspots/cities/{cc}`）
* [ ] 支持主地区选择逻辑（后续优化）
* [ ] 实现缓存逻辑（后续优化）

### P6.4 Schema

* [x] 新增地理响应 Schema
* [x] `CountryHotspotItem` / `CountryHotspotListResponse`
* [x] `Admin1HotspotItem` / `Admin1HotspotListResponse`
* [x] Region news list response（已存在）
* [x] Event geo mappings response（已存在）

## 验收

* [x] 国家级接口可用（`GET /api/hotspots/countries`）
* [x] admin1 接口可用（`GET /api/hotspots/admin1/{cc}`）
* [x] 区域详情接口可用（`GET /api/globe/regions/{geo_key}/news`）
* [x] 响应结构前端联调验证（`geoLayerStore` / `GlobeScene` 已接入 country + admin1 热点接口）

---

# P7 - 地理数据与静态资源体系（进行中）

## 目标

建立全球国家 + 重点国家 admin1 + 城市点位的数据资源体系。

## TODO

### P7.1 静态资源目录

* [x] 创建 `api-service/app/static/geodata/`
* [x] 创建国家级边界目录 (`countries/`)
* [x] 创建 admin1 目录 (`admin1/`)
* [x] 创建 geodata 索引文件
* [x] 挂载 FastAPI StaticFiles 至 `/static`

### P7.2 国家级边界

* [x] 下载全球国家 GeoJSON（Natural Earth 110m，476KB）
* [x] `prepare_geodata.py` 一键下载并部署
* [x] FastAPI 静态服务已验证可访问

### P7.3 admin1 边界

* [x] 已准备 admin1 边界国家：`AU / BR / CN / DE / FR / GB / IN / IR / JP / KR / RU / SA / TR / US`
* [x] 重点国家 `CN / US / GB / JP` 已验证可用于前端钻取
* [x] `prepare_geodata.py` 自动双源策略：50m 优先，10m 兜底

### P7.4 城市点位

* [ ] 准备主要城市坐标数据（待 P9 补充）
* [ ] 标准化到统一格式

### P7.5 数据索引

* [x] 生成 `geodata_index.json`（含 ready 状态 + available_countries + url_pattern）
* [x] 记录国家与 admin1 文件映射
* [x] 记录版本与更新时间

## 验收

* [x] 国家边界可渲染（`/static/geodata/countries/...` 已验证）
* [x] admin1 数据可按国家加载（当前 `geodata_index.json` 已有 14 个国家 ready）
* [ ] 城市点位可用（待 P9）

---

# P8 - 前端多层地球展示（进行中）

## 目标

让地球支持 `country polygon + admin1 polygon + city point` 三层展示。

## TODO

### P8.1 Store 升级

* [x] 新增 `geoLayerStore.ts`（Zustand，管理 global/country 层级）
* [x] `countryHeatMap`：来自 `/api/hotspots/countries`（server-side 聚合）
* [x] `admin1Hotspots`：来自 `/api/hotspots/admin1/{cc}`（country 钻取）
* [x] `selectCountry()` / `backToGlobal()` 状态切换
* [x] admin1 GeoJSON 动态加载与本地可用性判定

### P8.2 GlobeScene 重构

* [x] 本地优先 GeoJSON URL（`/static/geodata/...`），GitHub CDN 兜底
* [x] 国家 polygon 热力着色：server-side countryHeatMap（替代 client-side 聚合）
* [x] 国家 polygon click → selectCountry() → admin1 数据钻取
* [x] country 层：admin1 polygon 边界渲染
* [x] 层级指示器 overlay + "返回全球视图"按钮
* [x] `hotspotsApi` 新增至 `api.ts`，`types/news.ts` 补充 geo 响应类型

### P8.3 图层管理

* [x] 国家 polygon click 后加载 admin1.geojson 并展示边界
* [x] admin1 hover tooltip（区域名 + 新闻数量）
* [x] admin1 GeoJSON 加载指示器（loading overlay）
* [x] 城市点位分层显示（country 层展示 city hotspot 点位 + hover tooltip）

### P8.4 详情联动

* [x] hover 显示摘要（global hotspot tooltip）
* [x] click 打开详情面板（global hotspot）
* [x] admin1 click 打开地区新闻面板
* [x] 点击国家直接显示该国相关新闻（country 层新闻面板）
* [x] 同步右侧新闻面板 / 详情面板
* [x] 同步热点列表选中态

## 验收

* [x] 全球视图显示国家热点
* [x] 点击国家进入 admin1 层
* [ ] 城市点位分层展示仍待补全
* [ ] admin1 / city 交互细节仍需继续打磨

---

# P9 - 钻取交互与详情联动（基础链路已打通）

## 目标

实现“点击国家 -> 钻取 admin1 -> 返回上级”的空间交互链路。

## TODO

### P9.1 钻取逻辑

* [x] 点击国家进入国家视图
* [x] 动态加载该国 admin1 数据
* [x] 切换热点聚合层级
* [x] 保持选中路径状态

### P9.2 返回逻辑

* [x] 返回全球视图按钮
* [x] 面包屑导航（全球 › 国家名，点击返回全球）
* [x] 返回上一级按钮（App.tsx regionStack，支持 admin1 层返回国家新闻）
* [x] 历史路径记录（regionStack 局部维护首尾层导航）

### P9.3 详情联动

* [x] 点击 admin1 显示该地区相关新闻
* [x] 点击热点点位显示事件详情
* [x] 右侧面板可在“地区新闻列表 / 事件详情”间切换
* [x] 点击国家直接显示该国相关新闻（当前主要进入 admin1 层）
* [x] 城市点位点击显示该城市相关新闻面板（类似 admin1 地区面板）
* [x] NewsDetailPanel 地区面板增加摘要、数量标识、geo_name、返回上级按钮
* [ ] 多地区新闻展示其全部映射结果（当前详情已返回 `geo_mappings`，前端展示仍较粗）

### P9.4 动画与过渡

* [x] 视角平滑过渡
* [x] 图层切换过渡
* [x] 选中态动画（selectedAdmin1Code 高亮边框 + 上抬效果）
* [x] hover 微抬升 / 发光效果

## 验收

* [x] 点击国家能进入 admin1 层
* [x] 返回交互正常
* [ ] 面板与地图联动仍需继续打磨

---

# P10 - 性能优化（进行中）

## 目标

确保地图展示和接口响应可接受。

## TODO

### P10.1 前端渲染

* [ ] GeoJSON 分包优化
* [x] admin1 按需加载
* [ ] 点位数量控制
* [ ] 多边形数量控制
* [x] 缓存已加载 geodata（admin1 GeoJSON 模块级 Map 缓存）
* [ ] 减少不必要重渲染

### P10.2 API 与数据库

* [x] globe.py hotspot N+1 查询修复（批量 JOIN 一次加载所有 EventGeoMapping + GeoEntity）
* [ ] 热点聚合 SQL 优化
* [x] 常用查询索引优化（Alembic migration 002：复合索引 country_heat + event_primary）
* [x] 接口缓存（TTLCache 应用于 countries/admin1/cities/globe hotspots）
* [ ] 热点数据预聚合（如需要）

### P10.3 资源优化

* [ ] GeoJSON 简化压缩
* [x] 静态资源缓存策略（GeoDataCacheMiddleware：.geojson max-age=3600）
* [ ] gzip / brotli 支持
* [ ] CDN 预留

## 验收

* [ ] 地图操作响应时间达标
* [ ] Geo 数据加载时间可接受
* [ ] 热点接口响应稳定

---

# P11 - 调度、监控与运维

## 目标

保证数据采集和展示长期稳定运行。

## TODO

### P11.1 任务调度

* [ ] 优化周期采集任务
* [x] 支持手动触发单 spider
* [x] 支持手动触发 scope crawl（`china / world / all`）
* [x] 支持任务状态追踪（`/api/jobs` / `/api/jobs/latest` / `/api/jobs/{id}`）
* [ ] 支持失败重试

### P11.2 数据质量监控

* [x] 已有离线审计脚本（`crawler-service/source_audit.py`）
* [ ] 新闻抓取成功率监控
* [ ] 地理提取成功率监控
* [ ] 字段完整率监控
* [ ] 事件聚合异常监控

### P11.3 API 与前端监控

* [ ] API 响应时间监控
* [ ] 前端加载失败监控
* [ ] 地图渲染异常监控
* [ ] 静态资源缺失监控

### P11.4 错误兜底

* [x] 地理数据加载失败兜底（本地 static -> GitHub CDN）
* [ ] 地区提取失败兜底
* [x] 空数据兜底
* [ ] 用户友好错误提示

## 验收

* [ ] 可定位失败原因
* [ ] 关键链路可监控
* [ ] 线上问题可追踪

---

# P12 - 测试、验收与文档完善

## 目标

完成项目收口，形成可持续维护的工程状态。

## TODO

### P12.1 测试

* [x] crawler utils 基础测试（`crawler-service/tests/test_utils.py`）
* [ ] 词典加载器单元测试
* [ ] 地区提取单元测试
* [x] API 接口测试（`api-service/tests/test_api.py`）
* [x] 前端 store 基础测试（`web-app/src/__tests__/components.test.tsx`）
* [ ] 前端关键组件测试
* [ ] 联调测试
* [ ] 回归测试

### P12.2 验收

* [ ] 国家级热点展示验收
* [ ] admin1 钻取验收
* [ ] 城市点位展示验收
* [ ] 地区提取准确率验收
* [ ] 性能验收
* [ ] 稳定性验收

### P12.3 文档

* [ ] 更新 README
* [x] 增加地理词典说明文档
* [ ] 增加 API 文档
* [ ] 增加 GeoJSON 数据说明
* [ ] 增加部署说明
* [ ] 增加运维说明

## 验收

* [ ] 文档能支持新同事接手
* [ ] 系统具备上线和维护基础

---

# 关键验收指标

## 数据层

* [ ] 新新闻中，国家级地理提取准确率达到目标
* [ ] 重点国家 admin1 提取准确率达到目标
* [ ] 城市提取具备可用性
* [ ] 多地区新闻可正确存储多个映射

## API 层

* [ ] 国家级热点接口返回正确
* [ ] admin1 热点接口返回正确
* [ ] 区域详情接口返回正确
* [ ] 事件地理映射接口返回正确

## 前端层

* [ ] 国家 polygon 展示正常
* [ ] admin1 polygon 可钻取加载
* [ ] 城市 point 展示正常
* [ ] hover / click / 面板联动正常

## 性能层

* [ ] 地图基本操作流畅
* [ ] 热点数据加载速度达标
* [ ] admin1 GeoJSON 加载速度可接受

---

# 当前建议的实施顺序

## 已完成

* [x] P0
* [x] P1
* [x] P2
* [x] P3

## 当前进行中

* [ ] P4（已完成脚本与 dry-run，待小批量 commit 回填 + 抽样验证）
* [ ] P5（源清单与调度口径待统一，待真实库注册与逐源联调）
* [ ] P8（国家 -> admin1 已打通，待 city 分层与交互打磨）
* [ ] P9（基础钻取链路已打通，待 breadcrumb / history / country-level list）

## 下一阶段

* [ ] P6（剩余城市聚合 / 主地区逻辑 / 缓存）
* [ ] P7（城市点位资源与 GeoJSON 说明文档）
* [ ] P10

## 收尾阶段

* [ ] P11
* [ ] P12

---

# 当前最重要的下一步

你现在最应该做的是这 5 件事：

* [ ] 执行 `crawler-service/sync_news_sources.py --commit`，按当前默认调度源把 `news_sources` 注册状态与代码配置对齐
* [ ] 回归 `crawler-service/source_audit.py`，确认当前默认调度源都已注册、可创建 job、且最近链路可追踪
* [ ] 统一 `api-service/app/crawler_runner.py` 的手动 scope 源清单与 `crawler-service/scheduler.py` 的 `DEFAULT_SPIDERS`
* [ ] 选 2~3 个默认调度源 + 1~2 个手动 scope 源做实跑联调，确认抓取、地理提取、入库、接口回读链路
* [ ] 以小批量方式执行 `api-service/backfill_event_geo.py --limit N --commit`，随后运行 `api-service/geo_quality_overview.py` 并补一轮 100 条人工抽样
