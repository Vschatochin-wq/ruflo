"""
Tests for OcrService — OCR Text Extraction & 8D Field Mapping
==============================================================
Covers: text extraction, field mapping, apply to complaint, validation.
"""

import pytest
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from conftest import MockDB, make_complaint
from ocr_service import OcrService, SECTION_PATTERNS, METADATA_PATTERNS, SUPPORTED_TYPES, MAX_FILE_SIZE


@pytest.fixture
def svc(mock_db):
    return OcrService(mock_db)


# ─── FIELD MAPPING ──────────────────────────────────────────────

SAMPLE_8D_TEXT = """
Reklamations-Nr.: RK-2026-0042
KUNDENNAME: Bosch Rexroth AG
KUNDENNUMMER: 9214500
FA
75490706
ART.-/SOBO-NR.
ART-9876
DATUM DER FESTSTELLUNG: 15.03.2026
SPEZIFISCHER ORT: Wareneingang

D1 Team:
Max Müller (Leiter), Anna Schmidt (QM), Peter Weber (Produktion)

D2 Problembeschreibung:
Bohrer VHM Typ 3.5mm zeigt vorzeitigen Verschleiß nach 100 Zyklen.
Toleranzabweichung von +0.05mm am Durchmesser festgestellt.

D3 Sofortmaßnahmen:
Los 2026-0315 gesperrt. Betroffene Teile aus Wareneingang isoliert.
Rücksortierung eingeleitet.

D4 Ursachenanalyse:
Härteprozess im Ofen 3 war fehlerhaft. Temperaturregelung zeigte
Abweichung von -15°C. 5-Why: Sensordefekt → Kalibrierung überfällig.

D5 Abstellmaßnahmen:
Temperatursensor in Ofen 3 ersetzt. Kalibrierungsintervall von
6 Monate auf 3 Monate verkürzt. Alle Öfen nachkalibriert.

D6 Verifizierung:
Stichprobenprüfung (n=50) bestanden. Standzeit wieder im Sollbereich.
Prüfung durch QM am 20.03.2026.

D7 Vorbeugemaßnahmen:
SPC-Monitoring für alle Härteöfen eingeführt.
Automatische Alarme bei Temperaturabweichung > 5°C implementiert.

D8 Abschluss:
Lessons Learned dokumentiert. Team aufgelöst am 25.03.2026.
"""

SAMPLE_MINIMAL_TEXT = """
Kunde: Testfirma GmbH
Problem: Teile defekt.
"""


class TestFieldMapping:

    def test_maps_all_metadata(self, svc):
        result = svc.map_to_8d_fields(SAMPLE_8D_TEXT)

        assert result["metadata"]["complaint_number"] == "RK-2026-0042"
        assert "Bosch" in result["metadata"]["customer_name"]
        assert result["metadata"]["customer_number"] == "9214500"
        assert result["metadata"]["fa_code"] == "75490706"
        assert result["metadata"]["artikel_nummer"] == "ART-9876"
        assert "15" in result["metadata"]["detection_date"]
        assert "Wareneingang" in result["metadata"]["error_location"]

    def test_maps_all_8d_sections(self, svc):
        result = svc.map_to_8d_fields(SAMPLE_8D_TEXT)

        assert "Max Müller" in result["sections"]["team_members"]
        assert "Bohrer" in result["sections"]["problem_description"]
        assert "gesperrt" in result["sections"]["immediate_actions"]
        assert "Härteprozess" in result["sections"]["root_cause"]
        assert "Temperatursensor" in result["sections"]["corrective_actions"]
        assert "Stichprobenprüfung" in result["sections"]["verification"]
        assert "SPC" in result["sections"]["preventive_actions"]
        assert "Lessons Learned" in result["sections"]["closure"]

    def test_high_mapping_confidence(self, svc):
        result = svc.map_to_8d_fields(SAMPLE_8D_TEXT)
        # Should map most fields
        assert result["mapped_field_count"] >= 10

    def test_minimal_text_low_confidence(self, svc):
        result = svc.map_to_8d_fields(SAMPLE_MINIMAL_TEXT)
        assert result["mapped_field_count"] <= 3

    def test_empty_text(self, svc):
        result = svc.map_to_8d_fields("")
        assert result["mapped_field_count"] == 0
        assert result["mapping_confidence"] == 0.0


