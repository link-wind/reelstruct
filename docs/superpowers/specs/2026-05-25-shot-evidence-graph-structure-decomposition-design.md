# Shot Evidence Graph 驱动的视频结构拆解设计

## 背景

ReelStruct 当前已经打通了样例上传、镜头切分、关键帧抽取、AI 视觉理解、AI 结构拆解、结构迁移、素材缺口和 demo 渲染闭环。但现有 AI 拆结构链路仍偏“关键帧摘要 -> 一次性输出结构段”，中间缺少稳定的证据层。

下一阶段要把结构拆解重心前移：先把视频拆成可靠的镜头段，再把画面理解、OCR、ASR 和前后镜头关系对齐到每个镜头，形成 Shot Evidence Graph。AI 结构拆解必须基于这条证据链聚合结构，而不是直接对整条视频下结论。

## 核心定义

ReelStruct 的 AI 视频结构拆解定义为：

> 基于镜头级事实证据，识别每个镜头在短视频创作中的功能，并把连续镜头聚合成可解释、可迁移的叙事、节奏和包装结构。

核心中间产物是 `Shot Evidence Graph`：

- 节点：每个物理镜头段的画面、文本、包装和 AI 理解。
- 边：相邻镜头之间的语义关系、节奏变化和表达承接。

## 层级模型

系统必须区分四个层级：

```text
Frame -> Shot -> Beat -> Segment
```

- `Frame`：某一时刻的画面证据，用于 OCR、视觉识别和关键帧展示。
- `Shot`：物理镜头段，由镜头切分算法得到，表示连续画面片段。
- `Beat`：结构镜头段，由一个或多个连续 shot 组成，表示一个局部表达功能。
- `Segment`：可迁移结构段，由一个或多个 beat 组成，例如 Hook、痛点、卖点证明、使用过程、CTA。

`Shot` 是算法切分结果，`Beat` 和 `Segment` 是 AI 基于证据聚合出的创作结构。

## 非目标

本阶段不直接做以下事情：

- 不做完整剪辑时间线编辑器。
- 不做自动成片质量评分。
- 不把 OCR、ASR、视频理解一次性做到生产级全自动。
- 不让 AI 直接跳过 shot evidence 输出最终 Hook / CTA。
- 不用固定四段模板替代 AI 聚合结果。

## 总体链路

```text
Sample Video
  ↓
Physical Shot Segmentation
  ↓
Shot Quality Normalization
  ↓
Multi-frame Sampling
  ↓
OCR / ASR Alignment
  ↓
Shot-level Understanding
  ↓
Context Relation Understanding
  ↓
Semantic Beat Aggregation
  ↓
Segment Aggregation
  ↓
Transfer Rule Extraction
```

## 1. 物理镜头切分

物理镜头切分只负责回答：视频在哪里发生画面切换。

推荐策略：

```text
PySceneDetect AdaptiveDetector
  ↓ if unusable or poor quality
PySceneDetect ContentDetector
  ↓ if unavailable
FFmpeg scene detect
  ↓ if no reliable cuts
Uniform fallback
```

输出统一为 `VideoShot`：

```json
{
  "shot_index": 1,
  "start": 0.0,
  "end": 1.8,
  "duration": 1.8,
  "keyframe_time": 0.9,
  "detection_method": "pyscenedetect_adaptive"
}
```

要求：

- 底层 detector 可以替换，但输出模型必须稳定。
- 切分来源必须记录，前端可展示。
- 不能让 AI 主观决定物理切点。

## 2. 切分质量归一化

原始 shot list 不能直接进入 AI。系统需要做质量控制：

- 镜头过少：换 detector 或降低阈值。
- 镜头过碎：合并过短 shot。
- 单镜头过长：标记为 long shot，并允许后续按 OCR / ASR / frame change 做二次拆分。
- 时间非法：删除或修正 end <= start 的片段。

建议规则：

- 小于 `0.3s` 的 shot 默认尝试与相邻 shot 合并。
- 超过 `8s` 的 shot 标记 `needs_semantic_split=true`。
- 若 `shot_count < 3` 且视频超过 `12s`，尝试 fallback detector。
- 若 `shot_count > duration * 4`，说明过碎，进入短镜头合并。

## 3. 多帧采样

