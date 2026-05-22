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


def test_pin_saved_demo_run_moves_it_to_top():
    client = TestClient(app)

    first_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "置顶第一条样例",
                "duration": 18,
                "shot_count": 5,
                "transcript_summary": "先讲亮点，再展示过程。",
            },
            "content": {
                "topic": "置顶第一条短视频",
                "product_name": "置顶第一家门店",
                "selling_points": ["卖点一"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
        },
    )
    second_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "置顶第二条样例",
                "duration": 22,
                "shot_count": 7,
                "transcript_summary": "先给结果，再给过程。",
            },
            "content": {
                "topic": "置顶第二条短视频",
                "product_name": "置顶第二家门店",
                "selling_points": ["卖点二"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_run_id = first_response.json()["run_id"]

    pin_response = client.patch(f"/api/runs/{first_run_id}/pin", json={"pinned": True})
    list_response = client.get("/api/runs")
    detail_response = client.get(f"/api/runs/{first_run_id}")

    assert pin_response.status_code == 200
    assert pin_response.json()["pinned"] is True
    assert detail_response.status_code == 200
    assert detail_response.json()["pinned"] is True
    runs = list_response.json()
    assert runs[0]["run_id"] == first_run_id
    assert runs[0]["pinned"] is True


def test_save_run_as_template_and_apply_it_to_new_demo_run():
    client = TestClient(app)

    first_run_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "咖啡模板来源样例",
                "duration": 20,
                "shot_count": 6,
                "transcript_summary": "先用拉花特写吸引注意。再展示手作过程和门店氛围。最后引导到店打卡。",
            },
            "content": {
                "topic": "咖啡店开业短视频",
                "product_name": "巷口手作咖啡",
                "selling_points": ["手作拉花", "新店开业优惠"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
        },
    )

    assert first_run_response.status_code == 200
    first_run = first_run_response.json()
    source_run_id = first_run["run_id"]

    save_template_response = client.post(
        f"/api/templates/from-run/{source_run_id}",
        json={"title": "咖啡开业通用模板"},
    )
    list_templates_response = client.get("/api/templates")

    assert save_template_response.status_code == 200
    saved_template = save_template_response.json()
    assert saved_template["source_run_id"] == source_run_id
    assert saved_template["template"]["title"] == "咖啡开业通用模板"
    assert any(item["template_id"] == saved_template["template_id"] for item in list_templates_response.json())

    second_run_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "完全不同的样例",
                "duration": 36,
                "shot_count": 11,
                "transcript_summary": "这个样例只用来带素材和文本，不该再决定结构时长。",
            },
            "content": {
                "topic": "新店开业短视频",
                "product_name": "夜巷咖啡",
                "selling_points": ["深夜营业", "办公友好"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
            "template_id": saved_template["template_id"],
        },
    )

    assert second_run_response.status_code == 200
    second_run = second_run_response.json()
    first_slot_lookup = {slot["id"]: slot for slot in first_run["preview"]["template"]["script_pattern"]}
    second_slot_lookup = {slot["id"]: slot for slot in second_run["preview"]["template"]["script_pattern"]}

    assert second_run["template_id"] == saved_template["template_id"]
    assert second_run["template_title"] == "咖啡开业通用模板"
    assert second_run["preview"]["template"]["title"] == "咖啡开业通用模板"
    assert second_slot_lookup["hook"]["duration"] == first_slot_lookup["hook"]["duration"]
    assert second_slot_lookup["cta"]["start"] == first_slot_lookup["cta"]["start"]


def test_delete_template_removes_it_from_library():
    client = TestClient(app)

    run_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "待删除模板样例",
                "duration": 20,
                "shot_count": 6,
                "transcript_summary": "先讲亮点，再展示过程。",
            },
            "content": {
                "topic": "待删除模板短视频",
                "product_name": "待删除模板门店",
                "selling_points": ["卖点一"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
        },
    )

    assert run_response.status_code == 200
    run_id = run_response.json()["run_id"]

    save_response = client.post(f"/api/templates/from-run/{run_id}", json={"title": "待删除模板"})
    assert save_response.status_code == 200
    template_id = save_response.json()["template_id"]

    delete_response = client.delete(f"/api/templates/{template_id}")
    get_response = client.get(f"/api/templates/{template_id}")
    list_response = client.get("/api/templates")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
    assert template_id not in [item["template_id"] for item in list_response.json()]


