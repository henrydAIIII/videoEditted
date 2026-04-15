from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

from pipeline.ai_cards import generate_ai_cards, generate_subtitles_json

PLAN_VERSION = "2026-04-15"
TARGET_BLOCK_MIN_SECONDS = 8.0
TARGET_BLOCK_MAX_SECONDS = 15.0
SMALL_BLOCK_SECONDS = 4.0

CHAPTER_MARKERS = (
    "接下来",
    "然后我们",
    "那么我们",
    "为什么说",
    "在这个过程中",
    "在近现代",
    "那么在",
    "但是呢后来",
    "而相比而言",
    "于是呢",
)

VIEWPOINT_KEYWORDS = (
    "为什么",
    "关键",
    "重要",
    "核心",
    "深刻",
    "证明",
    "证据",
    "领先",
    "赶超",
    "独创",
    "推动",
    "优势",
    "值得一提",
)

KNOWLEDGE_KEYWORDS = (
    "理论",
    "方法",
    "关系",
    "过程",
    "体系",
    "法案",
    "基础",
    "背景",
    "证据",
    "内容",
    "手稿",
    "图",
    "大学",
    "实践",
    "报告",
)

CLIMAX_KEYWORDS = (
    "大量",
    "很多很多",
    "很多",
    "各种各样",
    "等等",
    "快速",
    "逐渐",
    "不断",
    "组合",
)

FILLER_PATTERNS = (
    "大家好",
    "那么",
    "实际上",
    "这个",
    "这样",
    "的话",
    "然后",
    "所以",
    "我们可以说",
    "可以说",
)

PERSON_ALIASES = {
    "亚里士多德": ("亚里士多德", "雅士多德", "亚里斯多德"),
    "康德": ("康德",),
    "奥斯本": ("奥斯本",),
    "阿基舒勒": ("阿基舒勒", "阿奇舒勒"),
    "达芬奇": ("达芬奇",),
    "葛洪": ("葛洪",),
    "爱迪生": ("爱迪生",),
    "贝尔": ("贝尔",),
    "范内瓦·布什": ("范内瓦布什", "范内瓦"),
}

GENERIC_NAME_PATTERN = re.compile(
    r"(?:包括|比如|例如|像|尤其值得一提的实际上是|值得一提的实际上是|是|来自于)([\u4e00-\u9fff]{2,5})"
)
TIME_RANGE_PATTERN = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})"
)
YEAR_PATTERN = re.compile(r"(?<!\d)(\d{3,4})年")


@dataclass(frozen=True)
class SubtitleCue:
    index: int
    start_seconds: float
    end_seconds: float
    text: str


def parse_srt_timecode(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, milliseconds = rest.split(",")
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(milliseconds) / 1000
    )


def format_seconds(seconds: float) -> str:
    total_milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def parse_plan_timecode(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, milliseconds = rest.split(".")
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(milliseconds) / 1000
    )


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).strip()


def clean_excerpt(text: str, limit: int = 26) -> str:
    condensed = normalize_text(text)
    for filler in FILLER_PATTERNS:
        if condensed.startswith(filler):
            condensed = condensed[len(filler) :]

    condensed = condensed.strip("，。；：、 ")
    if len(condensed) <= limit:
        return condensed
    return f"{condensed[:limit].rstrip('，。；：、 ')}..."


