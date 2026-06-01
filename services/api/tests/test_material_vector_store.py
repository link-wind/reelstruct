from app.material_embedding_service import MaterialEmbeddingService
from app.material_rag_service import create_material_vector_store
from app.material_vector_store import InMemoryMaterialVectorStore, MaterialVectorDocument


def test_material_embedding_service_returns_deterministic_vector():
    service = MaterialEmbeddingService(dimension=16)

    first = service.embed("清透保湿精华 产品特写")
    second = service.embed("清透保湿精华 产品特写")

    assert first == second
    assert len(first) == 16
    assert any(value > 0 for value in first)


def test_in_memory_material_vector_store_returns_ranked_documents():
    store = InMemoryMaterialVectorStore()
    store.upsert(
        [
            MaterialVectorDocument(
                id="asset-a:chunk-1",
                text="清透保湿精华 快速补水 产品特写 卖点展开",
                metadata={"asset_id": "asset-a", "chunk_id": "chunk-1", "slot": "selling_points"},
            ),
            MaterialVectorDocument(
                id="asset-b:chunk-1",
                text="门店地址 结尾 行动号召 优惠",
                metadata={"asset_id": "asset-b", "chunk_id": "chunk-1", "slot": "cta"},
            ),
        ]
    )

    results = store.search("保湿精华 产品特写", top_k=1, filters={"slot": "selling_points"})

    assert len(results) == 1
    assert results[0].id == "asset-a:chunk-1"
    assert results[0].score > 0
    assert results[0].metadata["chunk_id"] == "chunk-1"


def test_in_memory_material_vector_store_uses_embeddings_when_available():
    store = InMemoryMaterialVectorStore()
    store.upsert(
        [
            MaterialVectorDocument(id="asset-a:chunk-1", text="抽象画面", embedding=[1.0, 0.0]),
            MaterialVectorDocument(id="asset-b:chunk-1", text="抽象画面", embedding=[0.0, 1.0]),
        ]
    )

    results = store.search("任意查询", top_k=1, query_embedding=[0.95, 0.05])

    assert len(results) == 1
    assert results[0].id == "asset-a:chunk-1"
    assert results[0].score > 0.9


def test_create_material_vector_store_defaults_to_memory(monkeypatch):
    monkeypatch.delenv("REELSTRUCT_MATERIAL_VECTOR_BACKEND", raising=False)

    store = create_material_vector_store()

    assert isinstance(store, InMemoryMaterialVectorStore)


def test_create_material_vector_store_uses_milvus_backend_when_configured(monkeypatch):
    captured = {}

    class FakeMilvusStore:
        def __init__(self, *, uri):
            captured["uri"] = uri

    monkeypatch.setenv("REELSTRUCT_MATERIAL_VECTOR_BACKEND", "milvus")
    monkeypatch.setenv("REELSTRUCT_MILVUS_URI", "/tmp/reelstruct-milvus.db")
    monkeypatch.setattr("app.material_rag_service.MilvusLiteMaterialVectorStore", FakeMilvusStore)

    store = create_material_vector_store()

    assert isinstance(store, FakeMilvusStore)
    assert captured["uri"] == "/tmp/reelstruct-milvus.db"


def test_create_material_vector_store_falls_back_to_memory_when_milvus_unavailable(monkeypatch):
    def fail_milvus(*args, **kwargs):
        raise RuntimeError("Milvus unavailable")

    monkeypatch.setenv("REELSTRUCT_MATERIAL_VECTOR_BACKEND", "milvus")
    monkeypatch.setattr("app.material_rag_service.MilvusLiteMaterialVectorStore", fail_milvus)

    store = create_material_vector_store()

    assert isinstance(store, InMemoryMaterialVectorStore)