每个 shot 不能只取中点帧。采样规则：

```text
duration < 1.2s:
  middle

1.2s <= duration < 4s:
  start / middle / end

duration >= 4s:
  start / 33% / 66% / end
```

输出 `FrameEvidence`：

```json
{
  "shot_index": 2,
  "frame_index": 1,
  "time": 2.0,
  "role": "start",
  "local_path": "storage/keyframes/sample/shot_0002_start.jpg",
  "public_url": "/keyframes/sample/shot_0002_start.jpg"
}
```

多帧采样的目标是让 AI 理解镜头内部变化，而不是只理解一张孤立图片。

## 4. OCR / ASR 对齐

短视频结构大量存在于文字里，因此 OCR 和 ASR 必须对齐到 shot。

### OCR

第一阶段先对 sampled frames 做 OCR：

- 识别画面标题、字幕、贴纸、价格、优惠、CTA、界面文案。
- 同一个 shot 内相同文本去重。
- 保留文本出现的 frame time。

输出：

```json
{
  "shot_index": 3,
  "frame_time": 5.2,
  "text": "3分钟早餐",
  "position": "center",
  "confidence": 0.86
}
```

### ASR

第一阶段优先支持带时间戳的 `.srt` 或转写片段；自动 ASR 可以作为后续增强。

ASR 对齐方式：

- 每个 transcript segment 有 `start` 和 `end`。
- 与 shot 有时间交集时关联到该 shot。
- 记录 overlap duration 和 overlap ratio。

输出：

```json
{
  "shot_index": 3,
  "text": "三分钟就能搞定一份早餐",
  "source_start": 4.8,
  "source_end": 6.6,
  "overlap_ratio": 0.72
}
```

## 5. Shot-level Understanding

AI 首先理解每个 shot 自身，不直接拆最终结构。

输入：

- shot 时间
- 多帧图像
- OCR 文本
- ASR 文本
- 前后 shot 的简要上下文

输出 `ShotUnderstanding`：

```json
{
  "shot_index": 3,
  "visual_summary": "展示产品使用后的早餐成品",
  "text_summary": "字幕和口播都在强调速度与健康",
  "subject": "product_result",
  "scene": "kitchen",
  "action": "result_showcase",
  "packaging_signals": ["large_title", "bottom_caption", "number_claim"],
  "creative_function_hint": "benefit_proof",
  "confidence": 0.84,
  "warnings": []
}
```

要求：

- `visual_summary` 必须基于 frame evidence。
- `text_summary` 必须来自 OCR / ASR。
- `creative_function_hint` 只是初判，不等于最终 segment。

## 6. Context Relation Understanding

结构来自镜头之间的关系。系统需要识别相邻 shot 的承接方式。

常见关系类型：

- `continuation`：同一动作或同一信息延续。
- `problem_to_solution`：痛点到解决方案。
- `setup_to_payoff`：铺垫到结果。
- `process_to_result`：过程到结果。
- `contrast`：对比前后。
- `proof_extension`：连续证明同一卖点。
- `topic_shift`：话题或场景切换。
- `cta_transition`：进入行动号召。

输出 `ShotRelation`：

```json
{
  "from_shot": 2,
  "to_shot": 3,
  "relation_type": "problem_to_solution",
  "relation_summary": "Shot 2 提出早上没时间吃饭，Shot 3 用三分钟早餐结果承接解决方案",
  "rhythm_change": "faster",
  "semantic_shift": "pain -> solution",
  "confidence": 0.78
}
```

## 7. Semantic Beat Aggregation

Beat 是一组连续 shot 完成的局部表达功能。

AI 聚合 beat 时必须基于：

- 相邻 shot relation
- OCR / ASR 是否表达同一语义
- 视觉主体是否连续
- 创作功能是否一致
- 节奏是否属于同一表达段

输出 `CreativeBeat`：

```json
{
  "beat_id": "beat_1",
  "label": "痛点与解决方案引出",
  "shot_indices": [1, 2, 3],
  "start": 0.0,
  "end": 4.3,
  "function": "hook_setup",
  "reason": "Shot 1-2 提出早八赶时间痛点，Shot 3 引出解决方案",
  "confidence": 0.82
}
```

## 8. Segment Aggregation

