# Frontend Workspace Real Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current ReelStruct frontend from a polished mock shell into a real first-stage workspace that uses the existing API hook, shows honest empty/loading/error states, and passes build/static/mobile checks.

**Architecture:** Keep the new `MainApp` / `HomeView` / `WorkspaceView` component shell as the product entry. Mount `useReelStruct()` only inside the workspace view so the homepage does not fetch run/template data. Normalize hook data in `WorkspaceView`, pass display-ready state to `WorkPanel` and `AgentActionPanel`, and make CSS changes in the existing global stylesheet before any deeper component-style split.

**Tech Stack:** Next.js 16, React 19, TypeScript 6, Tailwind base utilities, existing `useReelStruct` hook, Node-based browser smoke scripts.

---

## File Structure

- Modify `apps/web/src/components/MainApp.tsx`: make homepage data-free and mount the hook only in a child workspace route.
- Modify `apps/web/src/components/Layout/Topbar.tsx`: rename brand from CutFlow AI to ReelStruct and keep status/back controls.
- Modify `apps/web/src/components/Views/HomeView.tsx`: simplify the landing screen into a task entry and remove fake preview output.
- Modify `apps/web/src/components/Views/WorkspaceView.tsx`: remove mock nodes/mappings, derive real display state from `useReelStruct`, call real upload/generate actions, and pass status/error down.
- Modify `apps/web/src/components/Workspace/AgentActionPanel.tsx`: show task, status, error, and honest local-only follow-up messages.
- Modify `apps/web/src/components/Workspace/WorkPanel.tsx`: support empty states, loading states, real upload, real generation action, real facts, and safe local video URLs.
- Modify `apps/web/src/components/Workspace/WorkflowNav.tsx`: align stages with the real workflow names and disabled/incomplete copy.
- Modify `apps/web/src/app/globals.css`: apply the agreed workbench design system and fix mobile overflow.
- Modify `apps/web/package.json`: replace invalid `next lint` with a runnable static check.
- Create `apps/web/scripts/check-workspace-shell.mjs`: browser smoke check for homepage request hygiene, branding, workspace empty state, and mobile overflow.

---

### Task 1: Mount Workspace Data Only Inside Workspace

**Files:**
- Modify: `apps/web/src/components/MainApp.tsx`

- [ ] **Step 1: Replace top-level hook usage with a workspace-only child component**

Change `MainApp.tsx` to this structure:

```tsx
'use client'

import React, { useState } from 'react'
import Topbar from './Layout/Topbar'
import HomeView from './Views/HomeView'
import WorkspaceView from './Views/WorkspaceView'
import { useReelStruct } from '../hooks/useReelStruct'

type ViewMode = 'home' | 'workspace'

function WorkspaceRoute({ taskText }: { taskText: string }) {
  const reelStruct = useReelStruct()
  return <WorkspaceView taskText={taskText} reelStruct={reelStruct} />
}

export default function MainApp() {
  const [view, setView] = useState<ViewMode>('home')
  const [taskText, setTaskText] = useState('')

  const handleStartMigration = (prompt: string) => {
    setTaskText(prompt)
    setView('workspace')
  }

  const handleBackHome = () => {
    setView('home')
    setTaskText('')
  }

  return (
    <div className="app">
      <Topbar
        modeLabel={view === 'home' ? '准备开始' : '工作台'}
        showBack={view === 'workspace'}
        onBackHome={handleBackHome}
      />
      <main>
        {view === 'home' ? (
          <HomeView onStartMigration={handleStartMigration} />
        ) : (
          <WorkspaceRoute taskText={taskText} />
        )}
      </main>
    </div>
  )
}
```

- [ ] **Step 2: Run the static build**

Run:

```bash
cd apps/web
npm run build
```

Expected: build passes. Homepage may still visually show old brand until Task 2.

- [ ] **Step 3: Commit Task 1**

```bash
git add apps/web/src/components/MainApp.tsx
git commit -m "fix: mount reelstruct data only in workspace"
```

---

### Task 2: Rename Brand And Simplify Homepage Entry

**Files:**
- Modify: `apps/web/src/components/Layout/Topbar.tsx`
- Modify: `apps/web/src/components/Views/HomeView.tsx`

- [ ] **Step 1: Update `Topbar.tsx` brand copy**

Use ReelStruct everywhere:

