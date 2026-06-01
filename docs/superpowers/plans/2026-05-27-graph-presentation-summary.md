# Graph Presentation Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the structure breakdown page show a concise graph summary by default, with a simplified graph view and evidence hidden behind explicit expansion.

**Architecture:** Add a backend `GraphPresentationSummary` to the template analysis payload so the frontend gets display-ready summary points and graph nodes. Then update the structure tab to render the summary and graph first, while moving verbose segment evidence into a collapsible details area. Keep existing `ShotEvidenceGraph` untouched for debugging and future RAG work.

**Tech Stack:** FastAPI/Pydantic backend models, existing ReelStruct template adapter, React/Next.js workspace components, Playwright workspace check.

---

## Files

- Modify: `services/api/app/models.py`
  - Add `GraphPresentationNode`, `GraphPresentationEdge`, and `GraphPresentationSummary`.
  - Add optional `graph_presentation` to `SampleAnalysisSummary`.
- Modify: `services/api/app/video_understanding/template_adapter.py`
  - Build `graph_presentation` from `ShotEvidenceGraph` in `adapt_graph_segments_to_template`.
  - Keep summary points short and Chinese.
- Modify: `services/api/tests/test_structure_service.py`
  - Assert graph-backed templates include concise presentation summary and nodes.
- Modify: `apps/web/src/hooks/useReelStruct.ts`
  - Add TypeScript types for `graph_presentation`.
  - Normalize and expose it through `analysisSummary`.
- Modify: `apps/web/src/components/Workspace/AnalysisSummaryPanel.tsx`
  - Show concise summary points before metrics.
  - Hide narrative evidence behind `<details>`.
- Modify: `apps/web/src/components/Workspace/WorkPanel.tsx`
  - Add simplified graph strip above the segment list.
  - Keep node evidence panel collapsed by default.
- Modify: `apps/web/scripts/check-workspace-shell.mjs`
  - Update generated structure assertions so the page checks concise graph UI rather than requiring verbose evidence to be visible by default.

## Task 1: Backend Presentation Summary

**Files:**
- Modify: `services/api/app/models.py`
- Modify: `services/api/app/video_understanding/template_adapter.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: Write the failing test**

Add a test that builds a graph-backed template and asserts:

```python
assert template.analysis_summary.graph_presentation is not None
assert template.analysis_summary.graph_presentation.headline
assert 1 <= len(template.analysis_summary.graph_presentation.summary_points) <= 5
assert any(node.node_type == "segment" for node in template.analysis_summary.graph_presentation.nodes)
assert all("analysis_units." not in point for point in template.analysis_summary.graph_presentation.summary_points)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_graph_template_includes_presentation_summary -q
```

Expected: fails because `graph_presentation` does not exist.

- [ ] **Step 3: Add backend models**

In `services/api/app/models.py`, add:

```python
class GraphPresentationNode(BaseModel):
    id: str
    label: str
    node_type: Literal["segment", "unit", "shot", "text", "gap"]
    summary: str = ""
    shot_indices: list[int] = Field(default_factory=list)
    confidence: float = 0


class GraphPresentationEdge(BaseModel):
    source: str
    target: str
    relation: str = ""


class GraphPresentationSummary(BaseModel):
    headline: str = ""
    summary_points: list[str] = Field(default_factory=list)
    nodes: list[GraphPresentationNode] = Field(default_factory=list)
    edges: list[GraphPresentationEdge] = Field(default_factory=list)
```

Then add `graph_presentation: Optional[GraphPresentationSummary] = None` to `SampleAnalysisSummary`.

- [ ] **Step 4: Build summary in adapter**

In `template_adapter.py`, add helper functions:

```python
def _graph_presentation_summary(sample_title: str, graph: ShotEvidenceGraph) -> GraphPresentationSummary:
    segment_nodes = [
        GraphPresentationNode(
            id=segment.segment_id,
            label=segment.label,
            node_type="segment",
            summary=segment.purpose or segment.method or segment.label,
            shot_indices=segment.shot_indices,
            confidence=segment.confidence,
        )
        for segment in graph.segments
    ]
    unit_nodes = [
        GraphPresentationNode(
            id=unit.unit_id,
            label=unit.unit_id.replace("unit_", "分析单元 "),
            node_type="unit",
            summary=unit.understanding.visual_summary if unit.understanding else "",
            shot_indices=unit.shot_indices,
            confidence=unit.understanding.confidence if unit.understanding else 0,
        )
        for unit in graph.analysis_units
    ]
    edges = [
        GraphPresentationEdge(source=segment.segment_id, target=unit.unit_id, relation="覆盖")
        for segment in graph.segments
        for unit in graph.analysis_units
        if set(segment.shot_indices).intersection(unit.shot_indices)
    ]
    points = _graph_summary_points(graph)
    return GraphPresentationSummary(
        headline=_graph_presentation_headline(sample_title, graph),
        summary_points=points,
        nodes=[*segment_nodes, *unit_nodes],
        edges=edges,
    )
