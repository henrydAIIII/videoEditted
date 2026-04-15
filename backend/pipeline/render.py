from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable

from moviepy import (
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_audioclips,
    concatenate_videoclips,
)
from moviepy.audio.AudioClip import AudioClip
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RENDER_VERSION = "2026-04-15"
DEFAULT_CANVAS_WIDTH = int(os.getenv("VIDEO_EDITTED_RENDER_WIDTH", "1280"))
DEFAULT_CANVAS_HEIGHT = int(os.getenv("VIDEO_EDITTED_RENDER_HEIGHT", "720"))
DEFAULT_FPS = int(os.getenv("VIDEO_EDITTED_RENDER_FPS", "24"))
DEFAULT_MAX_OUTPUT_SECONDS = os.getenv("VIDEO_EDITTED_RENDER_MAX_SECONDS")
MIN_CLIP_SECONDS = 0.08

FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


@dataclass(frozen=True)
class RenderConfig:
    canvas_size: tuple[int, int] = (DEFAULT_CANVAS_WIDTH, DEFAULT_CANVAS_HEIGHT)
    fps: int = DEFAULT_FPS
    max_output_seconds: float | None = (
        float(DEFAULT_MAX_OUTPUT_SECONDS) if DEFAULT_MAX_OUTPUT_SECONDS else None
    )


