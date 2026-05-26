# Workspace P0 Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover the existing ReelStruct P0 backend capabilities inside the new Workspace UI so a reviewer can see AI structure decomposition, material gaps, transfer reasoning, and the rendered MP4 demo in one clear flow.

**Architecture:** Keep the current `MainApp -> HomeView -> WorkspaceView` shell. Fix the stale backend test contract first, then add focused Workspace display components that consume fields already returned by `useReelStruct`: `preview`, `run`, `videoUrl`, `analysisSummary`, `analysisSource`, `analysisWarnings`, `selectedGaps`, and `requestSheetItems`. Avoid reintroducing the old monolithic `ReelStructWorkspace` UI; use it only as a source for proven display logic.

**Tech Stack:** Next.js 16, React 19, TypeScript 6, FastAPI, Pydantic, pytest, existing FFmpeg render pipeline, existing `useReelStruct` hook.

---

## File Structure

- Modify `services/api/tests/test_render_service.py`: update stale `RenderClip` test fixtures so backend tests pass with the current render contract.
- Modify `apps/web/src/components/Views/WorkspaceView.tsx`: derive display-ready AI summary, material gaps, transfer mappings, rendered video, and run trace from `useReelStruct`.
- Modify `apps/web/src/components/Workspace/WorkPanel.tsx`: accept and render analysis, gaps, result video, run trace, and richer mapping details.
- Create `apps/web/src/components/Workspace/AnalysisSummaryPanel.tsx`: show AI/rule/fallback source, confidence, warnings, metrics, narrative beats, and packaging signals.
- Create `apps/web/src/components/Workspace/MaterialGapPanel.tsx`: show slot-level material gaps and fill strategies.
- Create `apps/web/src/components/Workspace/ResultPreviewPanel.tsx`: show rendered MP4, run id, prepared assets, trace, and export/download affordances.
- Modify `apps/web/src/app/globals.css`: add compact styles for the new panels and mobile-safe layouts.
- Modify `apps/web/scripts/check-workspace-shell.mjs`: extend smoke checks to verify empty state, no mock nodes, and output-panel affordances.

---

### Task 1: Restore Backend Test Green

**Files:**
- Modify: `services/api/tests/test_render_service.py`

- [ ] **Step 1: Add a local render clip factory in the test file**

Insert below the imports:

```python
from app.models import MaterialFitAnalysis


def make_render_clip(
    *,
    scene_id: str,
    local_path: str,
    public_url: str,
    caption: str,
    start_time: float,
    duration: float,
) -> RenderClip:
    return RenderClip(
        scene_id=scene_id,
        local_path=local_path,
        public_url=public_url,
        caption=caption,
        start_time=start_time,
        duration=duration,
        source_type="fixture",
        source_label="test fixture",
        material_analysis=MaterialFitAnalysis(),
    )
```

- [ ] **Step 2: Replace direct `RenderClip(...)` calls**

Replace both direct test constructors with `make_render_clip(...)` using the same arguments already present in the tests.

- [ ] **Step 3: Verify the focused tests**

Run:

```bash
cd services/api
PYTHONPATH=. .venv/bin/pytest tests/test_render_service.py -q
```

Expected: all render service tests pass.

- [ ] **Step 4: Verify all backend tests**

Run:

```bash
cd services/api
PYTHONPATH=. .venv/bin/pytest tests -q
```

Expected: `123 passed, 1 skipped` or equivalent with no failures.

---

### Task 2: Add Workspace Analysis Summary Panel

**Files:**
- Create: `apps/web/src/components/Workspace/AnalysisSummaryPanel.tsx`
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/components/Workspace/WorkPanel.tsx`

- [ ] **Step 1: Create `AnalysisSummaryPanel.tsx`**

```tsx
import React from 'react'

type AnalysisSource = 'rule' | 'ai' | 'fallback'

type AnalysisMetric = {
  label: string
  value: string
  detail: string
}

type NarrativeBeat = {
  slot_id: string
  label: string
  evidence: string
}

export interface AnalysisSummaryViewModel {
  source: AnalysisSource
  confidence: number
  headline: string
  metrics: AnalysisMetric[]
  narrativeBeats: NarrativeBeat[]
  packagingSignals: string[]
  warnings: string[]
}

function sourceLabel(source: AnalysisSource) {
  if (source === 'ai') return 'AI 视频结构拆解'
  if (source === 'fallback') return 'AI 失败兜底'
  return '基础结构拆解'
}

function confidenceLabel(confidence: number) {
  if (!confidence) return ''
  const normalized = confidence <= 1 ? confidence * 100 : confidence
  return `${Math.round(normalized)}%`
}

