# 毕设视频合成系统 - AGENTS.md

## 项目目标
一个前后端网站，用户上传素材后，系统自动完成分析、规划、渲染，最终输出合成视频。

## 技术栈
- 前端：React + Tailwind
- 后端：FastAPI
- 视频处理：MoviePy
- 图片模型：通义千问 qwen-image-2.0-pro（dashscope SDK）
- 大语言模型：通义千问 qwen3.6-plus-2026-04-02（dashscope SDK）
- 任务队列：Celery + Redis（处理耗时任务）

## 目录结构
/frontend         React前端
/backend
  main.py         FastAPI 入口
  /routers        API路由
  /pipeline
    analyze.py    阶段一：Demo拆帧 → scenes.json
    plan.py       阶段二：SRT分析 → plan.json
    render.py     阶段三：视频合成 → output.mp4
  /tasks          Celery异步任务
/assets           素材存储
/output           成品存储

## 数据流（核心）
用户上传素材
  → 后端存储到 /assets/{job_id}/
  → 触发 Celery 任务链：
      analyze() → plan() → render()
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
2. 重要人物 → 人物出生年月，死亡日期，或者一句简短的话浮窗展示
3. 章节切换 → speaker 镜头 8-15 秒
4. speaker 期间可叠加 ai_card（graphic_overlay_cut）
5. 知识点展示 → ppt 整屏 5-10 秒
6. 段落高潮 → rapid_flash_cut 蒙太奇收束
7. 普通切换用 hard_cut

## 开发顺序（严格按此推进）
1. 搭建 FastAPI 基础框架 + 上传接口
2. 实现 pipeline/plan.py（SRT → plan.json）
3. 实现 pipeline/render.py（plan.json → output.mp4）
4. 接入 Celery 串联三个阶段
5. 实现前端三个页面
6. 联调测试

## 当前进度
- 2026-04-15：已完成步骤一。后端 FastAPI 基础框架已搭建，提供统一返回格式 `{code, data, message}`，并实现 `POST /api/upload` 上传接口，素材会写入 `assets/{job_id}/` 并生成初始任务元数据。
