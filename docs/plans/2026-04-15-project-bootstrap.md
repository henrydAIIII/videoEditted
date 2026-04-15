# Project Bootstrap Implementation Plan

**Goal:** Build an installable frontend/backend scaffold for the video composition project with placeholders for the timeline rendering pipeline.

**Architecture:** Use a Vite React frontend for the editor shell and a FastAPI backend for API endpoints and rendering services. Keep render-pipeline concerns split into models, schemas, services, and API routes so the future `timeline.json -> video` implementation can remain incremental.

**Tech Stack:** React, Vite, Tailwind CSS, FastAPI, Pydantic, MoviePy, pytest

---

### Task 1: Backend response contract

**Files:**
- Create: `backend/tests/test_health.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/app/core/responses.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_standard_response():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "data": {"status": "ok", "service": "video-editted-backend"},
        "message": "success",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_health.py -v`
Expected: FAIL because application files do not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {
        "code": 0,
        "data": {"status": "ok", "service": "video-editted-backend"},
        "message": "success",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_health.py -v`
Expected: PASS

### Task 2: Frontend editor shell

**Files:**
- Create: `frontend/src/pages/EditorPage.jsx`
- Create: `frontend/src/components/Timeline.jsx`
- Create: `frontend/src/components/PreviewCanvas.jsx`
- Create: `frontend/src/lib/api.js`

- [ ] **Step 1: Create the editor shell with timeline and preview placeholders**

```jsx
export default function EditorPage() {
  return <main>Editor shell</main>;
}
```

- [ ] **Step 2: Wire the shell into the Vite app entry**

Run: `cd frontend && npm run build`
Expected: PASS

### Task 3: Timeline render pipeline placeholders

**Files:**
- Create: `backend/app/models/timeline.py`
- Create: `backend/app/schemas/timeline.py`
- Create: `backend/app/services/project_service.py`
- Create: `backend/app/services/timeline_loader.py`
- Create: `backend/app/services/render_pipeline.py`

- [ ] **Step 1: Add typed placeholders for timeline data and render orchestration**

```python
class RenderPipeline:
    def render_project(self, timeline):
        raise NotImplementedError
```

- [ ] **Step 2: Keep method names aligned with API usage**

Run: `cd backend && .venv/bin/python -m compileall app`
Expected: PASS

### Task 4: Sample data and docs

**Files:**
- Create: `assets/sample_project/timeline.json`
- Create: `README.md`
- Create: `backend/.env.example`

- [ ] **Step 1: Add a sample timeline and startup instructions**

```json
{
  "project_id": "demo-project",
  "scenes": []
}
```

- [ ] **Step 2: Validate frontend and backend startup commands**

Run: `cd frontend && npm run build && cd ../backend && .venv/bin/pytest -v`
Expected: PASS
