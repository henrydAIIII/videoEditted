function ResultPage({ canDownload, downloadUrl, job, onRestart, onReturnProgress, stage }) {
  return (
    <div className="result-layout">
      <section className="preview-frame">
        <div className="preview-placeholder">
          <span className="placeholder-chip">Result Preview</span>
          <strong>这里预留成片预览区</strong>
          <p className="placeholder-note">
            后续接入下载与媒体流后，可以在这里放视频播放器、镜头摘要和生成日志。
          </p>
        </div>

        <div>
          <div>当前阶段：{stage}</div>
          <div>{job?.jobId ? `任务号：${job.jobId}` : '尚未生成任务'}</div>
        </div>
      </section>

      <aside className="result-card">
        <h2>结果页占位</h2>
        <p className="result-copy">
          这个页面已经为最终的“预览 + 下载”结构预留完成。只要后端补上状态和下载接口，就可以直接联调。
        </p>

        <div className="result-meta">
          <div className="highlight-card">
            <strong>后续接入点</strong>
            <ol className="result-list">
              <li>渲染完成后在这里展示 output.mp4。</li>
              <li>下载按钮会直连 `/api/download/{'{job_id}'}`。</li>
              <li>还可以补充镜头摘要和 plan.json 概览。</li>
            </ol>
          </div>

          <div className="inline-actions">
            <a
              className={`primary-button ${canDownload ? '' : 'is-disabled'}`}
              href={canDownload ? downloadUrl : undefined}
              onClick={(event) => {
                if (!canDownload) {
                  event.preventDefault()
                }
              }}
            >
              {canDownload ? '下载成片' : '等待下载接口'}
            </a>
            <button className="secondary-button" type="button" onClick={onReturnProgress}>
              返回进度页
            </button>
            <button className="ghost-button" type="button" onClick={onRestart}>
              新建任务
            </button>
          </div>
        </div>
      </aside>
    </div>
  )
}

export default ResultPage
