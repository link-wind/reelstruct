import test from "node:test";
import assert from "node:assert/strict";

test("runPlannedWorkspaceFlow executes analyze_structure before generate_result", async () => {
  const { runPlannedWorkspaceFlow } = await import("../workspaceExecutionFlow.mjs");

  const stages = [];
  const patches = [];
  const messages = [];
  const preview = { preview_id: "preview-1" };
  const run = { run_id: "run-1" };

  await runPlannedWorkspaceFlow({
    stepNames: ["analyze_structure", "generate_result"],
    preview: null,
    sample: { title: "样例" },
    content: { topic: "目标" },
    sampleUpload: { local_path: "/tmp/sample.mp4" },
    manualEvidenceGraph: null,
    outputVariant: "standard",
    setCurrentStage: (stage) => stages.push(stage),
    addMessage: (message) => messages.push(message.content),
    patchRuntime: (payload) => patches.push(payload),
    generateStructurePreview: async () => preview,
    generateOcrEvidence: async () => false,
    generateAsrEvidence: async () => false,
    requestAgentToolExecution: async ({ tool_name }) => {
      if (tool_name === "generate_result") return { data: { run } };
      throw new Error(`unexpected tool: ${tool_name}`);
    },
    applyPreviewResponse: () => {
      throw new Error("should not apply preview response in this path");
    },
    applyDemoRunResponse: (payload) => {
      assert.equal(payload, run);
    },
    runDemo: async () => {
      throw new Error("should not fall back to runDemo when preview exists");
    },
  });

  assert.deepEqual(stages, ["structure", "output"]);
  assert.equal(messages[0], "开始分析结构。");
  assert.equal(messages.at(-1), "结果已生成，可以开始检查输出。");
  assert.equal(patches[0].agentStatus, "running");
  assert.equal(patches.at(-1).agentStatus, "completed");
  assert.ok(patches.some((payload) => payload.currentStep === "analyze_structure" && payload.currentStepStatus === "completed"));
  assert.ok(patches.some((payload) => payload.currentStep === "generate_result" && payload.currentStepStatus === "completed"));
});
