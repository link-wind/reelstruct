# ReelStruct AI 架构与交付说明

## 重点总结

ReelStruct 的目标不是直接复制样例视频，而是把优质样例中的脚本结构、节奏结构和包装方法抽象成可迁移模板，再应用到新的主题、商品卖点和素材条件中，生成可解释、可调整、可验证的短视频方案。

当前版本已经完成第一版 P0 演示闭环：样例输入、结构拆解、新内容输入、结构迁移、素材缺口识别、素材补位、四版本生成、FFmpeg 成片 demo、结果导出包。当前 AI 能力以可解释的规则化流程为主，后续可接入 LLM、多模态理解、ASR 和 Agent。

## 课题要求对应关系

| 课题要求 | 当前实现 | 状态 |
| --- | --- | --- |
| 样例视频输入与解析 | 支持样例视频上传、txt / srt 转写上传；用 FFprobe 获取时长，用 FFmpeg scene detect 估算镜头数 | 已完成 P0 |
| 结构拆解 | 拆出 Hook、卖点展开、使用过程、CTA；生成节奏摘要、包装信号、结构角色、爆款手法、可迁移规则 | 已完成 P0 |
| 新内容与素材输入 | 支持主题、商品名、卖点、已有素材、真实补拍视频上传 | 已完成 P0 |
| 结构迁移与结果生成 | 输出迁移文案、结构映射、时间线草案、包装补位策略和 MP4 demo | 已完成 P0 |
| 素材缺口识别 | 按结构槽位识别缺少的开头吸引镜头、商品特写、使用过程、CTA 镜头，并说明影响 | 已完成 P0 |
| 素材缺口补全 | 支持字幕 / 标题卡片补位、fixture 素材重组复用、真实补拍素材绑定后重新生成 | 已完成 P0 |
| 迁移过程可视化 | 前端展示样例解析、结构槽位映射、迁移理由、缺口、补位策略、素材来源和生成 trace | 已完成 P0 |
| 结果可验证 | 提供 FFmpeg MP4 demo、四版本对比、run JSON、素材需求单、素材来源说明和结果 zip | 已完成 P0 |
| 画面包装生成 | 已有字幕、卡片、包装信号和版本化包装策略；尚未做完整封面、贴纸、转场生成 | 部分完成 |
| 多版本生成 | 支持默认版、高点击版、高转化版、高节奏版，并可批量生成同一 batch | 已完成 P1 |
| 真实素材适配 | 支持上传并绑定到结构槽位，渲染时优先使用；已生成时长、镜头数、推荐槽位、推荐理由和槽位适配分；尚未做主体识别和高光筛选 | 部分完成 |
| 人工可调 | 支持修改槽位依据、迁移文案、补位策略、模板时长、素材要求、卖点顺序，并重新生成 | 部分完成 |
| 自然语言改片 | 暂未实现 | 未完成 |

## 整体 AI 架构

```text
Sample Video / Transcript
  -> SampleVideoInput
  -> TemplateStructure
  -> TransferPlan
  -> MaterialGap
  -> CompositionSpec
  -> Fixture / Uploaded Asset Match
  -> FFmpeg Render
  -> DemoRun + Export Package
```

### 1. 样例理解层

输入包括样例视频和可选转写文本。

- 视频基础解析：读取视频时长，估算镜头数。
- 转写解析：清洗 txt / srt 文本，形成口播或字幕摘要。
- 样例摘要：前端展示时长、镜头数、转写状态和节奏摘要。

当前实现文件：

- `services/api/app/sample_service.py`
- `services/api/app/models.py`

### 2. 结构抽取层

系统把样例拆成四类结构槽位：

- `hook`：开头吸引，负责停留和注意力。
- `selling_points`：卖点展开，负责信息密度和利益点推进。
- `usage`：使用过程，负责场景化理解。
- `cta`：结尾行动号召，负责转化和记忆点。

每个槽位包含：

- 槽位名称
- 起止时间和时长
- 结构目的
- 结构角色
- 爆款手法
- 观众心理意图
- 节奏意图
- 可迁移规则
- 不应复制的样例内容
- 需要的素材类型
- 样例依据
- 包装意图

当前版本的拆解逻辑是 deterministic 规则：根据样例时长、镜头数和转写摘要生成结构。这样做的好处是稳定、可解释、便于演示；后续可替换为 LLM / 多模态模型输出。

当前实现文件：

- `services/api/app/structure_service.py`

### 3. 结构迁移层

系统把样例结构迁移到新的主题、商品名和卖点中。迁移不是复制样例内容，而是保留样例的创作方法：

- Hook 槽位迁移成新商品的开头抓人表达。
- 卖点槽位迁移成新商品的核心利益点。
- 使用过程槽位迁移成新商品的场景化说明。
- CTA 槽位迁移成新商品的行动引导。

系统同时支持四种输出策略：

- 默认版：平衡表达。
- 高点击版：强化反差、好奇心和停留。
- 高转化版：强化购买理由、信任背书和行动动机。
- 高节奏版：压缩时长，强化快切和短字幕。

当前实现文件：

