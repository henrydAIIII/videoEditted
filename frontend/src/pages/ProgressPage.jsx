import StageTimeline from '../components/StageTimeline'

function ProgressPage({ job, onBack, onPreviewResult, statusState }) {
  if (!job) {
    return (
      <section className="status-card">
        <h2>暂无任务</h2>
        <p className="empty-copy">请先回到上传页创建一个任务。</p>
        <div className="action-row">
          <button className="primary-button" type="button" onClick={onBack}>
            返回上传页
          </button>
        </div>
      </section>
    )
  }

  return (
    <div className="status-layout">
      <section className="status-card">
        <div className="status-hero">
          <div>
            <span className="status-stage">{statusState.stage}</span>
            <h2>任务进行中</h2>
            <p className="support-copy">{statusState.message}</p>
          </div>
          <div className="stage-meta">
            <div>job_id</div>
            <strong>{job.jobId}</strong>
            <div>{statusState.updatedAt ? `最近更新 ${statusState.updatedAt}` : '等待首次刷新'}</div>
          </div>
        </div>

        <div className="progress-meter">
          <div className="progress-bar" aria-hidden="true">
            <div
              className="progress-fill"
              style={{ width: `${Math.min(statusState.progress, 100)}%` }}
            />
          </div>
          <div className="progress-caption">
            <span>流程进度</span>
            <strong>{Math.min(statusState.progress, 100)}%</strong>
          </div>
        </div>

        <StageTimeline currentStage={statusState.stage} />
      </section>

      <aside className="status-aside">
        <section className="highlight-card">
          <strong>轮询说明</strong>
          <p className="support-copy">
            页面会每 4 秒尝试读取一次任务状态，后端完成 `/api/status` 后会自动接上。
          </p>
        </section>

        <section className="highlight-card">
          <strong>当前限制</strong>
          <p className="support-copy">
            {statusState.apiAvailable
              ? '状态接口已返回数据。'
              : '当前阶段只完成了上传接口，所以这里会展示前端占位信息。'}
          </p>
        </section>

        <div className="inline-actions">
          <button className="secondary-button" type="button" onClick={onPreviewResult}>
            预览结果页壳
          </button>
          <button className="ghost-button" type="button" onClick={onBack}>
            返回上传页
          </button>
        </div>
      </aside>
    </div>
  )
}

export default ProgressPage