```tsx
import React from 'react'

interface TopbarProps {
  modeLabel: string
  onBackHome?: () => void
  showBack?: boolean
}

export default function Topbar({ modeLabel, onBackHome, showBack }: TopbarProps) {
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <div className="brand" aria-label="ReelStruct">
          <div className="brand-mark" aria-hidden="true">RS</div>
          <div>
            <strong>ReelStruct</strong>
            <span id="brandSubtitle">短视频结构迁移工作台</span>
          </div>
        </div>
        <div className="top-actions">
          <span id="modeLabel">{modeLabel}</span>
          {showBack ? (
            <button className="btn btn-quiet" id="backHome" type="button" onClick={onBackHome}>
              返回首页
            </button>
          ) : null}
        </div>
      </div>
    </header>
  )
}
```

- [ ] **Step 2: Replace homepage with a single task entry**

Change `HomeView.tsx` so it no longer displays the fake `reference_creator_ad.mp4` preview card and does not show two competing primary actions:

```tsx
import React, { useState } from 'react'

interface HomeViewProps {
  onStartMigration: (prompt: string) => void
}

const EXAMPLES = [
  '把参考视频的五段式结构迁移到新品演示素材里，保留 2 秒 Hook 和轻 CTA。',
  '分析一个爆款 Reels 的镜头节奏，把开场反差、演示转场和字幕断句迁移到我的素材。',
  '把竞品视频拆成可审查结构节点，再用我方素材生成一版 30 秒竖屏剪辑计划。',
]

export default function HomeView({ onStartMigration }: HomeViewProps) {
  const [prompt, setPrompt] = useState('')

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    onStartMigration(prompt.trim())
  }

  return (
    <section className="view home" id="homeView" data-active="true">
      <div className="home-shell">
        <div className="home-copy">
          <p className="eyebrow">ReelStruct Workspace</p>
          <h1>短视频结构迁移工作台</h1>
          <p className="home-lead">
            输入任务并进入工作台，上传参考视频后再生成真实结构拆解、素材映射和 demo 输出。
          </p>
        </div>

        <form className="prompt-panel soft-card" id="homeForm" onSubmit={handleSubmit}>
          <textarea
            id="homePrompt"
            aria-label="输入视频结构迁移任务"
            placeholder="分析这个 42 秒参考广告的节奏，把 Hook、痛点、演示、证明和 CTA 迁移到我上传的产品素材里。"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
          />
          <div className="prompt-footer">
            <span>可先进入工作台，再上传参考视频和补充素材。</span>
            <button className="btn btn-primary" type="submit">进入工作台</button>
          </div>
        </form>

        <div className="examples" aria-label="示例任务">
          {EXAMPLES.map((example) => (
            <button
              className="example"
              key={example}
              type="button"
              onClick={() => setPrompt(example)}
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 3: Run build**

Run:

```bash
cd apps/web
npm run build
```

Expected: build passes and homepage brand reads ReelStruct.

- [ ] **Step 4: Commit Task 2**

```bash
git add apps/web/src/components/Layout/Topbar.tsx apps/web/src/components/Views/HomeView.tsx
git commit -m "feat: simplify reelstruct homepage entry"
```

---

### Task 3: Replace Workspace Mock Results With Real State

**Files:**
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/components/Workspace/WorkflowNav.tsx`

- [ ] **Step 1: Update workflow stages**

Change `WorkflowNav.tsx` stage labels to match the real workflow:

```tsx
import React from 'react'

export type Stage = 'sample' | 'structure' | 'output'

interface WorkflowNavProps {
  currentStage: Stage
  onStageChange: (stage: Stage) => void
}

const STAGES: Array<{
  id: Stage
  index: string
  title: string
  description: string
}> = [
  {
    id: 'sample',
    index: '01',
    title: '样例输入',
    description: '上传参考视频，读取真实视频信息。',
  },
  {
    id: 'structure',
    index: '02',
    title: '结构拆解',
    description: '生成结构节点、节奏和素材映射。',
  },
  {
    id: 'output',
    index: '03',
    title: '输出检查',
    description: '检查 demo、缺口和后续版本输出。',
  },
]

export default function WorkflowNav({ currentStage, onStageChange }: WorkflowNavProps) {
  return (
    <nav className="workflow-steps soft-card" id="workflowSteps" aria-label="工作台步骤">
      {STAGES.map((stage) => (
        <button
          className="workflow-step"
          type="button"
          key={stage.id}
          data-stage={stage.id}
          data-active={currentStage === stage.id}
          onClick={() => onStageChange(stage.id)}
        >
          <span className="workflow-index">{stage.index}</span>
          <span className="workflow-copy">
            <strong>{stage.title}</strong>
            <span>{stage.description}</span>
          </span>
        </button>
      ))}
    </nav>
  )
}
```

- [ ] **Step 2: Replace `WorkspaceView.tsx` mock constants and derived state**