- `services/api/app/structure_service.py`
- `services/api/app/workflow_service.py`

### 4. 素材适配与缺口处理层

系统会检查当前素材是否能支撑目标结构。每个槽位都有一个 `required_asset`，例如：

- 开头吸引镜头
- 商品特写镜头
- 使用过程镜头
- 结尾 CTA 镜头

如果用户已有素材无法覆盖某个槽位，系统生成 `MaterialGap`，包括：

- 缺少什么素材
- 对表达有什么影响
- 当前补位策略
- 建议补拍镜头
- 补拍检查清单

当前补全方式包括：

- 文案 / 字幕补全：用字幕强化信息表达。
- 包装补全：用标题卡片、卖点卡片、CTA 卡片补足画面表达。
- 现有素材重组复用：从 fixture 素材库匹配可用视频片段。
- 真实素材绑定：用户上传补拍视频后绑定到具体槽位，重新生成时优先使用。
- 真实素材适配分析：上传后生成时长、镜头数、推荐槽位、推荐理由和 Hook / 卖点 / 使用过程 / CTA 适配分。

当前实现文件：

- `services/api/app/structure_service.py`
- `services/api/app/fixture_asset_service.py`
- `services/api/app/material_asset_service.py`

### 5. 时间线协议与视频重组层

系统使用 `CompositionSpec` 描述最终视频草案，思想上参考 Hyperframes 的时间线描述方式和 Remotion 的组件化视频表达方式，但当前实现保持轻量。

一个 `CompositionSpec` 包含：

- 画布比例：默认 720 x 1280 竖屏。
- 帧率：默认 30fps。
- 总时长。
- 多条轨道：视频轨、字幕轨、卡片轨。

后端根据时间线准备素材，再用 FFmpeg 合成竖屏 MP4 demo。

当前实现文件：

- `services/api/app/render_service.py`
- `services/api/app/fixture_asset_service.py`
- `packages/protocol/structure-transfer.example.json`

### 6. 结果记录与导出层

每次生成都会形成 `DemoRunResponse`，记录：

- run id 和 batch id
- 输出版本
- 结构预览
- 已准备素材
- 渲染视频路径
- 生成 trace
- 备注、置顶、首选版本状态
- 模板信息

结果导出包包含：

- `run.json`：完整结构、素材和结果数据。
- `material-request-sheet.txt`：素材需求单。
- `material-sources.txt`：素材来源说明。
- `material-analysis.txt`：真实上传素材的推荐槽位、理由和适配分。
- `final-demo.mp4`：最终成片 demo。

当前实现文件：

- `services/api/app/run_record_service.py`
- `services/api/app/run_export_service.py`
- `services/api/app/template_record_service.py`

## 工具协议

### `TemplateStructure`

表示从样例中抽取出的可迁移结构。

核心字段：

- `title`：结构标题。
- `script_pattern`：结构槽位列表。
- `rhythm_summary`：节奏摘要。
- `packaging_notes`：包装要点。
- `analysis_summary`：样例解析摘要。

### `StructureSlot`

表示一个结构槽位。

核心字段：

- `id`：槽位标识，如 `hook`、`selling_points`、`usage`、`cta`。
- `label`：展示名称。
- `start` / `duration`：时间位置。
- `purpose`：创作目的。
- `required_asset`：需要的素材类型。
- `sample_evidence`：样例依据。
- `role`：结构角色，如吸引注意、建立兴趣、场景证明、推动转化。
- `method`：可迁移的爆款手法，如结果先行、利益点连续推进、真实场景证明。
- `intent`：希望观众产生的心理动作。
- `rhythm`：节奏意图。
- `transferable_rule`：可以迁移到新内容的创作规则。
- `non_transferable`：不能直接复制的样例内容。
- `packaging_intent`：字幕、标题条、卡片等包装元素在该槽位里的作用。

### `TransferPlan`

表示样例结构到新内容的迁移方案。

核心字段：

- `title`：迁移方案标题。
- `target_topic`：目标主题。
- `variant`：输出版本。
- `mappings`：槽位映射。
- `gaps`：素材缺口。
- `material_request_sheet`：素材需求单。

### `TransferMapping`

表示一个槽位的迁移结果。

核心字段：

- `slot_id`：对应结构槽位。
- `source_label`：样例结构标签。
- `target_message`：迁移后的文案表达。
- `asset_strategy`：素材使用或补位策略。
- `source_method`：样例槽位使用的创作方法。
- `target_adaptation`：这个方法如何迁移到新主题。
- `reasoning`：为什么这样迁移，以及哪些内容没有被复制。
- `asset_requirement`：支撑该迁移结果所需的素材。
- `packaging_plan`：字幕、卡片、标题条等包装计划。
- `fallback_strategy`：缺素材时的补位策略。

### `MaterialGap`

表示素材缺口。

核心字段：

- `slot_id`：缺口所在槽位。
- `missing_asset`：缺少的素材。
- `impact`：缺口影响。
- `fill_strategy`：补位方式。
- `suggested_asset_type`：建议补拍素材类型。
- `suggested_shots`：建议镜头。
- `pickup_checklist`：拍摄检查清单。

