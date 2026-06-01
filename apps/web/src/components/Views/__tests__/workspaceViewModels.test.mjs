import test from "node:test";
import assert from "node:assert/strict";

test("workspace view helpers derive product name and prompt signals", async () => {
  const { deriveProductName, extractPromptSignals } = await import("../workspaceViewModels.mjs");

  const prompt = "把参考视频迁移到新品空气炸锅，突出少油、快手和易清洁。";

  assert.deepEqual(extractPromptSignals(prompt), ["把参考视频迁移到新品空气炸锅", "突出少油", "快手和易清洁"]);
  assert.equal(deriveProductName(prompt), "把参考视频迁移到新品空气炸锅");
});

test("workspace view helpers normalize fallback labels and descriptions", async () => {
  const { displayStructureDescription, displayStructureLabel } = await import("../workspaceViewModels.mjs");

  assert.equal(displayStructureLabel("seg_01", "段落 1"), "段落 1");
  assert.equal(
    displayStructureDescription("", "这个节点暂无说明", "突出核心卖点"),
    "突出核心卖点",
  );
});

test("workspace view helpers build structure nodes from preview and keyframes", async () => {
  const { buildStructureNodes } = await import("../workspaceViewModels.mjs");

  const nodes = buildStructureNodes(
    {
      template: {
        script_pattern: [
          {
            id: "hook",
            label: "seg_01",
            start: 0,
            duration: 3,
            confidence: 0.86,
            purpose: "开场吸睛",
            intent: "",
            method: "结果先行",
            role: "吸引注意",
            sample_evidence: "拉花特写",
            evidence_shot_indices: [1],
          },
        ],
      },
    },
    [
      {
        shot_index: 1,
        keyframe_time: 0.8,
        public_url: "/frames/1.jpg",
      },
    ],
  );

  assert.equal(nodes.length, 1);
  assert.equal(nodes[0].label, "段落 1");
  assert.equal(nodes[0].score, "置信度 86%");
  assert.equal(nodes[0].evidenceShots[0].publicUrl, "/frames/1.jpg");
});

test("workspace view helpers build target brief and sample analysis models", async () => {
  const { buildSampleAnalysis, buildTargetBrief } = await import("../workspaceViewModels.mjs");

  const brief = buildTargetBrief({
    topic: "空气炸锅短视频",
    product_name: "轻油空气炸锅",
    selling_points: ["少油", "快手", "易清洁"],
    available_assets: ["开箱", "上菜"],
  });

  assert.equal(brief.productName, "轻油空气炸锅");
  assert.deepEqual(brief.sellingPoints, ["少油", "快手", "易清洁"]);

  const analysis = buildSampleAnalysis(
    { title: "样例视频", duration: 21, shot_count: 6, transcript_summary: "先展示成品，再展示步骤" },
    {
      filename: "sample.mp4",
      keyframes: [{ shot_index: 1, keyframe_time: 0.8, public_url: "/frames/1.jpg" }],
      video_signal: {
        metadata: { width: 1080, height: 1920, fps: 30, format_name: "mp4" },
        detection_method: "scene_detect",
        rhythm_metrics: {
          avg_shot_duration: 3.5,
          cut_density: "fast",
          fastest_window: "00:00-00:03",
          slowest_window: "00:12-00:18",
        },
      },
    },
    { filename: "sample.txt" },
  );

  assert.equal(analysis.filename, "sample.mp4");
  assert.equal(analysis.resolution, "1080x1920");
  assert.equal(analysis.transcriptFilename, "sample.txt");
  assert.equal(analysis.keyframes[0].shotIndex, 1);
});

