# RAG v4：素材补全闭环设计

## 背景

ReelStruct 现在已经具备结构槽位、素材缺口、素材证据 chunk、轻量向量检索、MaterialGraph、SlotRetrievalPlan 和 SlotFillDecision。系统可以回答“缺什么”“候选素材是什么”“推荐怎么补”。但当前 RAG 仍然停在候选和建议层，尚未成为真正驱动结果生成的决策引擎。

当前最大问题是：

- RAG 检索没有强绑定结构槽位需求画像。
- MaterialGraph 已能构建，但还没有成为检索、重排和解释的核心依据。
- SlotFillDecision 主要由规则生成，缺少基于图谱证据的推理链。
- 决策影响了展示和解释，但没有稳定影响最终 composition / timeline。
- 前端能看到补全建议，但不能一眼看清“样例结构如何映射到新素材并生成结果”。

RAG v4 的目标是把素材补全升级成闭环：

```text
结构槽位需求 -> 素材图谱检索 -> 候选重排 -> 补全决策 -> 时间线补丁 -> 可视化解释
```

## 目标

1. 为每个结构槽位生成明确的 `SlotQueryProfile`，描述它需要的视觉、文本、包装、时长和替代策略。
2. 让 `MaterialGraph` 参与素材召回、证据聚合和解释，而不只是作为孤立数据结构存在。
3. 增加图谱检索结果 `MaterialGraphSearchResult`，把命中的节点、边、证据、缺失项串起来。
4. 升级 `SlotFillDecision`，让它基于槽位画像和图谱证据做决策。
5. 新增 `TimelinePatch`，把素材补全决策转成可执行的时间线修改建议。
6. 前端展示“槽位需求 -> 命中素材 -> 缺口 -> 补全动作 -> 时间线结果”的短链路，而不是堆长文本。

## 非目标

本阶段不做以下事情：

- 不重写视频结构拆解、OCR、ASR 或 shot evidence graph。
- 不强制替换当前 memory/Milvus 向量检索。
- 不直接引入 RAG-Anything 或 Video-RAG 作为运行时依赖。
- 不做完整素材资产管理系统。
- 不做真实 AIGC 图像或视频生成，只输出 AIGC 可补位的结构化任务。
- 不保证最终视频视觉质量达到成片交付，只保证时间线补全逻辑可解释、可验证。

## 核心设计

### 1. SlotQueryProfile：槽位需求画像

`SlotQueryProfile` 是结构槽位进入 RAG 的统一查询对象。它不只记录 `required_asset`，还要明确该槽位要完成什么表达。

字段建议：

```json
{
  "slot_id": "selling_points",
  "slot_label": "卖点展开",
  "required_asset": "商品特写镜头",
  "required_expression": "连续推进核心卖点，保持信息密度。",
  "visual_terms": ["产品", "瓶身", "特写", "细节"],
  "action_terms": ["展示", "对比", "局部放大"],
  "text_terms": ["快速补水", "清爽不黏"],
  "packaging_terms": ["卖点卡片", "关键词高亮", "局部放大框"],
  "target_duration": 8.0,
  "min_usable_duration": 1.2,
  "replacement_modes": ["reuse_with_packaging", "caption_only", "shoot_or_aigc"]
}
```

生成规则：

- 从 `StructureSlot` 读取目的、方法、角色、包装意图和样例证据。
- 从 `NewContentInput` 读取主题、产品名、卖点和用户素材描述。
- 从槽位类型补充默认画像，例如 hook 需要“注意力/结果/反差”，cta 需要“行动词/入口/停留”。
- 输出中文字段，避免前端继续出现英文解释。

### 2. MaterialGraphSearchResult：图谱检索结果

`MaterialGraphSearchResult` 表示某个素材 chunk 为什么能支撑某个槽位。它应该保留命中的图谱路径，而不是只给一个分数。

字段建议：

```json
{
  "slot_id": "selling_points",
  "asset_id": "detail-shot.mp4",
  "chunk_id": "chunk_detail",
  "start": 1.2,
  "end": 3.8,
  "matched_nodes": [
    {"node_id": "chunk::detail-shot.mp4::chunk_detail", "node_type": "chunk", "text": "清透保湿精华瓶身细节特写"},
    {"node_id": "ocr_text::detail-shot.mp4::chunk_detail::0", "node_type": "ocr_text", "text": "快速补水"},
    {"node_id": "tag::detail-shot.mp4::chunk_detail::0", "node_type": "tag", "text": "产品"}
  ],
  "evidence_path": [
    "slot selling_points 需要 产品特写",
    "chunk_detail 命中 主体=产品",
    "chunk_detail 命中 OCR=快速补水",
    "chunk_detail 命中 包装=卖点字幕"
  ],
  "missing": ["缺少使用后效果镜头"],
  "score_breakdown": {
    "semantic": 82,
    "visual": 20,
    "ocr_asr": 25,
    "packaging": 15,
    "slot_hint": 25,
    "duration_fit": 5
  },
  "confidence": 0.86
}
```

