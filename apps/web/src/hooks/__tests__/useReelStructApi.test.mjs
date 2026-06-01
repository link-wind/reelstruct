import test from "node:test";
import assert from "node:assert/strict";

test("requestAgentToolExecution posts tool name and payload to agent tool endpoint", async () => {
  const captured = {};
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    captured.url = String(url);
    captured.options = options;
    return new Response(
      JSON.stringify({
        tool_name: "analyze_structure",
        stage: "structure",
        data: {
          preview: {
            transfer_plan: {
              title: "清透保湿精华 结构迁移方案",
            },
          },
        },
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    );
  };

  try {
    const { requestAgentToolExecution } = await import("../useReelStructApi.ts");

    const result = await requestAgentToolExecution({
      tool_name: "analyze_structure",
      payload: {
        sample: { title: "护肤样例", duration: 18, shot_count: 5 },
        content: { topic: "保湿精华短视频" },
      },
    });

    assert.equal(captured.url, "http://127.0.0.1:8010/api/agent/tools/execute");
    assert.equal(captured.options.method, "POST");
    assert.deepEqual(JSON.parse(captured.options.body), {
      tool_name: "analyze_structure",
      payload: {
        sample: { title: "护肤样例", duration: 18, shot_count: 5 },
        content: { topic: "保湿精华短视频" },
      },
    });
    assert.equal(result.stage, "structure");
    assert.equal(result.data.preview.transfer_plan.title, "清透保湿精华 结构迁移方案");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("requestAgentToolExecution keeps template_id in agent tool payload", async () => {
  const captured = {};
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    captured.url = String(url);
    captured.options = options;
    return new Response(
      JSON.stringify({
        tool_name: "analyze_structure",
        stage: "structure",
        data: {
          preview: {
            template: {
              title: "模板结构",
              script_pattern: [],
              rhythm_summary: "",
              packaging_notes: [],
              analysis_summary: {
                headline: "",
                metrics: [],
                narrative_beats: [],
                packaging_signals: [],
                source: "rule",
                confidence: 0,
                warnings: [],
              },
            },
            transfer_plan: {
              title: "模板迁移方案",
              target_topic: "保湿精华短视频",
              variant: "standard",
              mappings: [],
              gaps: [],
              material_request_sheet: [],
            },
            composition: { width: 1080, height: 1920, fps: 30, duration: 1, tracks: [] },
            evaluation_summary: {
              headline: "",
              highlights: [],
              structure_quality: "low",
              retrieval_quality: "low",
              completion_quality: "low",
              result_quality: "low",
            },
          },
        },
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    );
  };

  try {
    const { requestAgentToolExecution } = await import("../useReelStructApi.ts");

    const result = await requestAgentToolExecution({
      tool_name: "analyze_structure",
      payload: {
        sample: { title: "护肤样例", duration: 18, shot_count: 5 },
        content: { topic: "保湿精华短视频" },
        template_id: "tpl-1",
      },
    });

    assert.equal(captured.url, "http://127.0.0.1:8010/api/agent/tools/execute");
    assert.equal(JSON.parse(captured.options.body).payload.template_id, "tpl-1");
    assert.equal(result.data.preview.transfer_plan.title, "模板迁移方案");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