def parse_plan_timecode(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, milliseconds = rest.split(".")
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(milliseconds) / 1000
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_font(size: int) -> ImageFont.ImageFont:
    for font_path in FONT_CANDIDATES:
        candidate = Path(font_path)
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return int(bbox[2] - bbox[0])


def wrap_text(
    text: str,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return []

    lines: list[str] = []
    current = ""
    for char in normalized:
        candidate = f"{current}{char}"
        if current and text_width(draw, candidate, font) > max_width:
            lines.append(current)
            current = char
            if len(lines) == max_lines:
                break
        else:
            current = candidate

    if len(lines) < max_lines and current:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    if lines and len(lines) == max_lines and text_width(draw, lines[-1], font) > max_width:
        while lines[-1] and text_width(draw, f"{lines[-1]}...", font) > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = f"{lines[-1]}..."

    return lines


def render_text_lines(
    draw: ImageDraw.ImageDraw,
    lines: Iterable[str],
    xy: tuple[int, int],
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    line_gap: int,
    align: str = "left",
    max_width: int | None = None,
) -> int:
    x, y = xy
    for line in lines:
        line_width = text_width(draw, line, font)
        draw_x = x
        if align == "center" and max_width is not None:
            draw_x = x + max((max_width - line_width) // 2, 0)
        draw.text((draw_x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((draw_x, y), line, font=font)
        y = int(bbox[3]) + line_gap
    return y


def make_rgba_clip(image: Image.Image, duration: float) -> ImageClip:
    return ImageClip(np.asarray(image)).with_duration(duration)


def make_fullscreen_card_image(scene: dict[str, Any], size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size, (18, 22, 28, 255))
    draw = ImageDraw.Draw(image)

    title_font = load_font(max(44, width // 20))
    body_font = load_font(max(26, width // 38))
    meta_font = load_font(max(18, width // 58))

    card_margin = width // 10
    card_width = width - card_margin * 2
    card_height = int(height * 0.58)
    card_x = card_margin
    card_y = (height - card_height) // 2

    accent = (74, 193, 161, 255)
    if scene.get("transition_in") == "rapid_flash_cut":
        accent = (237, 96, 91, 255)

    draw.rounded_rectangle(
        (card_x, card_y, card_x + card_width, card_y + card_height),
        radius=28,
        fill=(246, 248, 247, 245),
    )
    draw.rectangle((card_x, card_y, card_x + 16, card_y + card_height), fill=accent)

    card = scene.get("card") or {}
    title = card.get("title") or scene.get("headline") or "重点内容"
    body_items = card.get("body") or [scene.get("transcript_excerpt") or ""]
    body_text = " ".join(str(item) for item in body_items if item)

    max_text_width = card_width - 120
    title_lines = wrap_text(title, draw, title_font, max_text_width, 2)
    body_lines = wrap_text(body_text, draw, body_font, max_text_width, 3)

    y = card_y + 72
    render_text_lines(
        draw,
        title_lines,
        (card_x + 64, y),
        title_font,
        (21, 27, 34, 255),
        line_gap=18,
        max_width=max_text_width,
    )
    y += 160
    render_text_lines(
        draw,
        body_lines,
        (card_x + 64, y),
        body_font,
        (54, 62, 72, 255),
        line_gap=14,
        max_width=max_text_width,
    )

    role_label = str(scene.get("narrative_role") or "").replace("_", " ")
    if role_label:
        draw.text(
            (card_x + 64, card_y + card_height - 58),
            role_label.upper(),
            font=meta_font,
            fill=(91, 101, 112, 255),
        )

    return image


def make_overlay_card_image(overlay: dict[str, Any], size: tuple[int, int]) -> Image.Image:
    width, height = size
    card_width = min(460, int(width * 0.38))
    card_height = min(220, int(height * 0.32))
    image = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (0, 0, card_width - 1, card_height - 1),
        radius=18,
        fill=(248, 248, 245, 238),
        outline=(214, 218, 211, 255),
        width=2,
    )
    draw.rectangle((0, 0, 10, card_height), fill=(74, 193, 161, 255))

    title_font = load_font(34)
    body_font = load_font(22)
    label_font = load_font(16)

    title = str(overlay.get("title") or "关键人物")
    body = overlay.get("body") or []
    body_text = " ".join(str(item) for item in body if item)
    max_text_width = card_width - 64

    draw.text((34, 24), "人物信息", font=label_font, fill=(91, 101, 112, 255))
    render_text_lines(
        draw,
        wrap_text(title, draw, title_font, max_text_width, 1),
        (34, 52),
        title_font,
        (22, 28, 35, 255),
        line_gap=10,
    )
    render_text_lines(
        draw,
        wrap_text(body_text, draw, body_font, max_text_width, 3),
        (34, 104),
        body_font,
        (54, 62, 72, 255),
        line_gap=10,
    )
    return image


def make_subtitle_image(text: str, size: tuple[int, int]) -> Image.Image:
    width, height = size
    subtitle_height = max(96, int(height * 0.15))
    image = Image.new("RGBA", (width, subtitle_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = load_font(max(24, width // 44))
    max_text_width = int(width * 0.78)
    lines = wrap_text(text, draw, font, max_text_width, 2)
    if not lines:
        return image

    line_height = max(34, font.size + 8 if hasattr(font, "size") else 34)
    box_height = min(subtitle_height - 18, line_height * len(lines) + 26)
    box_width = min(width - 120, max(text_width(draw, line, font) for line in lines) + 72)
    box_x = (width - box_width) // 2
    box_y = subtitle_height - box_height - 10
    draw.rounded_rectangle(
        (box_x, box_y, box_x + box_width, box_y + box_height),
        radius=18,
        fill=(14, 17, 21, 188),
    )
    text_y = box_y + 16
    render_text_lines(
        draw,
        lines,
        (box_x + 36, text_y),
        font,
        (250, 250, 246, 255),
        line_gap=8,
        align="center",
        max_width=box_width - 72,
    )
    return image


def make_flash_image(size: tuple[int, int], alpha: int = 150) -> Image.Image:
    return Image.new("RGBA", size, (255, 255, 255, alpha))


def crop_cover(clip, size: tuple[int, int], focus_y: float = 0.5):
    target_width, target_height = size
    target_ratio = target_width / target_height
    clip_ratio = clip.w / clip.h
    if clip_ratio < target_ratio:
        resized = clip.resized(width=target_width)
    else:
        resized = clip.resized(height=target_height)
    half_height = target_height / 2
    min_center_y = half_height
    max_center_y = max(half_height, resized.h - half_height)
    y_center = min(max(resized.h * focus_y, min_center_y), max_center_y)
    return resized.cropped(
        x_center=resized.w / 2,
        y_center=y_center,
        width=target_width,
        height=target_height,
    )


def fit_contain(
    clip,
    size: tuple[int, int],
    background: tuple[int, int, int] = (16, 18, 22),
    max_scale: tuple[float, float] = (1.0, 1.0),
):
    target_width, target_height = size
    available_width = max(1, int(target_width * max_scale[0]))
    available_height = max(1, int(target_height * max_scale[1]))
    scale = min(available_width / clip.w, available_height / clip.h)
    resized = clip.resized(
        new_size=(
            max(1, int(clip.w * scale)),
            max(1, int(clip.h * scale)),
        )
    )
    base = ColorClip(size=size, color=background, duration=clip.duration)
    return CompositeVideoClip([base, resized.with_position("center")], size=size).with_duration(clip.duration)


def make_ppt_template_clip(clip, size: tuple[int, int]):
    return fit_contain(clip, size, background=(12, 14, 18))


def make_speaker_template_clip(clip, size: tuple[int, int]):
    target_width, target_height = size
    target_ratio = target_width / target_height
    clip_ratio = clip.w / clip.h

    if clip_ratio >= target_ratio * 0.85:
        return crop_cover(clip, size, focus_y=0.42).with_duration(clip.duration)

    background = crop_cover(clip, size, focus_y=0.38)
    dim_layer = ColorClip(size=size, color=(0, 0, 0), duration=clip.duration).with_opacity(0.42)
    foreground = fit_contain(
        clip,
        size,
        background=(0, 0, 0),
        max_scale=(0.72, 0.96),
    )
    foreground_only = foreground.clips[1].with_position("center")
    return CompositeVideoClip(
        [background, dim_layer, foreground_only],
        size=size,
    ).with_duration(clip.duration)


def resize_to_fit_box(clip, box_size: tuple[int, int]):
    box_width, box_height = box_size
    scale = min(box_width / clip.w, box_height / clip.h)
    return clip.resized(
        new_size=(
            max(1, int(clip.w * scale)),
            max(1, int(clip.h * scale)),
        )
    )


def make_floating_speaker_panel_image(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    shadow_offset = max(4, width // 36)
    radius = max(10, width // 18)

    draw.rounded_rectangle(
        (shadow_offset, shadow_offset, width - 1, height - 1),
        radius=radius,
        fill=(0, 0, 0, 54),
    )
    draw.rounded_rectangle(
        (0, 0, width - shadow_offset - 1, height - shadow_offset - 1),
        radius=radius,
        fill=(248, 250, 248, 238),
        outline=(255, 255, 255, 255),
        width=max(2, width // 70),
    )
    return image


def make_floating_speaker_clip(clip, size: tuple[int, int]):
    width, height = size
    margin_x = max(28, int(width * 0.035))
    margin_bottom = max(30, int(height * 0.07))
    max_box_width = int(width * 0.30)
    max_box_height = int(height * 0.46)
    speaker = resize_to_fit_box(clip, (max_box_width, max_box_height))

    padding = max(8, int(width * 0.01))
    shadow_space = max(4, int(width * 0.008))
    panel_width = speaker.w + padding * 2 + shadow_space
    panel_height = speaker.h + padding * 2 + shadow_space
    panel_x = width - panel_width - margin_x
    panel_y = height - panel_height - margin_bottom

    panel = make_rgba_clip(
        make_floating_speaker_panel_image((panel_width, panel_height)),
        clip.duration,
    )

    return CompositeVideoClip(
        [
            panel.with_position((panel_x, panel_y)),
            speaker.with_position((panel_x + padding, panel_y + padding)),
        ],
        size=size,
    ).with_duration(clip.duration)


def normalize_segment_bounds(source_duration: float, start: float, end: float) -> tuple[float, float]:
    if source_duration <= 0:
        return 0.0, 0.0
    safe_start = min(max(start, 0.0), max(source_duration - MIN_CLIP_SECONDS, 0.0))
    safe_end = min(max(end, safe_start + MIN_CLIP_SECONDS), source_duration)
    if safe_end <= safe_start:
        safe_end = min(source_duration, safe_start + MIN_CLIP_SECONDS)
    return safe_start, safe_end


def loop_media_segment(source_clip, start: float, end: float, duration: float):
    if duration <= MIN_CLIP_SECONDS:
        duration = MIN_CLIP_SECONDS

    source_duration = float(source_clip.duration or 0.0)
    safe_start, safe_end = normalize_segment_bounds(source_duration, start, end)
    segment_duration = safe_end - safe_start
    if source_duration <= 0 or segment_duration <= 0:
        return None

    if segment_duration >= duration:
        return source_clip.subclipped(safe_start, safe_start + duration)

    parts = []
    repeats = int(math.ceil(duration / segment_duration))
    for index in range(repeats):
        remaining = duration - index * segment_duration
        part_duration = min(segment_duration, remaining)
        if part_duration <= 0:
            break
        parts.append(source_clip.subclipped(safe_start, safe_start + part_duration))

    if not parts:
        return None

    concatenate = concatenate_audioclips if isinstance(source_clip, AudioClip) else concatenate_videoclips
    return concatenate(parts).with_duration(duration)


def make_source_visual_clip(
    source_clip: VideoFileClip,
    start: float,
    end: float,
    duration: float,
    size: tuple[int, int],
    mode: str,
):
    source_without_audio = source_clip.without_audio()
    segment = loop_media_segment(source_without_audio, start, end, duration)
    if segment is None:
        return ColorClip(size=size, color=(16, 18, 22), duration=duration)

    if mode == "speaker":
        return make_speaker_template_clip(segment, size).with_duration(duration)
    if mode == "cover":
        return crop_cover(segment, size).with_duration(duration)
    if mode == "ppt":
        return make_ppt_template_clip(segment, size).with_duration(duration)
    return fit_contain(segment, size).with_duration(duration)


def make_scene_audio_clip(speaker_clip: VideoFileClip, start: float, end: float, duration: float):
    if speaker_clip.audio is None:
        return None
    return loop_media_segment(speaker_clip.audio, start, end, duration)


def make_speaker_overlay_clip(
    speaker_clip: VideoFileClip,
    start: float,
    end: float,
    duration: float,
    size: tuple[int, int],
):
    source_without_audio = speaker_clip.without_audio()
    segment = loop_media_segment(source_without_audio, start, end, duration)
    if segment is None:
        return None
    return make_floating_speaker_clip(segment, size).with_duration(duration)


def scene_timing(scene: dict[str, Any]) -> tuple[float, float, float]:
    start = parse_plan_timecode(scene["start"])
    end = parse_plan_timecode(scene["end"])
    duration = float(scene.get("duration_seconds") or (end - start))
    duration = max(duration, MIN_CLIP_SECONDS)
    return start, end, duration


def make_scene_clip(
    scene: dict[str, Any],
    ppt_clip: VideoFileClip,
    speaker_clip: VideoFileClip,
    config: RenderConfig,
):
    start, end, duration = scene_timing(scene)
    size = config.canvas_size
    main_type = scene.get("main_scene_type")
    layers = []

    if main_type == "speaker":
        base = make_source_visual_clip(ppt_clip, start, end, duration, size, mode="ppt")
    elif main_type == "ppt":
        base = make_source_visual_clip(ppt_clip, start, end, duration, size, mode="ppt")
    else:
        base = ColorClip(size=size, color=(18, 22, 28), duration=duration)

    layers.append(base)

    if main_type == "speaker":
        speaker_overlay = make_speaker_overlay_clip(speaker_clip, start, end, duration, size)
        if speaker_overlay is not None:
            layers.append(speaker_overlay)

    if scene.get("transition_in") == "rapid_flash_cut":
        flash_duration = min(0.28, duration / 3)
        layers.append(make_rgba_clip(make_flash_image(size), flash_duration).with_start(0))

    if main_type == "ai_card":
        card_image = make_fullscreen_card_image(scene, size)
        layers.append(make_rgba_clip(card_image, duration))
    else:
        overlay = scene.get("overlay")
        if overlay:
            overlay_image = make_overlay_card_image(overlay, size)
            overlay_clip = make_rgba_clip(overlay_image, max(duration - 0.35, MIN_CLIP_SECONDS))
            x = size[0] - overlay_image.width - 54
            y = size[1] - overlay_image.height - 120
            layers.append(overlay_clip.with_start(min(0.35, duration / 4)).with_position((x, y)))

        subtitle_text = scene.get("transcript_excerpt") or scene.get("headline") or ""
        subtitle_image = make_subtitle_image(subtitle_text, size)
        layers.append(
            make_rgba_clip(subtitle_image, duration).with_position(
                (0, size[1] - subtitle_image.height)
            )
        )

    composite = CompositeVideoClip(layers, size=size).with_duration(duration)
    audio = make_scene_audio_clip(speaker_clip, start, end, duration)
    if audio is not None:
        composite = composite.with_audio(audio)
    return composite.with_fps(config.fps)


def render_plan_to_video(
    plan_path: Path,
    ppt_video_path: Path,
    speaker_video_path: Path,
    output_path: Path,
    config: RenderConfig | None = None,
) -> dict[str, Any]:
    config = config or RenderConfig()
    plan = load_json(plan_path)
    scenes = plan.get("scenes") or []
    if not scenes:
        raise ValueError(f"plan.json 中没有可渲染 scenes: {plan_path}")

    if config.max_output_seconds is not None:
        scenes = limit_scenes_duration(scenes, config.max_output_seconds)
        if not scenes:
            raise ValueError("max_output_seconds 过短，没有可渲染 scenes")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with VideoFileClip(str(ppt_video_path)) as ppt_clip, VideoFileClip(str(speaker_video_path)) as speaker_clip:
        scene_clips = [
            make_scene_clip(scene, ppt_clip, speaker_clip, config)
            for scene in scenes
        ]
        final_clip = concatenate_videoclips(scene_clips, method="compose").without_mask()
        final_clip.write_videofile(
            str(output_path),
            fps=config.fps,
            codec="libx264",
            audio=final_clip.audio is not None,
            audio_codec="aac" if final_clip.audio is not None else None,
            preset="veryfast",
            threads=2,
            logger=None,
            pixel_format="yuv420p",
        )
        duration = float(final_clip.duration or 0.0)
        final_clip.close()
        for clip in scene_clips:
            clip.close()

    return {
        "render_version": RENDER_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_path": str(output_path),
        "scene_count": len(scenes),
        "duration_seconds": round(duration, 3),
        "resolution": {
            "width": config.canvas_size[0],
            "height": config.canvas_size[1],
        },
        "fps": config.fps,
    }


def load_job_metadata(job_dir: Path) -> dict[str, Any]:
    job_file = job_dir / "job.json"
    if not job_file.exists():
        return {}
    return load_json(job_file)


def save_job_metadata(job_dir: Path, metadata: dict[str, Any]) -> None:
    write_json(job_dir / "job.json", metadata)


def seconds_to_plan_timecode(value: float) -> str:
    value = max(value, 0.0)
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    seconds = int(value % 60)
    milliseconds = int(round((value - int(value)) * 1000))
    if milliseconds == 1000:
        seconds += 1
        milliseconds = 0
    if seconds == 60:
        minutes += 1
        seconds = 0
    if minutes == 60:
        hours += 1
        minutes = 0
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def limit_scenes_duration(scenes: list[dict[str, Any]], max_seconds: float) -> list[dict[str, Any]]:
    limited: list[dict[str, Any]] = []
    consumed = 0.0
    for scene in scenes:
        if consumed >= max_seconds:
            break
        start, _end, duration = scene_timing(scene)
        remaining = max_seconds - consumed
        next_scene = dict(scene)
        if duration > remaining:
            duration = max(remaining, MIN_CLIP_SECONDS)
            next_scene["duration_seconds"] = round(duration, 3)
            next_scene["end"] = seconds_to_plan_timecode(start + duration)
        limited.append(next_scene)
        consumed += duration
    return limited


def resolve_file(job_dir: Path, metadata: dict[str, Any], key: str, pattern: str) -> Path:
    files = metadata.get("files", {})
    filename = files.get(key)
    if filename:
        candidate = Path(filename)
        if not candidate.is_absolute():
            candidate = job_dir / candidate
        if candidate.exists():
            return candidate

    candidates = sorted(job_dir.glob(pattern))
    if candidates:
        return candidates[0]

    raise FileNotFoundError(f"未在任务目录中找到 {key}: {job_dir}")


def resolve_output_path(job_dir: Path, metadata: dict[str, Any], output_dir: Path | None) -> Path:
    job_id = metadata.get("job_id") or job_dir.name
    if output_dir is None:
        repo_root = Path(__file__).resolve().parents[2]
        output_dir = repo_root / "output"
    return output_dir / job_id / "output.mp4"


def generate_video_from_job(
    job_dir: Path,
    output_dir: Path | None = None,
    config: RenderConfig | None = None,
) -> Path:
    metadata = load_job_metadata(job_dir)
    plan_path = resolve_file(job_dir, metadata, "plan", "plan.json")
    ppt_video_path = resolve_file(job_dir, metadata, "ppt_video", "ppt_video.*")
    speaker_video_path = resolve_file(job_dir, metadata, "speaker_video", "speaker_video.*")
    output_path = resolve_output_path(job_dir, metadata, output_dir)

    metadata["status"] = "rendering"
    metadata["current_stage"] = "rendering"
    metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_job_metadata(job_dir, metadata)

    try:
        render_result = render_plan_to_video(
            plan_path=plan_path,
            ppt_video_path=ppt_video_path,
            speaker_video_path=speaker_video_path,
            output_path=output_path,
            config=config,
        )
    except Exception as error:
        metadata["status"] = "failed"
        metadata["current_stage"] = "failed"
        metadata["error"] = str(error)
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_job_metadata(job_dir, metadata)
        raise

    metadata.setdefault("files", {})
    metadata["files"]["output_video"] = str(output_path)
    metadata["status"] = "completed"
    metadata["current_stage"] = "completed"
    metadata["rendering"] = render_result
    metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
    metadata.pop("error", None)
    save_job_metadata(job_dir, metadata)

    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render output.mp4 from plan.json and uploaded assets.")
    parser.add_argument("--job-dir", type=Path, help="Job directory that contains plan.json and uploads.")
    parser.add_argument("--output-dir", type=Path, help="Output root when using --job-dir.")
    parser.add_argument("--plan-path", type=Path, help="Direct plan.json path.")
    parser.add_argument("--ppt-video-path", type=Path, help="Direct ppt video path.")
    parser.add_argument("--speaker-video-path", type=Path, help="Direct speaker video path.")
    parser.add_argument("--output-path", type=Path, help="Direct output video path.")
    parser.add_argument("--width", type=int, default=DEFAULT_CANVAS_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_CANVAS_HEIGHT)
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS)
    parser.add_argument("--max-duration-seconds", type=float, default=DEFAULT_MAX_OUTPUT_SECONDS)
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    max_output_seconds = (
        float(args.max_duration_seconds)
        if args.max_duration_seconds not in (None, "")
        else None
    )
    config = RenderConfig(
        canvas_size=(args.width, args.height),
        fps=args.fps,
        max_output_seconds=max_output_seconds,
    )

    if args.job_dir:
        output_path = generate_video_from_job(args.job_dir, output_dir=args.output_dir, config=config)
        print(output_path)
        return 0

    required_direct_args = [
        args.plan_path,
        args.ppt_video_path,
        args.speaker_video_path,
        args.output_path,
    ]
    if all(required_direct_args):
        render_plan_to_video(
            plan_path=args.plan_path,
            ppt_video_path=args.ppt_video_path,
            speaker_video_path=args.speaker_video_path,
            output_path=args.output_path,
            config=config,
        )
        print(args.output_path)
        return 0

    parser.error("必须提供 --job-dir，或同时提供 --plan-path/--ppt-video-path/--speaker-video-path/--output-path")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
