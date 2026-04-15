# 毕设视频合成系统 - AGENTS.md

## 项目目标
一个前后端网站，用户上传素材后，系统自动完成分析、规划、渲染，最终输出合成视频。

## 技术栈
- 前端：React + Tailwind
- 后端：FastAPI
- 视频处理：MoviePy
- 图片模型：通义千问 qwen-image-2.0-pro（dashscope SDK）
- 大语言模型：通义千问 qwen3.6-plus-2026-04-02（DashScope OpenAI-Compatible API）
- 任务队列：Celery + Redis（处理耗时任务）

## 目录结构
/frontend         React前端
/backend
  main.py         FastAPI 入口
  /routers        API路由
  /pipeline
    analyze.py    阶段一：Demo拆帧 → scenes.json
    plan.py       阶段二：SRT分析 + AI Card规划 → plan.json
    render.py     阶段三：视频合成 → output.mp4
  /tasks          Celery异步任务
/assets           素材存储
/output           成品存储

## 数据流（核心）
用户上传素材
  → 后端存储到 /assets/{job_id}/
  → 触发 Celery 任务链：
      analyze() → plan() → render()
      其中 plan() 内部应先生成字幕结构化 JSON，再生成 AI Card JSON，最后合并生成 plan.json
  → 前端轮询 /api/status/{job_id}
  → 完成后前端显示下载链接

## API 接口
POST /api/upload          接收素材，返回 job_id
GET  /api/status/{job_id} 返回当前阶段和进度
GET  /api/download/{job_id} 返回成品视频
所有接口统一返回格式：{code, data, message}

## 任务状态流转
待处理 → 分析中 → 规划中 → 渲染中 → 已完成 / 失败

## 前端页面
1. 上传页：拖拽上传 ppt视频、演讲视频、字幕srt
2. 进度页：实时显示当前阶段（分析中/规划中/渲染中）
3. 结果页：预览 + 下载按钮

## Demo规律（已从样例中提取，plan.py 需遵守）
1. 观点陈述 → 切整屏大字 ai_card 强调
2. 重要人物 → 生成 AI Floating Card 文案候选，人物出生年月、死亡日期或一句 10-15 字以内的短说明；人物名本身不触发 speaker
3. 视频开头 / 章节切换 → speaker 右下角悬浮叠加在 PPT 页面上，控制在 8-15 秒
4. speaker 不整屏霸屏，PPT 始终作为主画面
5. 知识点展示 → ppt 整屏 5-10 秒
6. 段落高潮 → rapid_flash_cut 蒙太奇收束
7. 普通切换用 hard_cut

## AI Card JSON 需求
AI Card 文案不能直接使用长字幕截断。`plan.py` 应先基于 `subtitles.srt` 生成结构化字幕 JSON，再结合字幕时间段生成独立的 `ai_cards.json`，供 `plan.json` 和 `render.py` 使用。

默认输出路径：
- `assets/{job_id}/subtitles.json`
- `assets/{job_id}/ai_cards.json`

当前本地样例可输出到：
- `output/subtitles.json`
- `output/ai_cards.json`

`subtitles.json` 最小结构：
```json
{
  "subtitle_count": 337,
  "subtitles": [
    {
      "id": 1,
      "start": "00:00:01.300",
      "end": "00:00:04.300",
      "start_seconds": 1.3,
      "end_seconds": 4.3,
      "duration_seconds": 3.0,
      "text": "大家好那么我们今天呢"
    }
  ]
}
```

`ai_cards.json` 最小结构：
```json
{
  "card_count": 1,
  "cards": [
    {
      "id": "card_001",
      "type": "ai_floating_card",
      "start": "00:08:51.000",
      "end": "00:08:56.000",
      "start_seconds": 531.0,
      "end_seconds": 536.0,
      "duration_seconds": 5.0,
      "title": "阿基舒勒",
      "text": "创新方法诞生",
      "source_subtitle_ids": [289, 290, 291],
      "anchor": "right_upper",
      "trigger_delay_seconds": 0.5,
      "display_duration_seconds": 4.0
    }
  ]
}
```