test("workspace view helpers build mapping and transfer explanation models", async () => {
  const { buildMappingItems, buildTransferExplanations } = await import("../workspaceViewModels.mjs");

  const preview = {
    template: {
      script_pattern: [
        {
          id: "hook",
          label: "seg_01",
          method: "结果先行",
          transferable_rule: "先给成品再讲步骤",
          packaging_intent: "大字标题",
          required_asset: "成品特写",
          sample_evidence: "拉花特写",
        },
      ],
    },
    transfer_plan: {
      mappings: [
        {
          slot_id: "hook",
          target_message: "先展示炸鸡出锅",
          asset_requirement: "成品近景",
          asset_strategy: "先用现有素材顶上",
          target_adaptation: "前三秒给结果",
          reasoning: "保留样例的强吸引开场",
          explanation: {
            source_observation: "开场直接给结果",
            transferable_principle: "用结果画面抢注意力",
            target_expression: "新品先出锅再展开步骤",
            asset_plan: "优先找成品端上桌镜头",
            gap_handling: "没有成片就补拍一条",
            confidence: 0.88,
            warnings: ["需要保证光线统一"],
          },
        },
      ],
    },
  };

  const mappingItems = buildMappingItems(preview);
  assert.deepEqual(mappingItems, [
    {
      key: "hook",
      label: "成品近景",
      score: "先用现有素材顶上",
      percent: 100,
    },
  ]);

  const explanations = buildTransferExplanations(preview);
  assert.equal(explanations.length, 1);
  assert.equal(explanations[0].label, "段落 1");
  assert.equal(explanations[0].sourceMethod, "开场直接给结果");
  assert.equal(explanations[0].targetAdaptation, "新品先出锅再展开步骤");
  assert.equal(explanations[0].warnings[0], "需要保证光线统一");
});

test("workspace view helpers build analysis and evaluation summary models", async () => {
  const { buildAnalysisView, buildEvaluationSummaryView } = await import("../workspaceViewModels.mjs");

  const analysisView = buildAnalysisView({
    analysisSummary: {
      headline: "结构拆解解释",
      metrics: [
        { label: "节奏结构", value: "fast", detail: "前段快切" },
        { label: "包装结构", value: "title_card", detail: "标题卡先抛结论" },
        { label: "hook", value: "cta", detail: "先结果后行动" },
      ],
      narrative_beats: [{ slot_id: "hook", label: "seg_01", evidence: "开场就是成品" }],
      packaging_signals: ["title_card"],
      graph_presentation: {
        headline: "图谱概览",
        summary_points: ["开头节点最强"],
        nodes: [{ id: "hook", label: "seg_01", node_type: "segment", summary: "结果先行", shot_indices: [1], confidence: 0.9 }],
        edges: [{ source: "hook", target: "proof", relation: "adjacent_cut" }],
      },
    },
    analysisSource: "ai",
    analysisConfidence: 0.92,
    analysisWarnings: ["Only 2 镜头 are available, so beat/segment granularity is coarse."],
    rhythmSummary: "节奏偏快，适合前三秒抓注意力",
  });

  assert.equal(analysisView.source, "ai");
  assert.equal(analysisView.metrics[0].label, "节奏结构");
  assert.equal(analysisView.metrics[0].value, "快节奏");
  assert.equal(analysisView.narrativeBeats[0].label, "hook");
  assert.equal(analysisView.packagingStructure.signals[0], "标题卡");
  assert.equal(analysisView.graphPresentation.edges[0].relation, "相邻剪切");
  assert.match(analysisView.warnings[0], /当前只有 2 个镜头可用/);

  const evaluationView = buildEvaluationSummaryView(
    { evaluation_summary: { headline: "结构预评估", highlights: ["结构完整"], structure_quality: "medium", retrieval_quality: "low", completion_quality: "low", result_quality: "low" } },
    { evaluation_summary: { headline: "最终评估", highlights: ["结果更稳定"], structure_quality: "high", retrieval_quality: "medium", completion_quality: "medium", result_quality: "high" } },
  );

  assert.equal(evaluationView.headline, "最终评估");
  assert.deepEqual(evaluationView.highlights, ["结果更稳定"]);
  assert.equal(evaluationView.resultQuality, "high");
});

