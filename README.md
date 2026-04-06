# AiNewser

面向全球热点新闻聚合与空间可视化场景的本地优先项目。  
项目把「新闻抓取 -> 去重聚合 -> 地理提取 -> 事件入库 -> 3D 地球展示 -> 国家 / 地区钻取」串成一条完整链路，后端使用 FastAPI + SQLAlchemy，爬虫使用 Scrapy，前端使用 React + Vite + react-globe.gl。

## 当前能力

- 聚合国内、国际、亚洲区域与 Google News 等多类新闻源
- 自动抓取新闻标题、摘要、正文、来源、发布时间与热度信息
- 对新闻进行去重与事件聚合，生成可供前端展示的热点事件
- 对新闻做国家 / 地区 / 城市级地理提取，并建立事件地理映射
- 在 3D 地球上展示热点新闻点位与国家热度着色
- 支持国家下钻到 admin1 地区层，并在侧栏查看区域新闻
- 支持后台定时爬取与手动触发爬取
- 支持 Docker 启动，也支持本地开发模式
- 提供一键启动前后端并自动打开浏览器的 Windows 脚本

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
│  ├─ requirements.txt
│  └─ alembic.ini
├─ crawler-service/
│  ├─ news_crawler/
│  │  ├─ spiders/
│  │  │  ├─ china/            # 国内新闻源
│  │  │  ├─ world/            # 国际新闻源
│  │  │  ├─ asia/             # 亚洲区域新闻源
│  │  │  └─ google_news/      # Google News 聚合源
│  │  ├─ utils/               # 地理提取、词典、清洗与辅助工具
│  │  ├─ pipelines.py         # 清洗、去重、地理提取、入库
│  │  ├─ items.py
│  │  └─ settings.py
│  ├─ tests/
│  ├─ requirements.txt
│  └─ scrapy.cfg
├─ web-app/
│  ├─ src/
│  │  ├─ components/
│  │  ├─ services/
│  │  ├─ stores/
│  │  ├─ types/
│  │  ├─ utils/
│  │  ├─ App.tsx
│  │  └─ main.tsx
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
- 如果使用 Docker，则本机只需要准备 Docker Desktop

## 快速开始

### 1. 配置环境变量

复制模板文件：

```powershell
Copy-Item .env.example .env
```

最少需要关注这些配置：

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
- `API_BASE_URL` 用于爬虫把抓到的新闻提交到 FastAPI
- `CRAWLER_ENABLED=true` 时，API 启动后会在后台周期性触发爬虫
- `VITE_API_PROXY_TARGET` 用于前端开发模式下代理 `/api` 和 `/static`

### 2. 安装后端依赖

```powershell
cd api-service
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如果你还没有根目录虚拟环境，也可以这样初始化：

```powershell
cd ..
python -m venv .venv
.\.venv\Scripts\activate
pip install -r api-service\requirements.txt
pip install -r crawler-service\requirements.txt
```

### 3. 安装前端依赖

```powershell
cd web-app
npm install
```

### 4. 初始化数据库

```powershell
cd ..\api-service
..\.venv\Scripts\python.exe -m alembic upgrade head
```

### 5. 启动项目

方式一：使用一键启动脚本（Windows，推荐）

```powershell
cd ..
.\start_frontend_backend.bat
```

这个脚本会：

- 读取 `.env` 中的前后端端口
- 自动检测端口占用并切换到可用端口
- 尝试通过 Docker 启动 PostgreSQL
- 分别启动前端和后端
- 自动打开浏览器

方式二：手动分别启动

后端：

```powershell
cd api-service
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

