# Analyze Pipeline

## 目标
`analyze.py` 负责把 `ppt_video` 转成 `scenes.json`，为后续 `plan.py` 提供真实的页面切换边界。

## 当前方案
1. 使用 MoviePy 顺序解码视频。
2. 按固定采样间隔抽样，当前快速模式默认 `3.0` 秒。
3. 对采样帧做灰度缩略图签名。
4. 用相邻帧差识别换页点。
5. 输出 `slide_scenes`，每段包含：
   - `start/end`
   - `start_seconds/end_seconds`
   - `duration_seconds`
   - `page_type`
   - `average_change_score`
   - `visual_summary`

## 模式设计
### 快速模式
- 默认模式
- 仅本地分析
- 不调用模型
- 用于毕设日常演示和联调

### 增强模式
- 手动开启模型增强
- 对每个视觉段抽 1 张关键帧
- 调用 `qwen3.6-plus-2026-04-02` 补充页面语义
- 用于最终样例或需要更高语义质量的场景

## 当前实测
测试案例：
- 目录：`material/3`
- 视频：`ppt_video.mp4`
- 时长：约 10 分钟

实测耗时：
- 快速模式：约 `138s`
- 增强模式：约 `625s`

## 当前问题
1. 本地环境未安装 `ffmpeg/ffprobe`，导致无法走更高效的视频探测和抽帧路径。
2. 当前实现基于 MoviePy，适合先完成毕设，不适合高吞吐批量处理。
3. 模型增强是逐页请求，耗时非常明显。

## 后续优化优先级
1. 接入 `ffmpeg/ffprobe`
2. 允许采样间隔提升到 `5` 秒
3. 限制模型增强页数
4. 改成仅对标题页、总结页、人物页做模型增强
