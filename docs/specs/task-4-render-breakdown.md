# 任务 4：渲染阶段细拆

## 背景

当前 `pipeline/render.py` 已经完成了最小可运行版本：可以基于 `plan.json + ppt_video + speaker_video` 生成 `output.mp4`，并更新任务元数据。

但当前实现主要解决的是“流程能跑通”，画面包装、字幕、人物浮窗、转场、音频细节和质量验收还需要继续细化。后续不再把“渲染”作为一个大任务推进，而是拆成可单独实现、单独验收的小任务。

## 总目标

把 `plan.json` 描述的剪辑计划稳定渲染成一个可演示、可预览、可下载的视频成品：

- 输入：`plan.json`、`ppt_video.*`、`speaker_video.*`
- 输出：`output/{job_id}/output.mp4`
- 状态：更新 `assets/{job_id}/job.json`
- 质量：画面可读、节奏清楚、字幕不挡内容、卡片不粗糙、转场不突兀

## 任务 4.1：渲染输入校验

### 目标

在真正开始渲染前，先保证输入数据和素材文件是可控的，避免渲染中途才失败。

### 实现内容

- 检查 `plan.json` 是否存在。
- 检查 `plan.json` 中是否存在 `scenes`。
- 检查每个 scene 是否包含：
  - `start`
  - `end`
  - `duration_seconds`
  - `main_scene_type`
- 检查 `main_scene_type` 是否属于支持范围：
  - `ppt`
  - `speaker`
  - `ai_card`
- 检查 `ppt_video.*` 是否存在并可打开。
- 检查 `speaker_video.*` 是否存在并可打开。
- 检查 scene 时间范围是否明显非法，例如结束时间早于开始时间。
- 检查 scene 时间是否超过素材时长，并根据策略处理。

### 验收标准

- 输入缺失时，渲染不会产生半成品。
- 错误原因能写入 `assets/{job_id}/job.json`。
- 失败时状态为：
  - `status = failed`
  - `current_stage = failed`
  - `error = 具体错误原因`

## 任务 4.2：时间轴组装

### 目标

先把“什么时候显示哪个画面”做准确，保证输出视频的整体节奏和 `plan.json` 一致。

### 实现内容

- 每个 scene 按 `start`、`end`、`duration_seconds` 生成片段。
- `ppt` scene 使用 PPT 视频对应时间段。
- `speaker` scene 使用讲者视频对应时间段。
- `ai_card` scene 使用生成卡片画面。
- 所有片段按 `plan.json.scenes` 的顺序拼接。
- 对素材片段不足的情况明确处理策略。

### 可选策略

- 循环素材片段。
- 冻结最后一帧。
- 直接报错并要求修正 `plan.json`。

当前快速模式优先推荐：先循环素材片段，保证演示链路稳定。

### 验收标准

- 每个 scene 的输出时长严格等于 `duration_seconds`。
- 输出总时长接近所有 scene 的 `duration_seconds` 之和。
- 不同 scene 之间不会出现明显黑屏。
- 不会因为单个片段比计划短而直接崩溃。

## 任务 4.3：基础画面模板

### 目标

把三种主画面做成可看的基础模板，先解决“像调试界面、不像视频成片”的问题。

### 4.3.1 PPT 模板

#### 实现内容

- 使用 PPT 视频作为主画面。
- 按 contain 模式放入 16:9 画布。
- 背景保持干净，避免花哨装饰。
- 不裁掉课件文字和关键图表。

#### 当前实现状态

- 已完成。
- 当前使用 contain 模式放入 16:9 画布。
- 画布背景使用干净深色底，避免非 16:9 PPT 两侧留白显得突兀。
- 不裁切 PPT 原画面。

#### 验收标准

- PPT 文字不被裁切。
- PPT 不变形。
- 画布边缘留白自然。
- 720p 下可读。

### 4.3.2 Speaker 模板

#### 实现内容

- 使用 PPT 视频作为主画面，不切走课件内容。
- 讲者视频以悬浮窗形式叠加在 PPT 页面右下角。
- 讲者悬浮窗需要完整保留人物主体，不能为了铺满而严重裁切。
- 讲者音频仍然作为默认旁白音频来源。

#### 当前实现状态

- 已完成。
- `main_scene_type = speaker` 时，渲染结果为 PPT 底图 + 右下角讲者悬浮窗。
- 不再把讲者视频整屏霸屏。
- 讲者悬浮窗使用浅色圆角面板和轻阴影，不使用突兀黑框。
- 当前 `material/3/speaker_video.mp4` 是竖屏素材，测试应重点检查右下角悬浮窗是否清楚且不遮挡 PPT 关键内容。

#### 验收标准

- 讲者画面不变形。
- 人物主体不被裁得太狠。
- 讲者悬浮窗出现在 PPT 页面右下角。
- 讲者悬浮窗不整屏霸占画面。
- 讲者悬浮窗不明显遮挡 PPT 关键内容。

#### 当前显示人脸的判断方式

