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
   - 人物名、年份
   - 观点关键词
   - 知识点关键词
   - 高潮/收束关键词
   - 章节切换触发词
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
结果：`main_scene_type = speaker`
叠加：`overlay.type = ai_card`
叠加转场：`graphic_overlay_cut`

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
