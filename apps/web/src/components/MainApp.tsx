'use client'

import React, { useState } from 'react'
import Topbar from './Layout/Topbar'
import HomeView from './Views/HomeView'
import WorkspaceView from './Views/WorkspaceView'
import { useReelStruct } from '../hooks/useReelStruct'
import { useAgentWorkspace } from '../hooks/useAgentWorkspace'

type ViewMode = 'home' | 'workspace'

function WorkspaceRoute({ taskText }: { taskText: string }) {
  const reelStruct = useReelStruct()
  const agentWorkspace = useAgentWorkspace(taskText)

  return (
    <WorkspaceView
      taskText={agentWorkspace.state.currentPlan.prompt || taskText}
      reelStruct={reelStruct}
    />
  )
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
