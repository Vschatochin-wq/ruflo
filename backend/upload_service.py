"""
Upload Service — Document Storage & Management
================================================
Handles file uploads, validation, storage, and metadata
for TAD documents associated with complaints.

Integration:
    from upload_service import UploadService
    upload_svc = UploadService(db, upload_dir="/data/uploads")
    result = await upload_svc.upload_file(file, complaint_id, user_id)
    docs = await upload_svc.list_documents(complaint_id)
"""

import logging
import os
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
}

# Maximum file size (20 MB)
MAX_FILE_SIZE = 20 * 1024 * 1024

# Maximum files per complaint
MAX_FILES_PER_COMPLAINT = 20


class UploadService:
    """Service for document upload, storage, and management."""

    def __init__(self, db: AsyncIOMotorDatabase, upload_dir: str = None):
        self.db = db
        self.documents = db.documents
        self.upload_dir = upload_dir or os.environ.get(
            "UPLOAD_DIR", os.path.join(os.getcwd(), "uploads")
        )
        os.makedirs(self.upload_dir, exist_ok=True)

    def _get_complaint_dir(self, complaint_id: str) -> str:
        """Get upload directory for a specific complaint."""
        safe_id = complaint_id.replace("/", "_").replace("..", "_")
        path = os.path.join(self.upload_dir, safe_id)
        os.makedirs(path, exist_ok=True)
        return path

    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str,
        complaint_id: str,
        uploaded_by: str,
        uploaded_by_name: str = "",
        document_type: str = "tad",
    ) -> Dict[str, Any]:
        """
        Upload and store a document file.

        Args:
            file_content: Raw file bytes
            filename: Original filename
            mime_type: MIME type
            complaint_id: Associated complaint
            uploaded_by: User ID
            uploaded_by_name: Display name
            document_type: Type of document (tad, evidence, other)

        Returns:
            Document record with id, path, metadata

        Raises:
            ValueError: If file validation fails
        """
        # Validate MIME type
        if mime_type not in ALLOWED_MIME_TYPES:
            raise ValueError(
                f"Dateityp '{mime_type}' nicht erlaubt. "
                f"Erlaubt: {', '.join(ALLOWED_MIME_TYPES.values())}"
            )

        # Validate file size
        if len(file_content) > MAX_FILE_SIZE:
            raise ValueError(
                f"Datei zu groß: {len(file_content) / 1024 / 1024:.1f} MB "
                f"(max {MAX_FILE_SIZE / 1024 / 1024:.0f} MB)"
            )

        if len(file_content) == 0:
            raise ValueError("Leere Datei kann nicht hochgeladen werden")

        # Check file count limit
        existing_count = await self.documents.count_documents(
            {"complaint_id": complaint_id, "deleted": {"$ne": True}}
        )
        if existing_count >= MAX_FILES_PER_COMPLAINT:
            raise ValueError(
                f"Maximale Anzahl von {MAX_FILES_PER_COMPLAINT} Dateien pro Reklamation erreicht"
            )

        # Generate safe filename
        doc_id = str(uuid.uuid4())
        extension = ALLOWED_MIME_TYPES[mime_type]
        safe_filename = f"{doc_id}{extension}"

        # Compute checksum
        checksum = hashlib.sha256(file_content).hexdigest()

        # Check for duplicates
        existing = await self.documents.find_one({
            "complaint_id": complaint_id,
            "checksum": checksum,
            "deleted": {"$ne": True},
        })
        if existing:
            raise ValueError("Diese Datei wurde bereits hochgeladen (Duplikat erkannt)")

        # Store file
        complaint_dir = self._get_complaint_dir(complaint_id)
        file_path = os.path.join(complaint_dir, safe_filename)

        with open(file_path, "wb") as f:
            f.write(file_content)

        # Create document record
        document = {
            "id": doc_id,
            "complaint_id": complaint_id,
            "original_filename": self._sanitize_filename(filename),
            "stored_filename": safe_filename,
            "file_path": file_path,
            "mime_type": mime_type,
            "file_size": len(file_content),
            "checksum": checksum,
            "document_type": document_type,
            "uploaded_by": uploaded_by,
            "uploaded_by_name": uploaded_by_name,
            "ocr_status": "pending",
            "ocr_result_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "deleted": False,
        }

        await self.documents.insert_one(document)
        document.pop("_id", None)

        logger.info(
            f"Document uploaded: {filename} ({mime_type}, {len(file_content)} bytes) "
            f"for complaint {complaint_id}"
        )

        return document

    async def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a single document by ID."""
        doc = await self.documents.find_one({"id": document_id, "deleted": {"$ne": True}})
        if doc:
            doc.pop("_id", None)
        return doc

    async def list_documents(
        self,
        complaint_id: str,
        document_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all documents for a complaint."""
        query = {"complaint_id": complaint_id, "deleted": {"$ne": True}}
        if document_type:
            query["document_type"] = document_type

        cursor = self.documents.find(query).sort("created_at", -1)
        docs = await cursor.to_list(length=MAX_FILES_PER_COMPLAINT)
        for doc in docs:
            doc.pop("_id", None)
        return docs

    async def delete_document(
        self,
        document_id: str,
        deleted_by: str,
    ) -> bool:
        """Soft-delete a document."""
        result = await self.documents.update_one(
            {"id": document_id, "deleted": {"$ne": True}},
            {
                "$set": {
                    "deleted": True,
                    "deleted_at": datetime.now(timezone.utc).isoformat(),
                    "deleted_by": deleted_by,
                }
            }
        )
        if result.modified_count > 0:
            logger.info(f"Document {document_id} soft-deleted by {deleted_by}")
            return True
        return False

    async def update_ocr_status(
        self,
        document_id: str,
        status: str,
        ocr_result_id: Optional[str] = None,
    ) -> bool:
        """Update OCR processing status for a document."""
        update = {"ocr_status": status}
        if ocr_result_id:
            update["ocr_result_id"] = ocr_result_id

        result = await self.documents.update_one(
            {"id": document_id},
            {"$set": update}
        )
        return result.modified_count > 0

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Sanitize original filename for safe storage/display."""
        if not filename:
            return "dokument"
        # Remove path separators
        filename = os.path.basename(filename)
        # Keep only safe characters
        safe = "".join(
            c for c in filename
            if c.isalnum() or c in ".-_ äöüÄÖÜß"
        )
        return safe[:255] or "dokument"