def test_build_material_graph_creates_nodes_and_edges_from_evidence_chunks():
    from app.material_graph_service import build_material_graph
    from app.models import UserSlotAsset

    asset = UserSlotAsset(
        slot_id="material_pool",
        filename="detail-shot.mp4",
        public_url="/materials/detail-shot.mp4",
        analysis={
            "evidence_chunks": [
                {
                    "asset_id": "detail-shot.mp4",
                    "chunk_id": "chunk_detail",
                    "start": 1.2,
                    "end": 3.8,
                    "visual_summary": "清透保湿精华瓶身细节特写。",
                    "ocr_texts": ["快速补水"],
                    "asr_texts": ["质地很清爽"],
                    "packaging_signals": ["卖点字幕"],
                    "subject_tags": ["产品", "瓶身"],
                    "action_tags": ["特写"],
                    "slot_hints": ["卖点展开"],
                    "modalities": ["visual", "ocr", "asr", "packaging"],
                    "embedding_text": "清透保湿精华 快速补水 质地清爽 产品 特写 卖点展开",
                }
            ]
        },
    )

    graph = build_material_graph([asset])
    node_types = {node.node_type for node in graph.nodes}
    relations = {edge.relation for edge in graph.edges}

    assert graph.material_id == "material_pool"
    assert {"asset", "chunk", "ocr_text", "asr_text", "packaging_signal", "tag", "slot_hint"}.issubset(node_types)
    assert {"contains", "has_evidence", "supports_slot"}.issubset(relations)
    assert any(node.text == "快速补水" for node in graph.nodes)


def test_search_material_graph_for_slot_returns_evidence_path():
    from app.material_graph_service import build_material_graph, search_material_graph_for_slot
    from app.models import SlotQueryProfile, UserSlotAsset

    asset = UserSlotAsset(
        slot_id="material_pool",
        filename="detail-shot.mp4",
        public_url="/materials/detail-shot.mp4",
        analysis={
            "evidence_chunks": [
                {
                    "asset_id": "detail-shot.mp4",
                    "chunk_id": "chunk_detail",
                    "start": 1.2,
                    "end": 3.8,
                    "duration": 2.6,
                    "visual_summary": "清透保湿精华瓶身细节特写。",
                    "ocr_texts": ["快速补水"],
                    "packaging_signals": ["卖点字幕"],
                    "subject_tags": ["产品", "瓶身"],
                    "action_tags": ["特写"],
                    "slot_hints": ["卖点展开"],
                    "modalities": ["visual", "ocr", "packaging"],
                    "embedding_text": "清透保湿精华 快速补水 产品 瓶身 特写 卖点展开",
                }
            ]
        },
    )
    profile = SlotQueryProfile(
        slot_id="selling_points",
        slot_label="卖点展开",
        required_asset="商品特写镜头",
        required_expression="连续推进卖点",
        visual_terms=["产品", "瓶身", "特写"],
        text_terms=["快速补水"],
        packaging_terms=["卖点字幕"],
        target_duration=8,
        min_usable_duration=1,
        replacement_modes=["reuse_with_packaging", "caption_only"],
    )

    graph = build_material_graph([asset])
    results = search_material_graph_for_slot(graph, profile)

    assert results
    result = results[0]
    assert result.asset_id == "detail-shot.mp4"
    assert result.chunk_id == "chunk_detail"
    assert result.score_breakdown["visual"] > 0
    assert result.score_breakdown["ocr_asr"] > 0
    assert result.score_breakdown["packaging"] > 0
    assert any("OCR=快速补水" in item for item in result.evidence_path)
    assert any(node.node_type == "ocr_text" for node in result.matched_nodes)


