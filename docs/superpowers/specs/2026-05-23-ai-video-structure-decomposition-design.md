# AI 视频结构拆解设计

## 背景

ReelStruct 当前已经有样例输入、结构迁移、素材缺口、包装计划、demo 渲染和导出包闭环，但样例结构拆解仍以规则四段式为主。下一阶段要把结构拆解升级为 AI 驱动的视频理解能力。

本设计废弃“规则决定结构”的主路径。规则只允许承担视频信号提取、算法兜底和系统失败保护；结构段落、创作手法、可迁移规则必须由 AI 基于真实视频证据判断。

## 目标

构建一个真实功能切片推进的 AI 视频结构拆解能力：

1. 上传样例视频后，系统真实解析视频基础信息。
2. 系统真实切分镜头，并产出 shot list。
3. 系统真实抽取每个镜头的关键帧。
4. AI 基于关键帧、镜头时间、转写和包装线索理解每个镜头。
5. AI 聚合镜头证据，拆出脚本结构、节奏结构、包装结构和可迁移规则。
6. AI 拆解结果驱动现有结构迁移、素材缺口、包装计划和 demo 生成。

## 非目标

第一阶段不做空壳 AI Core，不做 fake provider 冒充能力，不把规则四段式包装成 AI 拆解结果。

第一阶段也不把以下能力作为必须完成项：

- 多条样例融合分析
- 自动生成素材
- 完整时间线编辑器
- 专业级 OCR 字幕识别
- 全量视频逐帧语义理解

这些可以后续增强，但不能阻塞第一条真实视频结构理解链路。

## 核心原则

### AI 是结构判断主路径

AI 决定：

- 视频被拆成几个创作段落
- 每个段落的类型、目的和手法
- 哪些镜头归属于同一结构段
- 节奏高峰和停留位置
- 包装结构和封面风格
- 哪些方法可迁移，哪些内容不能复制

### 规则只生成证据

规则和传统算法可以做：

- `ffprobe` 读取时长、分辨率、fps
- PySceneDetect 或 OpenCV 做镜头切分
- `ffmpeg` 抽关键帧
- 转写文本粗对齐到镜头
- AI 失败时 emergency fallback

规则不能做：

- 固定前 3 秒是 Hook
- 固定中段是卖点
- 固定结尾是 CTA
- 固定输出四段结构

### 每个功能切片必须真实可用

每一步都必须有真实输入、真实处理、真实输出，并能在前端或导出结果中看到。不能先只定义 schema、prompt、mock 数据。

## 总体链路

```text
Sample Video
  ↓
真实视频基础解析
  ↓
真实镜头切分
  ↓
真实关键帧抽取
  ↓
真实 AI 视觉理解
  ↓
真实 AI 视频结构拆解
  ↓
Template Adapter
  ↓
Transfer Plan / Material Gaps / Packaging Plan / Demo Render
```

## 功能切片

### 功能 1：真实视频基础解析

输入：样例视频文件。

处理：

- 使用 `ffprobe` 获取 `duration`、`fps`、`width`、`height`、编码格式。
- 如果视频解析失败，返回明确错误，不生成伪造 AI 结构。

输出：

```json
{
  "duration": 23.6,
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "format": "mp4"
}
```

验收：

- 上传真实视频后，前端能展示真实基础信息。
- 后端测试使用 fixture 视频验证 duration、fps、resolution。

### 功能 2：真实镜头切分

输入：样例视频文件和基础信息。

处理：

- 使用 PySceneDetect 或现有 OpenCV scene detection 识别镜头切点。
- 输出每个镜头的 `start`、`end`、`duration`。
- 如果检测不到足够镜头，可以使用均匀切分兜底，但必须标明 `detection_method: "uniform_fallback"`。

输出：

```json
{
  "shot_count": 8,
  "detection_method": "scene_detect",
  "shots": [
    {
      "index": 1,
      "start": 0.0,
      "end": 2.1,
      "duration": 2.1
    }
  ]
}
```

验收：

- 前端能看到 shot list。
- 后端测试能验证真实视频得到多个镜头或明确 fallback。
- 节奏指标基于 shot list 计算，而不是规则四段结构。

### 功能 3：真实关键帧抽取

输入：样例视频文件和 shot list。

处理：

- 对每个 shot 取中间时间点 `keyframe_time = (start + end) / 2`。
- 使用 `ffmpeg` 抽取关键帧，保存到 storage。
- 记录关键帧 public URL，供前端和 AI 视觉理解使用。

输出：

```json
{
  "shot_index": 1,
  "keyframe_time": 1.05,
  "keyframe_local_path": "storage/keyframes/sample-shot-001.jpg",
  "keyframe_public_url": "/keyframes/sample-shot-001.jpg"
}
```

验收：

- 前端能展示每个镜头的关键帧。
- 后端测试验证关键帧文件真实生成。

### 功能 4：真实 AI 视觉理解

输入：每个 shot 的关键帧、时间信息、可选转写片段。

处理：

- 调用真实多模态模型分析关键帧。
- 每个镜头输出视觉摘要、主体、场景、包装信号。
- 视觉分析失败时，该 shot 标记 warning，不用 fake 描述顶替。

输出：