### `CompositionSpec`

表示可渲染时间线草案。

核心字段：

- `width` / `height` / `fps`：视频规格。
- `duration`：总时长。
- `tracks`：视频、字幕、卡片轨道。

### `DemoRunResponse`

表示一次完整生成结果。

核心字段：

- `run_id`
- `batch_id`
- `variant`
- `preview`
- `prepared_assets`
- `rendered_video`
- `trace`

## 安全边界

### 文件上传边界

- 样例视频和补拍素材只保存到服务端本地 `storage` 目录。
- 文件名使用随机 id 生成，避免直接信任用户上传文件名。
- 素材通过槽位绑定，不允许用户直接指定任意系统路径。
- 当前演示环境主要面向本地运行，生产环境需要继续增加文件大小限制、MIME 校验和病毒扫描。

### 渲染边界

- FFmpeg 调用由后端服务统一封装。
- 渲染输入来自已保存素材、fixture 素材库和系统生成的时间线，不暴露任意命令拼接入口。
- 字幕文本通过临时文件传入，减少命令行转义风险。

### 模型与 API key 边界

- 当前版本没有直接接入外部 LLM 或多模态模型，因此核心流程可离线演示。
- 后续接入火山方舟、OpenAI、Whisper 或其他模型时，API key 应通过环境变量注入，不写入仓库。
- 模型输出只作为结构建议或文案建议进入协议层，最终仍通过 `TemplateStructure`、`TransferPlan`、`CompositionSpec` 等结构化对象落地。

### 内容边界

- 系统强调迁移创作方法，不复制样例内容。
- 导出的 `run.json` 保留结构、映射和素材来源，便于说明生成过程。
- 对用户上传素材，当前只做本地演示使用；如果进入生产环境，需要增加版权提示和素材授权确认。

## 与 Remotion / Hyperframes 的关系

当前版本没有直接引入 Remotion 或 Hyperframes，而是参考它们的思想：

- 参考 Hyperframes：用结构化时间线描述视频，而不是只输出一段黑盒视频。
- 参考 Remotion：把视频看成可组合的结构和轨道，后续可以把字幕、卡片、封面和转场做成组件。

第一版仍使用 FFmpeg 渲染，原因是：

- 本地依赖简单。
- 适合快速产出可验证 MP4。
- 便于围绕课题主线先完成“结构迁移”闭环。

后续如果继续升级，可以把 `CompositionSpec` 转成 Remotion Composition，用 React 组件渲染更复杂的字幕、卡片、封面、贴纸和转场。

## 当前不足与下一步

### 1. 真实素材理解还不够

当前系统已经能根据时长和镜头数做第一版素材适配推荐，但还没有真正理解画面主体和高光内容。下一步可以加入：

- 镜头分类：开场、商品特写、使用过程、环境、CTA。
- 高光片段筛选：根据清晰度、运动、主体占比筛选。
- 推荐槽位：判断素材更适合 Hook、中段还是 CTA。

### 2. 包装生成还比较基础

当前已有字幕、卡片和包装信号，但还缺：

- 字幕样式推荐。
- 标题条和卖点卡片视觉方案。
- 封面文案和封面方案。
- 转场建议。
- 贴纸和强调元素推荐。

### 3. 自然语言改片未实现

后续可以支持：

- “开头更抓人一些”
- “把商品信息提前”
- “减少字幕，增强节奏感”

实现方式可以是：自然语言指令 -> 结构化修改意图 -> 更新 `TransferMapping` / `CompositionSpec` -> 重新生成。

### 4. AI 能力可逐步替换规则层

当前规则层稳定、可解释，但表达上还不够智能。后续可以把以下节点替换为模型能力：

- 样例结构抽取：由 LLM / 多模态模型生成更细的结构槽位。
- 素材理解：由视觉模型识别商品、人物、场景和高光片段。
- 文案迁移：由 LLM 生成更自然的 Hook、卖点和 CTA。
- 包装建议：由 LLM / 视觉模型生成封面、字幕样式和转场建议。

## 交付清单

当前仓库可交付：

- 代码仓库：Next.js 前端、FastAPI 后端、FFmpeg 渲染、测试和浏览器回归脚本。
- 演示产品：本地工作台，可完成结构迁移、素材补位、多版本生成和视频预览。
- 视频产物 case：生成后的 MP4 demo 和结果 zip。
- 项目说明文档：README、项目规划、AI 架构与交付说明。

答辩时建议按以下顺序讲：

1. 先讲问题：爆款视频有效的是结构能力，不只是素材本身。
2. 再讲方法：把样例拆成带角色、手法、迁移规则的 `TemplateStructure`，迁移成带理由和素材支撑的 `TransferPlan`，缺口落到 `MaterialGap`，最终生成 `CompositionSpec`。
3. 再演示流程：上传样例 / 填新内容 -> 生成四版 -> 看缺口 -> 上传补拍素材 -> 重生成 -> 下载结果包。
4. 最后讲边界：当前是 deterministic MVP，后续接入 LLM、多模态理解和 Remotion 组件化渲染。
