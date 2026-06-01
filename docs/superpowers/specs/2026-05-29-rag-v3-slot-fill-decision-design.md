# RAG v3：结构槽位驱动的素材补全推理设计

## 背景

ReelStruct 现在已经具备素材缺口识别、素材证据 chunk、轻量向量检索、补全方案选择和 `SlotRetrievalPlan`。这说明系统已经能回答“缺什么”和“候选素材是什么”。但当前 RAG 仍然偏检索展示，还没有真正成为素材补全决策层。

现阶段的主要问题：

- 检索仍偏关键词和规则分，不能稳定判断抽象表达，例如情绪、信任感、使用前后对比、开头张力。
- 素材证据、结构槽位、补全动作之间还没有统一图谱关系。
- 候选素材虽然能展示，但没有充分落到“怎么裁切、怎么包装、怎么放进时间线”。
- 前端能看到素材候选，但还不能一眼看出系统最终为什么这么补。

RAG v3 的目标是把素材 RAG 从“候选素材列表”升级为“结构槽位驱动的补全推理”。

## 目标

RAG v3 需要让每个结构槽位输出一条可执行判断：

> 这个槽位需要什么表达；当前素材库命中了哪些片段；命中证据是什么；还缺什么；最终建议怎么裁切、包装、重排或补文案。

具体目标：

1. 建立 `MaterialGraph`，把素材拆成可检索节点和关系。
2. 做混合检索，不只看 embedding，也看 OCR/ASR、包装信号、主体动作、槽位提示和时长。
3. 增加 `SlotFillDecision`，把 RAG 结果转成生成可用的补全决策。
4. 预留 AI rerank 接口，默认可用规则 rerank，开启 AI 时输出更强的语义判断。
5. 前端把素材补全展示成“槽位需求 → 命中素材 → 证据 → 缺口 → 推荐动作”。

## 非目标

本阶段不做以下事情：

- 不把 RAG-Anything 或 Video-RAG 项目直接作为依赖接入。
- 不强制引入新的向量数据库；继续兼容当前 memory/Milvus backend。
- 不做完整资产管理平台。
- 不做 AIGC 真实图像/视频生成。
- 不自动生成最终成片，只输出可验证的时间线/补全决策。
- 不重写已有 Shot Evidence Graph 或结构拆解系统。

## 核心设计

### 1. MaterialGraph

`MaterialGraph` 是用户素材的图谱化索引。它由已有 `UserSlotAsset.analysis.evidence_chunks` 转换而来，不替代现有模型。

节点类型：

- `asset`: 一个上传素材文件。
- `chunk`: 一个可复用片段。
- `frame`: 一个代表帧或关键帧。
- `ocr_text`: 帧上的文字。
- `asr_text`: 音频转写片段。
- `packaging_signal`: 标题卡、水印、贴纸、字幕密度等包装元素。
- `tag`: 主体、动作、场景、特写等标签。
- `slot_hint`: 素材可支持的结构槽位。

边类型：

- `contains`: asset 包含 chunk / chunk 包含 frame。
- `has_evidence`: chunk 关联 OCR/ASR/视觉摘要/包装信号。
- `supports_slot`: chunk 或 asset 可支持某个结构槽位。
- `needs_packaging`: 候选素材只能部分支持，需要包装补足。

### 2. Hybrid Retrieval

每个结构槽位查询素材时，先生成一个 `SlotQueryProfile`：

- `slot_id`
- `required_asset`
- `required_expression`
- `semantic_terms`
- `visual_terms`
- `text_terms`
- `packaging_terms`
- `target_duration`

检索时计算多路分数：

- `semantic`: 槽位需求与素材摘要/embedding 的相似度。
- `ocr_asr`: OCR/ASR 是否命中卖点、标题、CTA、品牌等文本。
- `visual`: 主体/动作/场景标签是否匹配。
- `packaging`: 是否适合做标题卡、字幕卡、贴纸、封面、转场。
- `slot_hint`: 素材分析或用户上传槽位是否指向该槽位。
- `duration_fit`: 片段长度是否适合结构槽位节奏。

输出仍使用现有 `MaterialRetrievalCandidate`，但 `score_breakdown` 必须更稳定，不能只有 vector 分。

### 3. Rerank

新增 rerank 层，接口固定，默认规则实现，AI 可选：

```python
class MaterialReranker:
    def rerank(slot, candidates, content) -> list[MaterialRetrievalCandidate]:
        ...
```

默认规则 rerank：

- 优先直接命中 slot_hint 的素材。
- 优先同时有视觉证据和 OCR/ASR 证据的素材。
- 对低分但包装信号强的素材标记为“可包装后使用”。
- 过滤无法解释证据来源的候选。