Use this implementation pattern. It removes `ORIGINAL_MOCK_NODES`, `ORIGINAL_MOCK_PROGRESS`, and `ORIGINAL_MOCK_MAPPING`:

```tsx
import React, { useEffect, useMemo, useState } from 'react'
import WorkflowNav, { Stage } from '../Workspace/WorkflowNav'
import AgentActionPanel, { ChatMessage } from '../Workspace/AgentActionPanel'
import WorkPanel from '../Workspace/WorkPanel'
import { useReelStruct } from '../../hooks/useReelStruct'

function formatSeconds(secs: number) {
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function isBusy(status: string) {
  return status.startsWith('正在')
}

interface WorkspaceViewProps {
  taskText: string
  reelStruct: ReturnType<typeof useReelStruct>
}

export default function WorkspaceView({ taskText, reelStruct }: WorkspaceViewProps) {
  const [currentStage, setCurrentStage] = useState<Stage>('sample')
  const [activeNodeKey, setActiveNodeKey] = useState('')
  const [localVideoFile, setLocalVideoFile] = useState<File | null>(null)
  const [localVideoUrl, setLocalVideoUrl] = useState<string | undefined>()
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      role: 'user',
      label: '任务',
      body: taskText || '未填写任务，可先上传参考视频再补充目标。',
    },
    {
      id: '2',
      role: 'agent',
      label: 'ReelStruct',
      body: '工作台已准备好。上传参考视频后，我会使用真实接口生成结构拆解和素材映射。',
    },
  ])

  const {
    preview,
    sample,
    sampleUpload,
    status,
    error,
    uploadSample,
    runDemo,
    videoUrl,
  } = reelStruct

  useEffect(() => {
    if (!localVideoFile) {
      setLocalVideoUrl(undefined)
      return
    }
    const objectUrl = URL.createObjectURL(localVideoFile)
    setLocalVideoUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [localVideoFile])

  const nodes = useMemo(() => {
    return (preview?.template.script_pattern || []).map((slot) => ({
      key: slot.id,
      time: `${formatSeconds(slot.start)} - ${formatSeconds(slot.start + slot.duration)}`,
      label: slot.label,
      desc: slot.purpose || slot.intent || slot.role || '这个节点暂无说明。',
      score: `置信度 ${Math.round(slot.confidence)}%`,
    }))
  }, [preview])

  useEffect(() => {
    if (!nodes.length) {
      setActiveNodeKey('')
      return
    }
    setActiveNodeKey((current) => (nodes.some((node) => node.key === current) ? current : nodes[0].key))
  }, [nodes])

  const mappingItems = useMemo(() => {
    return (preview?.transfer_plan.mappings || []).map((mapping) => ({
      label: mapping.asset_requirement || mapping.target_message,
      score: mapping.asset_strategy || '已生成映射',
      percent: 100,
    }))
  }, [preview])

  const progressItems = useMemo(() => {
    const items = [
      { label: '样例视频', v1: sampleUpload ? '已上传' : '未上传', v2: '', percent: sampleUpload ? 100 : 0 },
      { label: '结构拆解', v1: preview ? `${nodes.length}` : '未生成', v2: preview ? '节点' : '', percent: preview ? 100 : 0 },
      { label: '当前状态', v1: status, v2: '', percent: isBusy(status) ? 60 : status === '等待生成' ? 0 : 100 },
    ]
    return items
  }, [nodes.length, preview, sampleUpload, status])

  const handleSendMessage = (text: string) => {
    setMessages((current) => [
      ...current,
      { id: Date.now().toString(), role: 'user', label: '补充要求', body: text },
      {
        id: `${Date.now()}-local`,
        role: 'agent',
        label: 'ReelStruct',
        body: '我已记录这条补充要求。第一阶段不会自动重跑后端，请点击生成按钮重新执行。',
      },
    ])
  }

  const handleUploadVideo = (file: File) => {
    setLocalVideoFile(file)
    void uploadSample(file)
  }

  const handleGenerate = () => {
    setCurrentStage('structure')
    void runDemo()
  }

  return (
    <section className="view workspace" id="workspaceView" data-active="true">
      <div className="workspace-frame">
        <WorkflowNav currentStage={currentStage} onStageChange={setCurrentStage} />

        <div className="workspace-shell">
          <AgentActionPanel
            messages={messages}
            onSendMessage={handleSendMessage}
            status={status}
            error={error}
            isBusy={isBusy(status)}
          />

          <WorkPanel
            stageTitle={preview ? '结构拆解结果' : '样例输入'}
            stageDescription={preview ? preview.template.rhythm_summary : '上传参考视频后，使用真实接口生成结构节点和素材映射。'}
            workClock={preview ? `${formatSeconds(sample.duration)} 样例` : status}
            hasVideo={Boolean(sampleUpload?.public_url || localVideoUrl || videoUrl)}
            videoUrl={videoUrl || sampleUpload?.public_url || localVideoUrl}
            videoName={localVideoFile?.name || sampleUpload?.filename || '尚未上传参考视频'}
            videoDuration={formatSeconds(sample.duration)}
            sampleMeta={{
              shotCount: sampleUpload?.sample.shot_count,
              targetAssetCount: preview?.transfer_plan.mappings.length,
            }}
            nodes={nodes}
            activeNodeKey={activeNodeKey}
            onNodeClick={setActiveNodeKey}
            onUploadVideo={handleUploadVideo}
            onGenerate={handleGenerate}
            isBusy={isBusy(status)}
            status={status}
            error={error}
            progressItems={progressItems}
            mappingItems={mappingItems}
          />
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 3: Run build**

Run:

```bash
cd apps/web
npm run build
```

Expected: build fails if `WorkPanel` and `AgentActionPanel` have not yet accepted the new props. Continue to Task 4 before committing if this is the failure.

- [ ] **Step 4: Commit Task 3 only after Task 4 type errors are resolved**

Do not commit Task 3 alone if TypeScript fails. Commit it together with Task 4:

```bash
git add apps/web/src/components/Views/WorkspaceView.tsx apps/web/src/components/Workspace/WorkflowNav.tsx
git commit -m "feat: derive workspace state from real reelstruct data"
```

---

### Task 4: Add Honest Agent And Work Panel States

**Files:**
- Modify: `apps/web/src/components/Workspace/AgentActionPanel.tsx`
- Modify: `apps/web/src/components/Workspace/WorkPanel.tsx`

- [ ] **Step 1: Extend `AgentActionPanel` props**

Replace `AgentActionPanel.tsx` with:

```tsx
import React, { useState } from 'react'

