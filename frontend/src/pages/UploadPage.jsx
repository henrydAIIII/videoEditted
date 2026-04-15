import { useState } from 'react'
import FileField from '../components/FileField'

function UploadPage({ backend, isSubmitting, onSubmit, submitError }) {
  const [files, setFiles] = useState({
    pptVideo: null,
    speakerVideo: null,
    subtitles: null,
  })

  function updateFile(key, file) {
    setFiles((current) => ({
      ...current,
      [key]: file,
    }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    onSubmit(files)
  }

  const allReady = files.pptVideo && files.speakerVideo && files.subtitles

  return (
    <div className="page-grid">
      <section className="panel">
        <h2>上传素材</h2>
        <p className="panel-intro">
          先把 PPT 视频、演讲视频和字幕传上来，后端会为这次合成创建一个独立任务目录。
        </p>

        <form onSubmit={handleSubmit}>
          <div className="upload-grid">
            <FileField
              accept="video/*"
              file={files.pptVideo}
              hint="支持 mp4、mov，作为知识点整屏素材。"
              label="PPT 视频"
              onChange={(file) => updateFile('pptVideo', file)}
            />
            <FileField
              accept="video/*"
              file={files.speakerVideo}
              hint="演讲人口播视频，将作为章节切换和 speaker 段素材。"
              label="演讲视频"
              onChange={(file) => updateFile('speakerVideo', file)}
            />
            <FileField
              accept=".srt"
              file={files.subtitles}
              hint="标准 SRT 字幕文件，下一步会用于生成 plan.json。"
              label="字幕文件"
              onChange={(file) => updateFile('subtitles', file)}
            />
          </div>

          <div className="action-row">
            <button
              className="primary-button"
              disabled={!allReady || isSubmitting}
              type="submit"
            >
              {isSubmitting ? '上传中...' : '开始创建任务'}
            </button>
            <button
              className="ghost-button"
              disabled={isSubmitting}
              type="button"
              onClick={() =>
                setFiles({
                  pptVideo: null,
                  speakerVideo: null,
                  subtitles: null,
                })
              }
            >
              清空选择
            </button>
          </div>
        </form>

        {submitError ? <div className="error-banner">{submitError}</div> : null}
      </section>

      <aside className="highlight-stack">
        <section className="highlight-card">
          <strong>当前联调状态</strong>
          <p className="support-copy">
            {backend.online
              ? '健康检查和上传接口已经可用，可以直接和 FastAPI 联调。'
              : '前端已经就绪，但需要先启动后端服务才能真正上传。'}
          </p>
        </section>

        <section className="highlight-card">
          <strong>后续接口预留</strong>
          <ol>
            <li>`/api/status/{'{job_id}'}` 会驱动进度页轮询。</li>
            <li>`/api/download/{'{job_id}'}` 接通后，结果页可直接下载成片。</li>
            <li>Celery 接入后，这个流程壳不需要再重写。</li>
          </ol>
        </section>

        <section className="highlight-card">
          <strong>当前上传规则</strong>
          <p className="support-copy">
            前端表单字段已经和后端保持一致：`ppt_video`、`speaker_video`、`subtitles`。
          </p>
        </section>
      </aside>
    </div>
  )
}

export default UploadPage