export default function AnalysisSummaryPanel({ analysis }: { analysis: AnalysisSummaryViewModel | null }) {
  if (!analysis) {
    return (
      <article className="insight-panel soft-card">
        <div className="section-head">
          <div>
            <p className="eyebrow">AI structure</p>
            <h3>结构拆解解释</h3>
          </div>
          <span className="status">等待生成</span>
        </div>
        <div className="empty-state">
          <strong>还没有 AI 拆解结果</strong>
          <span>上传样例并生成结构后，这里会显示来源、置信度、证据和包装信号。</span>
        </div>
      </article>
    )
  }

  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">AI structure</p>
          <h3>{analysis.headline || '结构拆解解释'}</h3>
        </div>
        <span className="status" data-source={analysis.source}>
          {sourceLabel(analysis.source)}
          {confidenceLabel(analysis.confidence) ? ` · ${confidenceLabel(analysis.confidence)}` : ''}
        </span>
      </div>

      {analysis.warnings.length ? (
        <div className="warning-list">
          {analysis.warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}

      <div className="metric-grid">
        {analysis.metrics.map((metric) => (
          <div className="metric-item" key={`${metric.label}-${metric.value}`}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <p>{metric.detail}</p>
          </div>
        ))}
      </div>

      <div className="explain-list">
        {analysis.narrativeBeats.map((beat) => (
          <div className="explain-row" key={`${beat.slot_id}-${beat.label}`}>
            <strong>{beat.label}</strong>
            <span>{beat.evidence}</span>
          </div>
        ))}
      </div>

      {analysis.packagingSignals.length ? (
        <div className="tag-row">
          {analysis.packagingSignals.map((signal) => (
            <span key={signal}>{signal}</span>
          ))}
        </div>
      ) : null}
    </article>
  )
}
```

- [ ] **Step 2: Derive analysis view model in `WorkspaceView.tsx`**

Add `analysisSummary`, `analysisSource`, `analysisConfidence`, and `analysisWarnings` to the hook destructure:

```tsx
const {
  preview,
  sample,
  sampleUpload,
  status,
  error,
  uploadSample,
  runDemo,
  videoUrl,
  run,
  analysisSummary,
  analysisSource,
  analysisConfidence,
  analysisWarnings,
  selectedGaps,
} = reelStruct
```

Then add:

```tsx
const analysisView = useMemo(() => {
  if (!analysisSummary) return null
  return {
    source: analysisSource,
    confidence: analysisConfidence,
    headline: analysisSummary.headline,
    metrics: analysisSummary.metrics,
    narrativeBeats: analysisSummary.narrative_beats,
    packagingSignals: analysisSummary.packaging_signals,
    warnings: analysisWarnings,
  }
}, [analysisConfidence, analysisSource, analysisSummary, analysisWarnings])
```

- [ ] **Step 3: Pass `analysisView` to `WorkPanel`**

Add this prop:

```tsx
analysis={analysisView}
```

- [ ] **Step 4: Render `AnalysisSummaryPanel` from `WorkPanel`**

Import and render it below the structure node card:

```tsx
import AnalysisSummaryPanel, { AnalysisSummaryViewModel } from './AnalysisSummaryPanel'
```

Add to props:

```tsx
analysis: AnalysisSummaryViewModel | null
```

Render:

```tsx
<AnalysisSummaryPanel analysis={analysis} />
```

- [ ] **Step 5: Run frontend typecheck**

```bash
cd apps/web
npm run typecheck
```

Expected: no TypeScript errors.

---

### Task 3: Show Material Gaps And Fill Strategies

**Files:**
- Create: `apps/web/src/components/Workspace/MaterialGapPanel.tsx`
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/components/Workspace/WorkPanel.tsx`

- [ ] **Step 1: Create `MaterialGapPanel.tsx`**

```tsx
import React from 'react'

export interface MaterialGapViewModel {
  slotId: string
  label: string
  missingAsset: string
  impact: string
  fillStrategy: string
  suggestedAssetType: string
  suggestedShots: string[]
  pickupChecklist: string[]
}

export default function MaterialGapPanel({ gaps }: { gaps: MaterialGapViewModel[] }) {
  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">Material gaps</p>
          <h3>素材缺口与补全</h3>
        </div>
        <span className="status">{gaps.length ? `${gaps.length} 个缺口` : '无缺口'}</span>
      </div>

      {gaps.length ? (
        <div className="gap-list">
          {gaps.map((gap) => (
            <section className="gap-item" key={gap.slotId}>
              <div className="gap-title">
                <strong>{gap.label}</strong>
                <span>{gap.suggestedAssetType}</span>
              </div>
              <p>{gap.impact}</p>
              <div className="gap-strategy">{gap.fillStrategy}</div>
              {gap.suggestedShots.length ? (
                <ul>
                  {gap.suggestedShots.map((shot) => (
                    <li key={shot}>{shot}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <strong>暂时没有素材缺口</strong>
          <span>生成迁移方案后，系统会按结构槽位检查缺失素材。</span>
        </div>
      )}
    </article>
  )
}
```

- [ ] **Step 2: Derive gap view model in `WorkspaceView.tsx`**

Add:

```tsx
const slotLabelLookup = useMemo(() => {
  return new Map((preview?.template.script_pattern || []).map((slot) => [slot.id, slot.label]))
}, [preview])

const gapItems = useMemo(() => {
  return selectedGaps.map((gap) => ({
    slotId: gap.slot_id,
    label: slotLabelLookup.get(gap.slot_id) || gap.slot_id,
    missingAsset: gap.missing_asset,
    impact: gap.impact,
    fillStrategy: gap.fill_strategy,
    suggestedAssetType: gap.suggested_asset_type,
    suggestedShots: gap.suggested_shots,
    pickupChecklist: gap.pickup_checklist,
  }))
}, [selectedGaps, slotLabelLookup])
```

- [ ] **Step 3: Pass and render gap items**

Pass to `WorkPanel`:

```tsx
materialGaps={gapItems}
```

Import in `WorkPanel`:

```tsx
import MaterialGapPanel, { MaterialGapViewModel } from './MaterialGapPanel'
```

Add prop:

```tsx
materialGaps: MaterialGapViewModel[]
```

Render below the material mapping card:

```tsx
<MaterialGapPanel gaps={materialGaps} />
```

- [ ] **Step 4: Run frontend typecheck**

```bash
cd apps/web
npm run typecheck
```

Expected: no TypeScript errors.

---

### Task 4: Show Rendered MP4 And Run Trace

**Files:**
- Create: `apps/web/src/components/Workspace/ResultPreviewPanel.tsx`
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/components/Workspace/WorkPanel.tsx`

- [ ] **Step 1: Create `ResultPreviewPanel.tsx`**

```tsx
import React from 'react'

export interface PreparedAssetViewModel {
  sceneId: string
  sourceType: string
  sourceLabel: string
  caption: string
  duration: number
}

export interface TraceViewModel {
  step: string
  title: string
  message: string
  progress: number
}

export interface ResultPreviewViewModel {
  runId: string
  batchId: string
  videoUrl: string
  assets: PreparedAssetViewModel[]
  trace: TraceViewModel[]
}

export default function ResultPreviewPanel({ result }: { result: ResultPreviewViewModel | null }) {
  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">Output</p>
          <h3>结果验证</h3>
        </div>
        <span className="status">{result?.runId || '等待生成'}</span>
      </div>

      {result?.videoUrl ? (
        <div className="result-preview-grid">
          <video className="result-video" src={result.videoUrl} controls preload="metadata" />
          <div className="result-meta">
            <p>Run: {result.runId}</p>
            <p>Batch: {result.batchId || '-'}</p>
            <p>素材片段: {result.assets.length}</p>
            <a className="btn" href={`/api/runs/${result.runId}/export.zip`}>
              下载结果包
            </a>
          </div>
        </div>
      ) : (
        <div className="empty-state">
          <strong>还没有成片 demo</strong>
          <span>点击生成结构后，后端会渲染 MP4 demo 并显示在这里。</span>
        </div>
      )}

      {result?.trace.length ? (
        <div className="trace-list">
          {result.trace.map((event) => (
            <div className="trace-item" key={`${event.step}-${event.progress}`}>
              <strong>{event.title}</strong>
              <span>{event.message}</span>
              <div className="bar">
                <span style={{ '--value': `${event.progress}%` } as React.CSSProperties} />
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  )
}
```

- [ ] **Step 2: Derive result view model in `WorkspaceView.tsx`**

Add:

```tsx
const resultView = useMemo(() => {
  if (!run || !videoUrl) return null
  return {
    runId: run.run_id,
    batchId: run.batch_id,
    videoUrl,
    assets: run.prepared_assets.map((asset) => ({
      sceneId: asset.scene_id,
      sourceType: asset.source_type,
      sourceLabel: asset.source_label,
      caption: asset.caption,
      duration: asset.duration,
    })),
    trace: run.trace,
  }
}, [run, videoUrl])
```

Pass:

```tsx
result={resultView}
```

- [ ] **Step 3: Render result panel in `WorkPanel`**

Import:

```tsx
import ResultPreviewPanel, { ResultPreviewViewModel } from './ResultPreviewPanel'
```

Add prop:

```tsx
result: ResultPreviewViewModel | null
```

Render near the bottom:

```tsx
<ResultPreviewPanel result={result} />
```

- [ ] **Step 4: Switch main video to result video in output stage**

In `WorkspaceView.tsx`, replace:

```tsx
const displayVideoUrl = sampleUpload?.public_url || localVideoUrl
```

with:

```tsx
const displayVideoUrl = currentStage === 'output' && videoUrl ? videoUrl : sampleUpload?.public_url || localVideoUrl
```

Replace:

```tsx
const displayVideoName = localVideoFile?.name || sampleUpload?.filename || '尚未上传参考视频'
```

with:

```tsx
const displayVideoName =
  currentStage === 'output' && run?.run_id
    ? `${run.run_id}.mp4`
    : localVideoFile?.name || sampleUpload?.filename || '尚未上传参考视频'
```

- [ ] **Step 5: Run frontend typecheck and workspace check**

```bash
cd apps/web
npm run typecheck
npm run check:workspace
```

Expected: typecheck passes and `WORKSPACE_SHELL_OK=1`.

---

### Task 5: Add Compact Styles For New Panels

**Files:**
- Modify: `apps/web/src/app/globals.css`

- [ ] **Step 1: Add panel styles before the media queries**

```css
.insight-panel {
  padding: var(--space-5);
  display: grid;
  gap: var(--space-4);
}
.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}
.section-head h3 {
  margin-top: var(--space-2);
  font-size: var(--text-xl);
  font-weight: 560;
}
.warning-list,
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.warning-list span,
.tag-row span {
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  padding: 4px 10px;
  color: var(--muted);
  font-size: var(--text-xs);
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}
.metric-item,
.explain-row,
.gap-item,
.trace-item {
  border-top: 1px solid color-mix(in oklab, var(--border), transparent 34%);
  padding-top: var(--space-3);
  display: grid;
  gap: var(--space-2);
}
.metric-item span,
.explain-row span,
.gap-item p,
.gap-item li,
.trace-item span,
.result-meta {
  color: var(--muted);
  font-size: var(--text-sm);
}
.gap-list,
.explain-list,
.trace-list {
  display: grid;
  gap: var(--space-3);
}
.gap-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.gap-strategy {
  border-radius: var(--radius-md);
  background: color-mix(in oklab, var(--surface-2), var(--surface) 40%);
  padding: var(--space-3);
  color: var(--fg);
  font-size: var(--text-sm);
}
.result-preview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: var(--space-4);
  align-items: start;
}
.result-video {
  width: 100%;
  aspect-ratio: 9 / 16;
  max-height: 520px;
  border-radius: var(--radius-md);
  background: var(--fg);
}
```

- [ ] **Step 2: Add mobile overrides inside `@media (max-width: 720px)`**

```css
.metric-grid,
.result-preview-grid {
  grid-template-columns: 1fr;
}
.section-head,
.gap-title {
  flex-direction: column;
}
```

- [ ] **Step 3: Run build**

```bash
cd apps/web
npm run build
```

Expected: build passes.

---

### Task 6: Extend Workspace Smoke Check

**Files:**
- Modify: `apps/web/scripts/check-workspace-shell.mjs`

- [ ] **Step 1: Add text checks for new panel empty states**

After the existing workspace text assertions, add:

```js
if (!workspaceText.includes("结构拆解解释")) {
  throw new Error("workspace analysis summary panel is missing");
}
if (!workspaceText.includes("素材缺口与补全")) {
  throw new Error("workspace material gap panel is missing");
}
if (!workspaceText.includes("结果验证")) {
  throw new Error("workspace result preview panel is missing");
}
```

- [ ] **Step 2: Run smoke check with dev server**

Start the app if needed:

```bash
cd apps/web
npm run dev
```

In another shell:

```bash
cd apps/web
npm run check:workspace
```

Expected: `WORKSPACE_SHELL_OK=1`.

---

### Task 7: Final Verification

**Files:**
- No source changes unless verification reveals a regression.

- [ ] **Step 1: Run backend tests**

```bash
cd services/api
PYTHONPATH=. .venv/bin/pytest tests -q
```

Expected: no failures.

- [ ] **Step 2: Run frontend typecheck**

```bash
cd apps/web
npm run typecheck
```

Expected: no TypeScript errors.

- [ ] **Step 3: Run frontend production build**

```bash
cd apps/web
npm run build
```

Expected: build completes successfully.

- [ ] **Step 4: Run workspace smoke check**

```bash
cd apps/web
npm run check:workspace
```

Expected: `WORKSPACE_SHELL_OK=1`.

---

## Self-Review

- Spec coverage: This plan covers the next P0 recovery scope: test green, output MP4 visibility, AI/fallback explanation, material gaps, and migration/result verification surfaces.
- Scope control: This plan intentionally excludes full run history, template library editing, four-version comparison, and structured prompt parsing. Those belong to the following phase after the single-run demo is clear.
- Placeholder scan: No TBD/TODO placeholders remain in the implementation steps.
- Type consistency: New view models use existing hook data names and keep snake_case-to-camelCase conversion inside `WorkspaceView`.