AI rerank 后续通过环境变量开启：

- 输入：槽位需求、候选素材摘要、证据、当前内容卖点。
- 输出：是否可用、推荐用途、缺失证据、补全动作、置信度。
- 失败时回退规则 rerank。

### 4. SlotFillDecision

`SlotFillDecision` 是 RAG v3 的核心输出，附着在每个 `MaterialGap` 上，和当前 `SlotRetrievalPlan` 配合使用。

字段：

```json
{
  "slot_id": "selling_points",
  "decision_type": "reuse_with_packaging",
  "selected_asset_id": "detail-shot.mp4",
  "selected_chunk_id": "chunk_detail",
  "time_range": { "start": 1.2, "end": 3.8 },
  "confidence": 0.86,
  "why": "命中产品瓶身特写和快速补水 OCR，可支撑卖点展开。",
  "missing": ["缺少使用后效果镜头"],
  "actions": [
    "裁切 1.2s-3.8s 作为卖点段画面",
    "叠加卖点卡片：快速补水 / 清爽不黏",
    "用局部放大框强化瓶身特写"
  ],
  "timeline_hint": "放在卖点展开段前 2.6 秒"
}
```

`decision_type` 取值：

- `reuse_direct`: 现有素材可直接复用。
- `reuse_with_packaging`: 现有素材需要字幕、标题条、贴纸、局部放大等包装补足。
- `caption_only`: 用文案/字幕替代缺失画面。
- `structure_reorder`: 调整段落结构，降低当前素材需求。
- `shoot_or_aigc`: 需要补拍或 AIGC。

### 5. 生成链路接入

`SlotFillDecision` 应影响：

- `MaterialGap.primary_supplement`
- `MaterialGap.supplement_options`
- `TransferMapping.asset_strategy`
- `TransferMapping.fallback_strategy`
- `TransferExplanation.gap_handling`
- 后续时间线草案中的素材使用建议

本阶段先保证前三项稳定接入，时间线草案只输出 `timeline_hint`，不强制改渲染器。

### 6. 前端展示

素材补全页每个缺口卡片展示：

1. 槽位需求
2. 推荐决策
3. 命中素材和时间段
4. 证据来源：画面 / OCR / ASR / 包装 / 标签
5. 缺失证据
6. 下一步动作

默认显示 3-5 行概要，候选列表和原始 evidence 保持可展开。

## 数据流

```text
Uploaded Assets
  -> MaterialEvidenceChunk
  -> MaterialGraph
  -> SlotQueryProfile
  -> Hybrid Retrieval
  -> Rule/AI Rerank
  -> SlotRetrievalPlan
  -> SlotFillDecision
  -> MaterialGap / TransferPlan / UI
```

## 错误处理

- 没有素材节点：输出 `caption_only` 或 `shoot_or_aigc` 决策。
- 检索命中但证据不足：输出 `reuse_with_packaging`，并列出缺失证据。
- AI rerank 失败：回退规则 rerank，并在 warnings 里记录。
- 候选素材缺少时间段：按整段素材处理，但置信度降低。
- 前端收到旧数据没有 `slot_fill_decision`：回退展示 `retrieval_plan` 和 `fill_strategy`。

## 验收标准

后端：

- 给定带 OCR/视觉摘要的素材 chunk，`selling_points` 缺口能输出 `reuse_direct` 或 `reuse_with_packaging`。
- 给定无素材，缺口能输出 `caption_only` 或 `shoot_or_aigc`。
- `score_breakdown` 至少包含 semantic、visual、ocr_asr、packaging、slot_hint、duration_fit 中的 3 类。
- `SlotFillDecision.actions` 至少包含一个可执行动作。
- 所有旧 workflow 测试继续通过。

前端：

- 素材补全页能显示“推荐决策 / 命中素材 / 缺失证据 / 下一步动作”。
- 没有新字段时页面不崩，仍显示旧的 `retrieval_plan`。
- typecheck 通过。

## 实施顺序

1. 后端模型：新增 `MaterialGraph`、`SlotQueryProfile`、`SlotFillDecision`。
2. 素材图谱构建：从 uploaded assets 转换成 graph nodes/edges。
3. 混合检索增强：稳定输出多路 score_breakdown。
4. 决策生成：从候选和补全方案生成 `SlotFillDecision`。
5. 迁移链路接入：让决策影响 mapping 和 explanation。
6. 前端展示：素材补全卡片展示决策概要。
7. 验证：pytest、typecheck、浏览器烟测。
