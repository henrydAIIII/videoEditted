import { startTransition, useEffect, useEffectEvent, useState } from 'react'
import './App.css'
import { buildDownloadUrl, fetchHealth, fetchJobStatus, uploadAssets } from './lib/api'
import ProgressPage from './pages/ProgressPage'
import ResultPage from './pages/ResultPage'
import UploadPage from './pages/UploadPage'

const STAGE_PROGRESS = {
  pending: 12,
  analyzing: 34,
  planning: 62,
  rendering: 88,
  done: 100,
  failed: 100,
}

function estimateProgress(stage) {
  return STAGE_PROGRESS[stage] ?? 8
}

function App() {
  const [view, setView] = useState('upload')
  const [backend, setBackend] = useState({ loading: true, online: false, service: '', error: '' })
  const [uploading, setUploading] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [job, setJob] = useState(null)
  const [statusState, setStatusState] = useState({
    stage: 'pending',
    progress: estimateProgress('pending'),
    message: '上传完成后将在这里查看任务进度。',
    apiAvailable: true,
    updatedAt: '',
  })

  useEffect(() => {
    let cancelled = false

    async function loadHealth() {
      try {
        const response = await fetchHealth()
        if (cancelled) {
          return
        }

        setBackend({
          loading: false,
          online: true,
          service: response.data?.service ?? 'video-editted-backend',
          error: '',
        })
      } catch (error) {
        if (cancelled) {
          return
        }

        setBackend({
          loading: false,
          online: false,
          service: '',
          error: error.message,
        })
      }
    }

    loadHealth()

    return () => {
      cancelled = true
    }
  }, [])

  const pollJobStatus = useEffectEvent(async () => {
    if (!job?.jobId) {
      return
    }

    try {
      const response = await fetchJobStatus(job.jobId)

      if (!response) {
        setStatusState((current) => ({
          ...current,
          apiAvailable: false,
          message: '当前后端还没有接入状态查询接口，前端流程页已预留好位置。',
          updatedAt: new Date().toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          }),
        }))
        return
      }

      const data = response.data ?? {}
      const nextStage = data.stage ?? data.current_stage ?? data.status ?? 'pending'
      const nextProgress = data.progress ?? estimateProgress(nextStage)
      const nextMessage = data.message ?? `任务当前阶段：${nextStage}`

      setStatusState({
        stage: nextStage,
        progress: nextProgress,
        message: nextMessage,
        apiAvailable: true,
        updatedAt: new Date().toLocaleTimeString('zh-CN', {
          hour: '2-digit',
          minute: '2-digit',
        }),
      })

      if (nextStage === 'done') {
        startTransition(() => {
          setView('result')
        })
      }
    } catch (error) {
      setStatusState((current) => ({
        ...current,
        message: `状态获取失败：${error.message}`,
        updatedAt: new Date().toLocaleTimeString('zh-CN', {
          hour: '2-digit',
          minute: '2-digit',
        }),
      }))
    }
  })

  useEffect(() => {
    if (view !== 'progress' || !job?.jobId) {
      return
    }

    pollJobStatus()
    const timer = window.setInterval(() => {
      pollJobStatus()
    }, 4000)

    return () => {
      window.clearInterval(timer)
    }
  }, [job?.jobId, pollJobStatus, view])

  async function handleUploadSubmit(files) {
    setSubmitError('')
    setUploading(true)

    try {
      const response = await uploadAssets(files)
      const nextJob = {
        jobId: response.data.job_id,
      }

      setJob(nextJob)
      setStatusState({
        stage: response.data.stage ?? 'pending',
        progress: estimateProgress(response.data.stage ?? 'pending'),
        message: '素材上传成功，后续将进入分析、规划和渲染阶段。',
        apiAvailable: true,
        updatedAt: new Date().toLocaleTimeString('zh-CN', {
          hour: '2-digit',
          minute: '2-digit',
        }),
      })

      startTransition(() => {
        setView('progress')
      })
    } catch (error) {
      setSubmitError(error.message)
    } finally {
      setUploading(false)
    }
  }

  function handleRestart() {
    setJob(null)
    setSubmitError('')
    setStatusState({
      stage: 'pending',
      progress: estimateProgress('pending'),
      message: '上传完成后将在这里查看任务进度。',
      apiAvailable: true,
      updatedAt: '',
    })
    startTransition(() => {
      setView('upload')
    })
  }

  const canDownload = statusState.stage === 'done' && Boolean(job?.jobId)
  const downloadUrl = canDownload ? buildDownloadUrl(job.jobId) : ''

  return (
    <div className="shell">
      <header className="masthead">
        <div>
          <p className="eyebrow">毕设视频合成系统</p>
          <h1>把上传、编排、渲染流程先搭起来</h1>
          <p className="lede">
            当前前端先提供可联调的基础界面，后续继续接入计划生成、进度查询和成片下载。
          </p>
        </div>
        <div className="service-card">
          <span className={`service-dot ${backend.online ? 'is-online' : 'is-offline'}`} />
          <div>
            <p className="service-label">后端连接</p>
            <strong>
              {backend.loading
                ? '检测中'
                : backend.online
                  ? backend.service || '在线'
                  : '未连接'}
            </strong>
            <p className="service-hint">
              {backend.loading
                ? '正在检查 /api/health'
                : backend.online
                  ? '上传接口可用'
                  : backend.error || '请先启动 FastAPI 服务'}
            </p>
          </div>
        </div>
      </header>

      <nav className="step-nav" aria-label="流程步骤">
        {[
          ['upload', '1. 上传素材'],
          ['progress', '2. 查看进度'],
          ['result', '3. 成片结果'],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`step-tab ${view === key ? 'is-active' : ''}`}
            onClick={() => setView(key)}
            disabled={(key === 'progress' || key === 'result') && !job}
          >
            {label}
          </button>
        ))}
      </nav>

      <main className="main-panel">
        {view === 'upload' ? (
          <UploadPage
            backend={backend}
            isSubmitting={uploading}
            submitError={submitError}
            onSubmit={handleUploadSubmit}
          />
        ) : null}

        {view === 'progress' ? (
          <ProgressPage
            job={job}
            statusState={statusState}
            onBack={() => setView('upload')}
            onPreviewResult={() => setView('result')}
          />
        ) : null}

        {view === 'result' ? (
          <ResultPage
            canDownload={canDownload}
            downloadUrl={downloadUrl}
            job={job}
            stage={statusState.stage}
            onRestart={handleRestart}
            onReturnProgress={() => setView('progress')}
          />
        ) : null}
      </main>
    </div>
  )
}

export default App
