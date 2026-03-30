"""
OCR Service — Document Text Extraction & 8D Field Mapping
==========================================================
Extracts text from uploaded TAD documents (PDF, images) using
Tesseract OCR and pdfplumber, then maps extracted fields to
8D complaint sections.

Integration:
    from ocr_service import OcrService
    ocr = OcrService(db)
    result = await ocr.extract_text(file_path, mime_type)
    result = await ocr.extract_and_map(file_path, mime_type, complaint_id)
"""

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Supported file types
SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/tiff", "image/bmp", "image/webp"}
SUPPORTED_PDF_TYPES = {"application/pdf"}
SUPPORTED_TYPES = SUPPORTED_IMAGE_TYPES | SUPPORTED_PDF_TYPES

# Maximum file size (20 MB)
MAX_FILE_SIZE = 20 * 1024 * 1024

# 8D section patterns for German TAD documents
SECTION_PATTERNS = {
    "team_members": [
        re.compile(r"(?:D1|Team|Teammitglieder|Teilnehmer)[:\s]*(.+?)(?=D[2-8]|\Z)", re.DOTALL | re.IGNORECASE),
    ],
    "problem_description": [
        re.compile(r"(?:D2|Problembeschreibung|Fehlerbeschreibung|Beanstandung)[:\s]*(.+?)(?=D[3-8]|\Z)", re.DOTALL | re.IGNORECASE),
    ],
    "immediate_actions": [
        re.compile(r"(?:D3|Sofortmaßnahmen?|Containment)[:\s]*(.+?)(?=D[4-8]|\Z)", re.DOTALL | re.IGNORECASE),
    ],
    "root_cause": [
        re.compile(r"(?:D4|Ursache(?:nanalyse)?|Root.?Cause|Grundursache)[:\s]*(.+?)(?=D[5-8]|\Z)", re.DOTALL | re.IGNORECASE),
    ],
    "corrective_actions": [
        re.compile(r"(?:D5|Abstellmaßnahmen?|Korrekturmaßnahmen?|Corrective)[:\s]*(.+?)(?=D[6-8]|\Z)", re.DOTALL | re.IGNORECASE),
    ],
    "verification": [
        re.compile(r"(?:D6|Verifizierung|Wirksamkeit(?:sprüfung)?|Verification)[:\s]*(.+?)(?=D[7-8]|\Z)", re.DOTALL | re.IGNORECASE),
    ],
    "preventive_actions": [
        re.compile(r"(?:D7|Vorbeugemaßnahmen?|Präventivmaßnahmen?|Preventive)[:\s]*(.+?)(?=D8|\Z)", re.DOTALL | re.IGNORECASE),
    ],
    "closure": [
        re.compile(r"(?:D8|Abschluss|Teamauflösung|Closure|Lessons.?Learned)[:\s]*(.+?)(?=\Z)", re.DOTALL | re.IGNORECASE),
    ],
}