系统不是通过识别人脸自动判断，而是由 `plan.py` 生成 `plan.json` 时决定：

- 视频一开始的段落，设置为 `chapter_switch` 时，使用 `main_scene_type = speaker`。
- 字幕段落识别为章节边界，设置为 `chapter_switch` 时，使用 `main_scene_type = speaker`。
- 字幕段落里识别到人物名，不再触发 `speaker`。
- 其他普通知识点段落通常设置为 `main_scene_type = ppt`。
- 渲染阶段只读取 `plan.json`，看到 `main_scene_type = speaker` 就显示右下角讲者悬浮窗。

当前规则：只在视频开头或章节边界显示讲者悬浮窗，不因为人物名自动显示人脸。

### 4.3.3 AI Card 模板

#### 实现内容

- 生成整屏观点卡。
- 展示 `card.title` 和 `card.body`。
- 没有 `card` 时回退使用 `headline` 和 `transcript_excerpt`。
- 优先适配中文大字展示。

#### 验收标准

- 标题层级明显。
- 正文不挤、不溢出。
- 留白合理。
- 画面不像网页截图或调试 UI。
- 720p 下可读，1080p 下不粗糙。

## 任务 4.4：字幕系统

### 目标

字幕要服务叙事，而不是随便贴在画面底部。它需要可读、不挡主要内容，并且和不同 scene 类型协调。

### 实现内容

- 对非整屏 `ai_card` scene 渲染字幕。
- 字幕文本优先使用 `transcript_excerpt`。
- 没有 `transcript_excerpt` 时回退使用 `headline`。
- 支持中文自动换行。
- 字幕最多显示 2 行。
- 过长内容截断，或后续在 `plan.py` 阶段拆 scene。

### 任务 4.4.1：将 SRT 字幕添加到 PPT 演讲视频

#### 目标

如果原始 PPT 演讲视频没有内嵌字幕，需要先把用户上传的 `subtitles.srt` 添加到视频画面中，生成一份带字幕的视频素材，后续渲染阶段优先使用这份带字幕版本。

#### 输入

- `ppt_video.*`
- `subtitles.srt`

#### 输出

- `ppt_video_subtitled.mp4`

建议输出位置：

```text
assets/{job_id}/ppt_video_subtitled.mp4
```

本地调试素材可以先输出到：

```text
material/{case_id}/ppt_video_subtitled.mp4
```

#### 实现内容

- 读取 `subtitles.srt`。
- 校验 SRT 时间轴是否和 `ppt_video` 时长基本对齐。
- 使用视频工具把 SRT 字幕烧录到 `ppt_video` 画面中。
- 保留原始 `ppt_video`，不要覆盖。
- 在 `job.json` 中记录新增文件：
  - `files.ppt_video_subtitled`
- 后续 `render.py` 选择 PPT 素材时，优先使用 `ppt_video_subtitled.mp4`；如果不存在，再回退使用原始 `ppt_video.*`。

#### 字幕样式建议

- 中文字体优先使用系统中文字体，例如 `STHeiti`、`PingFang`、`Songti`。
- 字幕位置放在底部，但要避免遮挡 PPT 页脚和关键内容。
- 字幕最多 2 行。
- 使用白字、黑色描边或半透明黑底。
- 字幕大小需要按视频分辨率适配，不能固定得过小。

#### 命令行参考

如果环境中有 `ffmpeg`，可以使用类似命令：

```bash
ffmpeg -i ppt_video.mp4 \
  -vf "subtitles=subtitles.srt:force_style='FontName=STHeiti,FontSize=34,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H99000000,BorderStyle=3,Outline=1,Shadow=0,MarginV=54'" \
  -c:v libx264 -preset veryfast -crf 22 \
  -c:a copy \
  ppt_video_subtitled.mp4
```

如果系统没有安装 `ffmpeg`，可以优先使用 MoviePy / imageio-ffmpeg 自带的 ffmpeg 二进制，保证项目环境内也能执行。

#### 验收标准

- 生成 `ppt_video_subtitled.mp4`。
- 原始 `ppt_video.*` 不被覆盖。
- 字幕内容和 SRT 一致。
- 字幕时间轴和语音基本同步。
- 中文能正常显示，不乱码。
- 字幕不明显遮挡 PPT 主要内容。
- 后续渲染优先使用带字幕版本。

### 验收标准

- 字幕不挡住 PPT 关键区域太多。
- 字幕不压人物脸。
- 字幕背景透明度合适。
- 中文换行自然。
- `ai_card` 整屏卡默认不额外叠字幕。

## 任务 4.5：人物浮窗 / AI Card Overlay

### 目标

人物信息浮窗要像视频包装组件，而不是网页卡片截图。

### 实现内容

- 只在 `overlay.type = ai_card` 时出现。
- 默认位置为右下角。
- 显示：
  - 人物名
  - 出生年月 / 死亡日期 / 一句简介
- 支持延迟出现。
- 后续可增加简单动画，例如淡入或滑入。

### 验收标准

