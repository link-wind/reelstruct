from fastapi.testclient import TestClient

from app.main import app


def test_create_demo_run_returns_preview_assets_video_and_trace():
    client = TestClient(app)

    response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "咖啡拉花爆款样例",
                "duration": 20,
                "shot_count": 6,
                "transcript_summary": "先用拉花特写吸引注意，再展示手作过程。",
            },
            "content": {
                "topic": "精品咖啡店开业短视频",
                "product_name": "巷口手作咖啡",
                "selling_points": ["手作拉花", "新店开业优惠"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["preview"]["transfer_plan"]["title"] == "巷口手作咖啡 结构迁移方案"
    assert len(body["prepared_assets"]) >= 1
    assert body["rendered_video"]["video_url"].startswith("/output/")
    assert any(gap["suggested_asset_type"] for gap in body["preview"]["transfer_plan"]["gaps"])
    assert any(gap["suggested_shots"] for gap in body["preview"]["transfer_plan"]["gaps"])
    assert [event["step"] for event in body["trace"]] == [
        "analyze_structure",
        "transfer_structure",
        "prepare_assets",
        "render_video",
        "done",
    ]
    assert body["trace"][-1]["progress"] == 100


def test_create_demo_run_applies_mapping_overrides_to_preview_and_tracks():
    client = TestClient(app)

    response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "咖啡拉花爆款样例",
                "duration": 20,
                "shot_count": 6,
                "transcript_summary": "先用拉花特写吸引注意，再展示手作过程。",
            },
            "content": {
                "topic": "精品咖啡店开业短视频",
                "product_name": "巷口手作咖啡",
                "selling_points": ["手作拉花", "新店开业优惠"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
            "mapping_overrides": [
                {
                    "slot_id": "hook",
                    "target_message": "3 秒先讲新店开业限时福利",
                    "sample_evidence": "样例开头先给福利字幕，再给拉花特写",
                },
                {
                    "slot_id": "cta",
                    "target_message": "现在到店领取开业双杯券",
                    "asset_strategy": "结尾用优惠卡片 + 到店字幕补足 CTA",
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    slot_lookup = {item["id"]: item for item in body["preview"]["template"]["script_pattern"]}
    mapping_lookup = {item["slot_id"]: item for item in body["preview"]["transfer_plan"]["mappings"]}
    beat_lookup = {item["slot_id"]: item for item in body["preview"]["template"]["analysis_summary"]["narrative_beats"]}
    assert slot_lookup["hook"]["sample_evidence"] == "样例开头先给福利字幕，再给拉花特写"
    assert beat_lookup["hook"]["evidence"] == "样例开头先给福利字幕，再给拉花特写"
    assert mapping_lookup["hook"]["target_message"] == "3 秒先讲新店开业限时福利"
    assert mapping_lookup["cta"]["target_message"] == "现在到店领取开业双杯券"
    assert mapping_lookup["cta"]["asset_strategy"] == "结尾用优惠卡片 + 到店字幕补足 CTA"
    caption_texts = [track["text"] for track in body["preview"]["composition"]["tracks"] if track["type"] == "caption"]
    card_texts = [track["text"] for track in body["preview"]["composition"]["tracks"] if track["type"] == "card"]
    assert "3 秒先讲新店开业限时福利" in caption_texts
    assert "现在到店领取开业双杯券" in caption_texts
    assert "结尾用优惠卡片 + 到店字幕补足 CTA" in card_texts


def test_create_demo_run_returns_material_request_sheet_from_request():
    client = TestClient(app)

    response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "咖啡拉花爆款样例",
                "duration": 20,
                "shot_count": 6,
                "transcript_summary": "先用拉花特写吸引注意，再展示手作过程。",
            },
            "content": {
                "topic": "精品咖啡店开业短视频",
                "product_name": "巷口手作咖啡",
                "selling_points": ["手作拉花", "新店开业优惠"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
            "material_request_sheet": [
                {
                    "slot_id": "selling_points",
                    "status": "已拍",
                },
                {
                    "slot_id": "cta",
                    "status": "已交付",
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["preview"]["transfer_plan"]["material_request_sheet"] == [
        {"slot_id": "selling_points", "status": "已拍"},
        {"slot_id": "cta", "status": "已交付"},
    ]


def test_get_saved_demo_run_returns_snapshot():
    client = TestClient(app)

    create_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "咖啡拉花爆款样例",
                "duration": 20,
                "shot_count": 6,
                "transcript_summary": "先用拉花特写吸引注意，再展示手作过程。",
            },
            "content": {
                "topic": "精品咖啡店开业短视频",
                "product_name": "巷口手作咖啡",
                "selling_points": ["手作拉花", "新店开业优惠"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
            "material_request_sheet": [
                {
                    "slot_id": "selling_points",
                    "status": "已拍",
                }
            ],
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()

    get_response = client.get(f"/api/runs/{created['run_id']}")

    assert get_response.status_code == 200
    saved = get_response.json()
    assert saved["run_id"] == created["run_id"]
    assert saved["preview"]["transfer_plan"]["material_request_sheet"] == [
        {"slot_id": "selling_points", "status": "已拍"}
    ]


def test_list_saved_demo_runs_returns_latest_first():
    client = TestClient(app)

    first_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "第一条样例",
                "duration": 18,
                "shot_count": 5,
                "transcript_summary": "先讲亮点，再展示过程。",
            },
            "content": {
                "topic": "第一条短视频",
                "product_name": "第一家门店",
                "selling_points": ["卖点一"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
        },
    )
    second_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "第二条样例",
                "duration": 22,
                "shot_count": 7,
                "transcript_summary": "先给结果，再给过程。",
            },
            "content": {
                "topic": "第二条短视频",
                "product_name": "第二家门店",
                "selling_points": ["卖点二"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_run = first_response.json()
    second_run = second_response.json()
    list_response = client.get("/api/runs")

    assert list_response.status_code == 200
    runs = list_response.json()
    summary_lookup = {item["run_id"]: item for item in runs}
    run_ids = [item["run_id"] for item in runs]
    assert second_run["run_id"] in summary_lookup
    assert first_run["run_id"] in summary_lookup
    assert run_ids.index(second_run["run_id"]) < run_ids.index(first_run["run_id"])
    assert summary_lookup[second_run["run_id"]]["title"] == "第二家门店 结构迁移方案"
    assert "created_at" in summary_lookup[second_run["run_id"]]


def test_delete_saved_demo_run_removes_snapshot():
    client = TestClient(app)

    create_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "待删除样例",
                "duration": 20,
                "shot_count": 6,
                "transcript_summary": "先讲亮点，再展示过程。",
            },
            "content": {
                "topic": "待删除短视频",
                "product_name": "待删除门店",
                "selling_points": ["卖点一"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
        },
    )

    assert create_response.status_code == 200
    run_id = create_response.json()["run_id"]

    delete_response = client.delete(f"/api/runs/{run_id}")
    get_response = client.get(f"/api/runs/{run_id}")
    list_response = client.get("/api/runs")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
    assert run_id not in [item["run_id"] for item in list_response.json()]


def test_list_saved_demo_runs_supports_keyword_query():
    client = TestClient(app)

    create_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "搜索样例",
                "duration": 20,
                "shot_count": 6,
                "transcript_summary": "先讲亮点，再展示过程。",
            },
            "content": {
                "topic": "搜索短视频",
                "product_name": "搜索门店",
                "selling_points": ["卖点一"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
        },
    )

    assert create_response.status_code == 200
    run_id = create_response.json()["run_id"]

    query_response = client.get("/api/runs", params={"q": "搜索门店"})

    assert query_response.status_code == 200
    runs = query_response.json()
    assert any(item["run_id"] == run_id for item in runs)
    assert all("搜索门店" in item["title"] or "搜索门店" in item["target_topic"] for item in runs)


def test_update_saved_demo_run_note_persists_to_detail_and_list():
    client = TestClient(app)

    create_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "备注样例",
                "duration": 20,
                "shot_count": 6,
                "transcript_summary": "先讲亮点，再展示过程。",
            },
            "content": {
                "topic": "备注短视频",
                "product_name": "备注门店",
                "selling_points": ["卖点一"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
        },
    )

    assert create_response.status_code == 200
    run_id = create_response.json()["run_id"]

    patch_response = client.patch(f"/api/runs/{run_id}/note", json={"note": "优先补拍卖点特写"})
    detail_response = client.get(f"/api/runs/{run_id}")
    list_response = client.get("/api/runs", params={"q": "优先补拍卖点特写"})

    assert patch_response.status_code == 200
    assert patch_response.json()["note"] == "优先补拍卖点特写"
    assert detail_response.status_code == 200
    assert detail_response.json()["note"] == "优先补拍卖点特写"
    assert any(item["run_id"] == run_id and item["note"] == "优先补拍卖点特写" for item in list_response.json())
