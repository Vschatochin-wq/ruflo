"""
Tests for UploadService — Document Storage & Management
========================================================
Covers: upload, validation, list, delete, duplicate detection, limits.
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import AsyncMock, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from conftest import MockDB
from upload_service import UploadService, ALLOWED_MIME_TYPES, MAX_FILE_SIZE, MAX_FILES_PER_COMPLAINT


@pytest.fixture
def upload_dir():
    """Create a temporary upload directory."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def svc(mock_db, upload_dir):
    return UploadService(mock_db, upload_dir=upload_dir)


# ─── UPLOAD VALIDATION ──────────────────────────────────────────

class TestUploadValidation:

    @pytest.mark.asyncio
    async def test_rejects_unsupported_mime_type(self, svc):
        with pytest.raises(ValueError, match="nicht erlaubt"):
            await svc.upload_file(
                file_content=b"test",
                filename="test.exe",
                mime_type="application/x-msdownload",
                complaint_id="comp-1",
                uploaded_by="user-1",
            )

    @pytest.mark.asyncio
    async def test_rejects_empty_file(self, svc):
        with pytest.raises(ValueError, match="Leere Datei"):
            await svc.upload_file(
                file_content=b"",
                filename="empty.pdf",
                mime_type="application/pdf",
                complaint_id="comp-1",
                uploaded_by="user-1",
            )

    @pytest.mark.asyncio
    async def test_rejects_oversized_file(self, svc):
        big_content = b"x" * (MAX_FILE_SIZE + 1)
        with pytest.raises(ValueError, match="zu groß"):
            await svc.upload_file(
                file_content=big_content,
                filename="huge.pdf",
                mime_type="application/pdf",
                complaint_id="comp-1",
                uploaded_by="user-1",
            )

    @pytest.mark.asyncio
    async def test_accepts_valid_pdf(self, svc):
        result = await svc.upload_file(
            file_content=b"%PDF-1.4 test content",
            filename="report.pdf",
            mime_type="application/pdf",
            complaint_id="comp-1",
            uploaded_by="user-1",
            uploaded_by_name="Test User",
            document_type="tad",
        )

        assert result["id"]
        assert result["complaint_id"] == "comp-1"
        assert result["mime_type"] == "application/pdf"
        assert result["original_filename"] == "report.pdf"
        assert result["ocr_status"] == "pending"
        assert result["deleted"] is False
        assert os.path.exists(result["file_path"])

    @pytest.mark.asyncio
    async def test_accepts_valid_image(self, svc):
        result = await svc.upload_file(
            file_content=b"\x89PNG\r\n\x1a\n fake png",
            filename="photo.png",
            mime_type="image/png",
            complaint_id="comp-1",
            uploaded_by="user-1",
        )
        assert result["mime_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_accepts_jpeg(self, svc):
        result = await svc.upload_file(
            file_content=b"\xff\xd8\xff\xe0 fake jpeg",
            filename="scan.jpg",
            mime_type="image/jpeg",
            complaint_id="comp-1",
            uploaded_by="user-1",
        )
        assert result["mime_type"] == "image/jpeg"


# ─── DUPLICATE DETECTION ────────────────────────────────────────

class TestDuplicateDetection:

    @pytest.mark.asyncio
    async def test_rejects_duplicate_file(self, svc):
        content = b"PDF content here"

        await svc.upload_file(
            file_content=content,
            filename="first.pdf",
            mime_type="application/pdf",
            complaint_id="comp-1",
            uploaded_by="user-1",
        )

        with pytest.raises(ValueError, match="Duplikat"):
            await svc.upload_file(
                file_content=content,
                filename="second.pdf",
                mime_type="application/pdf",
                complaint_id="comp-1",
                uploaded_by="user-1",
            )

    @pytest.mark.asyncio
    async def test_same_content_different_complaint_ok(self, svc):
        content = b"PDF content"

        await svc.upload_file(
            file_content=content,
            filename="doc.pdf",
            mime_type="application/pdf",
            complaint_id="comp-1",
            uploaded_by="user-1",
        )

        # Different complaint — should succeed
        result = await svc.upload_file(
            file_content=content,
            filename="doc.pdf",
            mime_type="application/pdf",
            complaint_id="comp-2",
            uploaded_by="user-1",
        )
        assert result["complaint_id"] == "comp-2"


# ─── LIST & GET ─────────────────────────────────────────────────

class TestListAndGet:

    @pytest.mark.asyncio
    async def test_list_documents(self, svc):
        await svc.upload_file(b"a", "a.pdf", "application/pdf", "comp-1", "user-1")
        await svc.upload_file(b"b", "b.png", "image/png", "comp-1", "user-1")

        docs = await svc.list_documents("comp-1")
        assert len(docs) == 2

    @pytest.mark.asyncio
    async def test_list_empty(self, svc):
        docs = await svc.list_documents("nonexistent")
        assert docs == []

    @pytest.mark.asyncio
    async def test_get_document(self, svc):
        uploaded = await svc.upload_file(b"test", "test.pdf", "application/pdf", "comp-1", "user-1")

        doc = await svc.get_document(uploaded["id"])
        assert doc is not None
        assert doc["id"] == uploaded["id"]

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, svc):
        doc = await svc.get_document("nonexistent")
        assert doc is None


