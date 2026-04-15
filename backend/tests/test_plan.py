import json

from pipeline.plan import generate_plan_from_job


SRT_SAMPLE = """1
00:00:00,000 --> 00:00:03,000
这节课我们要回答创新为什么会改变世界

2
00:00:03,000 --> 00:00:07,500
关键问题是知识如何被传播并形成新的体系

3
00:00:07,500 --> 00:00:10,500
接下来我们先看达芬奇

4
00:00:10,500 --> 00:00:14,500
达芬奇在1452年出生于意大利并留下大量手稿

5
00:00:14,500 --> 00:00:19,000
然后我们看工业革命中的方法和理论如何扩散

6
00:00:19,000 --> 00:00:24,500
大量图纸公式和实验记录快速出现并不断累积
"""


def test_generate_plan_from_job_writes_plan_and_updates_metadata(tmp_path):
    job_dir = tmp_path / "assets" / "job-001"
    job_dir.mkdir(parents=True)

    (job_dir / "subtitles.srt").write_text(SRT_SAMPLE, encoding="utf-8")
    (job_dir / "job.json").write_text(
        json.dumps(
            {
                "job_id": "job-001",
                "status": "pending",
                "current_stage": "pending",
                "files": {"subtitles": "subtitles.srt"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    plan_path = generate_plan_from_job(job_dir)

    assert plan_path == job_dir / "plan.json"
    assert plan_path.exists()

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["job_id"] == "job-001"
    assert plan["plan_version"] == "2026-04-15"
    assert plan["summary"]["scene_count"] >= 3
    assert any(scene["main_scene_type"] == "speaker" for scene in plan["scenes"])
    assert any(scene["main_scene_type"] == "ai_card" for scene in plan["scenes"])
    assert any(scene["overlay"] for scene in plan["scenes"])
    assert any(scene["transition_in"] == "rapid_flash_cut" for scene in plan["scenes"])

    person_scene = next(scene for scene in plan["scenes"] if scene["overlay"])
    assert person_scene["overlay"]["transition"] == "graphic_overlay_cut"
    assert person_scene["overlay"]["title"] == "达芬奇"

    metadata = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    assert metadata["files"]["plan"] == "plan.json"
    assert metadata["planning"]["scene_count"] == plan["summary"]["scene_count"]