test("workspace view helpers build material and gap models", async () => {
  const { buildGapItems, buildMaterialAssets, buildSlotLabelLookup } = await import("../workspaceViewModels.mjs");

  const preview = {
    template: {
      script_pattern: [
        { id: "hook", label: "seg_01" },
      ],
    },
  };

  const uploadedAssets = [
    {
      slot_id: "hook",
      filename: "hook.mp4",
      public_url: "/materials/hook.mp4",
      analysis: {
        duration: 4,
        shot_count: 2,
        recommended_slot_id: "hook",
        recommended_slot_label: "开头钩子",
        visual_summary: "成品特写",
        tags: ["成品"],
        usable_for: ["开场吸睛"],
        warnings: ["时长略短"],
        evidence_chunks: [
          {
            chunk_id: "chunk-1",
            start: 0,
            end: 2,
            visual_summary: "近景出锅",
            modalities: ["visual", "ocr"],
            ocr_texts: ["少油空气炸"],
            asr_texts: ["刚出锅"],
            packaging_signals: ["标题卡"],
            subject_tags: ["空气炸锅"],
            action_tags: ["出锅"],
            slot_hints: ["hook"],
            frame_urls: ["/frames/1.jpg"],
          },
        ],
      },
    },
  ];

  const materialAssets = buildMaterialAssets(uploadedAssets);
  assert.equal(materialAssets[0].recommendedSlot, "开头钩子");
  assert.equal(materialAssets[0].nodes[0].time, "0s-2s");
  assert.equal(materialAssets[0].nodes[0].packagingSignals[0], "标题卡");

  const gapItems = buildGapItems({
    uploadedAssets,
    selectedGaps: [
      {
        slot_id: "hook",
        missing_asset: "成品近景",
        impact: "开场吸引力不足",
        fill_strategy: "优先复用成品素材",
        suggested_asset_type: "近景",
        suggested_shots: ["出锅瞬间"],
        pickup_checklist: ["补一个端上桌镜头"],
        retrieval_status: "可复用",
        retrieval_reason: "素材库已有成品近景",
        primary_supplement: "现有素材复用",
        retrieval_plan: {
          required_expression: "前三秒出结果",
          query_summary: "优先找成品出锅镜头",
          best_candidate_label: "hook.mp4 / chunk-1",
          matched_evidence: ["近景", "成品"],
          missing_evidence: ["端上桌动作"],
          recommended_method: "现有素材复用",
          generation_action: "先复用，再补字幕",
          confidence: 0.8,
        },
        slot_fill_decision: {
          decision_type: "reuse_with_packaging",
          selected_asset_id: "asset-1",
          selected_chunk_id: "chunk-1",
          start: 0,
          end: 2,
          confidence: 0.75,
          why: "画面已经接近目标表达",
          missing: ["缺上桌动作"],
          actions: ["加标题卡", "补一句利益点"],
          timeline_hint: "先强提示再切步骤",
          evidence_path: ["asset-1", "chunk-1"],
          timeline_patch_id: "patch-1",
        },
        slot_query_profile: {
          slot_label: "hook",
          required_asset: "成品近景",
          required_expression: "前三秒出结果",
          semantic_terms: ["成品"],
          visual_terms: ["近景"],
          action_terms: ["出锅"],
          text_terms: ["少油"],
          packaging_terms: ["标题卡"],
          target_duration: 3,
          min_usable_duration: 1.5,
          replacement_modes: ["reuse_with_packaging"],
        },
        coverage_result: {
          slot_id: "hook",
          coverage_score: 0.78,
          gap_level: "medium",
          fillability: "packaging",
          summary: "通过补包装可以达标",
        },
        graph_search_results: [],
        timeline_patches: [
          {
            patch_id: "patch-1",
            slot_id: "hook",
            operation: "replace_slot_media",
            target_start: 0,
            target_end: 3,
            execution_summary: "已用现有成品镜头替换开场",
            source_asset_id: "asset-1",
            source_chunk_id: "chunk-1",
            source_start: 0,
            source_end: 2,
            track_updates: [],
            warnings: ["注意字幕不要遮挡主体"],
          },
        ],
        supplement_options: [
          { method: "现有素材复用", title: "直接复用现有镜头", action: "优先顶上", evidence: ["已有成品镜头"], priority: 1 },
        ],
        candidates: [
          {
            asset_id: "asset-1",
            filename: "hook.mp4",
            chunk_id: "chunk-1",
            start: 0,
            end: 2,
            matched_modalities: ["visual"],
            evidence: ["成品特写"],
            match_score: 0.82,
            score_breakdown: { visual: 0.82 },
            match_reason: "主体和镜头距离匹配",
            reuse_strategy: "补标题卡后复用",
            public_url: "/materials/hook.mp4",
          },
        ],
      },
    ],
    slotLabelLookup: buildSlotLabelLookup(preview),
    supplementSelection: { hook: "现有素材复用" },
  });

  assert.equal(gapItems[0].label, "hook");
  assert.equal(gapItems[0].uploadedFilename, "hook.mp4");
  assert.equal(gapItems[0].slotFillDecision.why, "画面已经接近目标表达");
  assert.equal(gapItems[0].supplementOptions[0].title, "直接复用现有镜头");
  assert.equal(gapItems[0].selectedSupplementMethod, "现有素材复用");
});

