# AiNewser - 全球热点新闻 3D 地球可视化系统

一个以「全球热点新闻 + 3D 地球空间映射」为核心的 Web 应用。

## 功能特性

- 每天批量采集国内外各大平台的热点新闻
- 对新闻做结构化处理（标题、摘要、正文、来源、时间、热度、地区等）
- 新闻去重与事件聚合
- 基于地理映射的 3D 地球可视化展示
- 鼠标悬停显示新闻摘要
- 鼠标点击显示详情面板
- 黑白极简风格 3D 地球

## 技术栈

| 层级 | 技术 |
|------|------|
| 爬虫层 | Python, Scrapy, scrapy-playwright |
| 后端服务 | FastAPI, PostgreSQL, SQLAlchemy, Alembic |
| 前端展示 | React, TypeScript, react-globe.gl, Vite |
| 基础设施 | Docker, Docker Compose |

## 目录结构

```
AiNewser/
├── docker-compose.yml      # Docker Compose 编排
├── .env.example            # 环境变量模板
├── TODO.md                 # 项目 TODO 清单
├── README.md               # 本文档
│
├── api-service/            # 后端 API 服务
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   └── app/
│       ├── main.py         # FastAPI 入口
│       ├── config.py       # 配置管理
│       ├── database.py     # 数据库连接
│       ├── models/         # SQLAlchemy 模型
│       ├── schemas/        # Pydantic Schema
│       ├── api/            # API 路由
│       ├── services/       # 业务逻辑
│       └── crud/           # 数据访问层
│
├── crawler-service/        # 爬虫服务
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── scrapy.cfg
│   └── news_crawler/
│       ├── items.py        # Items 定义
│       ├── pipelines.py    # 数据处理管道
│       ├── settings.py     # 配置
│       ├── spiders/        # Spider 目录
│       │   ├── base.py     # 基础 Spider
│       │   ├── china/      # 中国新闻源
│       │   │   ├── sina.py
│       │   │   ├── tencent.py
│       │   │   ├── zhihu.py
│       │   │   └── weibo.py
│       │   └── world/      # 国际新闻源
│       │       ├── bbc.py
│       │       ├── reuters.py
│       │       └── cnn.py
│       └── utils/          # 工具模块
│           ├── text_cleaner.py
│           ├── geo_extractor.py
│           ├── dedup.py
│           └── normalizer.py
│
└── web-app/                # 前端 Web 应用
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── components/     # React 组件
        │   ├── GlobeScene/
        │   ├── HotspotTooltip/
        │   ├── NewsDetailPanel/
        │   ├── NewsSidebar/
        │   └── FilterBar/
        ├── services/        # API 服务
        ├── stores/         # 状态管理
        ├── hooks/          # 自定义 Hooks
        ├── types/          # TypeScript 类型
        └── utils/          # 工具函数
```

## 快速开始

### 环境要求

- Docker & Docker Compose
- Node.js 18+ (本地开发)
- Python 3.11+ (本地开发)

### 使用 Docker 启动 (推荐)

1. 复制环境变量配置：

```bash
cp .env.example .env
```

2. 启动所有服务：

```bash
docker-compose up -d
```

3. 查看服务状态：

```bash
docker-compose ps
```

4. 查看日志：

```bash
docker-compose logs -f api
```

### 本地开发

#### 后端 API

```bash
cd api-service

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 运行数据库迁移
alembic upgrade head

# 启动服务
uvicorn app.main:app --reload
```

API 服务地址: http://localhost:8000
API 文档: http://localhost:8000/docs

**后台爬虫（与 API 同进程）**

- 默认 `CRAWLER_ENABLED=true`：API 启动约 5 秒后首次执行 `scrapy crawl`，之后按 `CRAWLER_INTERVAL_SECONDS`（默认 300）周期运行；爬虫工作目录为仓库中的 `crawler-service`。
- 请在 **api-service** 虚拟环境中执行 `pip install -r requirements.txt`（已包含 Scrapy）；若 Scrapy 只装在爬虫 venv，可设置环境变量 `CRAWLER_PYTHON` 指向该解释器。
- 爬取到的条目会通过 `POST /api/news/ingest` 写入数据库（`news_articles` + `news_events`），前端「热点新闻」读的是 `NewsEvent`。请确保环境变量 **`API_BASE_URL`** 指向正在运行的 API（默认 `http://127.0.0.1:8000`），否则爬虫无法入库。
- 手动触发：`POST /api/jobs/crawl`（可选 Query：`spider=sina`）。
- Docker Compose：为避免与 `crawler` 容器重复抓取，镜像中默认 `CRAWLER_ENABLED=false`，可在 `.env` 中改为 `true` 仅保留一种方式。

#### 爬虫服务（独立命令行，可选）

```bash
cd crawler-service

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 运行爬虫
scrapy crawl sina
scrapy crawl tencent
scrapy crawl zhihu
scrapy crawl weibo
scrapy crawl bbc
scrapy crawl reuters
scrapy crawl cnn
```

#### 前端 Web

```bash
cd web-app

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端地址: http://localhost:3000

若后端不在 `8000` 端口，在 `web-app/.env` 中设置 `VITE_API_PROXY_TARGET=http://localhost:<端口>`（例如 `8123`），再运行 `npm run dev`。页面每约 45 秒自动刷新列表与热点；顶栏「更新」会请求 `POST /api/jobs/crawl` 并在数秒后重新拉取数据。

## API 接口

### 获取热点新闻

```
GET /api/news/hot
```

参数:
- `page`: 页码 (默认: 1)
- `page_size`: 每页数量 (默认: 20)
- `scope`: 范围 - china/world/all (默认: all)
- `category`: 分类

### 获取地球热点数据

```
GET /api/globe/hotspots
```

参数:
- `scope`: 范围 - china/world/all
- `min_heat`: 最低热度
- `limit`: 限制数量

### 获取地区新闻

```
GET /api/globe/regions/:geoKey/news
```

### 获取新闻事件详情

```
GET /api/news/events/:eventId
```

### 获取新闻源列表

```
GET /api/sources
```

### 获取最近爬取任务

```
GET /api/jobs/latest
```

## 数据库表

| 表名 | 说明 |
|------|------|
| news_sources | 新闻来源 |
| news_articles | 新闻文章 |
| news_events | 新闻事件 |
| event_articles | 事件文章关联 |
| geo_entities | 地理实体 |
| event_geo_mappings | 事件地理映射 |
| crawl_jobs | 爬取任务 |

## 新闻源

### 国内新闻源

- 新浪新闻 (sina)
- 腾讯新闻 (tencent)
- 知乎热榜 (zhihu)
- 微博热搜 (weibo)

### 国际新闻源

- BBC News (bbc)
- Reuters (reuters)
- CNN (cnn)

## 开发说明

### 添加新爬虫

1. 在 `crawler-service/news_crawler/spiders/` 下创建新的 spider 文件
2. 继承 `BaseNewsSpider` 类
3. 实现 `start_requests()` 和 `parse()` 方法
4. 在 `settings.py` 中注册 spider

### 添加新 API

1. 在 `api-service/app/schemas/` 中定义 Pydantic Schema
2. 在 `api-service/app/crud/` 中实现数据访问函数
3. 在 `api-service/app/services/` 中实现业务逻辑
4. 在 `api-service/app/api/` 中定义路由

### 前端组件开发

组件位于 `web-app/src/components/`，使用 React + TypeScript。

## TODO 清单

详见 [TODO.md](TODO.md)

## License

MIT License
