const STAGES = [
  {
    key: 'pending',
    title: '素材入库',
    description: '上传文件并生成 job_id，等待异步流程启动。',
  },
  {
    key: 'analyzing',
    title: '分析中',
    description: '拆分镜头并提取后续规划需要的结构信息。',
  },
  {
    key: 'planning',
    title: '规划中',
    description: '根据 SRT 和 Demo 规律生成 plan.json。',
  },
  {
    key: 'rendering',
    title: '渲染中',
    description: '按计划合成镜头、字幕、ai_card 和输出视频。',
  },
  {
    key: 'done',
    title: '已完成',
    description: '输出成片并提供下载入口。',
  },
]

function StageTimeline({ currentStage }) {
  const currentIndex = Math.max(
    STAGES.findIndex((stage) => stage.key === currentStage),
    0,
  )

  return (
    <div className="stage-list">
      {STAGES.map((stage, index) => {
        const itemClassName =
          index < currentIndex
            ? 'stage-item is-complete'
            : index === currentIndex
              ? 'stage-item is-current'
              : 'stage-item'

        return (
          <article key={stage.key} className={itemClassName}>
            <div className="stage-marker">{index + 1}</div>
            <div>
              <h3>{stage.title}</h3>
              <p className="timeline-note">{stage.description}</p>
            </div>
          </article>
        )
      })}
    </div>
  )
}

export default StageTimeline