# Metadata patterns for GÜHRING TAD-Problemmeldebogen (AN-VA-14-RB-01-05)
METADATA_PATTERNS = {
    "customer_name": [
        re.compile(r"KUNDENNAME[*\s.:]*\n?\s*(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"(?:Kunde|Customer|Auftraggeber)[.:\s]*(.+?)(?:\n|$)", re.IGNORECASE),
    ],
    "customer_number": [
        re.compile(r"KUNDENNUMMER[*\s.:]*\n?\s*(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"Kunden.?(?:Nr|Nummer)[.:\s]*([A-Z0-9\-]+)", re.IGNORECASE),
    ],
    "created_by_name": [
        re.compile(r"ERSTELLT VON[*\s.:]*\n?\s*(.+?)(?:\n|$)", re.IGNORECASE),
    ],
    "phone": [
        re.compile(r"TELEFON[*\s.:]*\n?\s*([0-9\s\+\-/]+?)(?:\n|$)", re.IGNORECASE),
    ],
    "customer_order_number": [
        re.compile(r"KUNDENAUFTRAGSNR[.*\s:]*\n?\s*([A-Z0-9\-]+)", re.IGNORECASE),
    ],
    "delivery_note_number": [
        re.compile(r"LIEFERSCHEINNR[.*\s:]*\n?\s*([A-Z0-9\-]+)", re.IGNORECASE),
    ],
    "return_number": [
        re.compile(r"RETOURENNUMMER[*\s.:]*\n?\s*([A-Z0-9\-]+)", re.IGNORECASE),
    ],
    "detection_date": [
        re.compile(r"DATUM DER FESTSTELLUNG(?:\s+DES\s+FEHLERS)?[*\s.:]*\n?\s*(\d{4}[\-./]\d{2}[\-./]\d{2}|\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})", re.IGNORECASE),
        re.compile(r"Feststellungsdatum[.:\s]*(\d{4}[\-./]\d{2}[\-./]\d{2}|\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})", re.IGNORECASE),
    ],
    "report_date": [
        re.compile(r"MELDEDATUM[*\s.:]*\n?\s*(\d{4}[\-./]\d{2}[\-./]\d{2}|\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})", re.IGNORECASE),
    ],
    "fa_code": [
        re.compile(r"(?:^|\n)\s*FA[*\s.:]+\n?\s*([0-9A-Z\-]{3,})", re.IGNORECASE),
        re.compile(r"FA[\-\s]?Code[.:\s]*([A-Z0-9\-]+)", re.IGNORECASE),
        re.compile(r"Fertigungsauftrag[.:\s]*([A-Z0-9\-]+)", re.IGNORECASE),
    ],
    "artikel_nummer": [
        re.compile(r"ART\.?-?/SOBO-?NR\.?[*\s.:]*\n?\s*([0-9A-Z\-]+)", re.IGNORECASE),
        re.compile(r"Artikel[\.\-]?(?:Nr|Nummer)[.:\s]*([A-Z0-9\-]+)", re.IGNORECASE),
        re.compile(r"Art\.?\-?Nr[.:\s]*([A-Z0-9\-]+)", re.IGNORECASE),
    ],
    "complaint_number": [
        re.compile(r"(?:Reklamations?.?(?:Nr|Nummer)|RK)[.:\s]*([A-Z0-9\-]+)", re.IGNORECASE),
    ],
    "error_location": [
        re.compile(r"SPEZIFISCHER ORT[*\s.:]*\n?\s*(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"(?:Fehlerort|Fundort|Entdeckungsort)[.:\s]*(.+?)(?:\n|$)", re.IGNORECASE),
    ],
}

# TAD-specific section patterns for Problemmeldebogen
TAD_SECTION_PATTERNS = {
    "problem_type": [
        re.compile(r"WHAT\?[^)]*\)?\s*\n?\s*(?:\[?[xX☑✓]\]?\s*)?(Produktfehler|Falschlieferung|Transportschaden)", re.IGNORECASE),
    ],
    "damage_category": [
        re.compile(r"SCHADENSBILD \(HAUPTGRUPPE\)[*\s.:]*\n?\s*(.+?)(?:\n|$)", re.IGNORECASE),
    ],
    "error_code": [
        re.compile(r"FEHLERCODE[*\s.:]*\n?\s*(.+?)(?:\n|$)", re.IGNORECASE),
    ],
    "problem_description": [
        re.compile(r"Detaillierte Problembeschreibung[*\s.:]*\n?\s*(.+?)(?=\n\s*\d\.\s|\n\s*WHERE|\Z)", re.DOTALL | re.IGNORECASE),
    ],
    "error_location_type": [
        re.compile(r"WHERE\?[^)]*\)?\s*\n?\s*(?:\[?[xX☑✓]\]?\s*)?(Wareneingang|Produktion|Lagerprüfung)", re.IGNORECASE),
    ],
    "specific_location": [
        re.compile(r"SPEZIFISCHER ORT[*\s.:]*\n?\s*(.+?)(?:\n|$)", re.IGNORECASE),
    ],
    "how_detected": [
        re.compile(r"HOW\?\s*\(?Wie wurde der Fehler entdeckt\?\)?[*\s.:]*\n?\s*(.+?)(?=\n\s*HOW MUCH|\Z)", re.DOTALL | re.IGNORECASE),
    ],
    "affected_quantity": [
        re.compile(r"BETROFFENE MENGE \(STÜCK\)[*\s.:]*\n?\s*(\d+)", re.IGNORECASE),
    ],
    "delivered_quantity": [
        re.compile(r"GELIEFERTE MENGE \(STÜCK\)[*\s.:]*\n?\s*(\d+)", re.IGNORECASE),
    ],
    "return_quantity": [
        re.compile(r"RÜCKSENDE[\-\s]?MENGE[*\s.:]*\n?\s*(\d+)", re.IGNORECASE),
    ],
    "message_type": [
        re.compile(r"(?:\[?[xX☑✓]\]?\s*)?(Q1[\-\s]Meldung|Q3[\-\s]Meldung)", re.IGNORECASE),
    ],
    "tool_return": [
        re.compile(r"Werkzeuge zurück versendet\?\s*\n?\s*(?:\[?[xX☑✓]\]?\s*)?(Ja|Nein)", re.IGNORECASE),
    ],
    "tool_return_reason": [
        re.compile(r"BEGRÜNDUNG[*\s.:]*\n?\s*(.+?)(?=\n\s*WER HAT|\Z)", re.DOTALL | re.IGNORECASE),
    ],
    "discovered_by": [
        re.compile(r"WER HAT DEN FEHLER ENTDECKT\?[*\s.:]*\n?\s*(.+?)(?=\n\s*\d\.\s|\Z)", re.DOTALL | re.IGNORECASE),
    ],
}


class OcrService:
    """Service for OCR text extraction and 8D field mapping."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.ocr_results = db.ocr_results

    async def extract_text(self, file_path: str, mime_type: str) -> Dict[str, Any]:
        """
        Extract text from a file using OCR (images) or direct parsing (PDFs).

        Args:
            file_path: Path to the uploaded file
            mime_type: MIME type of the file

        Returns:
            Dict with extracted_text, page_count, confidence, method
        """
        if mime_type not in SUPPORTED_TYPES:
            raise ValueError(f"Nicht unterstützter Dateityp: {mime_type}")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Datei nicht gefunden: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"Datei zu groß: {file_size / 1024 / 1024:.1f} MB (max {MAX_FILE_SIZE / 1024 / 1024:.0f} MB)")

        if mime_type in SUPPORTED_PDF_TYPES:
            return await self._extract_from_pdf(file_path)
        else:
            return await self._extract_from_image(file_path)

    async def _extract_from_pdf(self, file_path: str) -> Dict[str, Any]:
        """Extract text from PDF using pdfplumber with OCR fallback."""
        try:
            import pdfplumber
        except ImportError:
            raise RuntimeError("pdfplumber ist nicht installiert. Bitte installieren: pip install pdfplumber")

        pages_text = []
        total_confidence = 0.0

        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    pages_text.append(text)
                    total_confidence += 0.95  # Direct PDF text is high confidence
                else:
                    # Page has no text layer — try OCR on page image
                    ocr_result = await self._ocr_pdf_page(page)
                    pages_text.append(ocr_result["text"])
                    total_confidence += ocr_result["confidence"]

        full_text = "\n\n--- Seite ---\n\n".join(pages_text)
        avg_confidence = total_confidence / max(page_count, 1)

        return {
            "extracted_text": full_text,
            "page_count": page_count,
            "confidence": round(avg_confidence, 2),
            "method": "pdfplumber" if avg_confidence > 0.9 else "pdfplumber+ocr",
            "char_count": len(full_text),
        }

    async def _ocr_pdf_page(self, page) -> Dict[str, Any]:
        """OCR a single PDF page by converting to image first."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            return {"text": "", "confidence": 0.0}

        try:
            image = page.to_image(resolution=300).original
            data = pytesseract.image_to_data(image, lang="deu", output_type=pytesseract.Output.DICT)

            texts = []
            confidences = []
            for i, conf in enumerate(data["conf"]):
                if int(conf) > 0:
                    texts.append(data["text"][i])
                    confidences.append(int(conf))

            text = " ".join(t for t in texts if t.strip())
            avg_conf = sum(confidences) / max(len(confidences), 1) / 100.0

            return {"text": text, "confidence": round(avg_conf, 2)}
        except Exception as e:
            logger.warning(f"OCR für PDF-Seite fehlgeschlagen: {e}")
            return {"text": "", "confidence": 0.0}

    async def _extract_from_image(self, file_path: str) -> Dict[str, Any]:
        """Extract text from image using Tesseract OCR."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            raise RuntimeError("pytesseract/Pillow nicht installiert. Bitte installieren: pip install pytesseract Pillow")

        image = Image.open(file_path)

        # Get detailed OCR data with confidence
        data = pytesseract.image_to_data(image, lang="deu", output_type=pytesseract.Output.DICT)

        texts = []
        confidences = []
        for i, conf in enumerate(data["conf"]):
            if int(conf) > 0:
                texts.append(data["text"][i])
                confidences.append(int(conf))

        full_text = " ".join(t for t in texts if t.strip())
        avg_confidence = sum(confidences) / max(len(confidences), 1) / 100.0

        return {
            "extracted_text": full_text,
            "page_count": 1,
            "confidence": round(avg_confidence, 2),
            "method": "tesseract",
            "char_count": len(full_text),
        }

    def map_to_8d_fields(self, extracted_text: str) -> Dict[str, Any]:
        """
        Map extracted text to 8D report sections and TAD form fields.
        Handles both 8D reports (D1-D8) and GÜHRING TAD-Problemmeldebogen.

        Returns:
            Dict with metadata, sections, tad_fields, and mapping_confidence
        """
        all_pattern_sets = {
            **METADATA_PATTERNS,
            **SECTION_PATTERNS,
            **TAD_SECTION_PATTERNS,
        }
        result = {
            "metadata": {},
            "sections": {},
            "tad_fields": {},
            "unmapped_text": "",
            "mapping_confidence": 0.0,
            "mapped_field_count": 0,
            "total_field_count": len(all_pattern_sets),
        }

        # Extract metadata fields
        for field_name, patterns in METADATA_PATTERNS.items():
            for pattern in patterns:
                match = pattern.search(extracted_text)
                if match:
                    value = match.group(1).strip()
                    if value:
                        result["metadata"][field_name] = value
                        result["mapped_field_count"] += 1
                    break

        # Extract 8D sections (D1-D8)
        for section_name, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                match = pattern.search(extracted_text)
                if match:
                    value = match.group(1).strip()
                    if value and len(value) > 5:
                        result["sections"][section_name] = value
                        result["mapped_field_count"] += 1
                    break

        # Extract TAD-specific fields
        for field_name, patterns in TAD_SECTION_PATTERNS.items():
            for pattern in patterns:
                match = pattern.search(extracted_text)
                if match:
                    value = match.group(1).strip()
                    if value:
                        result["tad_fields"][field_name] = value
                        result["mapped_field_count"] += 1
                    break

        result["mapping_confidence"] = round(
            result["mapped_field_count"] / max(result["total_field_count"], 1), 2
        )

        return result

    async def extract_and_map(
        self,
        file_path: str,
        mime_type: str,
        complaint_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full pipeline: extract text via OCR, then map to 8D fields.

        Args:
            file_path: Path to uploaded file
            mime_type: MIME type
            complaint_id: Optional complaint to associate with
            document_id: Optional document ID to link

        Returns:
            Complete OCR result with text, mapping, and metadata
        """
        # Step 1: Extract text
        extraction = await self.extract_text(file_path, mime_type)

        # Step 2: Map to 8D fields
        mapping = self.map_to_8d_fields(extraction["extracted_text"])

        # Step 3: Build result record
        ocr_record = {
            "id": str(uuid.uuid4()),
            "complaint_id": complaint_id,
            "document_id": document_id,
            "extracted_text": extraction["extracted_text"],
            "page_count": extraction["page_count"],
            "ocr_confidence": extraction["confidence"],
            "ocr_method": extraction["method"],
            "char_count": extraction["char_count"],
            "mapped_metadata": mapping["metadata"],
            "mapped_sections": mapping["sections"],
            "mapped_tad_fields": mapping.get("tad_fields", {}),
            "mapping_confidence": mapping["mapping_confidence"],
            "mapped_field_count": mapping["mapped_field_count"],
            "total_field_count": mapping["total_field_count"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
        }

        # Step 4: Persist to DB
        await self.ocr_results.insert_one(ocr_record)

        return ocr_record

    async def apply_to_complaint(
        self,
        complaint_id: str,
        ocr_result_id: str,
        selected_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Apply mapped OCR fields to a complaint document.

        Args:
            complaint_id: Target complaint
            ocr_result_id: OCR result to apply
            selected_fields: Optional list of fields to apply (None = all)

        Returns:
            Dict with applied fields and updated complaint
        """
        ocr_result = await self.ocr_results.find_one({"id": ocr_result_id})
        if not ocr_result:
            raise ValueError("OCR-Ergebnis nicht gefunden")

        complaint = await self.db.complaints.find_one({"id": complaint_id})
        if not complaint:
            raise ValueError("Reklamation nicht gefunden")

        update_fields = {}
        applied = []

        # Apply metadata
        for field, value in ocr_result.get("mapped_metadata", {}).items():
            if selected_fields and field not in selected_fields:
                continue
            if not complaint.get(field):  # Only fill empty fields
                update_fields[field] = value
                applied.append({"field": field, "value": value, "source": "metadata"})

        # Apply sections
        section_field_map = {
            "problem_description": "problem_description",
            "team_members": "team_members_text",
            "immediate_actions": "immediate_actions_text",
            "root_cause": "root_cause_text",
            "corrective_actions": "corrective_actions_text",
            "verification": "verification_text",
            "preventive_actions": "preventive_actions_text",
            "closure": "closure_text",
        }

        for section, value in ocr_result.get("mapped_sections", {}).items():
            if selected_fields and section not in selected_fields:
                continue
            target_field = section_field_map.get(section, section)
            if not complaint.get(target_field):
                update_fields[target_field] = value
                applied.append({"field": target_field, "value": value[:100] + "..." if len(value) > 100 else value, "source": "section"})

        # Apply TAD-specific fields
        tad_field_map = {
            "problem_type": "problem_type",
            "damage_category": "damage_category",
            "error_code": "error_code",
            "problem_description": "problem_description",
            "error_location_type": "error_location",
            "specific_location": "specific_location",
            "how_detected": "how_detected",
            "affected_quantity": "affected_quantity",
            "delivered_quantity": "delivered_quantity",
            "return_quantity": "return_quantity",
            "message_type": "message_type",
            "tool_return": "tool_return",
            "tool_return_reason": "tool_return_reason",
            "discovered_by": "discovered_by",
        }

        for tad_field, value in ocr_result.get("mapped_tad_fields", {}).items():
            if selected_fields and tad_field not in selected_fields:
                continue
            target_field = tad_field_map.get(tad_field, tad_field)
            if not complaint.get(target_field):
                update_fields[target_field] = value
                applied.append({"field": target_field, "value": value[:100] + "..." if len(value) > 100 else value, "source": "tad"})

        if update_fields:
            update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
            await self.db.complaints.update_one(
                {"id": complaint_id},
                {"$set": update_fields}
            )

        return {
            "success": True,
            "applied_count": len(applied),
            "applied_fields": applied,
            "skipped_count": (
                len(ocr_result.get("mapped_metadata", {})) +
                len(ocr_result.get("mapped_sections", {})) +
                len(ocr_result.get("mapped_tad_fields", {})) -
                len(applied)
            ),
        }
