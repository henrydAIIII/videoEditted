# Plan Schema

## 目标
`plan.py` 负责把 `scenes.json + subtitles.srt` 转成 `plan.json`，输出后续渲染所需的镜头计划。

## 输入
- `subtitles.srt`
- `scenes.json`

其中：
- `scenes.json` 提供视觉边界
- `subtitles.srt` 提供语义内容和叙事节奏

## 核心生成逻辑
1. 先读取 `scenes.json` 的视觉段落。
2. 按视觉段落时间范围，把字幕 cue 分配到对应页面。
3. 对每段文本做规则判断：
   - 观点关键词
   - 知识点关键词
   - 高潮/收束关键词
   - 章节切换触发词
   - 人物名、年份仅作为文本信息候选，不触发 speaker
4. 生成最终 scene：
   - `main_scene_type`
   - `transition_in`
   - `card`
   - `overlay`
   - `render_hints`

## 主要字段
### 顶层
- `plan_version`
- `job_id`
- `generated_at`
- `source`
- `rules_applied`
- `summary`
- `chapters`
- `scenes`

### `summary`
- `cue_count`
- `chapter_count`
- `scene_count`
- `duration_seconds`
- `scene_type_breakdown`
- `dominant_transitions`

### `chapters`
- `id`
- `title`
- `start`
- `end`
- `scene_ids`
- `summary`

### `scenes`
- `id`
- `chapter_id`
- `start`
- `end`
- `duration_seconds`
- `narrative_role`
- `main_scene_type`
- `transition_in`
- `speaker_cut_in`
- `headline`
- `summary`
- `transcript_excerpt`
- `source_subtitle_ids`
- `source_visual_scene_id`
- `visual_page_type`
- `visual_summary`
- `card`
- `overlay`
- `render_hints`

## Demo 规律映射
1. 观点陈述
结果：`main_scene_type = ai_card`
转场：`hard_cut`

2. 重要人物
结果：不触发 `speaker`
说明：人物名、年份可以作为后续信息卡候选，但不决定人脸出现。

3. 章节切换
结果：优先 `speaker`

4. 知识点展示
结果：优先 `ppt`
转场：默认 `hard_cut`

5. 段落高潮
结果：优先 `ai_card`
转场：`rapid_flash_cut`

## 当前定位
`plan.json` 目前是“可渲染计划草案”，不是最终逐帧时间轴。
后续 `render.py` 需要基于这个计划继续细化到实际素材调用、图层和字幕排布。

## AI Card 中间产物
规划阶段现在会额外产出两个结构化文件：

- `subtitles.json`：由 `subtitles.srt` 解析得到，保留字幕 id、开始时间、结束时间、秒数和文本。
- `ai_cards.json`：由 `subtitles.json` 生成，优先使用通义千问大模型生成短文案；没有 `DASHSCOPE_API_KEY` 时使用本地规则兜底。

`ai_cards.json` 中的卡片会按时间挂载到 `plan.json.scenes[].floating_cards`，渲染阶段直接读取该字段叠加 AI Floating Card。

`floating_cards` 单项结构：

```json
{
  "id": "card_001",
  "type": "ai_floating_card",
  "start": "00:00:08.666",
  "end": "00:00:13.666",
  "start_seconds": 8.666,
  "end_seconds": 13.666,
  "duration_seconds": 5.0,
  "title": "古希腊传统",
  "text": "西方创新源头",
  "source_subtitle_ids": [4, 5],
  "anchor": "right_upper",
  "trigger_delay_seconds": 0.5,
  "display_duration_seconds": 4.0,
  "local_start_seconds": 8.666,
  "local_end_seconds": 13.666,
  "local_duration_seconds": 5.0
}
```