test("workspace view helpers build result preview model", async () => {
  const { buildResultView } = await import("../workspaceViewModels.mjs");

  assert.equal(buildResultView(null, "/video.mp4"), null);
  assert.equal(buildResultView({ run_id: "run-1" }, ""), null);

  const resultView = buildResultView(
    {
      run_id: "run-1",
      batch_id: "batch-1",
      prepared_assets: [
        {
          scene_id: "scene-1",
          source_type: "uploaded",
          source_label: "用户补拍",
          caption: "前三秒成品镜头",
          duration: 3,
        },
      ],
      trace: [{ step: "render", title: "渲染成片", message: "正在输出", progress: 90 }],
    },
    "/video.mp4",
  );

  assert.equal(resultView.runId, "run-1");
  assert.equal(resultView.videoUrl, "/video.mp4");
  assert.equal(resultView.assets[0].sourceType, "uploaded");
  assert.equal(resultView.trace[0].title, "渲染成片");
});

test("workspace view helpers build shot evidence and related evidence views", async () => {
  const {
    buildAnalysisUnits,
    buildProgressItems,
    buildShotEvidence,
    buildShotEvidenceWarnings,
    buildShotRelations,
  } = await import("../workspaceViewModels.mjs");

  const mergedShotEvidenceGraph = {
    shots: [
      {
        shot: { index: 1, start: 0, end: 2, duration: 2 },
        frames: [{ role: "middle", time: 1, public_url: "/frames/1.jpg" }],
        ocr_texts: [{ text: "少油空气炸", frame_index: 3, frame_time: 1.1, position: "center", confidence: 0.91 }],
        transcript_texts: [{ text: "三分钟出锅", source_start: 0.2, source_end: 1.4, overlap_ratio: 0.8 }],
        understanding: {
          visual_summary: "近景展示成品",
          text_summary: "字幕强调少油",
          creative_function_hint: "hook",
          confidence: 0.86,
          warnings: ["No ASR support for 镜头 1; beat and packaging interpretation there is based on OCR and 理解结果 only."],
        },
      },
    ],
    analysis_units: [
      {
        unit_id: "unit_1",
        shot_indices: [1],
        start: 0,
        end: 2,
        duration: 2,
        representative_frames: [{ role: "middle", time: 1, public_url: "/frames/1.jpg", shot_index: 1 }],
        ocr_texts: [{ text: "少油空气炸", frame_index: 3, frame_time: 1.1, position: "center", confidence: 0.91 }],
        transcript_texts: [{ text: "三分钟出锅", source_start: 0.2, source_end: 1.4, overlap_ratio: 0.8 }],
        understanding: {
          visual_summary: "这一段先给结果",
          text_summary: "文字补充利益点",
          creative_function_hint: "proof",
          confidence: 0.78,
          warnings: ["Only 1 镜头 are available, so beat/segment granularity is coarse."],
        },
      },
    ],
    relations: [
      {
        from_shot: 1,
        to_shot: 2,
        relation_type: "adjacent_cut",
        relation_summary: "前后镜头紧接承接",
        semantic_shift: "从结果切到步骤",
        confidence: 0.72,
      },
    ],
    warnings: ["Only 1 镜头 are available, so relation and rhythm aggregation are structurally limited."],
  };

  const sampleUpload = {
    video_signal: {
      shots: [{ index: 1, start: 0, end: 2, duration: 2 }],
    },
    keyframes: [{ shot_index: 1, keyframe_time: 1, public_url: "/frames/1.jpg" }],
  };

  const shotEvidence = buildShotEvidence({
    mergedShotEvidenceGraph,
    sampleUpload,
    resolveMediaUrl: (value) => `http://127.0.0.1:8010${value}`,
  });

  assert.equal(shotEvidence.length, 1);
  assert.equal(shotEvidence[0].time, "00:00 - 00:02");
  assert.equal(shotEvidence[0].frames[0].publicUrl, "http://127.0.0.1:8010/frames/1.jpg");
  assert.equal(shotEvidence[0].functionHint, "开头钩子");
  assert.match(shotEvidence[0].warnings[0], /没有 ASR 口播证据/);

  const analysisUnits = buildAnalysisUnits({
    mergedShotEvidenceGraph,
    shotEvidence,
    resolveMediaUrl: (value) => `http://127.0.0.1:8010${value}`,
  });

  assert.equal(analysisUnits.length, 1);
  assert.equal(analysisUnits[0].unitId, "unit_1");
  assert.equal(analysisUnits[0].shots[0].shotIndex, 1);
  assert.equal(analysisUnits[0].functionHint, "信任证明");
  assert.match(analysisUnits[0].warnings[0], /当前只有 1 个镜头可用/);

  const shotRelations = buildShotRelations(mergedShotEvidenceGraph);
  assert.equal(shotRelations[0].relationType, "相邻剪切");
  assert.equal(shotRelations[0].semanticShift, "从结果切到步骤");

  const shotEvidenceWarnings = buildShotEvidenceWarnings(mergedShotEvidenceGraph);
  assert.match(shotEvidenceWarnings[0], /关系和节奏聚合会受到结构限制/);

  const progressItems = buildProgressItems({
    sampleUpload,
    preview: { template: { script_pattern: [{ id: "hook" }] } },
    nodes: [{ key: "hook" }],
    status: "已完成",
    busy: false,
  });

  assert.deepEqual(progressItems, [
    { label: "样例视频", v1: "已上传", v2: "", percent: 100 },
    { label: "结构拆解", v1: "1", v2: "节点", percent: 100 },
    { label: "当前状态", v1: "已完成", v2: "", percent: 100 },
  ]);
});