def test_search_material_graph_for_slot_ignores_duration_only_matches():
    from app.material_graph_service import build_material_graph, search_material_graph_for_slot
    from app.models import SlotQueryProfile, UserSlotAsset

    asset = UserSlotAsset(
        slot_id="material_pool",
        filename="unrelated.mp4",
        public_url="/materials/unrelated.mp4",
        analysis={
            "evidence_chunks": [
                {
                    "asset_id": "unrelated.mp4",
                    "chunk_id": "chunk_unrelated",
                    "start": 0,
                    "end": 8,
                    "duration": 8,
                    "visual_summary": "门店外景空镜。",
                    "ocr_texts": ["营业中"],
                    "packaging_signals": ["门店招牌"],
                    "subject_tags": ["门店"],
                    "action_tags": ["空镜"],
                    "slot_hints": ["环境铺垫"],
                    "modalities": ["visual"],
                    "embedding_text": "门店 外景 营业中",
                }
            ]
        },
    )
    profile = SlotQueryProfile(
        slot_id="selling_points",
        slot_label="卖点展开",
        required_asset="商品特写镜头",
        required_expression="连续推进卖点",
        visual_terms=["产品", "瓶身", "特写"],
        text_terms=["快速补水"],
        packaging_terms=["卖点字幕"],
        target_duration=8,
    )

    graph = build_material_graph([asset])
    results = search_material_graph_for_slot(graph, profile)

    assert results == []


def test_material_retrieval_candidate_exposes_hybrid_score_breakdown():
    from app.material_rag_service import retrieve_material_candidates_for_slot
    from app.models import NewContentInput, StructureSlot, UserSlotAsset

    slot = StructureSlot(
        id="selling_points",
        label="卖点展开",
        start=3,
        duration=8,
        purpose="展示快速补水卖点",
        required_asset="商品特写镜头",
        sample_evidence="产品细节特写",
    )
    content = NewContentInput(
        topic="新品保湿精华短视频",
        product_name="清透保湿精华",
        selling_points=["快速补水"],
        uploaded_assets=[
            UserSlotAsset(
                slot_id="material_pool",
                filename="detail-shot.mp4",
                public_url="/materials/detail-shot.mp4",
                analysis={
                    "evidence_chunks": [
                        {
                            "asset_id": "detail-shot.mp4",
                            "chunk_id": "chunk_detail",
                            "start": 1.2,
                            "end": 3.8,
                            "visual_summary": "清透保湿精华瓶身细节特写。",
                            "ocr_texts": ["快速补水"],
                            "packaging_signals": ["卖点字幕"],
                            "subject_tags": ["产品", "瓶身"],
                            "action_tags": ["特写"],
                            "slot_hints": ["卖点展开"],
                            "modalities": ["visual", "ocr", "packaging"],
                            "embedding_text": "清透保湿精华 快速补水 产品 瓶身 特写 卖点展开",
                        }
                    ]
                },
            )
        ],
    )

    candidate = retrieve_material_candidates_for_slot(slot, content)[0]

    assert {"semantic", "visual", "ocr_asr", "packaging", "slot_hint", "duration_fit"}.issubset(candidate.score_breakdown)
    assert candidate.score_breakdown["ocr_asr"] > 0
    assert candidate.score_breakdown["visual"] > 0
    assert candidate.score_breakdown["slot_hint"] > 0


def test_rerank_material_graph_results_prefers_visual_and_text_evidence():
    from app.material_rerank_service import rerank_material_graph_results
    from app.models import MaterialGraphMatchedNode, MaterialGraphSearchResult, SlotQueryProfile

    profile = SlotQueryProfile(
        slot_id="selling_points",
        slot_label="卖点展开",
        required_asset="商品特写镜头",
        replacement_modes=["reuse_with_packaging", "caption_only"],
    )
    weak = MaterialGraphSearchResult(
        slot_id="selling_points",
        asset_id="text-only.mp4",
        chunk_id="chunk_text",
        matched_nodes=[MaterialGraphMatchedNode(node_type="ocr_text", text="快速补水")],
        evidence_path=["chunk_text 命中 OCR=快速补水"],
        score_breakdown={"ocr_asr": 25, "visual": 0, "packaging": 0, "slot_hint": 0, "duration_fit": 5},
        confidence=0.74,
    )
    strong = MaterialGraphSearchResult(
        slot_id="selling_points",
        asset_id="detail.mp4",
        chunk_id="chunk_detail",
        matched_nodes=[
            MaterialGraphMatchedNode(node_type="tag", text="产品"),
            MaterialGraphMatchedNode(node_type="ocr_text", text="快速补水"),
            MaterialGraphMatchedNode(node_type="packaging_signal", text="卖点字幕"),
        ],
        evidence_path=["chunk_detail 命中 标签=产品", "chunk_detail 命中 OCR=快速补水", "chunk_detail 命中 包装=卖点字幕"],
        score_breakdown={"ocr_asr": 25, "visual": 20, "packaging": 15, "slot_hint": 0, "duration_fit": 5},
        confidence=0.65,
    )

    ranked = rerank_material_graph_results(profile, [weak, strong])

    assert ranked[0].asset_id == "detail.mp4"
    assert ranked[0].confidence > strong.confidence
    assert weak.confidence == 0.74
    assert strong.confidence == 0.65