Segment 是最终可迁移结构段。AI 基于 beat 聚合 segment，不直接从 raw keyframes 生成 segment。

输出：

```json
{
  "segment_id": "seg_1",
  "label": "痛点 Hook",
  "beat_ids": ["beat_1"],
  "shot_indices": [1, 2, 3],
  "start": 0.0,
  "end": 4.3,
  "purpose": "提出高频痛点并制造代入感",
  "method": "痛点口播 + 结果承诺字幕 + 产品首次出现",
  "evidence": [
    "Shot 1 的 ASR 提到早上来不及",
    "Shot 2 的 OCR 强化早餐救星",
    "Shot 2 -> Shot 3 的关系是 problem_to_solution"
  ],
  "rhythm": "开头短镜头快速推进",
  "packaging": "大字标题 + 底部字幕强化利益点",
  "transferable_rule": "先用目标人群的高频时间压力开场，再用一句结果承诺承接",
  "non_transferable": "不能照搬原商品、原场景和原优惠信息",
  "required_asset": "目标人群痛点场景 + 产品结果承诺画面",
  "confidence": 0.84
}
```

## 9. 结构校验

AI 输出后必须经过结构校验：

- `shot_indices` 必须真实存在。
- beat 和 segment 必须按时间排序。
- segment 不能严重重叠。
- segment 覆盖率过低时记录 warning。
- `required_asset` 不能为空；无法判断时写明“不确定素材需求”。
- evidence 必须引用 shot、OCR、ASR 或 relation。

校验失败不一定中断流程，但必须进入 `warnings` 并在前端展示。

## 10. 前端展示

前端应围绕三层展示：

1. Shot Evidence
   - 每个 shot 的时间、帧、OCR、ASR、AI 理解。
2. Shot Relations
   - 相邻镜头之间的承接、对比、递进、证明关系。
3. Structure Segments
   - 最终结构段、引用 shot、证据、可迁移规则和素材需求。

评审需要能看到：

- 系统如何切镜头。
- 每个镜头理解了什么。
- 文字内容如何对齐到镜头。
- 前后镜头之间是什么关系。
- 最终结构段如何从证据聚合出来。

## 11. 与现有系统的关系

现有 `VideoSignal`、`KeyframeEvidence`、`ShotEvidence` 可以逐步升级，不需要一次性推翻。

建议演进顺序：

1. 保留现有 `VideoSignal`，扩展 detection method 和 normalization metadata。
2. 将 `KeyframeEvidence` 扩展为多帧 `FrameEvidence`。
3. 新增 `ShotEvidenceGraph`，承载 shot nodes 和 shot relations。
4. 新增 adapter，把 `Segment` 转回现有 `TemplateStructure`。
5. 现有迁移、素材缺口、渲染链路继续消费 `TemplateStructure`。

## 12. 第一阶段验收标准

第一阶段完成后，系统至少应做到：

- 上传视频后，能用 PySceneDetect 或 fallback 生成 normalized shot list。
- 每个 shot 至少有 1-3 张 frame evidence。
- 每个 shot 能展示 OCR 或空 OCR 结果、ASR 对齐结果或空 ASR 结果。
- AI 能输出 shot-level understanding。
- AI 能输出相邻 shot relation。
- AI 能把 shot 聚合成 beat，再聚合成 segment。
- 每个 segment 都能引用 shot evidence 和 relation evidence。
- 前端能展示 shot evidence、relation、segment 三层结果。

## 13. 风险与取舍

- PySceneDetect 只能解决物理切分，不能替代结构理解。
- OCR / ASR 第一阶段允许不完美，但必须在数据结构上保留时间对齐能力。
- 多帧采样会增加成本，需要限制长视频最大采样帧数。
- AI relation 和 beat 聚合可能不稳定，必须有 schema 校验和 warnings。
- 结构展示要服务解释链，不应提前做复杂编辑器。

## 结论

下一版 ReelStruct 不应再把 AI 拆结构理解成“一次 prompt 生成 Hook / CTA”。正确方向是：

> 先构建包含物理镜头、画面理解、OCR、ASR 和前后镜头关系的 Shot Evidence Graph，再基于这个证据图聚合出可解释、可迁移的视频结构。

这条路线能同时补强 AI 拆解准确性、过程可解释性和评审展示说服力。
