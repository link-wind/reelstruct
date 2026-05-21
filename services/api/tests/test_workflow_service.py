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
    assert [event["step"] for event in body["trace"]] == [
        "analyze_structure",
        "transfer_structure",
        "prepare_assets",
        "render_video",
        "done",
    ]
    assert body["trace"][-1]["progress"] == 100