class TestTadFormMapping:
    """Tests specific to GÜHRING TAD-Problemmeldebogen format."""

    def test_maps_tad_form_data(self, svc):
        tad_text = """
GÜHRING GRUPPE
TAD - Problemmeldebogen
AN-VA-14-RB-01-05_Rev.6

1. ALLGEMEINE INFORMATIONEN
KUNDENNAME *
Beinbauer Machining Kelberg GmbH
KUNDENNUMMER *
9214500
ERSTELLT VON*
Carsten Schäfer
TELEFON
01726581997
KUNDENAUFTRAGSNR. *
1412290043
LIEFERSCHEINNR. *
2415639652
RETOURENNUMMER
2415483986
DATUM DER FESTSTELLUNG DES FEHLERS*
2026-02-18
MELDEDATUM*
2026-02-19

2. WERKZEUGDATEN
FA *
75490706
ART.-/SOBO-NR. *
372280223
Werden Werkzeuge zurück versendet?
Nein
BEGRÜNDUNG *
Wegen drohendem Maschinenstillstand wurden die Werkzeuge beim Kunden angeschliffen
WER HAT DEN FEHLER ENTDECKT? *
Den Fehler hat Herr Schäfer (TAD Gühring) beim Kundeneinsatz vor Ort entdeckt.

3. PROBLEMBESCHREIBUNG (5W2H)
WHAT? (Was ist das Problem?)
Produktfehler
SCHADENSBILD (HAUPTGRUPPE)
GEOMET - Geometrie
FEHLERCODE
9307 - Schneidengeometrie
Detaillierte Problembeschreibung
Der Übergangsradius (Soll: R 3,8 mm ± 0,3 mm) von der Schneide zur Querschneide fehlt (Ist: 0 mm).

4. TECHNISCHE DETAILS
WHERE? (Wo trat der Fehler auf?)
Produktion
SPEZIFISCHER ORT
Hauptschneide – Radiusbereich zur Querschneide, auf Bohrstation 2 - Maschine: DMG Mo...
HOW? (Wie wurde der Fehler entdeckt?)
Der Fehler äußerte sich durch vorzeitigen Verschleiß, instabile Spanbildung.
HOW MUCH? (Wie viele Teile sind betroffen?)
BETROFFENE MENGE (STÜCK) *
9
GELIEFERTE MENGE (STÜCK) *
9

5. SAP MELDUNGSTYP
Q1-Meldung (Reklamation Direktkunde)
"""
        result = svc.map_to_8d_fields(tad_text)

        # Metadata
        assert "Beinbauer" in result["metadata"]["customer_name"]
        assert result["metadata"]["customer_number"] == "9214500"
        assert result["metadata"]["fa_code"] == "75490706"
        assert result["metadata"]["artikel_nummer"] == "372280223"
        assert "2026-02-18" in result["metadata"]["detection_date"]
        assert result["metadata"]["delivery_note_number"] == "2415639652"
        assert result["metadata"]["return_number"] == "2415483986"

        # TAD-specific fields
        assert "Produktfehler" in result["tad_fields"].get("problem_type", "")
        assert "GEOMET" in result["tad_fields"].get("damage_category", "")
        assert "9307" in result["tad_fields"].get("error_code", "")
        assert "Übergangsradius" in result["tad_fields"].get("problem_description", "")
        assert "9" in result["tad_fields"].get("affected_quantity", "")
        assert "Q1" in result["tad_fields"].get("message_type", "")

        # Overall mapped count should be high
        assert result["mapped_field_count"] >= 12


# ─── TEXT EXTRACTION VALIDATION ─────────────────────────────────

class TestExtractionValidation:

    @pytest.mark.asyncio
    async def test_rejects_unsupported_type(self, svc):
        with pytest.raises(ValueError, match="Nicht unterstützter"):
            await svc.extract_text("/tmp/test.doc", "application/msword")

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_file(self, svc):
        with pytest.raises(FileNotFoundError):
            await svc.extract_text("/nonexistent/file.pdf", "application/pdf")

    @pytest.mark.asyncio
    async def test_rejects_oversized_file(self, svc):
        # Create a temp file larger than MAX_FILE_SIZE
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"x" * (MAX_FILE_SIZE + 1))
            f.flush()
            path = f.name

        try:
            with pytest.raises(ValueError, match="zu groß"):
                await svc.extract_text(path, "application/pdf")
        finally:
            os.unlink(path)


# ─── APPLY TO COMPLAINT ────────────────────────────────────────