AI Card 文案规则：
- `title` 控制在 10-15 字以内。
- `text` 控制在 10-15 字以内。
- 优先抽取人物、概念、年份、关键事件和结论。
- 去掉“那么、实际上、呢、啊、这个、相关的”等口语填充词。
- 可使用通义千问大语言模型总结，但默认流程必须保留本地规则兜底。
- 渲染阶段只做展示、截断和兜底，不在渲染时调用大模型。

## 默认策略
1. 毕设默认走“快速模式优先”：
   - 先用本地粗切页生成 `scenes.json`
   - 再结合 `subtitles.srt` 生成 `plan.json`
   - 模型增强保留为可选能力，不作为默认执行路径
2. 先保证流程稳定、能演示、能联调，再考虑进一步优化精度和速度
3. 具体实现细节、运行参数和耗时记录不放在本文件，统一拆到 `docs/specs/`

## 详细文档
- 分析阶段方案：`docs/specs/analyze-pipeline.md`
- 规划阶段与 `plan.json` 结构：`docs/specs/plan-schema.md`
- 渲染阶段方案：`docs/specs/render-pipeline.md`
- 渲染阶段细拆与验收：`docs/specs/task-4-render-breakdown.md`
- 模型运行配置与成本/耗时取舍：`docs/specs/model-runtime.md`

## 开发顺序（严格按此推进）
1. 搭建 FastAPI 基础框架 + 上传接口
2. 实现 pipeline/analyze.py（ppt_video → scenes.json，本地分析 + 可选模型增强）
3. 实现 pipeline/plan.py（scenes.json + SRT → subtitles.json + ai_cards.json + plan.json）
4. 实现 pipeline/render.py（plan.json → output.mp4）
5. 接入 Celery 串联三个阶段
6. 实现前端三个页面
7. 联调测试

## 当前进度
- 2026-04-15：已完成步骤 1。后端 FastAPI 基础框架已搭建，提供统一返回格式 `{code, data, message}`，并实现 `POST /api/upload` 上传接口，素材会写入 `assets/{job_id}/` 并生成初始任务元数据。
- 2026-04-15：已完成步骤 2。已实现 `pipeline/analyze.py`，支持对 `ppt_video` 做本地换页分析，并预留 `qwen3.6-plus-2026-04-02` 的可选关键帧语义增强。
- 2026-04-15：已完成步骤 3。已实现 `pipeline/plan.py` 与 `scenes.json` 联动，当前可以基于 `ppt_video + subtitles.srt` 生成新的 `plan.json`。
- 2026-04-15：已完成步骤 4。已实现 `pipeline/render.py`，可基于 `plan.json + ppt_video + speaker_video` 生成 `output/{job_id}/output.mp4`，并更新任务元数据。
- 2026-04-15：已完成任务 4.3.1 PPT 模板。PPT 画面按 contain 模式放入 16:9 画布，不裁切课件内容。
- 2026-04-15：已完成任务 4.3.2 Speaker 模板。speaker 仅在视频开头或章节边界出现，并以右下角浅色圆角悬浮窗叠加在 PPT 页面上，不再整屏霸屏；人物名不触发 speaker。
- 2026-04-15：已实现 AI Floating Card 的正式中间产物链路：`plan.py` 会生成 `subtitles.json` 与 `ai_cards.json`，有 `DASHSCOPE_API_KEY` 时调用通义千问生成短文案，没有密钥时使用本地规则兜底；生成的卡片会挂载到 `plan.json.scenes[].floating_cards`，`render.py` 会按时间叠加渲染。
- 2026-04-15：当前累计已完成开发步骤 1-4，下一步应进入步骤 5：接入 Celery 串联 analyze → plan → render。
- 2026-04-15：毕设默认工作流已调整为“快速模式优先”，即本地粗切页 + 字幕规划；模型增强保留为可选能力，不作为默认执行路径。