export interface ChatMessage {
  id: string
  role: 'agent' | 'user'
  label: string
  body: string
  steps?: { title: string; time: string }[]
}

interface AgentActionPanelProps {
  messages: ChatMessage[]
  onSendMessage: (msg: string) => void
  status: string
  error: string
  isBusy: boolean
}

export default function AgentActionPanel({
  messages,
  onSendMessage,
  status,
  error,
  isBusy,
}: AgentActionPanelProps) {
  const [inputStr, setInputStr] = useState('')

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    const next = inputStr.trim()
    if (!next) return
    onSendMessage(next)
    setInputStr('')
  }

  return (
    <aside className="agent-panel soft-card" aria-label="Agent 对话区">
      <div className="panel-head">
        <div>
          <p className="eyebrow">Agent</p>
          <h2>结构迁移对话</h2>
          <p>记录任务、补充约束，并展示真实接口状态。</p>
        </div>
        <span className="status" id="agentState" data-busy={isBusy}>{status}</span>
      </div>

      {error ? (
        <div className="panel-alert" role="alert">
          <strong>执行失败</strong>
          <span>{error}</span>
        </div>
      ) : null}

      <div className="chat" id="chatBody" aria-live="polite">
        {messages.map((msg) => (
          <div key={msg.id} className="message" data-role={msg.role}>
            <div className="message-head">
              <span>{msg.label}</span>
            </div>
            <p>{msg.body}</p>
            {msg.steps?.length ? (
              <div className="agent-steps">
                {msg.steps.map((step) => (
                  <div key={`${msg.id}-${step.title}`} className="agent-step">
                    <span className="step-mark">✓</span>
                    <div>
                      <span>{step.title}</span><br />
                      <span className="step-time">{step.time}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>

      <form className="composer" id="chatForm" onSubmit={handleSubmit}>
        <textarea
          id="chatInput"
          aria-label="继续向 Agent 输入指令"
          placeholder="例如：缩短 Hook，保留参考片字幕节奏，不要使用纯 UI B-roll。"
          value={inputStr}
          onChange={(event) => setInputStr(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              handleSubmit(event)
            }
          }}
        />
        <button className="btn btn-primary" type="submit">记录</button>
      </form>
    </aside>
  )
}
```

- [ ] **Step 2: Extend `WorkPanel` props and empty states**

Replace the props and render logic in `WorkPanel.tsx` with this structure:

```tsx
import React, { useRef, useState } from 'react'

interface StructureNode {
  key: string
  time: string
  label: string
  desc: string
  score: string
}

interface SampleMeta {
  shotCount?: number
  targetAssetCount?: number
}

interface WorkPanelProps {
  stageTitle: string
  stageDescription: string
  workClock: string
  hasVideo: boolean
  videoUrl?: string
  videoDuration: string
  videoName: string
  sampleMeta: SampleMeta
  nodes: StructureNode[]
  activeNodeKey: string
  onNodeClick: (key: string) => void
  onUploadVideo: (file: File) => void
  onGenerate: () => void
  isBusy: boolean
  status: string
  error: string
  progressItems: { label: string; v1: string; v2: string; percent: number }[]
  mappingItems: { label: string; score: string; percent: number }[]
}

export default function WorkPanel({
  stageTitle,
  stageDescription,
  workClock,
  hasVideo,
  videoUrl,
  videoDuration,
  videoName,
  sampleMeta,
  nodes,
  activeNodeKey,
  onNodeClick,
  onUploadVideo,
  onGenerate,
  isBusy,
  status,
  error,
  progressItems,
  mappingItems,
}: WorkPanelProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [currentTimecode, setCurrentTimecode] = useState('00:00')

  const handleTimeUpdate = () => {
    if (!videoRef.current) return
    const ct = videoRef.current.currentTime
    const m = Math.floor(ct / 60).toString().padStart(2, '0')
    const s = Math.floor(ct % 60).toString().padStart(2, '0')
    setCurrentTimecode(`${m}:${s}`)
  }

  return (
    <section className="work-panel soft-card" aria-label="当前工作情况">
      <div className="panel-head">
        <div>
          <p className="eyebrow">Workspace</p>
          <h2 id="stageTitle">{stageTitle}</h2>
          <p id="stageDescription">{stageDescription}</p>
        </div>
        <span className="status" id="workClock">{workClock}</span>
      </div>

      {error ? (
        <div className="panel-alert panel-alert-inline" role="alert">
          <strong>需要处理</strong>
          <span>{error}</span>
        </div>
      ) : null}

      <div className="work-body">
        <article className="video-block soft-card" aria-label="输入视频">
          <div className="video-player" id="videoPlayer" data-has-video={hasVideo}>
            <video
              id="inputVideo"
              controls
              playsInline
              preload="metadata"
              ref={videoRef}
              src={videoUrl}
              onTimeUpdate={handleTimeUpdate}
            />
            <div className="video-placeholder" aria-hidden={hasVideo ? 'true' : 'false'}>
              <div className="video-label">
                <span>{hasVideo ? 'INPUT VIDEO' : 'UPLOAD VIDEO'}</span>
                <span>16:9 preview</span>
              </div>
              <div className="play" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                  <path d="M8 5l11 7-11 7z" />
                </svg>
              </div>
              <div className="video-time">
                <div className="timebar"><span /></div>
                <span id="videoTimecode">{currentTimecode} / {videoDuration}</span>
              </div>
            </div>
          </div>

          <div className="video-side">
            <div>
              <p className="eyebrow">Reference source</p>
              <h3 id="videoName" title={videoName}>{videoName}</h3>
              <p id="videoDescription">
                {hasVideo ? '样例视频已进入工作台，可生成真实结构拆解。' : '上传参考视频后，这里会显示真实视频和基础解析信息。'}
              </p>
            </div>
            <div className="facts">
              <div className="fact"><span>参考时长</span><strong id="videoDuration">{videoDuration}</strong></div>
              <div className="fact"><span>结构节点</span><strong>{nodes.length || '-'}</strong></div>
              <div className="fact"><span>镜头数量</span><strong>{sampleMeta.shotCount ?? '-'}</strong></div>
              <div className="fact"><span>素材映射</span><strong>{sampleMeta.targetAssetCount ?? '-'}</strong></div>
            </div>
            <div className="video-actions">
              <label className="btn upload">
                上传视频
                <input
                  id="videoUpload"
                  type="file"
                  accept="video/*"
                  aria-label="上传输入视频"
                  onChange={(event) => {
                    if (event.target.files?.[0]) onUploadVideo(event.target.files[0])
                  }}
                />
              </label>
              <button className="btn btn-primary" id="generateDemo" type="button" onClick={onGenerate} disabled={isBusy}>
                {isBusy ? status : '生成结构'}
              </button>
            </div>
          </div>
        </article>

        <div className="structure-card soft-card">
          <div className="structure-header">
            <div>
              <p className="eyebrow">Structure breakdown</p>
              <h3>参考视频结构</h3>
            </div>
            <span id="selectedNode">{activeNodeKey || '等待生成'}</span>
          </div>
          {nodes.length ? (
            <div className="structure-list" id="structureList">
              {nodes.map((node) => (
                <button
                  key={node.key}
                  type="button"
                  className="structure-node"
                  data-active={activeNodeKey === node.key}
                  onClick={() => onNodeClick(node.key)}
                >
                  <div className="node-time">{node.time}</div>
                  <div className="node-copy">
                    <strong>{node.label}</strong>
                    <span>{node.desc}</span>
                  </div>
                  <div className="node-score">{node.score}</div>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <strong>还没有结构结果</strong>
              <span>上传样例并点击“生成结构”后，这里会显示真实节点。</span>
            </div>
          )}
        </div>

        <div className="lower-grid">
          <article className="quiet-card soft-card">
            <p className="eyebrow">Agent progress</p>
            <h3>当前执行</h3>
            <div id="progressList">
              {progressItems.map((item) => (
                <div key={item.label} className="progress-row">
                  <div className="progress-meta">
                    <span>{item.label}</span>
                    <span>{item.v2 ? `${item.v1} / ${item.v2}` : item.v1}</span>
                  </div>
                  <div className="bar"><span style={{ '--value': `${item.percent}%` } as React.CSSProperties} /></div>
                </div>
              ))}
            </div>
          </article>

          <article className="quiet-card soft-card">
            <p className="eyebrow">Material mapping</p>
            <h3>目标素材映射</h3>
            {mappingItems.length ? (
              <div id="mappingGrid">
                {mappingItems.map((item) => (
                  <div key={`${item.label}-${item.score}`} className="mapping-item">
                    <strong>
                      <span>{item.label}</span>
                      <span>{item.score}</span>
                    </strong>
                    <div className="bar"><span style={{ '--value': `${item.percent}%` } as React.CSSProperties} /></div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <strong>还没有素材映射</strong>
                <span>生成迁移方案后，这里会显示每个结构节点需要的目标素材。</span>
              </div>
            )}
          </article>
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 3: Run build**

Run:

```bash
cd apps/web
npm run build
```

Expected: build passes. If TypeScript reports a missing prop, update the call site in `WorkspaceView.tsx` to match the exact prop names from Step 2.

- [ ] **Step 4: Commit Tasks 3 and 4 together if Task 3 was not committed**

```bash
git add apps/web/src/components/Views/WorkspaceView.tsx apps/web/src/components/Workspace/WorkflowNav.tsx apps/web/src/components/Workspace/AgentActionPanel.tsx apps/web/src/components/Workspace/WorkPanel.tsx
git commit -m "feat: connect workspace panels to real state"
```

---

### Task 5: Apply Workbench Visual System And Mobile Fixes

**Files:**
- Modify: `apps/web/src/app/globals.css`

- [ ] **Step 1: Replace visual tokens**

Update `:root` values to reduce beige/glass styling and use a quieter workbench palette:

```css
:root {
  --bg: #f6f7f8;
  --surface: #ffffff;
  --surface-2: #f0f3f5;
  --surface-3: #e4e9ed;
  --fg: #171a1f;
  --fg-2: #303640;
  --muted: #66707c;
  --meta: #8b96a3;
  --border: #dde3e8;
  --border-strong: #c8d1d9;
  --accent: #16756f;
  --accent-2: #2e8fcb;
  --accent-on: #ffffff;
  --success: #23845f;
  --warn: #a96d1f;
  --danger: #b42318;
  --mesh-1: #eef9f7;
  --mesh-2: #edf4ff;
  --mesh-3: #fff5e8;
  --mesh-4: #eef1f4;

  --font-display: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", system-ui, sans-serif;
  --font-body: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif;
  --font-mono: "SF Mono", ui-monospace, Menlo, Monaco, Consolas, monospace;

  --text-xs: 11px;
  --text-sm: 13px;
  --text-base: 15px;
  --text-lg: 17px;
  --text-xl: 20px;
  --text-2xl: 26px;
  --text-3xl: 36px;
  --text-4xl: 52px;

  --leading-body: 1.56;
  --leading-tight: 1.08;
  --tracking-display: 0;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;

  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 10px;
  --radius-xl: 12px;
  --radius-pill: 9999px;

  --container-max: 1520px;
  --gutter: clamp(16px, 2.6vw, 32px);
  --focus-ring: 0 0 0 3px color-mix(in oklab, var(--accent-2), transparent 68%);
  --shadow-soft: 0 14px 42px color-mix(in oklab, var(--fg), transparent 92%);
  --shadow-inner: inset 0 1px 0 color-mix(in oklab, var(--surface), transparent 12%);
  --spring: cubic-bezier(0.19, 1, 0.22, 1);
}
```

- [ ] **Step 2: Remove heavy decorative page background**

Change `body` background to:

```css
body {
  margin: 0;
  min-height: 100vh;
  background:
    linear-gradient(180deg, color-mix(in oklab, var(--mesh-1), transparent 12%), transparent 360px),
    var(--bg);
  color: var(--fg);
  font-family: var(--font-body);
  font-size: var(--text-base);
  line-height: var(--leading-body);
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}
body::before {
  content: none;
}
```

- [ ] **Step 3: Add empty/error/status utility styles**

Add near panel styles:

```css
.panel-alert {
  position: relative;
  z-index: 1;
  margin: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border: 1px solid color-mix(in oklab, var(--danger), transparent 70%);
  border-radius: var(--radius-md);
  background: color-mix(in oklab, var(--danger), var(--surface) 92%);
  color: var(--danger);
  display: grid;
  gap: var(--space-1);
  font-size: var(--text-sm);
}
.panel-alert strong {
  color: var(--danger);
}
.panel-alert-inline {
  margin-bottom: 0;
}
.status[data-busy="true"] {
  border-color: color-mix(in oklab, var(--accent), transparent 55%);
  color: var(--accent);
}
.step-time {
  color: var(--muted);
  font-size: 11px;
  font-family: var(--font-mono);
}
.empty-state {
  min-height: 120px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-md);
  background: color-mix(in oklab, var(--surface-2), var(--surface) 38%);
  display: grid;
  place-content: center;
  justify-items: center;
  gap: var(--space-2);
  padding: var(--space-5);
  text-align: center;
  color: var(--muted);
}
.empty-state strong {
  color: var(--fg);
}
```

- [ ] **Step 4: Fix long file names and mobile overflow**

Add or update these rules:

```css
.video-side h3,
.mapping-item strong span,
.node-copy strong,
.node-copy span {
  min-width: 0;
  overflow-wrap: anywhere;
}
.video-side h3 {
  max-width: 100%;
}
.video-player,
.video-side {
  max-width: 100%;
}
@media (max-width: 720px) {
  :root { --gutter: 14px; }
  .topbar-inner {
    align-items: flex-start;
    flex-direction: column;
  }
  .home[data-active="true"] {
    min-height: auto;
    place-items: stretch;
  }
  .home h1 {
    max-width: 100%;
    font-size: 38px;
  }
  .examples,
  .workflow-steps,
  .prompt-footer,
  .composer,
  .structure-node,
  .video-block,
  .lower-grid {
    grid-template-columns: 1fr;
  }
  .prompt-footer {
    align-items: stretch;
    display: grid;
  }
  .prompt-actions,
  .prompt-actions .btn,
  .composer .btn,
  .video-actions .btn,
  .video-actions .upload {
    width: 100%;
  }
  .workspace[data-active="true"] {
    padding: var(--space-3) var(--gutter) var(--space-6);
  }
  .workspace-shell,
  .work-body {
    gap: var(--space-3);
  }
  .video-block {
    padding: var(--space-2);
  }
  .video-side {
    padding: 0 var(--space-3) var(--space-3);
  }
  .panel-head,
  .work-body,
  .chat,
  .composer,
  .structure-card,
  .quiet-card {
    padding: var(--space-4);
  }
  .panel-head,
  .structure-header {
    align-items: flex-start;
    flex-direction: column;
  }
  .message {
    max-width: 100%;
  }
  .prompt-panel textarea {
    padding: var(--space-6);
  }
}
```

- [ ] **Step 5: Run build and mobile smoke manually**

Run:

```bash
cd apps/web
npm run build
```

Expected: build passes. Then start dev server:

```bash
cd apps/web
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Expected: local app starts. Open `http://127.0.0.1:3000` at 390px width and confirm no horizontal scrolling.

- [ ] **Step 6: Commit Task 5**

```bash
git add apps/web/src/app/globals.css
git commit -m "style: align workspace visual system"
```

---

### Task 6: Add Static Check And Browser Smoke Script

**Files:**
- Modify: `apps/web/package.json`
- Create: `apps/web/scripts/check-workspace-shell.mjs`

- [ ] **Step 1: Replace invalid lint script**

Change `apps/web/package.json` scripts to:

```json
"scripts": {
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "typecheck": "tsc --noEmit",
  "lint": "npm run typecheck",
  "check:workspace": "node scripts/check-workspace-shell.mjs"
}
```

- [ ] **Step 2: Create workspace shell browser check**

Create `apps/web/scripts/check-workspace-shell.mjs`:

```js
const playwrightModule =
  process.env.PLAYWRIGHT_MODULE ||
  "file:///Users/linkwind/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs";

const { chromium } = await import(playwrightModule);

const baseUrl = process.env.BASE_URL || "http://127.0.0.1:3000";
const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const browser = await chromium.launch({
  headless: true,
  executablePath: chromePath,
});

try {
  const badHomepageRequests = [];
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  page.on("response", (response) => {
    const url = response.url();
    if ((url.includes("/api/runs") || url.includes("/api/templates")) && response.status() >= 400) {
      badHomepageRequests.push(`${response.status()} ${url}`);
    }
  });

  await page.goto(baseUrl, { waitUntil: "networkidle" });
  const homeText = await page.locator("body").innerText();
  if (!homeText.includes("ReelStruct")) {
    throw new Error("homepage is missing ReelStruct brand");
  }
  if (homeText.includes("CutFlow AI")) {
    throw new Error("homepage still shows CutFlow AI brand");
  }
  if (badHomepageRequests.length > 0) {
    throw new Error(`homepage made failing run/template requests: ${badHomepageRequests.join(", ")}`);
  }

  await page.getByRole("button", { name: "进入工作台" }).click();
  await page.waitForTimeout(500);
  const workspaceText = await page.locator("body").innerText();
  if (!workspaceText.includes("还没有结构结果")) {
    throw new Error("workspace empty structure state is missing");
  }
  if (workspaceText.includes("视觉反差 Hook")) {
    throw new Error("workspace still shows mock structure node before generation");
  }

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true });
  await mobile.goto(baseUrl, { waitUntil: "networkidle" });
  await mobile.getByRole("button", { name: "进入工作台" }).click();
  await mobile.waitForTimeout(500);
  const metrics = await mobile.evaluate(() => ({
    width: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  if (metrics.scrollWidth > metrics.width + 1) {
    throw new Error(`mobile viewport overflows horizontally: ${metrics.scrollWidth} > ${metrics.width}`);
  }

  console.log("WORKSPACE_SHELL_OK=1");
} finally {
  await browser.close();
}
```

- [ ] **Step 3: Run checks**

Run:

```bash
cd apps/web
npm run lint
npm run build
```

Expected:

```text
> @reelstruct/web@0.1.0 lint
> npm run typecheck
```

and both commands exit 0.

- [ ] **Step 4: Run browser smoke check with dev server**

Start dev server in one terminal:

```bash
cd apps/web
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Run in another terminal:

```bash
cd apps/web
npm run check:workspace
```

Expected:

```text
WORKSPACE_SHELL_OK=1
```

- [ ] **Step 5: Commit Task 6**

```bash
git add apps/web/package.json apps/web/scripts/check-workspace-shell.mjs
git commit -m "test: add workspace shell checks"
```

---

## Final Verification

- [ ] **Step 1: Run full frontend verification**

```bash
cd apps/web
npm run lint
npm run build
```

Expected: both pass with exit code 0.

- [ ] **Step 2: Run browser smoke check**

With dev server running on `127.0.0.1:3000`:

```bash
cd apps/web
npm run check:workspace
```

Expected:

```text
WORKSPACE_SHELL_OK=1
```

- [ ] **Step 3: Manual browser review**

Check these states in the browser:

- Homepage shows `ReelStruct`, not `CutFlow AI`.
- Homepage does not show fake video preview output.
- Entering workspace shows upload guidance and empty structure state.
- Before generation, workspace does not show `视觉反差 Hook`.
- 390px mobile viewport has no horizontal scroll.
- If the API backend is unavailable, upload/generate errors are visible in the UI.

- [ ] **Step 4: Final commit if any verification fixes were needed**

```bash
git status --short
git add apps/web/src/components apps/web/src/app/globals.css apps/web/package.json apps/web/scripts/check-workspace-shell.mjs
git commit -m "fix: complete workspace integration verification"
```

Only run this commit if verification required additional fixes after the task commits.

---

## Self-Review

Spec coverage:

- Brand unification: Task 2.
- Homepage no run/template fetches: Task 1 and Task 6.
- Real upload and generation: Task 3 and Task 4.
- No mock result panels: Task 3, Task 4, Task 6.
- Empty/loading/error states: Task 4 and Task 5.
- Mobile overflow: Task 5 and Task 6.
- Static check replacement: Task 6.

Placeholder scan: no placeholder requirements remain.

Type consistency:

- `WorkflowNav` uses `Stage = 'sample' | 'structure' | 'output'`.
- `WorkspaceView` passes `onGenerate`, `sampleMeta`, `isBusy`, `status`, and `error`.
- `WorkPanel` receives the same prop names.
- `AgentActionPanel` receives `status`, `error`, and `isBusy`.