检索策略：

- 先用 `SlotQueryProfile` 召回候选 chunk。
- 用 MaterialGraph 节点类型分别匹配视觉、OCR/ASR、包装、标签和 slot hint。
- 对每条候选保留 evidence path。
- 如果一个素材没有 chunk 级证据，则退回 asset 级摘要，但置信度降低。
- 同一素材多个 chunk 可以命中不同槽位，避免整段素材被粗暴复用。

### 3. Rerank：规则稳定，AI 可选

RAG v4 的重排分两层：

1. 规则 rerank：默认开启，保证无模型时也能稳定运行。
2. AI rerank：可选开启，只处理前 3-5 个候选，输出更强的语义判断。

规则 rerank 逻辑：

- 同时命中 visual + OCR/ASR 的候选优先。
- 命中 slot hint 的候选优先。
- 包装信号强但视觉弱的候选标记为 `reuse_with_packaging`。
- 只有文本命中、画面证据弱的候选标记为 `caption_only` 或“字幕卡补全”。
- 时长严重不匹配时降低置信度，但不直接丢弃。

AI rerank 输入：

- `SlotQueryProfile`
- top candidates 的 `MaterialGraphSearchResult`
- 新内容主题、产品、卖点
- 当前结构节奏和包装要求

AI rerank 输出：

- 推荐候选排序
- 每个候选的适配理由
- 缺失证据
- 推荐补全动作
- 决策类型
- 置信度

失败处理：

- AI 请求失败时回退规则 rerank。
- AI 输出校验失败时丢弃 AI 结果，保留规则结果。
- 前端展示 warning，但不阻断生成。

### 4. SlotFillDecision v2：从建议升级为决策

`SlotFillDecision` 继续附着在 `MaterialGap` 上，但语义升级为“最终补全决策”。它要引用 `SlotQueryProfile` 和 `MaterialGraphSearchResult`。

新增或强化字段：

```json
{
  "slot_id": "selling_points",
  "decision_type": "reuse_with_packaging",
  "selected_asset_id": "detail-shot.mp4",
  "selected_chunk_id": "chunk_detail",
  "start": 1.2,
  "end": 3.8,
  "confidence": 0.86,
  "why": "命中产品瓶身特写、OCR 快速补水和卖点字幕，可支撑卖点展开。",
  "missing": ["缺少使用后效果镜头"],
  "actions": [
    "裁切 detail-shot.mp4 的 1.2s-3.8s 放入卖点展开段",
    "叠加卖点卡片：快速补水",
    "使用局部放大框强化瓶身特写"
  ],
  "evidence_path": [
    "槽位需要 商品特写镜头",
    "chunk_detail 命中 主体=产品",
    "chunk_detail 命中 OCR=快速补水"
  ],
  "timeline_patch_id": "patch_selling_points_1"
}
```

决策类型保持五类：

- `reuse_direct`
- `reuse_with_packaging`
- `caption_only`
- `structure_reorder`
- `shoot_or_aigc`

### 5. TimelinePatch：让决策可执行

`TimelinePatch` 是 RAG v4 的关键新增层。它不直接渲染视频，而是描述“应该如何修改 composition”。

字段建议：

```json
{
  "patch_id": "patch_selling_points_1",
  "slot_id": "selling_points",
  "operation": "replace_slot_media",
  "target_start": 3.0,
  "target_end": 11.0,
  "source_asset_id": "detail-shot.mp4",
  "source_chunk_id": "chunk_detail",
  "source_start": 1.2,
  "source_end": 3.8,
  "track_updates": [
    {
      "type": "video",
      "action": "replace",
      "duration": 2.6
    },
    {
      "type": "card",
      "action": "insert",
      "text": "快速补水",
      "style_hint": "卖点卡片"
    },
    {
      "type": "caption",
      "action": "insert",
      "text": "清爽不黏，适合日常通勤前使用"
    }
  ],
  "warnings": ["素材片段短于目标段落，剩余时间用卖点卡补足"]
}
```

支持的操作：

- `replace_slot_media`: 用素材 chunk 替换某个 slot 的画面。
- `insert_caption_card`: 插入字幕卡或卖点卡。
- `insert_packaging_overlay`: 插入标题条、贴纸、局部放大框等包装建议。
- `reuse_partial_clip`: 复用素材局部片段。
- `reorder_slot`: 调整槽位顺序或把某个素材提前。
- `merge_slot`: 把 CTA 合并到最后一个卖点或使用过程镜头。
- `request_asset`: 生成补拍/AIGC 素材任务。

