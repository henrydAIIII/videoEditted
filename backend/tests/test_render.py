import json

from pipeline import render
from pipeline.render import (
    RenderConfig,
    generate_video_from_job,
    make_floating_speaker_panel_image,
    make_floating_speaker_clip,
    make_fullscreen_card_image,
    make_overlay_card_image,
    make_subtitle_image,
    scene_timing,
)
from moviepy import ColorClip


PLAN_SAMPLE = {
    "plan_version": "2026-04-15",
    "job_id": "job-001",
    "summary": {"scene_count": 2},
    "scenes": [
        {
            "id": "scene_01",
            "start": "00:00:00.000",
            "end": "00:00:03.000",
            "duration_seconds": 3.0,
            "narrative_role": "viewpoint_statement",
            "main_scene_type": "ai_card",
            "transition_in": "hard_cut",
            "headline": "观点强调",
            "transcript_excerpt": "创新为什么会改变世界",
            "card": {
                "type": "ai_card",
                "style": "full_screen_quote",
                "title": "创新为什么会改变世界",
                "body": ["关键问题是知识如何传播。"],
            },
            "overlay": None,
        },
        {
            "id": "scene_02",
            "start": "00:00:03.000",
            "end": "00:00:06.000",
            "duration_seconds": 3.0,
            "narrative_role": "person_highlight",
            "main_scene_type": "speaker",
            "transition_in": "hard_cut",
            "headline": "达芬奇人物卡",
            "transcript_excerpt": "达芬奇在1452年出生于意大利",
            "card": None,
            "overlay": {
                "type": "ai_card",
                "style": "person_fact",
                "transition": "graphic_overlay_cut",
                "anchor": "right_lower",
                "title": "达芬奇",
                "body": ["1452年", "留下大量手稿"],
            },
        },
    ],
}


def test_generate_video_from_job_writes_output_and_updates_metadata(monkeypatch, tmp_path):
    job_dir = tmp_path / "assets" / "job-001"
    job_dir.mkdir(parents=True)
    (job_dir / "plan.json").write_text(json.dumps(PLAN_SAMPLE, ensure_ascii=False), encoding="utf-8")
    (job_dir / "ppt_video.mp4").write_bytes(b"ppt-video")
    (job_dir / "speaker_video.mp4").write_bytes(b"speaker-video")
    (job_dir / "job.json").write_text(
        json.dumps(
            {
                "job_id": "job-001",
                "status": "planning",
                "current_stage": "planning",
                "files": {
                    "plan": "plan.json",
                    "ppt_video": "ppt_video.mp4",
                    "speaker_video": "speaker_video.mp4",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    def fake_render_plan_to_video(plan_path, ppt_video_path, speaker_video_path, output_path, config=None):
        assert plan_path == job_dir / "plan.json"
        assert ppt_video_path == job_dir / "ppt_video.mp4"
        assert speaker_video_path == job_dir / "speaker_video.mp4"
        assert isinstance(config, RenderConfig) or config is None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"rendered-video")
        return {
            "render_version": "test",
            "generated_at": "2026-04-15T00:00:00+00:00",
            "output_path": str(output_path),
            "scene_count": 2,
            "duration_seconds": 6.0,
            "resolution": {"width": 1280, "height": 720},
            "fps": 24,
        }

    monkeypatch.setattr(render, "render_plan_to_video", fake_render_plan_to_video)

    output_path = generate_video_from_job(job_dir, output_dir=tmp_path / "output")

    assert output_path == tmp_path / "output" / "job-001" / "output.mp4"
    assert output_path.read_bytes() == b"rendered-video"

    metadata = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert metadata["current_stage"] == "completed"
    assert metadata["files"]["output_video"] == str(output_path)
    assert metadata["rendering"]["scene_count"] == 2
    assert "error" not in metadata


def test_scene_timing_and_card_images_are_renderable():
    scene = PLAN_SAMPLE["scenes"][0]

    assert scene_timing(scene) == (0.0, 3.0, 3.0)

    full_card = make_fullscreen_card_image(scene, (640, 360))
    subtitle = make_subtitle_image(scene["transcript_excerpt"], (640, 360))
    overlay = make_overlay_card_image(PLAN_SAMPLE["scenes"][1]["overlay"], (640, 360))

    assert full_card.mode == "RGBA"
    assert full_card.size == (640, 360)
    assert subtitle.mode == "RGBA"
    assert subtitle.size[0] == 640
    assert overlay.mode == "RGBA"
    assert overlay.size[0] <= 460


def test_floating_speaker_clip_keeps_canvas_size():
    source = ColorClip(size=(720, 1280), color=(80, 80, 80), duration=1)

    floating = make_floating_speaker_clip(source, (640, 360))

    assert floating.w == 640
    assert floating.h == 360
    assert floating.duration == 1

    floating.close()
    source.close()


def test_floating_speaker_panel_is_lightweight_rgba():
    panel = make_floating_speaker_panel_image((120, 180))

    assert panel.mode == "RGBA"
    assert panel.size == (120, 180)
    assert panel.getpixel((60, 90))[3] > 0
    assert panel.getpixel((116, 176))[3] > 0
