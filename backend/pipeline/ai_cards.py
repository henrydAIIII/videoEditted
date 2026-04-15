from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

import httpx


def load_project_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_project_env()

QWEN_BASE_URL = os.getenv(
    "VIDEO_EDITTED_QWEN_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
QWEN_MODEL = os.getenv("VIDEO_EDITTED_QWEN_MODEL", "qwen3-max-2026-01-23")
QWEN_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

AI_CARDS_VERSION = "ai_cards_v1"
SUBTITLES_VERSION = "srt_to_json_v1"
DEFAULT_CARD_COUNT = 16
DEFAULT_CARD_DURATION_SECONDS = 5.0
DEFAULT_TRIGGER_DELAY_SECONDS = 0.5
DEFAULT_DISPLAY_DURATION_SECONDS = 4.0
SRT_TIME_PATTERN = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})"
)

FILLER_WORDS = (
    "大家好",
    "那么",
    "实际上",
    "这个",
    "这样",
    "的话",
    "然后",
    "所以",
    "也就是说",
    "我们可以说",
    "可以说",
    "呢",
    "啊",
    "嗯",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_text(text: Any) -> str:
    value = re.sub(r"\s+", "", str(text or ""))
    for filler in FILLER_WORDS:
        value = value.replace(filler, "")
    return value.strip("，。；：、 ")


def clamp_text(text: Any, limit: int = 15) -> str:
    value = normalize_text(text)
    if len(value) <= limit:
        return value
    return value[:limit].rstrip("，。；：、 ")


def format_seconds(seconds: float) -> str:
    total_milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def parse_srt_timecode(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, milliseconds = rest.split(",")
    return round(
        int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000,
        3,
    )


def normalize_srt_timecode(value: str) -> str:
    return value.replace(",", ".")


def parse_srt_to_subtitles(srt_path: Path) -> list[dict[str, Any]]:
    content = srt_path.read_text(encoding="utf-8-sig")
    subtitles: list[dict[str, Any]] = []

    for fallback_index, block in enumerate(re.split(r"\n\s*\n", content.strip()), start=1):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        index = fallback_index
        time_line_index = 0
        if lines[0].isdigit():
            index = int(lines[0])
            time_line_index = 1

        if time_line_index >= len(lines):
            continue

        match = SRT_TIME_PATTERN.search(lines[time_line_index])
        if match is None:
            continue

        start_raw = match.group("start")
        end_raw = match.group("end")
        start_seconds = parse_srt_timecode(start_raw)
        end_seconds = parse_srt_timecode(end_raw)
        text = " ".join(lines[time_line_index + 1 :]).strip()
        if not text:
            continue

        subtitles.append(
            {
                "id": index,
                "start": normalize_srt_timecode(start_raw),
                "end": normalize_srt_timecode(end_raw),
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "duration_seconds": round(max(0.0, end_seconds - start_seconds), 3),
                "text": text,
            }
        )

    return subtitles


def generate_subtitles_json(srt_path: Path, output_path: Path) -> dict[str, Any]:
    subtitles = parse_srt_to_subtitles(srt_path)
    if not subtitles:
        raise ValueError(f"字幕文件中未解析到有效片段: {srt_path}")

    payload = {
        "source": str(srt_path),
        "format": SUBTITLES_VERSION,
        "subtitle_count": len(subtitles),
        "subtitles": subtitles,
    }
    write_json(output_path, payload)
    return payload


def subtitle_digest(subtitles: list[dict[str, Any]]) -> str:
    lines = []
    for item in subtitles:
        lines.append(
            f"{item['id']:03d} | {item['start']} - {item['end']} | {item['text']}"
        )
    return "\n".join(lines)


def build_prompt(subtitles: list[dict[str, Any]], card_count: int) -> str:
    return f"""
请你作为视频剪辑包装文案策划，根据下面的课堂演讲字幕，生成适合 AI Floating Card 的 JSON。

目标：
- 生成 {card_count} 张轻量悬浮信息卡。
- 每张卡服务视频包装，不要复述字幕，不要像摘要报告。
- 文案要短、准、像视频成片里的提示卡。

强制要求：
- 只输出 JSON，不要输出 Markdown。
- JSON 顶层结构必须是：{{"cards": [...]}}。
- 每个 card 必须包含字段：
  id, type, start, end, start_seconds, end_seconds, duration_seconds,
  title, text, source_subtitle_ids, anchor, trigger_delay_seconds, display_duration_seconds。
- type 固定为 "ai_floating_card"。
- title 控制在 4-10 个中文字，最多 12 字。
- text 控制在 4-12 个中文字，最多 15 字。
- 不要使用“那么、实际上、这个、呢、啊、相关的、这样的一些”等口语填充词。
- 优先选择人物、概念、年份、法案、理论、关键事件、核心结论。
- source_subtitle_ids 必须来自字幕 id。
- 每张卡出现 5 秒，duration_seconds = 5.0。
- start/end 必须与 source_subtitle_ids 附近的字幕时间匹配。
- anchor 只能是 right_lower 或 right_upper；人物讲者段落或可能遮挡右下角时用 right_upper。
- trigger_delay_seconds = 0.5。
- display_duration_seconds = 4.0。
- 结果按 start_seconds 升序排列。
- 不要生成过密卡片，相邻卡片 start_seconds 至少间隔 12 秒。

字幕：
{subtitle_digest(subtitles)}
""".strip()


def call_qwen_for_cards(subtitles: list[dict[str, Any]], card_count: int) -> dict[str, Any]:
    if not QWEN_API_KEY:
        raise RuntimeError("DASHSCOPE_API_KEY is not configured")

    payload = {
        "model": QWEN_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是严格输出 JSON 的视频包装文案策划，只返回可解析 JSON。",
            },
            {"role": "user", "content": build_prompt(subtitles, card_count)},
        ],
        "temperature": 0.35,
        "response_format": {"type": "json_object"},
    }

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{QWEN_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {QWEN_API_KEY}"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return json.loads(content)


def normalize_cards(raw_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards = []
    last_start = -999.0

    for index, card in enumerate(raw_cards, start=1):
        source_ids = card.get("source_subtitle_ids") or []
        if not source_ids:
            continue

        start_seconds = float(card.get("start_seconds") or 0.0)
        if start_seconds - last_start < 8.0:
            continue

        duration = DEFAULT_CARD_DURATION_SECONDS
        end_seconds = float(card.get("end_seconds") or (start_seconds + duration))
        if end_seconds <= start_seconds:
            end_seconds = start_seconds + duration

        normalized = {
            "id": str(card.get("id") or f"card_{len(cards) + 1:03d}"),
            "type": "ai_floating_card",
            "start": str(card.get("start") or format_seconds(start_seconds)),
            "end": str(card.get("end") or format_seconds(end_seconds)),
            "start_seconds": round(start_seconds, 3),
            "end_seconds": round(end_seconds, 3),
            "duration_seconds": round(end_seconds - start_seconds, 3),
            "title": clamp_text(card.get("title"), 12),
            "text": clamp_text(card.get("text"), 15),
            "source_subtitle_ids": [int(item) for item in source_ids],
            "anchor": card.get("anchor") if card.get("anchor") in {"right_lower", "right_upper"} else "right_lower",
            "trigger_delay_seconds": DEFAULT_TRIGGER_DELAY_SECONDS,
            "display_duration_seconds": DEFAULT_DISPLAY_DURATION_SECONDS,
        }
        if not normalized["title"] or not normalized["text"]:
            continue

        cards.append(normalized)
        last_start = normalized["start_seconds"]

    for index, card in enumerate(cards, start=1):
        card["id"] = f"card_{index:03d}"
    return cards


def local_card_candidates(subtitles: list[dict[str, Any]], card_count: int) -> list[dict[str, Any]]:
    keyword_titles = (
        ("古希腊", "古希腊传统", "西方创新源头"),
        ("文艺复兴", "文艺复兴", "催生近现代科学"),
        ("东方", "东方智慧", "影响西方发明"),
        ("工业革命", "工业革命", "发明推动生产"),
        ("科学革命", "科学革命", "历史碰撞催生"),
        ("领先", "东方曾领先", "发明领先千年"),
        ("达芬奇", "达芬奇", "文艺复兴发明家"),
        ("葛洪", "葛洪旋翼", "早期飞行设想"),
        ("工程科学", "工程科学", "实验理论结合"),
        ("莫利尔", "莫利尔法案", "大学连接生产"),
        ("科学无尽", "科学无尽前沿", "政府投资科研"),
        ("贝赫多尔", "贝赫多尔法案", "促进成果转化"),
        ("名人堂", "发明家名人堂", "表彰创新贡献"),
        ("巴斯", "巴斯德象限", "基础应用并重"),
        ("阿奇舒勒", "阿奇舒勒", "TRIZ理论创始人"),
        ("阿基舒勒", "阿基舒勒", "TRIZ理论创始人"),
        ("五个层次", "五级发明层次", "原始创新最难"),
    )
    cards: list[dict[str, Any]] = []
    used_keywords: set[str] = set()
    last_start = -999.0

    for subtitle in subtitles:
        text = normalize_text(subtitle.get("text"))
        for keyword, title, body in keyword_titles:
            if keyword in used_keywords or keyword not in text:
                continue
            start_seconds = float(subtitle["start_seconds"])
            if start_seconds - last_start < 10.0:
                continue
            cards.append(
                {
                    "id": f"card_{len(cards) + 1:03d}",
                    "type": "ai_floating_card",
                    "start": format_seconds(start_seconds),
                    "end": format_seconds(start_seconds + DEFAULT_CARD_DURATION_SECONDS),
                    "start_seconds": start_seconds,
                    "end_seconds": round(start_seconds + DEFAULT_CARD_DURATION_SECONDS, 3),
                    "duration_seconds": DEFAULT_CARD_DURATION_SECONDS,
                    "title": title,
                    "text": body,
                    "source_subtitle_ids": [int(subtitle["id"])],
                    "anchor": "right_upper" if title in {"达芬奇", "阿奇舒勒", "阿基舒勒"} else "right_lower",
                    "trigger_delay_seconds": DEFAULT_TRIGGER_DELAY_SECONDS,
                    "display_duration_seconds": DEFAULT_DISPLAY_DURATION_SECONDS,
                }
            )
            used_keywords.add(keyword)
            last_start = start_seconds
            break
        if len(cards) >= card_count:
            break

    return cards


def generate_ai_cards(
    subtitles_path: Path,
    output_path: Path,
    card_count: int = DEFAULT_CARD_COUNT,
    use_model: bool = True,
) -> dict[str, Any]:
    subtitles_payload = load_json(subtitles_path)
    subtitles = subtitles_payload.get("subtitles") or []
    if not subtitles:
        raise ValueError(f"subtitles.json 中没有 subtitles: {subtitles_path}")

    generator: dict[str, Any]
    if use_model and QWEN_API_KEY:
        raw = call_qwen_for_cards(subtitles, card_count)
        cards = normalize_cards(raw.get("cards") or [])
        generator = {
            "type": "qwen",
            "model": QWEN_MODEL,
            "base_url": QWEN_BASE_URL,
        }
    else:
        cards = normalize_cards(local_card_candidates(subtitles, card_count))
        generator = {
            "type": "local_rules",
            "model": None,
            "base_url": None,
            "reason": "DASHSCOPE_API_KEY is not configured" if use_model else "model generation disabled",
        }

    payload = {
        "source": str(subtitles_path),
        "format": AI_CARDS_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": generator,
        "card_count": len(cards),
        "cards": cards,
    }
    write_json(output_path, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ai_cards.json from subtitles.json with Qwen.")
    parser.add_argument("--subtitles-path", type=Path, default=Path("output/subtitles.json"))
    parser.add_argument("--output-path", type=Path, default=Path("output/ai_cards.json"))
    parser.add_argument("--card-count", type=int, default=DEFAULT_CARD_COUNT)
    args = parser.parse_args()

    payload = generate_ai_cards(args.subtitles_path, args.output_path, args.card_count)
    print(json.dumps({"output_path": str(args.output_path), "card_count": payload["card_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
