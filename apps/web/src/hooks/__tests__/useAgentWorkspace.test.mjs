import test from "node:test";
import assert from "node:assert/strict";

const { shouldAutoPlanAfterSampleUpload } = await import("../agentWorkspaceGate.mjs");

test("shouldAutoPlanAfterSampleUpload blocks planning before sample upload", () => {
  assert.equal(
    shouldAutoPlanAfterSampleUpload({
      hasSampleUpload: false,
      prompt: "分析这个视频",
      agentStatus: "idle",
      hasPlan: false,
    }),
    false,
  );
});

test("shouldAutoPlanAfterSampleUpload allows planning only after upload with an idle agent", () => {
  assert.equal(
    shouldAutoPlanAfterSampleUpload({
      hasSampleUpload: true,
      prompt: "分析这个视频",
      agentStatus: "idle",
      hasPlan: false,
    }),
    true,
  );
});

test("shouldAutoPlanAfterSampleUpload avoids duplicate planning after a plan exists", () => {
  assert.equal(
    shouldAutoPlanAfterSampleUpload({
      hasSampleUpload: true,
      prompt: "分析这个视频",
      agentStatus: "awaiting_start_confirm",
      hasPlan: true,
    }),
    false,
  );
});