本阶段执行边界：

- 后端生成 `TimelinePatch`。
- composition 构建时先支持 `replace_slot_media`、`insert_caption_card`、`request_asset` 三种。
- 其他操作先展示为建议，不强制渲染。

### 6. 前端展示

前端素材补全页需要从“列表解释”升级为“链路解释”。

每个素材缺口卡片显示：

1. 槽位需求：这个位置要完成什么表达。
2. 命中素材：哪个素材、哪个片段、命中了哪些证据。
3. 缺失项：还缺什么画面/文字/包装。
4. 补全动作：裁切、字幕卡、包装、重排或补拍。
5. 时间线结果：最终放在什么时间段，改了哪些 track。

展示原则：

- 默认只显示精准概要，不展示大段原始 evidence。
- evidence path 可以展开查看。
- TimelinePatch 用小型时间线或步骤条展示。
- 仍保留候选列表，但放到次级区域。

## 数据流

```text
TemplateStructure.script_pattern
  -> build_slot_query_profile()
  -> SlotQueryProfile

UserSlotAsset.analysis.evidence_chunks
  -> build_material_graph()
  -> MaterialGraph

SlotQueryProfile + MaterialGraph
  -> search_material_graph_for_slot()
  -> MaterialGraphSearchResult[]

MaterialGraphSearchResult[]
  -> rerank_material_candidates()
  -> ranked candidates

ranked candidates + supplement options
  -> build_slot_fill_decision_v2()
  -> SlotFillDecision

SlotFillDecision
  -> build_timeline_patch()
  -> TimelinePatch

TimelinePatch
  -> build_composition_spec()
  -> preview / demo output
```

## 错误处理

- 没有素材：生成 `caption_only` 或 `shoot_or_aigc` 决策，并输出 `request_asset` patch。
- 素材有文本无画面：可以生成字幕卡或包装补全，但不得标记为 `reuse_direct`。
- 素材有画面无文本：可以生成 `reuse_with_packaging`，并插入标题卡或字幕。
- 素材片段过短：允许复用，但 patch 必须说明剩余时间如何补。
- Graph 为空：回退现有 `MaterialRetrievalCandidate` 逻辑。
- AI rerank 失败：回退规则 rerank，并记录 warning。
- TimelinePatch 执行失败：composition 回退旧的 slot track，同时保留 patch warning。

## 验收标准

后端：

- 给定一个带 OCR、视觉摘要、包装信号的素材 chunk，卖点槽位能生成 `MaterialGraphSearchResult`，并包含 evidence path。
- 给定同一个素材多个 chunk，系统能选择最适合目标槽位的 chunk。
- 给定无素材，系统能生成 `shoot_or_aigc` 或 `caption_only` 的 `TimelinePatch`。
- `SlotFillDecision` 必须引用至少一条 graph evidence 或明确说明没有 graph evidence。
- `TimelinePatch` 至少能驱动 composition 插入字幕卡或替换 slot media。
- 旧的 structure/workflow/media 测试继续通过。

前端：

- 素材缺口卡片能展示“需求、命中、缺失、动作、时间线结果”。
- 没有图谱结果时页面不崩，回退旧的补全建议。
- evidence path 可展开，默认不占用主视觉空间。
- typecheck 通过。

演示：

- 评审可以看到样例结构抽取了什么。
- 可以看到新素材命中了哪个槽位。
- 可以看到缺口在哪里。
- 可以看到系统最终怎么补进时间线。

## 实施顺序

1. 后端模型：新增或升级 `SlotQueryProfile`、`MaterialGraphSearchResult`、`TimelinePatch`，扩展 `SlotFillDecision`。
2. 槽位画像：实现 `build_slot_query_profile()`，并为四类基础槽位写测试。
3. 图谱检索：实现 `search_material_graph_for_slot()`，返回 evidence path 和 missing evidence。
4. 候选重排：实现规则 rerank，预留 AI rerank 接口。
5. 决策升级：让 `SlotFillDecision` 使用 profile + graph search result。
6. TimelinePatch：从决策生成 patch，并让 composition 至少支持字幕卡插入和素材替换。
7. 前端展示：素材缺口卡片展示补全链路和 timeline patch。
8. 验证：pytest、typecheck、diff check、浏览器烟测。

## 范围控制

本阶段只做“能闭环”的最小版本：

- 支持 4 个基础结构槽位：hook、selling_points、usage、cta。
- 支持 3 种可执行 patch：素材替换、字幕卡插入、素材任务请求。
- AI rerank 只预留接口，默认使用规则 rerank。
- 不做复杂视频剪辑特效，不做真实 AIGC 生成。

这样可以先把 RAG 和素材补全真正接进生成链路，再继续扩展多模态和更复杂的素材编排。
