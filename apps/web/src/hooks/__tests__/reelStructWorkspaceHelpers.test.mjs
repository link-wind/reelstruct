import test from "node:test";
import assert from "node:assert/strict";

test("mergeShotEvidenceGraphs merges shot and analysis unit evidence without duplicates", async () => {
  const { mergeShotEvidenceGraphs } = await import("../reelStructWorkspaceShared.ts");

  const current = {
    shots: [
      {
        shot: { index: 1, start: 0, end: 1.2, duration: 1.2 },
        frames: [{ shot_index: 1, frame_index: 0, time: 0.1, public_url: "/a.jpg", role: "start" }],
        ocr_texts: [{ shot_index: 1, frame_index: 0, frame_time: 0.1, text: "咖啡" }],
        transcript_texts: [],
        understanding: { visual_summary: "开场特写", text_summary: "", creative_function_hint: "", confidence: 0.8, warnings: [] },
      },
    ],
    analysis_units: [
      {
        unit_id: "legacy",
        start: 0,
        end: 1.2,
        duration: 1.2,
        shot_indices: [1],
        representative_frames: [{ shot_index: 1, frame_index: 0, time: 0.1, public_url: "/a.jpg", role: "start" }],
        ocr_texts: [],
        transcript_texts: [],
        understanding: { unit_id: "legacy", visual_summary: "开场特写", text_summary: "", creative_function_hint: "", confidence: 0.8, warnings: [] },
      },
    ],
    relations: [],
    warnings: ["base warning"],
  };

  const next = {
    shots: [
      {
        shot: { index: 1, start: 0, end: 1.2, duration: 1.2 },
        frames: [
          { shot_index: 1, frame_index: 0, time: 0.1, public_url: "/a.jpg", role: "start" },
          { shot_index: 1, frame_index: 1, time: 0.6, public_url: "/b.jpg", role: "middle" },
        ],
        ocr_texts: [{ shot_index: 1, frame_index: 0, frame_time: 0.1, text: "咖啡" }],
        transcript_texts: [{ shot_index: 1, source_start: 0, source_end: 1, text: "欢迎光临" }],
        understanding: { visual_summary: "", text_summary: "欢迎光临", creative_function_hint: "", confidence: 0.9, warnings: [] },
      },
    ],
    analysis_units: [
      {
        unit_id: "new",
        start: 0,
        end: 1.2,
        duration: 1.2,
        shot_indices: [1],
        representative_frames: [{ shot_index: 1, frame_index: 1, time: 0.6, public_url: "/b.jpg", role: "middle" }],
        ocr_texts: [],
        transcript_texts: [{ shot_index: 1, source_start: 0, source_end: 1, text: "欢迎光临" }],
        understanding: { unit_id: "new", visual_summary: "", text_summary: "欢迎光临", creative_function_hint: "", confidence: 0.9, warnings: [] },
      },
    ],
    relations: [{ from_shot: 1, to_shot: 2, relation_type: "contrast", relation_summary: "", semantic_shift: "", confidence: 0.7 }],
    warnings: ["base warning", "next warning"],
  };

  const merged = mergeShotEvidenceGraphs(current, next);

  assert.equal(merged.shots.length, 1);
  assert.equal(merged.shots[0].frames.length, 2);
  assert.equal(merged.shots[0].ocr_texts.length, 1);
  assert.equal(merged.shots[0].transcript_texts.length, 1);
  assert.equal(merged.analysis_units.length, 1);
  assert.equal(merged.analysis_units[0].unit_id, "unit_1");
  assert.equal(merged.analysis_units[0].representative_frames.length, 2);
  assert.equal(merged.analysis_units[0].transcript_texts.length, 1);
  assert.deepEqual(merged.warnings, ["base warning", "next warning"]);
  assert.equal(merged.relations.length, 1);
});

test("buildMaterialRequestSheetText keeps status and selected supplement", async () => {
  const { buildMaterialRequestSheetText } = await import("../reelStructWorkspaceShared.ts");

  const text = buildMaterialRequestSheetText(
    [
      {
        task: { slot_id: "hook", status: "待补拍" },
        slot: {
          id: "hook",
          label: "开头钩子",
          required_asset: "开头吸引镜头",
        },
        gap: {
          suggested_asset_type: "开头吸引镜头",
          missing_asset: "开头吸引镜头",
          fill_strategy: "先补拍",
          primary_supplement: "包装补全",
          supplement_options: [
            { method: "包装补全", action: "补字幕", evidence: [] },
          ],
          suggested_shots: ["开头特写"],
          pickup_checklist: ["补字幕"],
        },
      },
    ],
    { hook: "已拍" },
    { hook: "包装补全" },
  );

  assert.match(text, /素材需求单/);
  assert.match(text, /开头钩子/);
  assert.match(text, /当前状态：已拍/);
  assert.match(text, /已选补全：包装补全-补字幕/);
});
