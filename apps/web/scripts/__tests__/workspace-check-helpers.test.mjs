import test from "node:test";
import assert from "node:assert/strict";
import { hasVisibleResultSuccess } from "../workspace-check-helpers.mjs";

test("hasVisibleResultSuccess treats result video as success even when stage strip is stale", () => {
  const ok = hasVisibleResultSuccess({
    bodyText: "结果验证\n任务编号：run_123\n下载结果包",
    stageStripText: "结构刷新\n正在生成结构预览\n素材补全\n等待执行",
    hasResultVideo: true,
    hasDownloadButton: true,
    resultStatusText: "run_123",
  });

  assert.equal(ok, true);
});

test("hasVisibleResultSuccess stays false before result output is visible", () => {
  const ok = hasVisibleResultSuccess({
    bodyText: "结果验证\n还没有成片样片",
    stageStripText: "结果生成\n等待执行",
    hasResultVideo: false,
    hasDownloadButton: false,
    resultStatusText: "等待生成",
  });

  assert.equal(ok, false);
});

test("hasVisibleResultSuccess stays false when stage strip looks advanced but result panel is still empty", () => {
  const ok = hasVisibleResultSuccess({
    bodyText: "结果验证\n还没有成片样片",
    stageStripText: "结构分析\n结构预览已生成\n结果生成\n等待执行",
    hasResultVideo: false,
    hasDownloadButton: false,
    resultStatusText: "等待生成",
  });

  assert.equal(ok, false);
});
