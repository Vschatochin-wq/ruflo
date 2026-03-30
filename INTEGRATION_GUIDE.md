# Opus 4.6 Integration Guide — 8D-Report-KI

## Overview

This package adds **Opus 4.6 quality review**, **workflow state machine**, **in-app notifications**, **unified AI routing**, and **TAD document upload with OCR** to the 8D-Report-KI system.

## Files Created

### Backend (copy to `backend/`)

| File | Purpose |
|------|---------|
| `review_service.py` | Opus 4.6 review engine — evaluates 8D reports for completeness, consistency, plausibility |
| `review_endpoints.py` | FastAPI router for review, approve, reject endpoints |
| `workflow_service.py` | Status state machine with guards, role checks, notifications |
| `notification_service.py` | In-app notification service with WebSocket support |
| `ai_service.py` | Unified Sonnet 4 + Opus 4.6 routing with fallbacks |
| `upload_service.py` | Document upload, storage, validation, metadata management |
| `upload_endpoints.py` | FastAPI router for upload, OCR trigger, field mapping |
| `ocr_service.py` | OCR text extraction (Tesseract + pdfplumber) and 8D field mapping |

### Frontend (copy to `frontend/src/`)

| File | Target Path | Purpose |
|------|-------------|---------|
| `OpusReviewPanel.js` | `components/OpusReviewPanel.js` | Review score display, section scores, action items |
| `ReviewQueue.js` | `pages/ReviewQueue.js` | Approval queue for ZQM/Admin |
| `NotificationCenter.js` | `components/NotificationCenter.js` | Header notification dropdown with WebSocket |
| `DocumentUpload.js` | `components/DocumentUpload.js` | TAD document upload with drag & drop |
| `OcrResultPanel.js` | `components/OcrResultPanel.js` | OCR results display and 8D field mapping |

---

## Backend Integration Steps

### 1. Copy files

```bash
cp backend/review_service.py    /path/to/8D-Report-KI/backend/
cp backend/review_endpoints.py  /path/to/8D-Report-KI/backend/
cp backend/workflow_service.py  /path/to/8D-Report-KI/backend/
cp backend/notification_service.py /path/to/8D-Report-KI/backend/
cp backend/ai_service.py        /path/to/8D-Report-KI/backend/
cp backend/upload_service.py    /path/to/8D-Report-KI/backend/
cp backend/upload_endpoints.py  /path/to/8D-Report-KI/backend/
cp backend/ocr_service.py       /path/to/8D-Report-KI/backend/
```

### 2. Add to requirements.txt

```
anthropic>=0.39.0
pdfplumber>=0.10.0
pytesseract>=0.3.10
Pillow>=10.0.0
```

> **System dependency:** Tesseract OCR must be installed on the server:
> ```bash
> # Ubuntu/Debian
> sudo apt install tesseract-ocr tesseract-ocr-deu
> # macOS
> brew install tesseract tesseract-lang
> ```

### 3. Patch server.py — Add imports

At the top of `server.py`, add:

```python
from review_endpoints import create_review_router
from upload_endpoints import create_upload_router
from upload_service import UploadService
from ocr_service import OcrService
from workflow_service import WorkflowService
from notification_service import NotificationService
from ai_service import AIService
```

### 4. Patch server.py — Initialize services after DB connection

After `db = client[...]`, add:

```python
# Initialize new services
notification_service = NotificationService(db)
workflow_service = WorkflowService(db, notification_service, audit_service)
ai_service = AIService(db)
upload_service = UploadService(db, upload_dir="./uploads")
ocr_service = OcrService(db)

# Register review router
review_router = create_review_router(db, audit_service, get_current_user, workflow_service)
app.include_router(review_router, prefix="/api")

# Register upload/OCR router
upload_router = create_upload_router(db, upload_service, ocr_service, get_current_user)
app.include_router(upload_router, prefix="/api")
```

### 5. Patch server.py — Add notification endpoints

```python
# ─── NOTIFICATION ENDPOINTS ─────────────────────────────────────────

@app.get("/api/notifications")
async def get_notifications(
    limit: int = 50,
    unread_only: bool = False,
    current_user: dict = Depends(get_current_user)
):
    notifications = await notification_service.get_notifications(
        user_id=current_user["id"],
        unread_only=unread_only,
        limit=limit
    )
    return notifications

@app.get("/api/notifications/unread-count")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    count = await notification_service.get_unread_count(current_user["id"])
    return {"count": count}

@app.patch("/api/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    success = await notification_service.mark_as_read(notification_id, current_user["id"])
    return {"success": success}

@app.patch("/api/notifications/read-all")
async def mark_all_read(current_user: dict = Depends(get_current_user)):
    count = await notification_service.mark_all_as_read(current_user["id"])
    return {"success": True, "marked_count": count}
```

### 6. Patch server.py — Add WebSocket endpoint

```python
from fastapi import WebSocket, WebSocketDisconnect
import jwt

@app.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    await websocket.accept()

    # Authenticate via token query param
    token = websocket.query_params.get("token", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id", "")
    except:
        await websocket.close(code=4001)
        return

    notification_service.register_websocket(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        notification_service.unregister_websocket(user_id, websocket)
```

### 7. Patch server.py — Add workflow transition endpoint

