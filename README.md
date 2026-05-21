# ReelStruct

**爆款结构迁移引擎**

ReelStruct 是一个 AI 短视频创作平台。它从样例视频中拆解脚本结构、镜头节奏和包装方式，再迁移到新的主题、商品信息或用户素材中，生成可解释、可调整、可渲染的新短视频方案。

## 项目目标

- 解析样例视频，提取时长、镜头、字幕和基础结构
- 拆解爆款结构，包括 hook、卖点展开、节奏变化和 CTA
- 将样例结构迁移到新内容，生成脚本、分镜和时间线
- 识别素材缺口，并通过字幕、卡片、重排或素材复用完成补全
- 展示迁移过程，让用户看清结构如何被复用
- 输出时间线可视化或短视频 demo

## 核心流程

```text
样例视频
  -> 结构拆解
  -> 新主题/商品/素材输入
  -> 结构迁移
  -> 素材缺口识别
  -> 补全策略生成
  -> 时间线/成片输出
```

## 技术方向

- 前端：Next.js、React、TypeScript、Tailwind CSS
- 后端：FastAPI、Pydantic、PostgreSQL、Redis
- 异步任务：Celery
- AI 编排：LLM、Agent、结构化 planner
- 视频处理：FFmpeg
- 参考方案：Hyperframes 的时间线描述思路，Remotion 的组件化视频思路

## 复用策略

ReelStruct 是新项目，但不从零重写底层能力。第一阶段会复用 ClipForge_v2 已验证过的媒体能力：

- fixture 素材库和本地 demo 素材
- 素材匹配、复制和下载目录约定
- FFmpeg 渲染思路
- 后续再迁移 Celery worker 和完整 render service

当前已提供 demo 渲染接口：

- `POST /api/media/prepare-demo-assets`：根据 `CompositionSpec` 匹配并准备 fixture clips
- `POST /api/media/render-demo`：根据 `CompositionSpec` 生成一个 demo MP4，返回 `/output/demo.mp4`

## 第一版范围

第一版优先完成比赛 P0 闭环：

- 支持上传 1 个样例视频
- 展示样例基础信息
- 拆解脚本结构和节奏结构
- 输入新主题或商品卖点
- 生成新脚本和分镜时间线
- 标记素材缺口
- 使用字幕、标题卡片或素材复用完成补全
- 提供结果页或视频 demo

## 仓库结构

```text
apps/web/           # Next.js 前端工作台
services/api/       # FastAPI 后端服务
packages/protocol/  # 结构迁移协议示例
docs/               # 设计文档、架构说明、演示说明
```

## 本地启动

启动前端：

```bash
cd apps/web
npm install
npm run dev
```

启动后端：

```bash
cd services/api
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

本地联调时，先启动后端，再启动前端。前端默认把 `/api/*`、`/downloads/*`、`/output/*` 代理到 `http://127.0.0.1:8010`。

打开前端后点击：

```text
生成迁移 demo
```

页面会依次调用：

```text
POST /api/structure/preview
POST /api/media/render-demo
GET  /output/demo.mp4
```

运行后端测试：

```bash
cd services/api
PYTHONPATH=. pytest
```

## 当前状态

项目已完成命名、方向规划和第一版工程骨架。当前后端提供 deterministic 的结构迁移预览接口，前端提供第一版结构迁移工作台界面。
