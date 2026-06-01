'use client'

import { useEffect, useMemo } from 'react'
import { apiUrl, buildMaterialRequestSheetText, normalizeUserSlotAsset, type MaterialTaskStatus } from './reelStructWorkspaceShared'

type MaterialWorkspaceDeps = {
  preview: any | null
  content: any
  setContent: (value: any) => void
  selectedGapIds: string[]
  setSelectedGapIds: (value: string[] | ((current: string[]) => string[])) => void
  requestSheetIds: string[]
  setRequestSheetIds: (value: string[] | ((current: string[]) => string[])) => void
  requestSheetStatus: Record<string, MaterialTaskStatus>
  setRequestSheetStatus: (value: Record<string, MaterialTaskStatus> | ((current: Record<string, MaterialTaskStatus>) => Record<string, MaterialTaskStatus>)) => void
  requestSheetFeedback: string
  setRequestSheetFeedback: (value: string) => void
  supplementSelection: Record<string, string>
  setSupplementSelection: (value: Record<string, string> | ((current: Record<string, string>) => Record<string, string>)) => void
  setStatus: (value: string) => void
  setError: (value: string) => void
}

export function useMaterialWorkspace(deps: MaterialWorkspaceDeps) {
  useEffect(() => {
    const nextGapIds = (deps.preview?.transfer_plan?.gaps || []).map((gap: any) => gap.slot_id)
    const nextRequestSheet = deps.preview?.transfer_plan?.material_request_sheet || []
    deps.setSelectedGapIds(nextGapIds)
    deps.setRequestSheetIds(nextRequestSheet.map((item: any) => item.slot_id))
    deps.setRequestSheetStatus(Object.fromEntries(nextRequestSheet.map((item: any) => [item.slot_id, item.status])))
    deps.setSupplementSelection((current) =>
      Object.fromEntries(Object.entries(current).filter(([slotId]) => nextGapIds.includes(slotId))),
    )
    deps.setRequestSheetFeedback('')
  }, [deps.preview])

  useEffect(() => {
    if (!deps.requestSheetFeedback) return
    const timer = window.setTimeout(() => deps.setRequestSheetFeedback(''), 1800)
    return () => window.clearTimeout(timer)
  }, [deps.requestSheetFeedback])

  const gapLookup = useMemo(() => {
    return new Map((deps.preview?.transfer_plan?.gaps || []).map((gap: any) => [gap.slot_id, gap]))
  }, [deps.preview])

  const selectedGaps = useMemo(() => {
    return (deps.preview?.transfer_plan?.gaps || []).filter((gap: any) => deps.selectedGapIds.includes(gap.slot_id))
  }, [deps.preview, deps.selectedGapIds])

  const requestSheetItems = useMemo(() => {
    const slotLookup = new Map((deps.preview?.template?.script_pattern || []).map((slot: any) => [slot.id, slot]))
    const serverTaskLookup = new Map((deps.preview?.transfer_plan?.material_request_sheet || []).map((task: any) => [task.slot_id, task]))
    return deps.requestSheetIds
      .map((slotId) => {
        const slot = slotLookup.get(slotId)
        return slot
          ? {
              task: serverTaskLookup.get(slotId) || {
                slot_id: slotId,
                status: deps.requestSheetStatus[slotId] ?? '待补拍',
              },
              slot,
              gap: gapLookup.get(slotId),
            }
          : null
      })
      .filter(Boolean)
  }, [gapLookup, deps.preview, deps.requestSheetIds, deps.requestSheetStatus])

  const requestSheetText = useMemo(() => {
    return buildMaterialRequestSheetText(requestSheetItems, deps.requestSheetStatus, deps.supplementSelection)
  }, [requestSheetItems, deps.requestSheetStatus, deps.supplementSelection])

  const uploadedAssetLookup = useMemo(() => {
    return new Map((deps.content.uploaded_assets || []).map((asset: any) => [asset.slot_id, asset]))
  }, [deps.content.uploaded_assets])

  const uploadMaterialAsset = async (slotId: string, file: File | null) => {
    if (!file) return

    deps.setError('')
    deps.setStatus('正在上传补拍素材')
    const formData = new FormData()
    formData.append('slot_id', slotId)
    formData.append('file', file)

    try {
      const response = await fetch(apiUrl('/api/materials/upload'), {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        throw new Error(`上传补拍素材失败：${response.status}`)
      }
      const uploadedAsset = normalizeUserSlotAsset((await response.json()) as any)
      deps.setContent((current: any) => ({
        ...current,
        uploaded_assets: [
          ...current.uploaded_assets.filter((asset: any) => asset.slot_id !== uploadedAsset.slot_id),
          uploadedAsset,
        ],
      }))
      deps.setRequestSheetStatus((current) => ({
        ...current,
        [slotId]: '已拍',
      }))
      deps.setRequestSheetFeedback('补拍素材已上传')
      deps.setStatus('补拍素材已绑定')
    } catch (caught) {
      deps.setStatus('上传失败')
      deps.setError(caught instanceof Error ? caught.message : '上传补拍素材失败')
    }
  }

  const generateMaterialEvidence = async (slotId: string) => {
    const asset = deps.content.uploaded_assets.find((item: any) => item.slot_id === slotId)
    if (!asset) {
      deps.setError('请先上传素材')
      return
    }

    deps.setError('')
    deps.setStatus('正在生成素材证据')
    try {
      const response = await fetch(apiUrl('/api/materials/evidence'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(asset),
      })
      if (!response.ok) {
        throw new Error(`生成素材证据失败：${response.status}`)
      }
      const enrichedAsset = normalizeUserSlotAsset((await response.json()) as any)
      deps.setContent((current: any) => ({
        ...current,
        uploaded_assets: [
          ...current.uploaded_assets.filter((item: any) => item.slot_id !== enrichedAsset.slot_id),
          enrichedAsset,
        ],
      }))
      deps.setStatus('素材证据已生成')
    } catch (caught) {
      deps.setStatus('生成素材证据失败')
      deps.setError(caught instanceof Error ? caught.message : '生成素材证据失败')
    }
  }

  const addSelectedGapsToRequestSheet = () => {
    deps.setRequestSheetIds((current) => {
      const nextIds = new Set([...current, ...deps.selectedGapIds])
      return (deps.preview?.transfer_plan?.gaps || [])
        .map((gap: any) => gap.slot_id)
        .filter((slotId: string) => nextIds.has(slotId))
    })
    deps.setRequestSheetStatus((current) => {
      const next = { ...current }
      deps.selectedGapIds.forEach((slotId) => {
        next[slotId] = next[slotId] ?? '待补拍'
      })
      return next
    })
    deps.setRequestSheetFeedback('')
  }

  const updateMaterialTaskStatus = (slotId: string, nextStatus: MaterialTaskStatus) => {
    deps.setRequestSheetStatus((current) => ({
      ...current,
      [slotId]: nextStatus,
    }))
    deps.setRequestSheetFeedback('')
  }

  const removeFromRequestSheet = (slotId: string) => {
    deps.setRequestSheetIds((current) => current.filter((item) => item !== slotId))
    deps.setRequestSheetStatus((current) => {
      const next = { ...current }
      delete next[slotId]
      return next
    })
    deps.setRequestSheetFeedback('已移出任务')
  }

  const clearRequestSheet = () => {
    deps.setRequestSheetIds([])
    deps.setRequestSheetStatus({})
    deps.setSupplementSelection({})
    deps.setRequestSheetFeedback('需求单已清空')
  }

  const selectSupplementOption = (slotId: string, method: string) => {
    deps.setSupplementSelection((current) => ({
      ...current,
      [slotId]: method,
    }))
    deps.setRequestSheetFeedback('补全方案已选择')
  }

  const copyRequestSheet = async () => {
    if (!requestSheetText) return
    try {
      await navigator.clipboard.writeText(requestSheetText)
      deps.setRequestSheetFeedback('需求单已复制')
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '复制失败')
    }
  }

  const exportRequestSheet = () => {
    if (!requestSheetText) return
    const blob = new Blob([requestSheetText], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'material-request-sheet.txt'
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    deps.setRequestSheetFeedback('需求单已导出')
  }

  return {
    selectedGapIds: deps.selectedGapIds,
    setSelectedGapIds: deps.setSelectedGapIds,
    requestSheetIds: deps.requestSheetIds,
    setRequestSheetIds: deps.setRequestSheetIds,
    requestSheetStatus: deps.requestSheetStatus,
    setRequestSheetStatus: deps.setRequestSheetStatus,
    requestSheetFeedback: deps.requestSheetFeedback,
    setRequestSheetFeedback: deps.setRequestSheetFeedback,
    supplementSelection: deps.supplementSelection,
    selectSupplementOption,
    gapLookup,
    selectedGaps,
    requestSheetItems,
    requestSheetText,
    uploadedAssetLookup,
    uploadMaterialAsset,
    generateMaterialEvidence,
    addSelectedGapsToRequestSheet,
    updateMaterialTaskStatus,
    removeFromRequestSheet,
    clearRequestSheet,
    copyRequestSheet,
    exportRequestSheet,
  }
}