class TestApplyToComplaint:

    @pytest.mark.asyncio
    async def test_applies_mapped_fields(self, svc, mock_db):
        complaint = make_complaint(has_d_steps=False)
        # Clear fields so OCR can fill them
        complaint["problem_description"] = ""
        complaint["customer_name"] = ""
        mock_db.add_complaint(complaint)

        # Create OCR result
        ocr_result = {
            "id": "ocr-1",
            "mapped_metadata": {
                "customer_name": "Bosch Rexroth AG",
                "complaint_number": "RK-2026-0042",
            },
            "mapped_sections": {
                "problem_description": "Bohrer zeigt Verschleiß",
            },
        }
        mock_db.ocr_results._data.append(ocr_result)

        result = await svc.apply_to_complaint(complaint["id"], "ocr-1")

        assert result["success"] is True
        assert result["applied_count"] >= 2

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing(self, svc, mock_db):
        complaint = make_complaint(has_d_steps=True)
        complaint["customer_name"] = "Existing Customer"
        mock_db.add_complaint(complaint)

        ocr_result = {
            "id": "ocr-2",
            "mapped_metadata": {"customer_name": "OCR Customer"},
            "mapped_sections": {},
        }
        mock_db.ocr_results._data.append(ocr_result)

        result = await svc.apply_to_complaint(complaint["id"], "ocr-2")

        # customer_name already has value, should be skipped
        assert result["skipped_count"] >= 1

    @pytest.mark.asyncio
    async def test_selected_fields_filter(self, svc, mock_db):
        complaint = make_complaint(has_d_steps=False)
        complaint["customer_name"] = ""
        complaint["problem_description"] = ""
        mock_db.add_complaint(complaint)

        ocr_result = {
            "id": "ocr-3",
            "mapped_metadata": {
                "customer_name": "Test Kunde",
                "fa_code": "FA-999",
            },
            "mapped_sections": {
                "problem_description": "Test problem",
            },
        }
        mock_db.ocr_results._data.append(ocr_result)

        # Only apply customer_name
        result = await svc.apply_to_complaint(
            complaint["id"], "ocr-3", selected_fields=["customer_name"]
        )

        assert result["applied_count"] == 1
        applied_fields = [f["field"] for f in result["applied_fields"]]
        assert "customer_name" in applied_fields
        assert "fa_code" not in applied_fields

    @pytest.mark.asyncio
    async def test_nonexistent_ocr_result(self, svc, mock_db):
        complaint = make_complaint()
        mock_db.add_complaint(complaint)

        with pytest.raises(ValueError, match="OCR-Ergebnis nicht gefunden"):
            await svc.apply_to_complaint(complaint["id"], "nonexistent")

    @pytest.mark.asyncio
    async def test_nonexistent_complaint(self, svc, mock_db):
        ocr_result = {"id": "ocr-4", "mapped_metadata": {}, "mapped_sections": {}}
        mock_db.ocr_results._data.append(ocr_result)

        with pytest.raises(ValueError, match="Reklamation nicht gefunden"):
            await svc.apply_to_complaint("nonexistent", "ocr-4")


# ─── EXTRACT AND MAP PIPELINE ──────────────────────────────────

class TestExtractAndMap:

    @pytest.mark.asyncio
    async def test_full_pipeline_stores_result(self, svc, mock_db):
        # Create a temp text file and mock OCR
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG fake image data for test")
            f.flush()
            path = f.name

        try:
            with patch.object(svc, '_extract_from_image', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = {
                    "extracted_text": SAMPLE_8D_TEXT,
                    "page_count": 1,
                    "confidence": 0.85,
                    "method": "tesseract",
                    "char_count": len(SAMPLE_8D_TEXT),
                }

                result = await svc.extract_and_map(
                    file_path=path,
                    mime_type="image/png",
                    complaint_id="comp-1",
                    document_id="doc-1",
                )

                assert result["id"]
                assert result["complaint_id"] == "comp-1"
                assert result["document_id"] == "doc-1"
                assert result["ocr_confidence"] == 0.85
                assert result["mapping_confidence"] > 0
                assert result["status"] == "completed"
                assert "Bosch" in result["mapped_metadata"].get("customer_name", "")

                # Verify stored in DB
                stored = await mock_db.ocr_results.find_one({"id": result["id"]})
                assert stored is not None
        finally:
            os.unlink(path)


# ─── SUPPORTED TYPES ───────────────────────────────────────────

class TestSupportedTypes:

    def test_pdf_is_supported(self):
        assert "application/pdf" in SUPPORTED_TYPES

    def test_images_are_supported(self):
        assert "image/png" in SUPPORTED_TYPES
        assert "image/jpeg" in SUPPORTED_TYPES
        assert "image/tiff" in SUPPORTED_TYPES

    def test_word_not_supported(self):
        assert "application/msword" not in SUPPORTED_TYPES

    def test_all_patterns_compile(self):
        """Verify all regex patterns are valid."""
        for patterns in SECTION_PATTERNS.values():
            for p in patterns:
                assert p.pattern  # Compiled regex has pattern attribute

        for patterns in METADATA_PATTERNS.values():
            for p in patterns:
                assert p.pattern
