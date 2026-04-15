# Model Runtime

## 当前模型配置
- Base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- Model: `qwen3.6-plus-2026-04-02`

## 当前用途
模型不参与整段视频逐帧分析，只在增强模式下用于关键帧理解。

## 增强模式工作方式
1. 本地先完成粗切页。
2. 每个视觉段只取 1 张关键帧。
3. 把关键帧发给 `qwen3.6-plus-2026-04-02`。
4. 要求模型输出结构化 JSON，包括：
   - `page_type`
   - `visual_summary`
   - `suggested_usage`
   - `contains_person`
   - `contains_year`
   - `contains_formula`
   - `contains_table`
   - `text_density`

## 环境变量
- `DASHSCOPE_API_KEY`
- `VIDEO_EDITTED_QWEN_BASE_URL`
- `VIDEO_EDITTED_QWEN_MODEL`
- `VIDEO_EDITTED_SAMPLE_INTERVAL_SECONDS`

## 默认取舍
毕设默认关闭模型增强，原因：
1. 耗时太长
2. 本地快速模式已经足够支撑演示
3. `plan.py` 的核心规则主要依赖字幕和页面边界，不一定需要每页都做深度语义理解

## 当前实测
案例：`material/3/ppt_video.mp4`

- 快速模式：约 `138s`
- 增强模式：约 `625s`

## 建议使用方式
1. 日常开发、联调、答辩演示：快速模式
2. 最终展示样例、论文截图材料：增强模式
3. 如果后续还要压时间，优先减少增强页数，而不是继续增加提示词复杂度