test("workspace view helpers build conversation messages and execution stages", async () => {
  const { buildConversationMessages, buildExecutionStagesView } = await import("../workspaceViewModels.mjs");

  const messages = buildConversationMessages({
    sampleUpload: { filename: "sample.mp4" },
    taskText: "做一版空气炸锅短视频",
    steps: [{ title: "结构拆解" }],
    pendingConfirmation: {
      id: "confirm-1",
      title: "开始执行",
      message: "确认后立即推进",
    },
    errors: ["上一步失败"],
    messages: [{ id: "m1", role: "assistant", content: "收到" }],
  });

  assert.equal(messages[0].body, "做一版空气炸锅短视频");
  assert.equal(messages[1].body, "参考视频已上传，我会先生成执行计划并等待你确认。");
  assert.equal(messages[2].body, "当前计划：结构拆解");
  assert.equal(messages[3].body, "开始执行：确认后立即推进");
  assert.equal(messages[4].body, "上一步失败");
  assert.equal(messages[5].body, "收到");

  const stages = buildExecutionStagesView({
    steps: [{ id: "step-1", title: "结构拆解", tool_name: "analyze_structure" }],
    toolRuns: [],
    currentStep: "analyze_structure",
    agentStatus: "running",
    busyStatus: "正在生成",
    pendingConfirmationTitle: "开始执行",
    hasStructurePreview: true,
    hasMaterialAnalysis: false,
    hasResultVideo: false,
  });

  assert.equal(stages.length, 2);
  assert.equal(stages[0].state, "completed");
  assert.equal(stages[0].detail, "结构预览已生成");
  assert.equal(stages[1].label, "结构刷新");
});

test("workspace view helpers build workspace stage view state", async () => {
  const { buildWorkspaceStageView } = await import("../workspaceViewModels.mjs");

  const view = buildWorkspaceStageView({
    currentStage: "output",
    preview: {
      template: {
        rhythm_summary: "节奏偏快，适合先给结果",
      },
    },
    sampleUpload: {
      public_url: "/sample.mp4",
      filename: "sample.mp4",
    },
    run: {
      run_id: "run-9",
    },
    videoUrl: "/final.mp4",
    localVideoUrl: "/local.mp4",
    localVideoFileName: "local.mp4",
  });

  assert.equal(view.stageDescription, "节奏偏快，适合先给结果");
  assert.equal(view.displayVideoUrl, "/final.mp4");
  assert.equal(view.displayVideoName, "run-9.mp4");
  assert.equal(view.stageStates.output.completed, true);
  assert.equal(view.stageStates.structure.enabled, true);
});
