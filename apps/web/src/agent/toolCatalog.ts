import type { ToolConfirmationKind } from "./types"

export type AgentToolStage = "structure" | "materials" | "output"
export type AgentToolConfirmationKind = ToolConfirmationKind | ""

export type AgentToolCatalogItem = {
  name: string
  title: string
  stage: AgentToolStage
  confirmationKind: AgentToolConfirmationKind
}

export const toolCatalog: AgentToolCatalogItem[] = [
  {
    name: "analyze_structure",
    title: "分析结构",
    stage: "structure",
    confirmationKind: "",
  },
  {
    name: "run_ocr",
    title: "执行 OCR",
    stage: "structure",
    confirmationKind: "run_ocr",
  },
  {
    name: "run_asr",
    title: "执行 ASR",
    stage: "structure",
    confirmationKind: "run_asr",
  },
  {
    name: "complete_materials",
    title: "补全素材",
    stage: "materials",
    confirmationKind: "material_strategy",
  },
  {
    name: "generate_result",
    title: "生成结果",
    stage: "output",
    confirmationKind: "generate_result",
  },
]