- 浮窗不会压字幕。
- 浮窗不会压人物脸。
- 文字不溢出。
- 中文展示清楚。
- 和整片视觉风格一致。

## 任务 4.6：转场实现

### 目标

把 `plan.py` 给出的转场语义真正落到画面上，让不同叙事场景有不同视觉提示。

### 4.6.1 Hard Cut

#### 实现内容

- 直接切换到下一个 scene。

#### 验收标准

- 画面切换干净。
- 不引入额外黑屏。
- 音画不明显错位。

### 4.6.2 Rapid Flash Cut

#### 实现内容

- 在段落高潮或蒙太奇收束时使用。
- 在 scene 开头叠加短闪白层，或后续扩展为快速切片。

#### 验收标准

- 视觉上能和普通硬切区分。
- 闪白不刺眼。
- 不影响主体内容阅读。

### 4.6.3 Graphic Overlay Cut

#### 实现内容

- 用于讲者画面叠加信息卡。
- 当前可先通过浮窗延迟出现体现。
- 后续可扩展为更完整的图形转场。

#### 验收标准

- 视觉上能感知到信息卡进入。
- 不破坏讲者画面。
- 不导致字幕和浮窗互相覆盖。

## 任务 4.7：音频处理

### 目标

保证输出视频有稳定音频，并且每个 scene 的音频和画面时长一致。

### 实现内容

- 默认使用 `speaker_video` 的音频。
- 按 scene 时间范围截取音频。
- scene 时长超过音频片段时，采用明确策略处理。
- 没有音频时输出静音视频，不崩溃。
- 后续可加入：
  - 音频淡入淡出
  - 音量归一化
  - 背景音乐
  - scene 拼接处去爆音

### 验收标准

- 输出视频有声音。
- 音频和画面时长一致。
- 没有音频素材时仍能输出 mp4。
- scene 拼接处没有明显爆音。

## 任务 4.8：输出与任务状态

### 目标

让后端和前端能够稳定拿到渲染结果。

### 实现内容

- 输出视频到 `output/{job_id}/output.mp4`。
- 更新 `assets/{job_id}/job.json`。
- 渲染开始时写入：
  - `status = rendering`
  - `current_stage = rendering`
- 渲染成功后写入：
  - `status = completed`
  - `current_stage = completed`
  - `files.output_video`
  - `rendering`
- 渲染失败后写入：
  - `status = failed`
  - `current_stage = failed`
  - `error`

### `rendering` 字段建议结构

```json
{
  "render_version": "2026-04-15",
  "generated_at": "2026-04-15T00:00:00+00:00",
  "output_path": "output/{job_id}/output.mp4",
  "scene_count": 12,
  "duration_seconds": 96.5,
  "resolution": {
    "width": 1280,
    "height": 720
  },
  "fps": 24
}
```

### 验收标准

- 前端可以通过状态接口拿到完成状态。
- 下载接口可以找到 `files.output_video`。
- 渲染失败时能看到具体错误。
- 不会出现状态 completed 但文件不存在的情况。

## 任务 4.9：渲染质量测试

### 目标

不要只测函数返回值，要测实际输出视频是否可看。

### 自动测试

- 构造短 `plan.json`。
- 构造或准备短 `ppt_video`、`speaker_video`。
- 执行完整渲染。
- 检查 `output.mp4` 是否存在。
- 检查输出时长是否接近预期。
- 抽帧检查不是黑屏。
- 检查整屏卡片、字幕、人物浮窗图片可以正常生成。

### 手动验收

- 至少用 2-3 组样例素材跑完整渲染。
- 手动预览输出视频。
- 根据预览结果调整：
  - 字号
  - 留白
  - 卡片颜色
  - 字幕位置
  - 浮窗位置
  - 转场强度

### 验收标准

- 视频能完整播放。
- 画面没有大面积黑屏。
- 文字能看清。
- PPT 不被裁。
- 人物不严重变形。
- 字幕和浮窗不互相遮挡。

## 推荐推进顺序

当前不建议马上进入 Celery 串联。应该先把任务 4 打磨到能看，再接任务 5。

为了加速渲染测试，任务 4 阶段默认只制作前 2 分钟测试视频。完整 10 分钟版本等模板、字幕和转场稳定后再跑。

推荐顺序：

1. 任务 4.3：重做基础画面模板，尤其是 `ai_card`。
2. 任务 4.4.1：先支持把 `subtitles.srt` 烧录到 PPT 演讲视频。
3. 任务 4.4：优化字幕系统。
4. 任务 4.5：优化人物浮窗。
5. 任务 4.2：校准时间轴组装策略。
6. 任务 4.7：补音频处理细节。
7. 任务 4.6：完善转场表现。
8. 任务 4.1：补完整输入校验。
9. 任务 4.8：确认状态写入和前端接口配合。
10. 任务 4.9：增加真实渲染质量测试。

## 下一步建议

从任务 4.3 开始改，因为当前最影响观感的是基础画面模板，尤其是整屏 `ai_card`、字幕和人物浮窗的视觉质量。
