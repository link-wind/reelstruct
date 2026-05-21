# ReelStruct 项目规划

## 重点总结

ReelStruct 不做普通的视频生成器，而是做“结构迁移引擎”：先理解样例视频为什么有效，再把这种结构迁移到新内容里。

## 产品定位

用户输入一个优质样例视频，再输入新的主题、商品卖点或素材。系统分析样例的脚本结构、节奏结构和包装结构，生成新的短视频方案，并展示结构如何迁移、哪些素材不足、如何补全。

## 推荐架构

```text
Sample Video
  -> TemplateStructure
  -> TransferPlan
  -> MaterialGap
  -> CompositionSpec
  -> Timeline Preview / Video Render
```

核心对象：

- `SampleVideo`：样例视频基础信息
- `TemplateStructure`：样例拆解出的脚本、节奏和包装结构
- `StructureSlot`：hook、卖点、对比、使用过程、CTA 等结构槽位
- `TransferPlan`：样例结构到新内容的映射方案
- `MaterialGap`：素材缺口及影响
- `CompositionSpec`：最终视频时间线协议

## 阶段 1：P0 闭环

目标：能完整演示课题主线。

- 样例视频上传与基础解析
- 脚本结构拆解：hook、展开、CTA
- 节奏结构拆解：镜头数量、段落时长、快慢变化
- 新主题/商品信息输入
- 结构迁移生成脚本和时间线
- 素材缺口识别
- 文案、字幕、标题卡片补全
- 时间线可视化或视频 demo

## 阶段 2：展示强化

目标：让评委看清过程。

- 样例结构与新结果对比
- 结构槽位映射视图
- 缺口标记和补全说明
- 迁移过程 trace
- 结果预览页

## 阶段 3：P1 加分

目标：提高完成度和亮点。

- 字幕样式、标题条、卖点卡片生成
- 高点击版、高转化版、高节奏版多版本输出
- 用户调整 hook、卖点顺序、节奏或 CTA 后重新生成
- 自然语言改片

## 技术取舍

- 第一版保留 FFmpeg 渲染，避免过早引入复杂渲染体系。
- 参考 Hyperframes 的时间线描述方式，设计自己的 `CompositionSpec`。
- 参考 Remotion 的组件化模板思想，后续再考虑 React 视频模板。
- P0 不追求完整多模态理解，先用可解释结构和稳定 demo 拿分。