```json
{
  "shot_index": 1,
  "visual_summary": "人物近景，画面中央有大标题字幕。",
  "subject_type": "person",
  "scene_type": "talking_head",
  "packaging_signals": ["大标题", "高密度字幕"],
  "confidence": 0.82,
  "warnings": []
}
```

验收：

- 前端能看到每个关键帧的 AI 视觉描述。
- AI 输出必须来自真实模型调用。
- 测试环境可以跳过真实模型集成测试，但业务功能验收必须使用真实模型跑通。

### 功能 5：真实 AI 视频结构拆解

输入：

- 视频基础信息
- shot list
- 关键帧视觉理解结果
- 用户上传或输入的转写/字幕概览

处理：

- AI 基于证据拆出创作结构。
- 段落数量不固定。
- 段落类型不固定。
- 每个段落必须引用 `shot_indices` 和 evidence。
- AI 输出必须是合法 JSON，并通过 schema 校验。

输出：

```json
{
  "source": "ai",
  "headline": "痛点种草型短视频结构",
  "segments": [
    {
      "id": "seg_1",
      "label": "痛点 Hook",
      "type": "hook",
      "start": 0.0,
      "end": 2.8,
      "shot_indices": [1, 2],
      "purpose": "用痛点问题吸引停留",
      "method": "痛点提问 + 大标题",
      "evidence": "第 1-2 个镜头位于开头，视觉有大标题，转写是痛点提问。",
      "rhythm": "快进入，高密度字幕",
      "packaging": "开头大标题强化痛点",
      "required_asset": "开头吸引镜头",
      "transferable_rule": "保留痛点提问作为开头方法",
      "non_transferable": "不复制原商品、原文案和原优惠",
      "confidence": 0.86
    }
  ],
  "rhythm_structure": {
    "summary": "前段快进入，中段一镜一卖点，结尾停留。",
    "peak_position": "3-12s",
    "slowdown_position": "18-23.6s"
  },
  "packaging_structure": {
    "caption_density": "高",
    "title_style": "开头大标题",
    "transition_style": "快切",
    "cover_style": "痛点承诺型"
  },
  "confidence": 0.84,
  "warnings": []
}
```

验收：

- 同一个视频不再固定输出四段结构。
- 每个结构段都有 AI evidence 和 shot reference。
- 前端能显示“AI 视频结构拆解”、置信度、证据镜头。
- AI 失败时显示失败原因，不把规则结果伪装为 AI 结果。

### 功能 6：AI 结构驱动迁移

输入：`AIStructureAnalysis`。

处理：

- Adapter 把 AI segments 转成现有 `TemplateStructure.script_pattern`。
- 后续沿用现有 `build_transfer_plan`、`detect_material_gaps`、`build_composition_spec`。
- `TemplateStructure.analysis_summary` 要保留 AI source、confidence、shot evidence。

输出：

```text
AIStructureAnalysis
  ↓
TemplateStructure
  ↓
TransferPlan
  ↓
CompositionSpec
```

验收：

- 新内容迁移基于 AI segments，而不是规则四段。
- 素材缺口来自 AI segment 的 `required_asset`。
- 前端能从样例证据一路看到迁移结果。

## 前端展示

前端需要新增或强化这些展示：

- 样例基础信息：真实时长、fps、分辨率、镜头数。
- Shot list：每个镜头的时间范围和关键帧。
- AI 镜头理解：每个 shot 的视觉摘要和包装信号。
- AI 结构拆解：每个结构段的类型、目的、手法、证据、shot_indices、置信度。
- 拆解来源：`AI 视频结构拆解` 或 `AI 拆解失败`。
- 后续迁移：保留现有三列解释，但 “样例方法” 来自 AI segment。

## 错误处理

- 视频解析失败：提示上传视频不可解析，不进入 AI 拆解。
- 镜头切分过少：使用均匀切分兜底，并标明 fallback。
- 关键帧抽取失败：该 shot 标记 warning，允许其他 shot 继续。
- AI 视觉理解失败：该 shot 标记 warning，不生成 fake visual summary。
- AI 结构拆解失败：返回失败状态和原因，可允许用户重试或走 emergency fallback，但 UI 必须标明不是 AI 拆解。

## 分阶段实施建议

### 阶段 1：真实视频信号闭环

完成功能 1-3：

- 视频基础解析
- 镜头切分
- 关键帧抽取
- 前端展示基础信息、shot list、关键帧

阶段结果：系统能真实读懂视频的时间和镜头骨架。

### 阶段 2：真实 AI 视觉理解

完成功能 4：

- 关键帧送入真实视觉模型
- 输出 shot visual summary
- 前端展示 AI 镜头理解

阶段结果：AI 开始看真实视频画面。

### 阶段 3：真实 AI 结构拆解

完成功能 5：

- AI 基于 shot evidence 拆创作结构
- 输出 segments、rhythm、packaging、transferable rules
- 前端展示 AI 拆解证据

阶段结果：结构拆解主路径变成 AI 驱动。

### 阶段 4：AI 结构驱动迁移

完成功能 6：

- AI segments 转换为 `TemplateStructure`
- 后续迁移、素材缺口、包装、demo 使用 AI 结构

阶段结果：完整 AI 视频结构拆解进入 ReelStruct 主闭环。

## 评审口径

这条路线要证明的不是“我们调用了 AI”，而是：

> 系统基于真实视频信号和真实 AI 视觉理解，拆出了可解释、可迁移、可展示的视频创作结构。

