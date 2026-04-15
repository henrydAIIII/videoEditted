from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import statistics
import tempfile
import time
from typing import Any

import httpx
from moviepy import VideoFileClip
import numpy as np
from PIL import Image

QWEN_BASE_URL = os.getenv(
    "VIDEO_EDITTED_QWEN_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
QWEN_MODEL = os.getenv(
    "VIDEO_EDITTED_QWEN_MODEL",
    "qwen3.6-plus-2026-04-02",
)
QWEN_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

DEFAULT_SAMPLE_INTERVAL_SECONDS = 1.0
DEFAULT_MIN_SCENE_SECONDS = 3.0
DEFAULT_SIGNATURE_WIDTH = 48
DEFAULT_SIGNATURE_HEIGHT = 27
FAST_SAMPLE_INTERVAL_SECONDS = float(os.getenv("VIDEO_EDITTED_SAMPLE_INTERVAL_SECONDS", "3.0"))


@dataclass(frozen=True)
class FrameSample:
    time_seconds: float
    signature: np.ndarray
    change_score: float


def format_seconds(seconds: float) -> str:
    total_milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def build_signature(frame: np.ndarray) -> np.ndarray:
    image = Image.fromarray(frame.astype("uint8"))
    grayscale = image.convert("L")
    thumbnail = grayscale.resize(
        (DEFAULT_SIGNATURE_WIDTH, DEFAULT_SIGNATURE_HEIGHT),
        Image.Resampling.BILINEAR,
    )
    signature = np.asarray(thumbnail, dtype=np.float32) / 255.0
    return signature


def score_change(previous_signature: np.ndarray | None, current_signature: np.ndarray) -> float:
    if previous_signature is None:
        return 1.0
    return float(np.mean(np.abs(current_signature - previous_signature)))


def sample_video(video_path: Path, sample_interval_seconds: float = FAST_SAMPLE_INTERVAL_SECONDS) -> tuple[list[FrameSample], float]:
    samples: list[FrameSample] = []
    previous_signature: np.ndarray | None = None

    with VideoFileClip(str(video_path), audio=False) as clip:
        duration_seconds = float(clip.duration or 0.0)
        if duration_seconds <= 0:
            return samples, 0.0

        sample_fps = max(0.1, 1.0 / sample_interval_seconds)
        for index, frame in enumerate(clip.iter_frames(fps=sample_fps, dtype="uint8")):
            time_seconds = min(index * sample_interval_seconds, duration_seconds)
            signature = build_signature(frame)
            change_score = score_change(previous_signature, signature)
            samples.append(
                FrameSample(
                    time_seconds=time_seconds,
                    signature=signature,
                    change_score=change_score,
                )
            )
            previous_signature = signature

    return samples, duration_seconds


def detect_change_points(samples: list[FrameSample], min_scene_seconds: float = DEFAULT_MIN_SCENE_SECONDS) -> list[int]:
    if len(samples) <= 1:
        return [0]

    scores = [sample.change_score for sample in samples[1:]]
    median_score = statistics.median(scores)
    stdev_score = statistics.pstdev(scores) if len(scores) > 1 else 0.0
    threshold = max(0.08, median_score + stdev_score * 1.5)

    change_points = [0]
    for index, sample in enumerate(samples[1:], start=1):
        previous_index = change_points[-1]
        elapsed = sample.time_seconds - samples[previous_index].time_seconds
        if sample.change_score >= threshold and elapsed >= min_scene_seconds:
            change_points.append(index)

    return change_points


def extract_scene_frames(
    video_path: Path,
    scene_boundaries: list[tuple[float, float]],
    output_dir: Path | None = None,
) -> list[Path]:
    frame_paths: list[Path] = []
    if not scene_boundaries:
        return frame_paths

    target_dir = output_dir or Path(tempfile.mkdtemp(prefix="video_editted_keyframes_"))
    target_dir.mkdir(parents=True, exist_ok=True)

    with VideoFileClip(str(video_path), audio=False) as clip:
        duration = float(clip.duration or 0.0)
        for index, (start_seconds, end_seconds) in enumerate(scene_boundaries, start=1):
            capture_time = min((start_seconds + end_seconds) / 2, max(duration - 0.001, 0.0))
            frame = clip.get_frame(capture_time)
            frame_path = target_dir / f"scene_{index:03d}.jpg"
            Image.fromarray(frame.astype("uint8")).save(frame_path, format="JPEG", quality=85)
            frame_paths.append(frame_path)

    return frame_paths


def call_qwen_visual(frame_path: Path) -> dict[str, Any] | None:
    if not QWEN_API_KEY:
        return None

    prompt = (
        "你是视频编辑分析助手。请根据这张PPT视频关键帧，输出严格JSON，字段包括："
        "page_type, visual_summary, suggested_usage, contains_person, contains_year, contains_formula, "
        "contains_table, text_density。page_type 只能是 title/person/knowledge/compare/summary/other。"
    )

    import base64

    image_base64 = base64.b64encode(frame_path.read_bytes()).decode("utf-8")
    payload = {
        "model": QWEN_MODEL,
        "messages": [
            {"role": "system", "content": "你是一个严格输出JSON的多模态视频分析助手。"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                    },
                ],
            },
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            f"{QWEN_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {QWEN_API_KEY}"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    if isinstance(content, list):
        text = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    else:
        text = str(content)
    return json.loads(text)


def enrich_scenes_with_qwen(
    scenes: list[dict[str, Any]],
    video_path: Path,
    keyframe_dir: Path | None = None,
) -> dict[str, Any]:
    scene_boundaries = [(scene["start_seconds"], scene["end_seconds"]) for scene in scenes]
    frame_paths = extract_scene_frames(video_path, scene_boundaries, output_dir=keyframe_dir)

    enriched_count = 0
    for scene, frame_path in zip(scenes, frame_paths):
        try:
            result = call_qwen_visual(frame_path)
        except Exception as error:  # pragma: no cover - network path
            scene["model_error"] = str(error)
            continue

        if not result:
            continue

        enriched_count += 1
        scene["model_tags"] = result
        scene["visual_summary"] = result.get("visual_summary") or scene["visual_summary"]
        scene["page_type"] = result.get("page_type") or scene["page_type"]

    return {
        "enabled": bool(QWEN_API_KEY),
        "model": QWEN_MODEL,
        "base_url": QWEN_BASE_URL,
        "enriched_scene_count": enriched_count,
    }


def infer_page_type(duration_seconds: float, change_score: float) -> str:
    if duration_seconds <= 4.0:
        return "transition"
    if duration_seconds >= 14.0 and change_score < 0.12:
        return "title"
    if change_score >= 0.22:
        return "compare"
    if duration_seconds >= 10.0:
        return "knowledge"
    return "other"


def build_visual_summary(page_type: str, duration_seconds: float, change_score: float) -> str:
    if page_type == "title":
        return "页面停留时间较长，适合作为标题页或章节承接页。"
    if page_type == "compare":
        return "页面变化幅度较大，可能包含多元素对比或复杂图文布局。"
    if page_type == "knowledge":
        return "页面停留稳定，适合作为知识点或图解展示页。"
    if page_type == "transition":
        return "页面停留较短，更像过渡页或切页瞬间。"
    return f"页面停留约 {duration_seconds:.1f} 秒，变化分数 {change_score:.3f}。"


def build_scenes(samples: list[FrameSample], duration_seconds: float) -> list[dict[str, Any]]:
    if not samples:
        return []

    change_points = detect_change_points(samples)
    scenes: list[dict[str, Any]] = []

    for index, start_sample_index in enumerate(change_points):
        end_sample_index = change_points[index + 1] if index + 1 < len(change_points) else len(samples)
        block = samples[start_sample_index:end_sample_index]
        if not block:
            continue

        start_seconds = block[0].time_seconds
        if end_sample_index < len(samples):
            end_seconds = samples[end_sample_index].time_seconds
        else:
            end_seconds = duration_seconds

        duration = max(end_seconds - start_seconds, DEFAULT_SAMPLE_INTERVAL_SECONDS)
        average_change = float(sum(sample.change_score for sample in block[1:]) / max(len(block) - 1, 1))
        page_type = infer_page_type(duration, average_change)

        scenes.append(
            {
                "id": f"visual_scene_{index + 1:03d}",
                "start": format_seconds(start_seconds),
                "end": format_seconds(end_seconds),
                "start_seconds": round(start_seconds, 3),
                "end_seconds": round(end_seconds, 3),
                "duration_seconds": round(duration, 3),
                "page_index": index + 1,
                "page_type": page_type,
                "average_change_score": round(average_change, 4),
                "sample_count": len(block),
                "visual_summary": build_visual_summary(page_type, duration, average_change),
            }
        )

    return scenes


def build_summary(scenes: list[dict[str, Any]], duration_seconds: float, sample_interval_seconds: float, sampled_frame_count: int) -> dict[str, Any]:
    page_type_counts: dict[str, int] = {}
    for scene in scenes:
        page_type_counts[scene["page_type"]] = page_type_counts.get(scene["page_type"], 0) + 1

    return {
        "duration_seconds": round(duration_seconds, 3),
        "sample_interval_seconds": sample_interval_seconds,
        "sampled_frame_count": sampled_frame_count,
        "scene_count": len(scenes),
        "page_type_breakdown": page_type_counts,
    }


def generate_analysis(video_path: Path, enable_model_enrichment: bool = False) -> dict[str, Any]:
    started_at = time.perf_counter()
    samples, duration_seconds = sample_video(video_path)
    scenes = build_scenes(samples, duration_seconds)

    model_enrichment = {
        "enabled": False,
        "model": QWEN_MODEL,
        "base_url": QWEN_BASE_URL,
        "enriched_scene_count": 0,
        "reason": "DASHSCOPE_API_KEY is not configured",
    }
    if enable_model_enrichment and QWEN_API_KEY:
        model_enrichment = enrich_scenes_with_qwen(scenes, video_path)
    elif enable_model_enrichment and not QWEN_API_KEY:
        model_enrichment["enabled"] = False

    elapsed_seconds = time.perf_counter() - started_at
    return {
        "analysis_version": "2026-04-15",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_video": str(video_path),
        "summary": build_summary(
            scenes=scenes,
            duration_seconds=duration_seconds,
            sample_interval_seconds=FAST_SAMPLE_INTERVAL_SECONDS,
            sampled_frame_count=len(samples),
        ),
        "model_enrichment": model_enrichment,
        "timing": {"elapsed_seconds": round(elapsed_seconds, 3)},
        "slide_scenes": scenes,
    }


def write_analysis(analysis: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze ppt video and generate scenes.json.")
    parser.add_argument("--video-path", type=Path, required=True, help="Path to ppt_video.mp4")
    parser.add_argument("--output-path", type=Path, required=True, help="Path to output scenes.json")
    parser.add_argument(
        "--enable-model-enrichment",
        action="store_true",
        help="Enable Qwen visual understanding for keyframes.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    analysis = generate_analysis(
        video_path=args.video_path,
        enable_model_enrichment=args.enable_model_enrichment,
    )
    output_path = write_analysis(analysis, args.output_path)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
