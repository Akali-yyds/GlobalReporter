# GlobalReporter

面向全球热点新闻聚合与空间可视化场景的本地优先项目。

项目将“新闻抓取 -> 去重聚合 -> 地理提取 -> 事件入库 -> 3D 地球展示 -> 国家 / 地区钻取”串成一条完整链路，适合用于新闻热点发现、空间数据展示、爬虫与可视化联调，以及本地演示场景。

## 视频演示

- Bilibili 演示视频：[GlobalReporter 项目演示](https://www.bilibili.com/video/BV1DqQuBzEwa/?spm_id_from=333.1387.homepage.video_card.click&vd_source=c341905eeed943c3cfd84258750f594e)

如果你想先快速看效果，建议先看视频，再按下文步骤本地启动项目。

## 核心能力

- 聚合国内、国际、亚洲区域与 Google News 等多类新闻源
- 自动抓取新闻标题、摘要、正文、来源、发布时间与热度信息
- 对新闻进行去重与事件聚合，生成适合前端展示的热点事件
- 对新闻做国家 / 地区 / 城市级地理提取，并建立事件地理映射
- 在 3D 地球上展示热点事件点位与国家热度着色
- 支持国家下钻到 `admin1` 区域，并在侧栏查看区域新闻
- 支持 API 内后台定时爬取与手动触发爬取
- 支持 Docker 启动，也支持本地开发模式
- 提供 Windows 一键启动脚本，自动拉起前后端并打开浏览器

## 架构概览

| 服务 | 目录 | 说明 |
|------|------|------|
| 前端 | `web-app/` | 基于 React + Vite 的可视化页面，负责 3D 地球、热点列表、地区钻取等交互 |
| API | `api-service/` | 基于 FastAPI 的后端服务，负责新闻写入、事件聚合、热点查询、任务触发等 |
| 爬虫 | `crawler-service/` | 基于 Scrapy 的采集服务，负责新闻抓取、清洗、去重、地理提取与入库 |
| 数据库 | PostgreSQL | 存储新闻源、文章、事件、地理实体与爬取任务记录 |

### 数据流

1. Scrapy spider 抓取新闻列表、详情页或 RSS。
2. Pipeline 清洗文本、生成去重标识、执行地理提取。
3. 爬虫通过数据库直连或 HTTP 调用将数据送入 API。
4. API 将文章写入 `news_articles`，并聚合为 `news_events`。
5. 地理结果写入 `geo_entities` 与 `event_geo_mappings`。
6. 前端通过热点接口、国家接口和区域接口完成可视化展示。

## 技术栈

### 前端

- React 18
- TypeScript
- Vite
- Zustand
- Axios
- react-globe.gl
- Three.js

### 后端

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL

### 爬虫与数据处理

- Scrapy
- scrapy-playwright
- itemloaders
- lxml
- 自定义地理词典与地理实体标准化流程

### 基础设施

- Docker
- Docker Compose
- Windows `.bat` 一键启动脚本

## 项目结构

```text
GlobalReporter/
├─ api-service/
│  ├─ app/
│  │  ├─ api/                 # FastAPI 路由
│  │  ├─ schemas/             # Pydantic schema
│  │  ├─ services/            # 业务逻辑、事件聚合、地理聚合
│  │  ├─ static/              # GeoJSON 等静态资源
│  │  ├─ config.py
│  │  ├─ crawler_runner.py    # API 内后台爬虫调度
│  │  ├─ database.py
│  │  └─ main.py              # FastAPI 入口
│  ├─ alembic/
│  ├─ tests/
│  ├─ requirements.txt
│  └─ alembic.ini
├─ crawler-service/
│  ├─ news_crawler/
│  │  ├─ spiders/
│  │  │  ├─ china/
│  │  │  ├─ world/
│  │  │  ├─ asia/
│  │  │  └─ google_news/
│  │  ├─ utils/               # 地理提取、词典、清洗与辅助工具
│  │  ├─ pipelines.py         # 清洗、去重、地理提取、入库
│  │  ├─ items.py
│  │  └─ settings.py
│  ├─ tests/
│  ├─ requirements.txt
│  └─ scrapy.cfg
├─ web-app/
│  ├─ src/
│  ├─ package.json
│  └─ vite.config.ts
├─ docker-compose.yml
├─ .env.example
├─ start_frontend_backend.bat
└─ README.md
```

## 运行环境

- Node.js 18+
- Python 3.11+
- PostgreSQL 14+
- Windows 本地开发环境下，建议直接使用项目根目录的 `.venv`
- 如果使用 Docker，本机只需要准备 Docker Desktop

## 快速开始

### 1. 配置环境变量

复制模板文件：

```powershell
Copy-Item .env.example .env
```

建议优先关注以下配置：

```env
API_PORT=8000
WEB_PORT=3000
POSTGRES_PORT=5432
DATABASE_URL=postgresql://ainewser:ainewser_secure_pass_2024@localhost:5432/ainewser
API_BASE_URL=http://127.0.0.1:8000
CRAWLER_ENABLED=true
CRAWLER_INTERVAL_SECONDS=300
CRAWLER_SPIDER=sina
VITE_API_PROXY_TARGET=http://localhost:8000
```

说明：

- `DATABASE_URL` 是后端和爬虫共同使用的数据库连接
- `API_BASE_URL` 用于爬虫将抓到的新闻提交到 FastAPI
- `CRAWLER_ENABLED=true` 时，API 启动后会在后台周期性触发爬虫
- `VITE_API_PROXY_TARGET` 用于前端开发模式下代理 `/api` 与 `/static`

### 2. 安装依赖

如果根目录还没有虚拟环境，可以先初始化：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r api-service\requirements.txt
pip install -r crawler-service\requirements.txt
```

安装前端依赖：

```powershell
cd web-app
npm install
cd ..
```

### 3. 初始化数据库

先确保本地 PostgreSQL 已启动，或先用 Docker 拉起数据库：

```powershell
docker compose up -d postgres
```

然后执行数据库迁移：

```powershell
cd api-service
..\.venv\Scripts\python.exe -m alembic upgrade head
```

### 4. 启动项目

方式一：使用一键启动脚本（Windows，推荐）

```powershell
.\start_frontend_backend.bat
```

这个脚本会自动完成以下动作：

- 读取 `.env` 中的前后端端口
- 自动检测端口占用并切换到可用端口
- 尝试通过 Docker 启动 PostgreSQL
- 分别启动前端和后端
- 自动打开浏览器

方式二：手动分别启动

启动后端：

```powershell
cd api-service
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动前端：

```powershell
cd web-app
npm run dev
```

访问地址：

- 前端开发地址：[http://localhost:3000](http://localhost:3000)
- 后端 API：[http://localhost:8000](http://localhost:8000)
- Swagger 文档：[http://localhost:8000/docs](http://localhost:8000/docs)

## Docker 启动

### 1. 启动全部服务

```powershell
docker compose up -d
```

### 2. 查看服务状态

```powershell
docker compose ps
```

### 3. 查看日志

```powershell
docker compose logs -f api
docker compose logs -f crawler
docker compose logs -f web
```

补充说明：

- `postgres` 提供数据库
- `api` 提供 FastAPI 服务
- `crawler` 是独立爬虫容器
- `web` 提供前端页面
- Docker 模式下前端默认映射到宿主机 `WEB_PORT`，容器内部端口为 `80`
- 如果你已经启用了 API 内的后台爬虫，建议不要再同时长期运行独立 `crawler` 容器，以免重复抓取

## 新闻源与爬虫

当前代码中已实现的 spider 包括：

### 国内新闻源

- `bilibili_hot`
- `sina`
- `tencent`
- `weibo`
- `xinhua`
- `zhihu`

### 国际新闻源

- `abc_news`
- `aljazeera`
- `ap`
- `bbc`
- `cbs_news`
- `cnn`
- `dw`
- `euronews`
- `fox_news`
- `france24`
- `ft`
- `global_times`
- `guardian`
- `nbc_news`
- `nhk_world`
- `pbs_newshour`
- `reuters`
- `rfi`
- `sky_news`
- `times_of_india`
- `voa`

### 亚洲区域源

- `cna`
- `ndtv`
- `nhk`
- `scmp`
- `straits_times`

### Google News 聚合源

- `google_news_cn`
- `google_news_en`

手动运行单个爬虫示例：

```powershell
cd crawler-service
..\.venv\Scripts\python.exe -m scrapy crawl sina
..\.venv\Scripts\python.exe -m scrapy crawl bbc
..\.venv\Scripts\python.exe -m scrapy crawl google_news_en
```

## 主要接口

| 功能 | 接口 |
|------|------|
| 热点新闻 | `GET /api/news/hot` |
| 新闻详情 | `GET /api/news/events/{event_id}` |
| 地球热点 | `GET /api/globe/hotspots` |
| 国家热点聚合 | `GET /api/hotspots/countries` |
| 国家下的 `admin1` 热点 | `GET /api/hotspots/admin1/{country_code}` |
| 国家下的城市热点 | `GET /api/hotspots/cities/{country_code}` |
| 区域新闻 | `GET /api/globe/regions/{geo_key}/news` |
| 新闻源列表 | `GET /api/sources` |
| 最近爬取任务 | `GET /api/jobs/latest` |
| 手动触发爬取 | `POST /api/jobs/crawl` |

`GET /api/news/hot` 常用参数：

- `page`
- `page_size`
- `scope=all|china|world`
- `category`
- `since_hours`

## 数据库核心表

| 表名 | 说明 |
|------|------|
| `news_sources` | 新闻源定义 |
| `news_articles` | 原始新闻文章 |
| `news_events` | 聚合后的新闻事件 |
| `event_articles` | 事件与文章关联 |
| `geo_entities` | 国家 / 地区 / 城市实体 |
| `event_geo_mappings` | 事件与地理实体映射 |
| `crawl_jobs` | 爬取任务记录 |

## 地理提取说明

当前地理提取链路主要位于：

- `crawler-service/news_crawler/pipelines.py`
- `crawler-service/news_crawler/utils/enhanced_geo_processor.py`
- `crawler-service/news_crawler/utils/geo_text_builder.py`

目前已具备的能力：

- 结合标题、摘要和正文中的高相关句子进行地理提取
- 将地理词标准化到 `country / admin1 / city`
- 保留 `country_code`、`admin1_code`、`city_name` 等关键字段
- 对同名城市尝试根据州 / 省上下文做消歧

当前限制：

- `admin1` 词典仍然不是全世界全覆盖
- 某些文章如果只出现模糊地名或代称，仍可能只停留在国家层
- 非结构化转载文本、极短快讯与标题党文本会影响地区识别效果

## 常用命令

### 前端

```powershell
cd web-app
npm run dev
npm run build
npm run test
```

### 后端

```powershell
cd api-service
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m pytest
```

### 爬虫

```powershell
cd crawler-service
..\.venv\Scripts\python.exe -m scrapy crawl sina
..\.venv\Scripts\python.exe -m scrapy crawl reuters
..\.venv\Scripts\python.exe -m pytest
```

## 排查建议

- 前端页面没有数据：先确认后端是否真正启动在当前代理端口上
- `/api/*` 返回 404：通常是前端代理到了错误端口，或后端没有启动成功
- 国家没有热度颜色：先检查 `/api/hotspots/countries` 是否返回数据
- 国家能点开但地区为空：先检查对应国家是否存在 `admin1` GeoJSON 与可用的地区提取结果
- 爬虫能抓到新闻但前端没显示：先检查 `API_BASE_URL`、数据库连接和 `/api/news/ingest` 是否成功
- 数据库连接失败：先确认 PostgreSQL 已启动，并执行过 `alembic upgrade head`
- 一键启动脚本未拉起数据库：脚本依赖本机安装 Docker；如果没有 Docker，请先手动启动 PostgreSQL

## 备注

- 项目当前主要面向本地开发与演示环境
- `.env` 不要提交真实数据库密码
- 如果同时启用 API 内后台爬虫与独立 `crawler` 容器，需要注意避免重复抓取
- 如果后续继续扩展地区级可视化，优先建议补充更多国家的 `admin1` 词典与 GeoJSON