```python
@app.post("/api/complaints/{complaint_id}/transition")
async def transition_complaint(
    complaint_id: str,
    body: dict,
    current_user: dict = Depends(get_current_user)
):
    """Transition complaint status using the workflow state machine."""
    try:
        result = await workflow_service.transition(
            complaint_id=complaint_id,
            target_status=body.get("target_status", ""),
            user=current_user,
            reason=body.get("reason", "")
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@app.get("/api/complaints/{complaint_id}/allowed-transitions")
async def get_allowed_transitions(
    complaint_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get allowed status transitions for current user."""
    transitions = await workflow_service.get_allowed_transitions(
        complaint_id, current_user.get("role", "viewer")
    )
    return {"transitions": transitions}
```

### 8. Create indexes on startup

In the `startup` event handler:

```python
@app.on_event("startup")
async def startup():
    # ... existing code ...
    from review_service import ReviewService
    review_svc = ReviewService(db)
    await review_svc.create_indexes()
    await notification_service.create_indexes()
```

---

## Frontend Integration Steps

### 1. Copy files

```bash
cp frontend/components/OpusReviewPanel.js  /path/to/frontend/src/components/
cp frontend/components/NotificationCenter.js /path/to/frontend/src/components/
cp frontend/pages/ReviewQueue.js           /path/to/frontend/src/pages/
```

### 2. Add route in App.js

```javascript
import ReviewQueue from './pages/ReviewQueue';

// In <Routes>:
<Route path="/review-queue" element={user ? <ReviewQueue /> : <Navigate to="/login" />} />
```

### 3. Add OpusReviewPanel to ComplaintViewNew.js

At the bottom of the complaint view, before the closing tag:

```javascript
import OpusReviewPanel from '../components/OpusReviewPanel';

// Inside the render, after the D8 section:
<OpusReviewPanel
  complaintId={complaint.id}
  onReviewComplete={(review) => {
    toast.info(`Opus-Score: ${review.overall_score}/100`);
    fetchComplaint(); // Refresh complaint data
  }}
/>
```

### 4. Add NotificationCenter to GruehringHeader.js

```javascript
import NotificationCenter from './NotificationCenter';

// In the header, next to user info:
<div className="flex items-center gap-4">
  <NotificationCenter />
  <span>{user?.full_name}</span>
</div>
```

### 5. Add "Review Queue" link to navigation

In `HomeNew.js` or sidebar navigation:

```javascript
// For ZQM/Admin users:
{(user?.role === 'zqm' || user?.role === 'admin') && (
  <NavLink to="/review-queue" icon={<Brain />} label="Review & Freigabe" />
)}
```

---

## API Endpoints Added

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/complaints/{id}/review` | admin, zqm, bearbeiter | Trigger Opus 4.6 review |
| GET | `/api/complaints/{id}/reviews` | any authenticated | Get review history |
| GET | `/api/complaints/{id}/review/latest` | any authenticated | Get latest review |
| POST | `/api/complaints/{id}/approve` | admin, zqm | Approve 8D report |
| POST | `/api/complaints/{id}/reject` | admin, zqm | Reject 8D report |
| GET | `/api/reviews/queue` | admin, zqm | Get approval queue |
| GET | `/api/reviews/pending` | admin, zqm | Get pending reviews |
| GET | `/api/reviews/statistics` | admin, zqm, analyst | Review statistics |
| POST | `/api/complaints/{id}/transition` | role-based | Status transition |
| GET | `/api/complaints/{id}/allowed-transitions` | any authenticated | Allowed next statuses |
| GET | `/api/notifications` | any authenticated | Get notifications |
| GET | `/api/notifications/unread-count` | any authenticated | Unread count |
| PATCH | `/api/notifications/{id}/read` | any authenticated | Mark as read |
| PATCH | `/api/notifications/read-all` | any authenticated | Mark all as read |
| WS | `/ws/notifications` | token-based | Real-time notifications |

### Upload & OCR Endpoints

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| POST | `/api/complaints/{id}/documents` | stakeholder/admin/zqm | Upload document (auto-triggers OCR for TAD) |
| GET | `/api/complaints/{id}/documents` | stakeholder/admin/zqm | List documents |
| GET | `/api/documents/{id}` | stakeholder/admin/zqm | Get document metadata |
| DELETE | `/api/documents/{id}` | uploader/admin/zqm | Soft-delete document |
| POST | `/api/complaints/{id}/ocr` | authenticated | Trigger OCR on existing document |
| GET | `/api/ocr-results/{id}` | authenticated | Get OCR result |
| POST | `/api/complaints/{id}/ocr/apply` | bearbeiter/admin/zqm | Apply OCR fields to complaint |

## Environment Variables Required

See `.env.example` for a complete template. Required variables:

```bash
ANTHROPIC_API_KEY=sk-ant-...   # Required for Opus 4.6 and Sonnet 4
MONGODB_URI=mongodb://...      # MongoDB connection string
MONGODB_DATABASE=ruflo_8d      # Database name
SECRET_KEY=...                 # JWT signing key
UPLOAD_DIR=./uploads           # Document upload directory (default: ./uploads)
```

## MongoDB Collections Added

| Collection | Purpose |
|------------|---------|
| `opus_reviews` | Stores all Opus 4.6 review results |
| `notifications` | In-app notifications per user |
| `ai_call_logs` | AI API call logging for cost tracking |
| `documents` | Uploaded document metadata and OCR status |
| `ocr_results` | OCR extraction results with mapped 8D fields |