def parse_srt_text(content: str) -> list[SubtitleCue]:
    cues: list[SubtitleCue] = []

    for block in re.split(r"\n\s*\n", content.strip()):
        lines = [line.strip("\ufeff") for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue

        try:
            index = int(lines[0])
        except ValueError:
            continue

        match = TIME_RANGE_PATTERN.match(lines[1])
        if match is None:
            continue

        text = normalize_text("".join(lines[2:]))
        cues.append(
            SubtitleCue(
                index=index,
                start_seconds=parse_srt_timecode(match.group("start")),
                end_seconds=parse_srt_timecode(match.group("end")),
                text=text,
            )
        )

    return cues


def parse_srt_file(srt_path: Path) -> list[SubtitleCue]:
    return parse_srt_text(srt_path.read_text(encoding="utf-8"))


def is_chapter_boundary(text: str) -> bool:
    normalized = normalize_text(text)
    return any(normalized.startswith(marker) for marker in CHAPTER_MARKERS)


def should_split_block(current_cues: list[SubtitleCue], next_cue: SubtitleCue) -> bool:
    block_start = current_cues[0].start_seconds
    block_end = current_cues[-1].end_seconds
    current_duration = block_end - block_start
    gap = next_cue.start_seconds - block_end

    if gap >= 1.2:
        return True

    if current_duration >= TARGET_BLOCK_MAX_SECONDS:
        return True

    if is_chapter_boundary(next_cue.text):
        return current_duration >= 6.0

    if current_duration < TARGET_BLOCK_MIN_SECONDS:
        return False

    if gap >= 0.6:
        return True

    return current_duration >= 12.0


def group_cues(cues: list[SubtitleCue]) -> list[list[SubtitleCue]]:
    if not cues:
        return []

    blocks: list[list[SubtitleCue]] = []
    current_block = [cues[0]]

    for cue in cues[1:]:
        if should_split_block(current_block, cue):
            blocks.append(current_block)
            current_block = [cue]
        else:
            current_block.append(cue)

    blocks.append(current_block)

    merged_blocks: list[list[SubtitleCue]] = []
    for block in blocks:
        duration = block[-1].end_seconds - block[0].start_seconds
        if (
            merged_blocks
            and duration < SMALL_BLOCK_SECONDS
            and not is_chapter_boundary(block[0].text)
        ):
            merged_blocks[-1].extend(block)
        else:
            merged_blocks.append(block)

    return merged_blocks


def keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def extract_years(text: str) -> list[str]:
    return YEAR_PATTERN.findall(text)


def extract_person_names(text: str) -> list[str]:
    names: list[str] = []

    for canonical_name, aliases in PERSON_ALIASES.items():
        if any(alias in text for alias in aliases):
            names.append(canonical_name)

    if names:
        return names

    for match in GENERIC_NAME_PATTERN.finditer(text):
        candidate = match.group(1)
        if candidate in {"我们", "创新", "理论", "方法", "过程", "内容", "大学"}:
            continue
        if 2 <= len(candidate) <= 4:
            names.append(candidate)

    # Preserve order while removing duplicates.
    deduped = list(dict.fromkeys(names))
    return deduped


def build_headline(text: str, names: list[str], role: str) -> str:
    if names:
        return f"{names[0]}人物卡"
    if role == "viewpoint_statement":
        return f"观点强调：{clean_excerpt(text, limit=16)}"
    if role == "climax_montage":
        return f"高潮收束：{clean_excerpt(text, limit=16)}"
    if role == "chapter_switch":
        return f"章节切换：{clean_excerpt(text, limit=16)}"
    return clean_excerpt(text, limit=18)


def choose_scene_role(
    text: str,
    duration_seconds: float,
    has_person: bool,
    is_boundary: bool,
    index: int,
    block_count: int,
) -> str:
    viewpoint_score = keyword_hits(text, VIEWPOINT_KEYWORDS)
    knowledge_score = keyword_hits(text, KNOWLEDGE_KEYWORDS)
    climax_score = keyword_hits(text, CLIMAX_KEYWORDS)

    if index == 0 or is_boundary:
        return "chapter_switch"

    if climax_score >= 2 and duration_seconds >= 6:
        return "climax_montage"

    if viewpoint_score >= 2 or ("为什么" in text and duration_seconds <= 10):
        return "viewpoint_statement"

    if knowledge_score >= 1:
        return "knowledge_point"

    if index == block_count - 1 and duration_seconds >= 8:
        return "climax_montage"

    return "knowledge_point"


def build_overlay(role: str, text: str, names: list[str], years: list[str]) -> dict[str, Any] | None:
    if role != "person_highlight":
        return None

    title = names[0] if names else "关键人物"
    facts: list[str] = []
    if years:
        facts.append(" / ".join(f"{year}年" for year in years[:2]))
    facts.append(clean_excerpt(text, limit=24))

    return {
        "type": "ai_card",
        "style": "person_fact",
        "transition": "graphic_overlay_cut",
        "anchor": "right_lower",
        "title": title,
        "body": facts[:2],
    }


def build_card(role: str, text: str, names: list[str], years: list[str]) -> dict[str, Any] | None:
    if role == "viewpoint_statement":
        return {
            "type": "ai_card",
            "style": "full_screen_quote",
            "title": clean_excerpt(text, limit=18),
            "body": [clean_excerpt(text, limit=28)],
        }

    if role == "climax_montage":
        return {
            "type": "ai_card",
            "style": "montage_summary",
            "title": clean_excerpt(text, limit=18),
            "body": [clean_excerpt(text, limit=28)],
        }

    if role == "person_highlight" and names:
        body = [clean_excerpt(text, limit=24)]
        if years:
            body.insert(0, " / ".join(f"{year}年" for year in years[:2]))
        return {
            "type": "ai_card",
            "style": "person_fact",
            "title": names[0],
            "body": body[:2],
        }

    return None


def build_render_hints(role: str, names: list[str]) -> list[str]:
    hints_by_role = {
        "chapter_switch": [
            "speaker 镜头控制在 8-15 秒，作为章节切换镜头。",
            "保留底部字幕，避免同时堆叠过多信息。",
        ],
        "viewpoint_statement": [
            "使用整屏大字 ai_card 强调核心观点。",
            "转场优先使用 hard_cut，保证结论感。",
        ],
        "person_highlight": [
            "人物名不触发 speaker，默认保留 PPT 主画面。",
            "人物信息仅作为后续文本卡片候选。",
        ],
        "knowledge_point": [
            "优先展示 ppt 整屏或知识图解，时长控制在 5-10 秒。",
            "普通段落切换默认 hard_cut。",
        ],
        "climax_montage": [
            "用 rapid_flash_cut 做段落高潮收束。",
            "内部可以拆成公式、图片、图表的快闪蒙太奇。",
        ],
    }

    hints = list(hints_by_role[role])
    if names:
        hints.append(f"人物信息围绕 {names[0]} 组织，优先展示姓名与一句简介。")
    return hints


def build_scene(
    block: list[SubtitleCue],
    chapter_id: str,
    index: int,
    block_count: int,
    start_seconds: float | None = None,
    end_seconds: float | None = None,
    primary_visual_scene: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text = "".join(cue.text for cue in block)
    scene_start_seconds = start_seconds if start_seconds is not None else block[0].start_seconds
    scene_end_seconds = end_seconds if end_seconds is not None else block[-1].end_seconds
    duration_seconds = round(scene_end_seconds - scene_start_seconds, 3)
    boundary = index == 0 or is_chapter_boundary(block[0].text)
    names = extract_person_names(text)
    years = extract_years(text)
    role = choose_scene_role(
        text=text,
        duration_seconds=duration_seconds,
        has_person=bool(names),
        is_boundary=boundary,
        index=index,
        block_count=block_count,
    )

    if role == "chapter_switch":
        main_scene_type = "speaker"
        transition_in = "hard_cut"
    elif role == "person_highlight":
        main_scene_type = "ppt"
        transition_in = "hard_cut"
    elif role == "viewpoint_statement":
        main_scene_type = "ai_card"
        transition_in = "hard_cut"
    elif role == "climax_montage":
        main_scene_type = "ai_card"
        transition_in = "rapid_flash_cut"
    else:
        main_scene_type = "ppt"
        transition_in = "hard_cut"

    if primary_visual_scene:
        visual_page_type = primary_visual_scene.get("page_type")
        if role == "knowledge_point" and visual_page_type == "title":
            transition_in = "hard_cut"
        if role == "knowledge_point" and visual_page_type == "compare":
            transition_in = "rapid_flash_cut"

    overlay = build_overlay(role, text, names, years)
    card = build_card(role, text, names, years)
    headline = build_headline(text, names, role)

    summary = {
        "chapter_switch": "章节切换段落，建议切入 speaker 镜头稳住叙事。",
        "viewpoint_statement": "观点陈述段落，建议用整屏 ai_card 做强调。",
        "person_highlight": "人物介绍段落，不触发 speaker，可作为文本信息卡候选。",
        "knowledge_point": "知识点展开段落，建议使用 ppt 或图解整屏展示。",
        "climax_montage": "段落高潮或收束段落，建议使用 rapid_flash_cut 快闪蒙太奇。",
    }[role]

    return {
        "id": f"scene_{index + 1:02d}",
        "chapter_id": chapter_id,
        "start": format_seconds(scene_start_seconds),
        "end": format_seconds(scene_end_seconds),
        "duration_seconds": duration_seconds,
        "narrative_role": role,
        "main_scene_type": main_scene_type,
        "transition_in": transition_in,
        "speaker_cut_in": main_scene_type == "speaker",
        "headline": headline,
        "summary": summary,
        "transcript_excerpt": clean_excerpt(text, limit=40),
        "source_subtitle_ids": [cue.index for cue in block],
        "source_visual_scene_id": primary_visual_scene.get("id") if primary_visual_scene else None,
        "visual_page_type": primary_visual_scene.get("page_type") if primary_visual_scene else None,
        "visual_summary": primary_visual_scene.get("visual_summary") if primary_visual_scene else None,
        "card": card,
        "overlay": overlay,
        "render_hints": build_render_hints(role, names),
    }


def assign_chapter_ids(blocks: list[dict[str, Any]]) -> list[str]:
    chapter_ids: list[str] = []
    chapter_index = 0

    for index, block in enumerate(blocks):
        cues: list[SubtitleCue] = block["cues"]
        block_boundary = index == 0 or (bool(cues) and is_chapter_boundary(cues[0].text))
        if block_boundary:
            chapter_index += 1
        chapter_ids.append(f"chapter_{chapter_index:02d}")

    return chapter_ids


def build_chapters(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chapter_scene_map: dict[str, list[dict[str, Any]]] = {}
    for scene in scenes:
        chapter_scene_map.setdefault(scene["chapter_id"], []).append(scene)

    chapters: list[dict[str, Any]] = []
    for chapter_id, chapter_scenes in chapter_scene_map.items():
        first_scene = chapter_scenes[0]
        last_scene = chapter_scenes[-1]
        chapters.append(
            {
                "id": chapter_id,
                "title": first_scene["headline"],
                "start": first_scene["start"],
                "end": last_scene["end"],
                "scene_ids": [scene["id"] for scene in chapter_scenes],
                "summary": f"围绕“{first_scene['headline']}”展开，共 {len(chapter_scenes)} 个镜头。",
            }
        )

    return chapters


def build_summary(cues: list[SubtitleCue], scenes: list[dict[str, Any]], chapters: list[dict[str, Any]]) -> dict[str, Any]:
    scene_type_counter = Counter(scene["main_scene_type"] for scene in scenes)
    transition_counter = Counter(scene["transition_in"] for scene in scenes)

    return {
        "cue_count": len(cues),
        "chapter_count": len(chapters),
        "scene_count": len(scenes),
        "duration_seconds": round(cues[-1].end_seconds - cues[0].start_seconds, 3) if cues else 0,
        "scene_type_breakdown": dict(scene_type_counter),
        "dominant_transitions": [transition for transition, _ in transition_counter.most_common(3)],
    }


def attach_ai_cards_to_scenes(
    plan: dict[str, Any],
    ai_cards_payload: dict[str, Any],
) -> dict[str, Any]:
    cards = ai_cards_payload.get("cards") or []
    if not cards:
        return plan

    for scene in plan.get("scenes", []):
        scene_start = parse_plan_timecode(scene["start"])
        scene_end = parse_plan_timecode(scene["end"])
        floating_cards = []
        for card in cards:
            card_start = float(card.get("start_seconds") or 0.0)
            card_end = float(card.get("end_seconds") or card_start)
            if card_end <= scene_start or card_start >= scene_end:
                continue
            local_start = max(0.0, card_start - scene_start)
            local_end = min(scene_end, card_end) - scene_start
            floating_cards.append(
                {
                    **card,
                    "local_start_seconds": round(local_start, 3),
                    "local_end_seconds": round(local_end, 3),
                    "local_duration_seconds": round(max(0.0, local_end - local_start), 3),
                }
            )

        if floating_cards:
            scene["floating_cards"] = floating_cards

    plan.setdefault("source", {})
    plan["source"]["ai_cards"] = "ai_cards.json"
    plan["source"]["ai_cards_path"] = ai_cards_payload.get("output_path")
    plan.setdefault("summary", {})
    plan["summary"]["ai_card_count"] = len(cards)
    return plan


def load_analysis_scenes(scenes_path: Path | None) -> list[dict[str, Any]]:
    if scenes_path is None or not scenes_path.exists():
        return []

    payload = json.loads(scenes_path.read_text(encoding="utf-8"))
    visual_scenes = payload.get("slide_scenes", [])
    normalized_scenes: list[dict[str, Any]] = []
    for scene in visual_scenes:
        normalized_scenes.append(
            {
                **scene,
                "start_seconds": scene.get("start_seconds", parse_plan_timecode(scene["start"])),
                "end_seconds": scene.get("end_seconds", parse_plan_timecode(scene["end"])),
            }
        )
    return normalized_scenes


def build_blocks_from_visual_scenes(
    cues: list[SubtitleCue],
    visual_scenes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not visual_scenes:
        return [
            {
                "cues": cue_block,
                "start_seconds": cue_block[0].start_seconds,
                "end_seconds": cue_block[-1].end_seconds,
                "visual_scene": None,
            }
            for cue_block in group_cues(cues)
        ]

    blocks: list[dict[str, Any]] = []
    for visual_scene in visual_scenes:
        start_seconds = float(visual_scene["start_seconds"])
        end_seconds = float(visual_scene["end_seconds"])
        block_cues = []
        for cue in cues:
            cue_midpoint = (cue.start_seconds + cue.end_seconds) / 2
            if start_seconds <= cue_midpoint < end_seconds:
                block_cues.append(cue)

        if not block_cues:
            continue

        blocks.append(
            {
                "cues": block_cues,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "visual_scene": visual_scene,
            }
        )

    if blocks:
        return blocks

    return [
        {
            "cues": cue_block,
            "start_seconds": cue_block[0].start_seconds,
            "end_seconds": cue_block[-1].end_seconds,
            "visual_scene": None,
        }
        for cue_block in group_cues(cues)
    ]


def generate_plan_from_srt(
    srt_path: Path,
    job_id: str | None = None,
    scenes_path: Path | None = None,
) -> dict[str, Any]:
    cues = parse_srt_file(srt_path)
    if not cues:
        raise ValueError(f"字幕文件中未解析到有效片段: {srt_path}")

    visual_scenes = load_analysis_scenes(scenes_path)
    blocks = build_blocks_from_visual_scenes(cues, visual_scenes)
    chapter_ids = assign_chapter_ids(blocks)

    scenes = [
        build_scene(
            block=block["cues"],
            chapter_id=chapter_ids[index],
            index=index,
            block_count=len(blocks),
            start_seconds=block["start_seconds"],
            end_seconds=block["end_seconds"],
            primary_visual_scene=block["visual_scene"],
        )
        for index, block in enumerate(blocks)
    ]
    chapters = build_chapters(scenes)

    return {
        "plan_version": PLAN_VERSION,
        "job_id": job_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "subtitles": srt_path.name,
            "subtitles_path": str(srt_path),
            "scenes_path": str(scenes_path) if scenes_path else None,
        },
        "rules_applied": [
            "观点陈述 -> ai_card 整屏强调",
            "人物名不触发 speaker；只作为文本信息候选",
            "视频开头或章节切换 -> speaker 镜头 8-15 秒",
            "知识点展示 -> ppt 整屏 5-10 秒",
            "高潮收束 -> rapid_flash_cut 蒙太奇",
            "普通段落 -> hard_cut",
        ],
        "summary": build_summary(cues, scenes, chapters),
        "chapters": chapters,
        "scenes": scenes,
    }


def write_plan(plan: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def load_job_metadata(job_dir: Path) -> dict[str, Any]:
    job_file = job_dir / "job.json"
    if not job_file.exists():
        return {}
    return json.loads(job_file.read_text(encoding="utf-8"))


def save_job_metadata(job_dir: Path, metadata: dict[str, Any]) -> None:
    job_file = job_dir / "job.json"
    job_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_subtitles_path(job_dir: Path, metadata: dict[str, Any]) -> Path:
    files = metadata.get("files", {})
    subtitle_name = files.get("subtitles")
    if subtitle_name:
        candidate = job_dir / subtitle_name
        if candidate.exists():
            return candidate

    candidates = sorted(job_dir.glob("subtitles.*"))
    if candidates:
        return candidates[0]

    raise FileNotFoundError(f"未在任务目录中找到字幕文件: {job_dir}")


def resolve_analysis_path(job_dir: Path, metadata: dict[str, Any]) -> Path | None:
    files = metadata.get("files", {})
    analysis_name = files.get("analysis")
    if analysis_name:
        candidate = job_dir / analysis_name
        if candidate.exists():
            return candidate

    candidate = job_dir / "scenes.json"
    if candidate.exists():
        return candidate
    return None


def generate_plan_from_job(job_dir: Path) -> Path:
    metadata = load_job_metadata(job_dir)
    subtitles_path = resolve_subtitles_path(job_dir, metadata)
    analysis_path = resolve_analysis_path(job_dir, metadata)
    subtitles_json_path = job_dir / "subtitles.json"
    ai_cards_path = job_dir / "ai_cards.json"
    subtitles_payload = generate_subtitles_json(subtitles_path, subtitles_json_path)
    ai_cards_payload = generate_ai_cards(
        subtitles_json_path,
        ai_cards_path,
        use_model=not bool(os.getenv("PYTEST_CURRENT_TEST")),
    )
    ai_cards_payload["output_path"] = str(ai_cards_path)
    plan = generate_plan_from_srt(
        subtitles_path,
        job_id=metadata.get("job_id") or job_dir.name,
        scenes_path=analysis_path,
    )
    plan = attach_ai_cards_to_scenes(plan, ai_cards_payload)
    plan_path = write_plan(plan, job_dir / "plan.json")

    metadata.setdefault("files", {})
    metadata["files"]["subtitles_json"] = subtitles_json_path.name
    metadata["files"]["ai_cards"] = ai_cards_path.name
    metadata["files"]["plan"] = plan_path.name
    metadata["planning"] = {
        "plan_version": plan["plan_version"],
        "generated_at": plan["generated_at"],
        "scene_count": plan["summary"]["scene_count"],
        "chapter_count": plan["summary"]["chapter_count"],
        "subtitle_count": subtitles_payload["subtitle_count"],
        "ai_card_count": ai_cards_payload["card_count"],
        "ai_card_generator": ai_cards_payload.get("generator"),
    }
    metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_job_metadata(job_dir, metadata)

    return plan_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate plan.json from SRT subtitles.")
    parser.add_argument("--job-dir", type=Path, help="Job directory that contains subtitles and job.json")
    parser.add_argument("--srt-path", type=Path, help="Direct subtitles path")
    parser.add_argument("--scenes-path", type=Path, help="Optional scenes.json path from analyze.py")
    parser.add_argument("--output-path", type=Path, help="Output path for plan.json when using --srt-path")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.job_dir:
        plan_path = generate_plan_from_job(args.job_dir)
        print(plan_path)
        return 0

    if args.srt_path:
        output_path = args.output_path or args.srt_path.with_name("plan.json")
        plan = generate_plan_from_srt(args.srt_path, scenes_path=args.scenes_path)
        write_plan(plan, output_path)
        print(output_path)
        return 0

    parser.error("必须提供 --job-dir 或 --srt-path")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