前端：

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
```

说明：

- `postgres` 提供数据库
- `api` 提供 FastAPI 服务
- `crawler` 是独立爬虫容器
- `web` 提供前端页面
- 如果你已经启用了 API 内的后台爬虫，建议把 compose 中的独立 `crawler` 与它错开使用，避免重复抓取

## 爬虫与新闻源

当前项目包含这些新闻源类型：

### 国内新闻源

- `sina`
- `tencent`
- `weibo`
- `xinhua`
- `zhihu`

### 国际新闻源

- `aljazeera`
- `ap`
- `bbc`
- `cnn`
- `dw`
- `france24`
- `ft`
- `global_times`
- `guardian`
- `reuters`
- `rfi`

### 亚洲区域源

- `cna`
- `ndtv`
- `nhk`
- `scmp`

### Google News 聚合源

- `google_news_cn`
- `google_news_en`

## 数据流说明

项目主流程如下：

1. Scrapy spider 抓取新闻列表或 RSS
2. Pipeline 清洗文本、生成 hash、做地理提取
3. 爬虫通过直连或 HTTP 调用把数据送入 API
4. API 将文章写入 `news_articles`，并聚合为 `news_events`
5. 同时写入 `geo_entities` 与 `event_geo_mappings`
6. 前端通过热点接口、国家接口和地区接口进行可视化展示

## 主要接口

### 热点新闻

```http
GET /api/news/hot
```

常用参数：

- `page`
- `page_size`
- `scope=all|china|world`
- `category`
- `since_hours`

### 新闻详情

```http
GET /api/news/events/{event_id}
```

### 地球热点

```http
GET /api/globe/hotspots
```

### 国家热点聚合

```http
GET /api/hotspots/countries
```

### 国家下的 admin1 热点

```http
GET /api/hotspots/admin1/{country_code}
```

### 国家下的城市热点

```http
GET /api/hotspots/cities/{country_code}
```

### 区域新闻

```http
GET /api/globe/regions/{geo_key}/news
```

### 新闻源列表

```http
GET /api/sources
```

### 最近爬取任务

```http
GET /api/jobs/latest
```

### 手动触发爬取

```http
POST /api/jobs/crawl
```

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

当前地理提取链路位于：

- `crawler-service/news_crawler/pipelines.py`
- `crawler-service/news_crawler/utils/enhanced_geo_processor.py`
- `crawler-service/news_crawler/utils/geo_text_builder.py`

目前已做的能力包括：

- 结合标题、摘要和正文中的地理高相关句子做提取
- 将地理词标准化到 `country / admin1 / city`
- 同时保留 `country_code`、`admin1_code`、`city_name`
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
```

### 爬虫

```powershell
cd crawler-service
..\.venv\Scripts\python.exe -m scrapy crawl sina
..\.venv\Scripts\python.exe -m scrapy crawl bbc
..\.venv\Scripts\python.exe -m scrapy crawl cnn
```

### 测试

```powershell
cd api-service
..\.venv\Scripts\python.exe -m pytest

cd ..\crawler-service
..\.venv\Scripts\python.exe -m pytest
```

## 排查建议

- 前端页面没有数据：先确认后端是否真正启动在当前代理端口上
- `/api/*` 返回 404：通常是前端代理到了错误端口，或后端没有启动成功
- 国家没有热度颜色：先检查 `/api/hotspots/countries` 是否返回数据
- 国家能点开但地区为空：先检查该国家是否有 `admin1` GeoJSON 和可用的地区提取结果
- 爬虫能抓到新闻但前端没显示：先检查 `API_BASE_URL`、数据库连接、`/api/news/ingest` 是否成功
- 数据库连接失败：先确认 PostgreSQL 已启动，并执行过 `alembic upgrade head`
- 一键启动脚本未拉起数据库：脚本依赖本机安装 Docker；没有 Docker 时请自己先启动 PostgreSQL

## 备注

- 项目当前主要面向本地开发与演示环境
- `.env` 不要提交真实数据库密码
- 如果同时启用 API 内后台爬虫与独立 crawler 容器，要注意避免重复抓取
- 如果你后续继续扩展地区级可视化，优先建议补充更多国家的 `admin1` 词典与 GeoJSON