```

Set `graph_presentation=_graph_presentation_summary(sample_title, graph)` when constructing `SampleAnalysisSummary`.

- [ ] **Step 5: Run backend test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_graph_template_includes_presentation_summary -q
```

Expected: pass.

## Task 2: Frontend Summary and Graph View

**Files:**
- Modify: `apps/web/src/hooks/useReelStruct.ts`
- Modify: `apps/web/src/components/Workspace/AnalysisSummaryPanel.tsx`
- Modify: `apps/web/src/components/Workspace/WorkPanel.tsx`
- Modify: `apps/web/src/app/globals.css`

- [ ] **Step 1: Add frontend types**

Add:

```ts
type GraphPresentationNode = {
  id: string
  label: string
  node_type: 'segment' | 'unit' | 'shot' | 'text' | 'gap'
  summary: string
  shot_indices: number[]
  confidence: number
}

type GraphPresentationEdge = {
  source: string
  target: string
  relation: string
}

type GraphPresentationSummary = {
  headline: string
  summary_points: string[]
  nodes: GraphPresentationNode[]
  edges: GraphPresentationEdge[]
}
```

Expose it in `AnalysisSummaryViewModel` as `graphPresentation`.

- [ ] **Step 2: Render concise summary**

In `AnalysisSummaryPanel`, before metrics, render `analysis.graphPresentation.summaryPoints` as short bullets. Wrap narrative beats in:

```tsx
<details className="evidence-details">
  <summary>展开段落证据</summary>
  ...
</details>
```

- [ ] **Step 3: Render simplified graph**

In `WorkPanel`, add a small graph strip above the segment list:

```tsx
<div className="graph-strip" aria-label="图谱结构概要">
  {analysis?.graphPresentation?.nodes.slice(0, 12).map((node) => (
    <button className="graph-node-pill" data-type={node.nodeType} key={node.id}>
      <span>{node.nodeType === 'segment' ? '段落' : '单元'}</span>
      <strong>{node.label}</strong>
    </button>
  ))}
</div>
```

- [ ] **Step 4: Collapse node evidence**

Change the existing `.node-evidence` block to render inside:

```tsx
<details className="node-evidence-details">
  <summary>查看节点证据</summary>
  ...
</details>
```

Default state must be collapsed.

- [ ] **Step 5: Add CSS**

Add styles for:

- `.summary-point-list`
- `.graph-strip`
- `.graph-node-pill`
- `.evidence-details`
- `.node-evidence-details`

Use existing card colors and 8px radius. Do not create a new decorative visual theme.

## Task 3: Verification

**Files:**
- Modify: `apps/web/scripts/check-workspace-shell.mjs`

- [ ] **Step 1: Update Playwright assertions**

After generation, assert:

```js
for (const label of ["图谱概要", "图谱结构概要", "展开段落证据", "查看节点证据"]) {
  if (!generatedWorkspaceText.includes(label)) {
    throw new Error(`workspace graph presentation is missing label: ${label}`);
  }
}
```

Also assert the default generated body text does not contain a long evidence marker before opening details:

```js
const visibleEvidenceDetails = await page.locator(".node-evidence-details[open]").count();
if (visibleEvidenceDetails > 0) {
  throw new Error("node evidence details should be collapsed by default");
}
```

- [ ] **Step 2: Run verification**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py tests/test_ai_video_structure_service.py -q
```

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run typecheck
npm run check:workspace
```

Run:

```bash
cd /Users/linkwind/Code/ReelStruct
git diff --check
```

Expected: all pass.

