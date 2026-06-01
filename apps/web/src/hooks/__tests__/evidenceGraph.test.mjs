import test from "node:test";
import assert from "node:assert/strict";

const { shotEvidenceGraphHasTextEvidence } = await import("../evidenceGraph.ts");

test("shotEvidenceGraphHasTextEvidence stays false for empty OCR and ASR outputs", () => {
  assert.equal(
    shotEvidenceGraphHasTextEvidence({
      shots: [
        {
          shot: { index: 1 },
          ocr_texts: [],
          transcript_texts: [],
        },
      ],
      analysis_units: [
        {
          unit_id: "unit_1",
          ocr_texts: [],
          transcript_texts: [],
        },
      ],
      warnings: [],
    }),
    false,
  );
});

test("shotEvidenceGraphHasTextEvidence detects OCR or ASR text on shots and units", () => {
  assert.equal(
    shotEvidenceGraphHasTextEvidence({
      shots: [{ ocr_texts: [{ text: "SALE" }], transcript_texts: [] }],
    }),
    true,
  );
  assert.equal(
    shotEvidenceGraphHasTextEvidence({
      analysis_units: [{ ocr_texts: [], transcript_texts: [{ text: "少油快手" }] }],
    }),
    true,
  );
});