def test_rerank_material_graph_results_breaks_ties_by_evidence_quality():
    from app.material_rerank_service import rerank_material_graph_results
    from app.models import MaterialGraphMatchedNode, MaterialGraphSearchResult, SlotQueryProfile

    profile = SlotQueryProfile(
        slot_id="selling_points",
        slot_label="卖点展开",
        required_asset="商品特写镜头",
        replacement_modes=["reuse_with_packaging"],
    )
    text_only = MaterialGraphSearchResult(
        slot_id="selling_points",
        asset_id="text-only.mp4",
        chunk_id="chunk_text",
        matched_nodes=[MaterialGraphMatchedNode(node_type="ocr_text", text="快速补水")],
        score_breakdown={"ocr_asr": 25, "visual": 0, "packaging": 0, "slot_hint": 0, "duration_fit": 5},
        confidence=0.75,
    )
    complete = MaterialGraphSearchResult(
        slot_id="selling_points",
        asset_id="detail.mp4",
        chunk_id="chunk_detail",
        matched_nodes=[
            MaterialGraphMatchedNode(node_type="tag", text="产品"),
            MaterialGraphMatchedNode(node_type="ocr_text", text="快速补水"),
            MaterialGraphMatchedNode(node_type="packaging_signal", text="卖点字幕"),
        ],
        score_breakdown={"ocr_asr": 25, "visual": 20, "packaging": 15, "slot_hint": 0, "duration_fit": 5},
        confidence=0.53,
    )

    ranked = rerank_material_graph_results(profile, [text_only, complete])

    assert ranked[0].asset_id == "detail.mp4"
    assert ranked[0].confidence == ranked[1].confidence


def test_rerank_prefers_multimodal_evidence_over_single_signal():
    from app.material_rerank_service import rerank_material_graph_results
    from app.models import MaterialGraphSearchResult, SlotQueryProfile

    profile = SlotQueryProfile(
        slot_id="hook",
        slot_label="开头吸引镜头",
        visual_terms=["人物", "特写"],
        text_terms=["限时"],
        packaging_terms=["标题卡"],
        target_duration=2.5,
    )

    multimodal = MaterialGraphSearchResult(
        slot_id="hook",
        asset_id="a.mp4",
        chunk_id="chunk_a",
        start=0,
        end=2.4,
        matched_nodes=[],
        evidence_path=["视觉+OCR+包装共同命中"],
        missing=[],
        score_breakdown={"visual": 20, "ocr_asr": 25, "packaging": 15, "duration_fit": 14},
        confidence=0.62,
    )
    duration_only = MaterialGraphSearchResult(
        slot_id="hook",
        asset_id="b.mp4",
        chunk_id="chunk_b",
        start=0,
        end=2.5,
        matched_nodes=[],
        evidence_path=["只命中时长"],
        missing=["缺少画面和文本证据"],
        score_breakdown={"duration_fit": 15},
        confidence=0.7,
    )

    reranked = rerank_material_graph_results(profile, [duration_only, multimodal])

    assert reranked[0].asset_id == "a.mp4"
