# ReelStruct

**爆款结构迁移引擎**

ReelStruct 是一个短视频结构迁移 MVP。它把样例视频拆成 Hook、卖点展开、使用过程、CTA 等结构槽位，再迁移到新的商品或主题，生成可解释、可编辑、可渲染的短视频 demo。

## 当前进度

当前版本已经打通第一版演示闭环：

- 样例视频上传和 txt / srt 转写上传
- 样例结构拆解、节奏摘要、包装信号展示
- 新主题、商品名、卖点、已有素材输入
- 结构迁移预览和槽位级文案改写
- 素材缺口识别、补拍建议、素材需求单复制 / 导出
- fixture 素材匹配和 FFmpeg 竖屏 MP4 demo 渲染
- 默认版、高点击版、高转化版、高节奏版四种输出版本
- 四版本摘要对比和批量生成真实 demo
- run 记录管理：搜索、筛选、载入、删除、备注、置顶、首选版本
- 批量生成结果支持 `batch_id` 分组，同一批次只保留一个首选版本
- 结构模板库：从 run 保存模板、标签筛选、编辑、版本回退、复制、删除

## 核心流程

```text
样例视频 / 转写
  -> 结构拆解
  -> 新内容输入
  -> 结构迁移
  -> 素材缺口补全
  -> 多版本生成
  -> run 对比和首选版本
  -> MP4 demo 输出
```

## 技术栈

- 前端：Next.js、React、TypeScript、Tailwind CSS
- 后端：FastAPI、Pydantic
- 视频处理：FFmpeg
- 本地素材：fixture 视频素材库
- 参考方向：Hyperframes 的时间线描述思路，Remotion 的组件化视频思路

当前 AI 拆解仍是 deterministic 规则逻辑，后续再接入 LLM / Agent / 异步任务队列。

## 主要接口

- `POST /api/samples/upload`：上传样例视频
- `POST /api/samples/upload-transcript`：上传 txt / srt 转写
- `POST /api/structure/preview`：生成结构迁移预览
- `POST /api/structure/variants`：生成四种输出版本摘要
- `POST /api/runs/demo`：生成单个 demo run
- `POST /api/runs/demo-variants`：批量生成四个版本 demo，并写入同一个 `batch_id`
- `GET /api/runs`：读取最近 run 记录，支持搜索、状态、模板、标签筛选
- `GET /api/runs/{run_id}`：读取 run 详情
- `PATCH /api/runs/{run_id}/note`：保存 run 备注
- `PATCH /api/runs/{run_id}/pin`：置顶 / 取消置顶
- `PATCH /api/runs/{run_id}/preferred`：设为首选 / 取消首选；同批次只保留一个首选
- `POST /api/templates/from-run/{run_id}`：从 run 保存结构模板
- `PATCH /api/templates/{template_id}`：编辑模板
- `POST /api/templates/{template_id}/rollback/{version_id}`：回退模板版本
- `POST /api/templates/{template_id}/fork`：复制模板

## 仓库结构

```text
apps/web/           # Next.js 前端工作台
services/api/       # FastAPI 后端服务
fixtures/           # 本地 fixture 视频素材
packages/protocol/  # 结构迁移协议示例
docs/               # 规划和实现文档
```

## 本地启动

启动后端：

```bash
cd services/api
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

启动前端：

```bash
cd apps/web
npm install
npm run dev
```

前端默认把 `/api/*`、`/downloads/*`、`/output/*` 代理到 `http://127.0.0.1:8010`。

## 演示路径

```text
1. 打开前端工作台
2. 可选上传样例视频和转写文本
3. 编辑目标主题、商品名、卖点和已有素材
4. 点击“生成版本对比”查看四种版本摘要
5. 点击“批量生成四版 demo”
6. 在最近 run 记录里比较 Hook、CTA、时长、缺口和视频结果
7. 点击“设为首选”确定同批次最终版本
8. 可把满意 run 保存为结构模板
```

## 验证

后端测试：

```bash
cd services/api
PYTHONPATH=. pytest tests/test_structure_service.py tests/test_workflow_service.py -q
```

前端构建：

```bash
cd apps/web
npm run build
```

浏览器回归：

```bash
node apps/web/scripts/check-material-request-sheet.mjs
```
