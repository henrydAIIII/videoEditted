# Render Pipeline

## 目标
`render.py` 负责把 `plan.json + ppt_video + speaker_video` 合成为最终 `output.mp4`。

当前阶段优先服务毕设演示链路：稳定生成可预览、可下载的视频；卡片样式和镜头精度后续再迭代。

## 输入
- `plan.json`
- `ppt_video.*`
- `speaker_video.*`

其中：
- `plan.json` 提供镜头类型、时间范围、卡片、人物浮窗和转场提示。
- `ppt_video` 提供知识点展示画面。
- `speaker_video` 提供讲者画面，并作为默认旁白音频来源。

## 输出
- `output/{job_id}/output.mp4`
- `assets/{job_id}/job.json` 中写入：
  - `status = completed`
  - `current_stage = completed`
  - `files.output_video`
  - `rendering`

## 渲染规则
### `main_scene_type = ppt`
使用 PPT 视频在当前 scene 时间范围内的片段，按 contain 模式放入 16:9 画布，避免裁掉课件内容。

### `main_scene_type = speaker`
使用 PPT 视频作为主画面，同时把讲者视频在当前 scene 时间范围内的片段以右下角悬浮窗叠加到 PPT 页面上；不再让讲者画面整屏霸屏。

### `main_scene_type = ai_card`
生成整屏卡片画面，显示 `card.title` 和 `card.body`；没有 card 时回退到 `headline` 和 `transcript_excerpt`。

### `overlay.type = ai_card`
在非整屏卡片镜头上叠加 AI Floating Card 轻量悬浮窗，使用 `overlay.title` 与 `overlay.body`。浮窗会在 0.5 秒后自动唤起，停留 3-5 秒，并使用 ease-in-out 淡入淡出；默认右下角，speaker 场景自动放到右上角以避开讲者画面。

### `scene.floating_cards[]`
优先使用 `plan.py` 从 `ai_cards.json` 挂载到 scene 的 `floating_cards`。每张卡使用自己的 `local_start_seconds`、`display_duration_seconds`、`title`、`text` 和 `anchor` 渲染。存在 `floating_cards` 时，不再使用旧的单个 `overlay` 兜底，避免重复叠卡。

### 字幕
对非整屏卡片镜头，在底部渲染 `transcript_excerpt`，保证演示时可以跟随叙事内容。

### 转场
- `hard_cut`：直接拼接。
- `rapid_flash_cut`：在 scene 开头叠加短闪白层，作为当前快速模式下的蒙太奇提示。
- `graphic_overlay_cut`：当前由人物浮窗延迟出现体现，后续可扩展为更复杂的图形转场。

## 命令行使用
任务目录模式：

```bash
python -m pipeline.render --job-dir assets/{job_id}
```

直接路径模式：

```bash
python -m pipeline.render \
  --plan-path assets/{job_id}/plan.json \
  --ppt-video-path assets/{job_id}/ppt_video.mp4 \
  --speaker-video-path assets/{job_id}/speaker_video.mp4 \
  --output-path output/{job_id}/output.mp4
```

## 当前取舍
1. 默认分辨率为 1280x720，默认帧率为 24fps，可通过参数或环境变量调整。
2. 若 scene 时长超过对应原视频片段可用时长，会循环该片段以保证总时长可渲染。
3. 音频默认来自 `speaker_video` 的对应时间段。
4. 当前不依赖模型生成图片，符合“快速模式优先”的默认策略。