def test_list_saved_demo_runs_supports_template_filter():
    client = TestClient(app)

    base_run_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "模板来源样例",
                "duration": 20,
                "shot_count": 6,
                "transcript_summary": "先讲亮点，再展示过程。",
            },
            "content": {
                "topic": "模板来源短视频",
                "product_name": "模板来源门店",
                "selling_points": ["卖点一"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
        },
    )
    normal_run_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "普通样例",
                "duration": 18,
                "shot_count": 5,
                "transcript_summary": "先给结果，再给过程。",
            },
            "content": {
                "topic": "普通短视频",
                "product_name": "普通门店",
                "selling_points": ["卖点二"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
        },
    )

    assert base_run_response.status_code == 200
    assert normal_run_response.status_code == 200

    save_template_response = client.post(
        f"/api/templates/from-run/{base_run_response.json()['run_id']}",
        json={"title": "筛选模板"},
    )
    assert save_template_response.status_code == 200
    template_id = save_template_response.json()["template_id"]

    templated_run_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "套模板样例",
                "duration": 30,
                "shot_count": 9,
                "transcript_summary": "这个样例不该决定最终结构。",
            },
            "content": {
                "topic": "模板筛选短视频",
                "product_name": "模板筛选门店",
                "selling_points": ["卖点三"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
            "template_id": template_id,
        },
    )

    assert templated_run_response.status_code == 200
    templated_run = templated_run_response.json()
    filtered_list_response = client.get("/api/runs", params={"template_id": template_id})

    assert filtered_list_response.status_code == 200
    runs = filtered_list_response.json()
    assert any(item["run_id"] == templated_run["run_id"] for item in runs)
    assert all(item["template_id"] == template_id for item in runs)


def test_update_template_changes_title_rhythm_and_slot_fields():
    client = TestClient(app)

    run_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "模板编辑来源样例",
                "duration": 20,
                "shot_count": 6,
                "transcript_summary": "先讲亮点，再展示过程。",
            },
            "content": {
                "topic": "模板编辑短视频",
                "product_name": "模板编辑门店",
                "selling_points": ["卖点一"],
                "available_assets": ["开头吸引镜头", "使用过程镜头"],
            },
        },
    )

    assert run_response.status_code == 200
    run_id = run_response.json()["run_id"]

    save_response = client.post(f"/api/templates/from-run/{run_id}", json={"title": "待编辑模板"})
    assert save_response.status_code == 200
    template = save_response.json()
    template_id = template["template_id"]

    update_response = client.patch(
        f"/api/templates/{template_id}",
        json={
            "title": "夜咖开业模板",
            "rhythm_summary": "5-7-4-4 的夜场节奏",
            "slots": [
                {"slot_id": "hook", "duration": 5.0, "required_asset": "夜景开场镜头"},
                {"slot_id": "selling_points", "duration": 7.0, "required_asset": "吧台特写镜头"},
            ],
        },
    )
    detail_response = client.get(f"/api/templates/{template_id}")

    assert update_response.status_code == 200
    assert detail_response.status_code == 200
    updated = detail_response.json()
    slot_lookup = {slot["id"]: slot for slot in updated["template"]["script_pattern"]}
    assert updated["template"]["title"] == "夜咖开业模板"
    assert updated["template"]["rhythm_summary"] == "5-7-4-4 的夜场节奏"
    assert slot_lookup["hook"]["duration"] == 5.0
    assert slot_lookup["hook"]["required_asset"] == "夜景开场镜头"
    assert slot_lookup["selling_points"]["duration"] == 7.0
    assert slot_lookup["selling_points"]["required_asset"] == "吧台特写镜头"
    assert slot_lookup["selling_points"]["start"] == 5.0

    templated_run_response = client.post(
        "/api/runs/demo",
        json={
            "sample": {
                "title": "套编辑后模板样例",
                "duration": 30,
                "shot_count": 8,
                "transcript_summary": "这个样例不该决定最终结构。",
            },
            "content": {
                "topic": "夜咖开业短视频",
                "product_name": "夜巷咖啡",
                "selling_points": ["深夜营业"],
                "available_assets": ["使用过程镜头"],
            },
            "template_id": template_id,
        },
    )

    assert templated_run_response.status_code == 200
    templated_run = templated_run_response.json()
    run_slot_lookup = {slot["id"]: slot for slot in templated_run["preview"]["template"]["script_pattern"]}
    run_gap_lookup = {gap["slot_id"]: gap for gap in templated_run["preview"]["transfer_plan"]["gaps"]}
    assert templated_run["template_title"] == "夜咖开业模板"
    assert templated_run["preview"]["template"]["rhythm_summary"] == "5-7-4-4 的夜场节奏"
    assert run_slot_lookup["hook"]["duration"] == 5.0
    assert run_slot_lookup["hook"]["required_asset"] == "夜景开场镜头"
    assert run_gap_lookup["hook"]["missing_asset"] == "夜景开场镜头"
