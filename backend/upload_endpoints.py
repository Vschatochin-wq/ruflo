"""
Upload & OCR API Endpoints
===========================
FastAPI router for document upload, OCR processing, and field mapping.

Integration:
    from upload_endpoints import create_upload_router
    upload_router = create_upload_router(db, upload_service, ocr_service, get_current_user)
    app.include_router(upload_router, prefix="/api")
"""

import re
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List

COMPLAINT_ID_PATTERN = re.compile(r'^[a-zA-Z0-9\-]{1,64}$')


def _validate_complaint_id(complaint_id: str) -> str:
    if not complaint_id or not COMPLAINT_ID_PATTERN.match(complaint_id):
        raise HTTPException(status_code=400, detail="Ungültige Reklamations-ID")
    return complaint_id


class OcrApplyRequest(BaseModel):
    """Request body for applying OCR results to complaint."""
    ocr_result_id: str = Field(..., min_length=1, max_length=64)
    selected_fields: Optional[List[str]] = None


class OcrTriggerRequest(BaseModel):
    """Request body for triggering OCR on existing document."""
    document_id: str = Field(..., min_length=1, max_length=64)


def create_upload_router(db, upload_service, ocr_service, get_current_user):
    """
    Factory function to create upload/OCR API router.

    Args:
        db: AsyncIOMotorDatabase instance
        upload_service: UploadService instance
        ocr_service: OcrService instance
        get_current_user: Dependency for JWT auth
    """
    router = APIRouter(tags=["Upload & OCR"])

    # ─── UPLOAD FILE ────────────────────────────────────────────────

    @router.post("/complaints/{complaint_id}/documents")
    async def upload_document(
        complaint_id: str,
        file: UploadFile = File(...),
        document_type: str = Form("tad"),
        current_user: dict = Depends(get_current_user),
    ):
        """
        Upload a document (PDF, image) for a complaint.
        Automatically triggers OCR processing.
        """
        complaint_id = _validate_complaint_id(complaint_id)

        # Verify complaint exists and user has access
        complaint = await db.complaints.find_one({"id": complaint_id})
        if not complaint:
            raise HTTPException(status_code=404, detail="Reklamation nicht gefunden")

        user_role = current_user.get("role", "")
        user_id = current_user.get("id", "")
        if user_role not in ["admin", "zqm"] and not _is_stakeholder(complaint, user_id):
            raise HTTPException(status_code=403, detail="Kein Zugriff auf diese Reklamation")

        # Read file content
        content = await file.read()

        # Validate document_type
        if document_type not in ("tad", "evidence", "other"):
            document_type = "other"

        try:
            document = await upload_service.upload_file(
                file_content=content,
                filename=file.filename or "upload",
                mime_type=file.content_type or "application/octet-stream",
                complaint_id=complaint_id,
                uploaded_by=user_id,
                uploaded_by_name=current_user.get("full_name", ""),
                document_type=document_type,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Auto-trigger OCR for TAD documents
        ocr_result = None
        if document_type == "tad":
            try:
                ocr_result = await ocr_service.extract_and_map(
                    file_path=document["file_path"],
                    mime_type=document["mime_type"],
                    complaint_id=complaint_id,
                    document_id=document["id"],
                )
                await upload_service.update_ocr_status(
                    document["id"], "completed", ocr_result["id"]
                )
                document["ocr_status"] = "completed"
                document["ocr_result_id"] = ocr_result["id"]
            except Exception as e:
                await upload_service.update_ocr_status(document["id"], "failed")
                document["ocr_status"] = "failed"
                # Don't fail the upload itself — OCR is secondary
                ocr_result = {"error": "OCR-Verarbeitung fehlgeschlagen"}

        return {
            "success": True,
            "document": _safe_document(document),
            "ocr_result": _safe_ocr_result(ocr_result) if ocr_result else None,
        }

    # ─── LIST DOCUMENTS ─────────────────────────────────────────────

    @router.get("/complaints/{complaint_id}/documents")
    async def list_documents(
        complaint_id: str,
        document_type: Optional[str] = None,
        current_user: dict = Depends(get_current_user),
    ):
        """List all documents for a complaint."""
        complaint_id = _validate_complaint_id(complaint_id)

        complaint = await db.complaints.find_one({"id": complaint_id})
        if not complaint:
            raise HTTPException(status_code=404, detail="Reklamation nicht gefunden")

        user_role = current_user.get("role", "")
        user_id = current_user.get("id", "")
        if user_role not in ["admin", "zqm"] and not _is_stakeholder(complaint, user_id):
            raise HTTPException(status_code=403, detail="Kein Zugriff")

        docs = await upload_service.list_documents(complaint_id, document_type)
        return {
            "documents": [_safe_document(d) for d in docs],
            "total": len(docs),
        }

    # ─── GET SINGLE DOCUMENT ────────────────────────────────────────

    @router.get("/documents/{document_id}")
    async def get_document(
        document_id: str,
        current_user: dict = Depends(get_current_user),
    ):
        """Get document metadata by ID."""
        doc = await upload_service.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

        # Verify access
        complaint = await db.complaints.find_one({"id": doc["complaint_id"]})
        user_role = current_user.get("role", "")
        user_id = current_user.get("id", "")
        if complaint and user_role not in ["admin", "zqm"] and not _is_stakeholder(complaint, user_id):
            raise HTTPException(status_code=403, detail="Kein Zugriff")

        return {"document": _safe_document(doc)}

    # ─── DELETE DOCUMENT ────────────────────────────────────────────

    @router.delete("/documents/{document_id}")
    async def delete_document(
        document_id: str,
        current_user: dict = Depends(get_current_user),
    ):
        """Soft-delete a document."""
        doc = await upload_service.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

        user_role = current_user.get("role", "")
        user_id = current_user.get("id", "")

        # Only uploader, admin, or zqm can delete
        if user_role not in ["admin", "zqm"] and doc.get("uploaded_by") != user_id:
            raise HTTPException(status_code=403, detail="Keine Berechtigung zum Löschen")

        success = await upload_service.delete_document(document_id, user_id)
        if not success:
            raise HTTPException(status_code=500, detail="Löschen fehlgeschlagen")

        return {"success": True, "message": "Dokument gelöscht"}

    # ─── TRIGGER OCR ────────────────────────────────────────────────

    @router.post("/complaints/{complaint_id}/ocr")
    async def trigger_ocr(
        complaint_id: str,
        body: OcrTriggerRequest,
        current_user: dict = Depends(get_current_user),
    ):
        """Manually trigger OCR processing for a document."""
        complaint_id = _validate_complaint_id(complaint_id)

        doc = await upload_service.get_document(body.document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

        if doc["complaint_id"] != complaint_id:
            raise HTTPException(status_code=400, detail="Dokument gehört nicht zu dieser Reklamation")

        try:
            ocr_result = await ocr_service.extract_and_map(
                file_path=doc["file_path"],
                mime_type=doc["mime_type"],
                complaint_id=complaint_id,
                document_id=doc["id"],
            )
            await upload_service.update_ocr_status(doc["id"], "completed", ocr_result["id"])
        except Exception as e:
            await upload_service.update_ocr_status(doc["id"], "failed")
            raise HTTPException(status_code=500, detail="OCR-Verarbeitung fehlgeschlagen")

        return {
            "success": True,
            "ocr_result": _safe_ocr_result(ocr_result),
        }

    # ─── GET OCR RESULT ─────────────────────────────────────────────

    @router.get("/ocr-results/{ocr_result_id}")
    async def get_ocr_result(
        ocr_result_id: str,
        current_user: dict = Depends(get_current_user),
    ):
        """Get OCR result by ID."""
        result = await db.ocr_results.find_one({"id": ocr_result_id})
        if not result:
            raise HTTPException(status_code=404, detail="OCR-Ergebnis nicht gefunden")

        result.pop("_id", None)
        return {"ocr_result": _safe_ocr_result(result)}

    # ─── APPLY OCR TO COMPLAINT ─────────────────────────────────────

    @router.post("/complaints/{complaint_id}/ocr/apply")
    async def apply_ocr_to_complaint(
        complaint_id: str,
        body: OcrApplyRequest,
        current_user: dict = Depends(get_current_user),
    ):
        """
        Apply mapped OCR fields to a complaint.
        Only fills empty fields — does not overwrite existing data.
        """
        complaint_id = _validate_complaint_id(complaint_id)

        complaint = await db.complaints.find_one({"id": complaint_id})
        if not complaint:
            raise HTTPException(status_code=404, detail="Reklamation nicht gefunden")

        user_role = current_user.get("role", "")
        user_id = current_user.get("id", "")
        if user_role not in ["admin", "zqm", "bearbeiter"] and not _is_stakeholder(complaint, user_id):
            raise HTTPException(status_code=403, detail="Keine Berechtigung")

        try:
            result = await ocr_service.apply_to_complaint(
                complaint_id=complaint_id,
                ocr_result_id=body.ocr_result_id,
                selected_fields=body.selected_fields,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return result

    # ─── HELPERS ────────────────────────────────────────────────────

    def _is_stakeholder(complaint: dict, user_id: str) -> bool:
        """Check if user is a stakeholder of the complaint."""
        return (
            complaint.get("created_by") == user_id
            or complaint.get("assigned_zqm", {}).get("user_id") == user_id
            or complaint.get("assigned_processor", {}).get("user_id") == user_id
        )

    def _safe_document(doc: dict) -> dict:
        """Remove internal fields from document before returning to client."""
        if not doc:
            return {}
        safe = {k: v for k, v in doc.items() if k not in ("_id", "file_path")}
        return safe

    def _safe_ocr_result(result: dict) -> dict:
        """Remove internal fields and truncate large text for API response."""
        if not result:
            return {}
        safe = {k: v for k, v in result.items() if k != "_id"}
        # Truncate extracted_text for API response (full text in DB)
        if "extracted_text" in safe and len(safe["extracted_text"]) > 2000:
            safe["extracted_text_preview"] = safe["extracted_text"][:2000] + "..."
            safe["extracted_text_full_length"] = len(safe["extracted_text"])
            del safe["extracted_text"]
        return safe

    return router