# ─── DELETE ─────────────────────────────────────────────────────

class TestDelete:

    @pytest.mark.asyncio
    async def test_soft_delete(self, svc):
        uploaded = await svc.upload_file(b"test", "test.pdf", "application/pdf", "comp-1", "user-1")

        success = await svc.delete_document(uploaded["id"], "user-1")
        assert success is True

        # Should not appear in list
        docs = await svc.list_documents("comp-1")
        assert len(docs) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, svc):
        success = await svc.delete_document("nonexistent", "user-1")
        assert success is False


# ─── OCR STATUS ─────────────────────────────────────────────────

class TestOcrStatus:

    @pytest.mark.asyncio
    async def test_update_ocr_status(self, svc):
        uploaded = await svc.upload_file(b"test", "test.pdf", "application/pdf", "comp-1", "user-1")

        success = await svc.update_ocr_status(uploaded["id"], "completed", "ocr-123")
        assert success is True

        doc = await svc.get_document(uploaded["id"])
        assert doc["ocr_status"] == "completed"
        assert doc["ocr_result_id"] == "ocr-123"


# ─── FILENAME SANITIZATION ─────────────────────────────────────

class TestFilenameSanitization:

    def test_removes_path_separators(self):
        assert "/" not in UploadService._sanitize_filename("/etc/passwd")
        assert ".." not in UploadService._sanitize_filename("../../secret.txt")

    def test_preserves_german_chars(self):
        result = UploadService._sanitize_filename("Prüfbericht_ÄÖÜ.pdf")
        assert "Prüfbericht" in result
        assert ".pdf" in result

    def test_empty_returns_default(self):
        assert UploadService._sanitize_filename("") == "dokument"
        assert UploadService._sanitize_filename(None) == "dokument"

    def test_truncates_long_names(self):
        long_name = "a" * 300 + ".pdf"
        result = UploadService._sanitize_filename(long_name)
        assert len(result) <= 255


# ─── FILE COUNT LIMIT ──────────────────────────────────────────

class TestFileCountLimit:

    @pytest.mark.asyncio
    async def test_enforces_max_files_per_complaint(self, svc):
        # Upload MAX_FILES documents
        for i in range(MAX_FILES_PER_COMPLAINT):
            await svc.upload_file(
                file_content=f"content-{i}".encode(),
                filename=f"doc-{i}.pdf",
                mime_type="application/pdf",
                complaint_id="comp-1",
                uploaded_by="user-1",
            )

        # Next upload should fail
        with pytest.raises(ValueError, match="Maximale Anzahl"):
            await svc.upload_file(
                file_content=b"one too many",
                filename="overflow.pdf",
                mime_type="application/pdf",
                complaint_id="comp-1",
                uploaded_by="user-1",
            )
