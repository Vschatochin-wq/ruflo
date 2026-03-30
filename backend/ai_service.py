"""
AI Service — Unified Claude Sonnet 4 + Opus 4.6 Routing
=========================================================
Central service for all AI operations with model routing,
confidence checks, and fallback strategies.

Model Routing:
- Sonnet 4: Extraction, suggestions, auto-replies (fast, cost-efficient)
- Opus 4.6: 8D quality review, plausibility checks (deep reasoning)

Integration:
    from ai_service import AIService
    ai = AIService(db)
    result = await ai.extract_from_email(email_body)
    result = await ai.check_completeness(complaint_data)
    result = await ai.generate_auto_reply(complaint_data, missing_fields)
    result = await ai.suggest_error_codes(problem_description)
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


def _sanitize_for_prompt(text: str) -> str:
    """Sanitize user input before injecting into LLM prompts."""
    if not text:
        return ""
    text = text.replace("{", "{{").replace("}", "}}")
    text = re.sub(r'(?i)(ignore|forget|disregard)\s+(all\s+)?(previous\s+)?(instructions|rules|prompts)', '[FILTERED]', text)
    return text


# ─── MODEL CONFIGURATION ─────────────────────────────────────────────

MODELS = {
    "sonnet": {
        "id": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "use_for": ["extraction", "suggestions", "completeness", "auto_reply", "five_why"],
        "cost_per_1k_input": 0.003,
        "cost_per_1k_output": 0.015,
        "avg_latency_ms": 2000,
    },
    "opus": {
        "id": "claude-opus-4-20250514",
        "max_tokens": 4096,
        "use_for": ["8d_review", "plausibility", "consistency_check"],
        "cost_per_1k_input": 0.015,
        "cost_per_1k_output": 0.075,
        "avg_latency_ms": 5000,
    }
}

# Required fields for complaint creation
REQUIRED_FIELDS = [
    "customer_name", "customer_number", "fa_code", "artikel_nummer",
    "problem_description", "affected_quantity", "message_type",
    "detection_date", "error_location"
]


class AIService:
    """Unified AI service with intelligent model routing via Emergent LLM Key."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._api_key = None

    @property
    def api_key(self):
        if not self._api_key:
            from dotenv import load_dotenv
            load_dotenv()
            self._api_key = os.getenv("EMERGENT_LLM_KEY")
            if not self._api_key:
                raise RuntimeError("EMERGENT_LLM_KEY nicht konfiguriert")
        return self._api_key

    async def _call_model(
        self,
        model_key: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096
    ) -> str:
        """Call a Claude model via Emergent LLM integration and return text response."""
        import uuid
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        model_config = MODELS[model_key]
        chat = LlmChat(
            api_key=self.api_key,
            session_id=f"ai-{model_key}-{uuid.uuid4().hex[:8]}",
            system_message=system_prompt
        ).with_model("anthropic", model_config["id"])

        user_message = UserMessage(text=user_prompt)
        response = await chat.send_message(user_message)
        return response.strip()

    async def _call_model_json(
        self,
        model_key: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """Call a Claude model and parse JSON response."""
        text = await self._call_model(model_key, system_prompt, user_prompt, max_tokens)

        # Extract JSON from markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        return json.loads(text)

    # ─── SONNET 4: EMAIL EXTRACTION ──────────────────────────────────

    async def extract_from_email(self, email_body: str, attachments: List[str] = None) -> Dict[str, Any]:
        """
        Extract complaint data from an incoming email using Sonnet 4.
        Returns structured complaint data with confidence scores.
        """
        system = """Du bist ein Datenextraktions-Spezialist für das GÜHRING Reklamationssystem.
Extrahiere alle relevanten Informationen aus der E-Mail und gib sie als JSON zurück.
Wenn ein Feld nicht eindeutig erkennbar ist, setze den Wert auf null.
Gib für jedes Feld einen Confidence-Score (0.0-1.0) an."""

        sanitized_body = _sanitize_for_prompt(email_body)

        user = f"""Extrahiere die Reklamationsdaten aus folgender E-Mail:

--- E-MAIL-BEGINN ---
{sanitized_body}
--- E-MAIL-ENDE ---

Antworte im JSON-Format:
{{
  "extracted": {{
    "customer_name": {{"value": "...", "confidence": 0.9}},
    "customer_number": {{"value": "...", "confidence": 0.8}},
    "customer_email": {{"value": "...", "confidence": 0.95}},
    "fa_code": {{"value": "...", "confidence": 0.7}},
    "artikel_nummer": {{"value": "...", "confidence": 0.6}},
    "problem_description": {{"value": "...", "confidence": 0.9}},
    "affected_quantity": {{"value": 0, "confidence": 0.5}},
    "error_location": {{"value": "...", "confidence": 0.4}},
    "message_type": {{"value": "Q3", "confidence": 0.6}},
    "detection_date": {{"value": "2026-01-01", "confidence": 0.7}}
  }},
  "overall_confidence": 0.7,
  "summary": "Kurze Zusammenfassung der Reklamation"
}}"""

        try:
            result = await self._call_model_json("sonnet", system, user)
            await self._log_ai_call("extract_from_email", "sonnet", result)
            return result
        except Exception as e:
            logger.error(f"Email extraction failed: {e}")
            return {"error": str(e), "extracted": {}, "overall_confidence": 0}

    # ─── SONNET 4: COMPLETENESS CHECK ────────────────────────────────

    async def check_completeness(self, complaint_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if complaint data is complete enough for automatic creation.

        Returns:
            status: COMPLETE | PARTIAL | INSUFFICIENT
            missing_fields: list of missing field names
            confidence: overall completeness score
            suggestions: what to ask the sender
        """
        missing = []
        filled = 0

        for field in REQUIRED_FIELDS:
            value = complaint_data.get(field)
            if value and str(value).strip() and str(value) != "0":
                filled += 1
            else:
                missing.append(field)

        confidence = filled / len(REQUIRED_FIELDS)

        if confidence >= 1.0:
            status = "COMPLETE"
        elif confidence >= 0.7:
            status = "PARTIAL"
        else:
            status = "INSUFFICIENT"

        # Use Sonnet to generate human-readable missing field descriptions
        field_labels = {
            "customer_name": "Kundenname",
            "customer_number": "Kundennummer",
            "fa_code": "FA-Code des Werkzeugs",
            "artikel_nummer": "Artikelnummer / Sobo-Nr.",
            "problem_description": "Problembeschreibung",
            "affected_quantity": "Betroffene Menge (Stück)",
            "message_type": "SAP-Meldungstyp (Q1/Q3)",
            "detection_date": "Datum der Feststellung",
            "error_location": "Fehlerort (Wareneingang/Produktion/Lagerprüfung)"
        }
        missing_labels = [field_labels.get(f, f) for f in missing]

        return {
            "status": status,
            "confidence": round(confidence, 2),
            "missing_fields": missing,
            "missing_labels": missing_labels,
            "filled_count": filled,
            "total_required": len(REQUIRED_FIELDS)
        }

    # ─── SONNET 4: AUTO REPLY GENERATION ─────────────────────────────

    async def generate_auto_reply(
        self,
        complaint_data: Dict[str, Any],
        missing_fields: List[str],
        sender_name: str = "",
        sender_email: str = "",
        complaint_number: str = ""
    ) -> Dict[str, Any]:
        """
        Generate an automated reply email asking for missing information.
        Uses Sonnet 4 for natural, professional German language.
        """
        field_labels = {
            "customer_name": "Kundenname",
            "customer_number": "Kundennummer",
            "fa_code": "FA-Code des betroffenen Werkzeugs (auf dem Werkzeug-Etikett oder der Auftragsbestätigung)",
            "artikel_nummer": "Artikelnummer / Sobo-Nr.",
            "problem_description": "Detaillierte Problembeschreibung",
            "affected_quantity": "Anzahl der betroffenen Stücke",
            "message_type": "Art der Meldung (Direktkunde oder Niederlassung)",
            "detection_date": "Datum der Feststellung",
            "error_location": "Wo wurde der Fehler festgestellt (Wareneingang, Produktion oder Lagerprüfung)"
        }

        missing_descriptions = [field_labels.get(f, f) for f in missing_fields]

        system = """Du bist der automatische E-Mail-Assistent des GÜHRING KG Qualitätsmanagements.
Schreibe professionelle, freundliche und präzise E-Mails auf Deutsch.
Die E-Mail soll den Absender höflich bitten, die fehlenden Informationen nachzureichen.
Verwende formelle Anrede (Sie-Form).
Unterschreibe mit: GÜHRING KG — Qualitätsmanagement"""

        user = f"""Erstelle eine Antwort-E-Mail an den Kunden.

Absender: {sender_name} ({sender_email})
Reklamationsnummer: {complaint_number or 'wird nach Vervollständigung vergeben'}
Bereits vorhandene Daten: {json.dumps({k: v for k, v in complaint_data.items() if v}, ensure_ascii=False, indent=2)[:500]}

Fehlende Informationen:
{chr(10).join(f'- {desc}' for desc in missing_descriptions)}

Erstelle die E-Mail im JSON-Format:
{{
  "subject": "Re: Reklamation - Fehlende Angaben benötigt [Ref: ...]",
  "body": "vollständiger E-Mail-Text",
  "tone": "professional",
  "missing_count": {len(missing_fields)}
}}"""

        try:
            result = await self._call_model_json("sonnet", system, user)
            await self._log_ai_call("generate_auto_reply", "sonnet", {"missing": missing_fields})
            return result
        except Exception as e:
            logger.error(f"Auto-reply generation failed: {e}")
            # Fallback: generate a basic reply without AI
            return self._generate_fallback_reply(sender_name, complaint_number, missing_descriptions)

    # ─── SONNET 4: SUGGESTIONS ───────────────────────────────────────

    async def suggest_error_codes(
        self,
        problem_description: str,
        existing_errors: List[str] = None
    ) -> List[Dict[str, str]]:
        """Suggest error codes based on problem description."""
        system = """Du bist ein Qualitätsmanagement-Experte bei GÜHRING KG (Werkzeughersteller).
Schlage passende Fehlercodes und Fehlerbeschreibungen vor basierend auf der Problembeschreibung.
Berücksichtige typische Fehlerbilder bei Präzisionswerkzeugen (Bohrer, Fräser, etc.)."""

        user = f"""Problembeschreibung: {_sanitize_for_prompt(problem_description)}

Schlage 3-5 passende Fehlercodes vor im JSON-Format:
[
  {{"code": "F-001", "description": "Fehlerbezeichnung", "category": "Kategorie"}},
  ...
]"""

        try:
            result = await self._call_model_json("sonnet", system, user)
            return result if isinstance(result, list) else result.get("suggestions", [])
        except Exception as e:
            logger.error(f"Error code suggestion failed: {e}")
            return []

    async def suggest_causes(
        self,
        problem_description: str,
        errors: List[Dict] = None
    ) -> List[Dict[str, str]]:
        """Suggest root causes based on problem and errors."""
        system = """Du bist ein Qualitätsmanagement-Experte bei GÜHRING KG.
Schlage mögliche Ursachen für das beschriebene Problem vor.
Nutze die Ishikawa-Kategorien: Mensch, Maschine, Material, Methode, Messung, Mitwelt."""

        errors_str = json.dumps(errors, ensure_ascii=False) if errors else "Keine"

        user = f"""Problem: {_sanitize_for_prompt(problem_description)}
Fehler: {errors_str}

Schlage 3-5 mögliche Ursachen vor im JSON-Format:
[
  {{"code": "U-001", "description": "Ursachenbeschreibung", "category": "Mensch|Maschine|Material|Methode|Messung|Mitwelt"}},
  ...
]"""

        try:
            result = await self._call_model_json("sonnet", system, user)
            return result if isinstance(result, list) else result.get("suggestions", [])
        except Exception as e:
            logger.error(f"Cause suggestion failed: {e}")
            return []

    async def suggest_actions(
        self,
        action_type: str,
        problem_description: str,
        causes: List[Dict] = None
    ) -> List[Dict[str, str]]:
        """Suggest corrective/preventive actions."""
        type_labels = {
            "immediate": "Sofortmaßnahmen (D3)",
            "corrective": "Korrekturmaßnahmen (D5)",
            "preventive": "Vorbeugemaßnahmen (D7)"
        }

        system = f"""Du bist ein Qualitätsmanagement-Experte bei GÜHRING KG.
Schlage passende {type_labels.get(action_type, action_type)} vor.
Maßnahmen müssen konkret, messbar und umsetzbar sein."""

        causes_str = json.dumps(causes, ensure_ascii=False) if causes else "Keine"

        user = f"""Problem: {_sanitize_for_prompt(problem_description)}
Ursachen: {causes_str}
Gewünschter Maßnahmentyp: {type_labels.get(action_type, action_type)}

Schlage 3-5 Maßnahmen vor im JSON-Format:
[
  {{"code": "M-001", "description": "Maßnahmenbeschreibung", "responsible": "Rolle/Abteilung", "deadline_days": 14}},
  ...
]"""

        try:
            result = await self._call_model_json("sonnet", system, user)
            return result if isinstance(result, list) else result.get("suggestions", [])
        except Exception as e:
            logger.error(f"Action suggestion failed: {e}")
            return []

    # ─── AI CALL LOGGING ─────────────────────────────────────────────

    async def _log_ai_call(self, operation: str, model: str, result_summary: Any):
        """Log AI API calls for audit and cost tracking."""
        try:
            await self.db.ai_call_logs.insert_one({
                "id": str(__import__("uuid").uuid4()),
                "operation": operation,
                "model": MODELS[model]["id"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "result_summary": str(result_summary)[:500]
            })
        except Exception:
            pass  # Logging should never block operations

    def _generate_fallback_reply(
        self,
        sender_name: str,
        complaint_number: str,
        missing_descriptions: List[str]
    ) -> Dict[str, Any]:
        """Generate a basic reply when AI is unavailable."""
        missing_list = "\n".join(f"  {i+1}. {desc}" for i, desc in enumerate(missing_descriptions))

        return {
            "subject": f"Re: Reklamation - Fehlende Angaben benötigt [Ref: {complaint_number}]",
            "body": (
                f"Sehr geehrte/r {sender_name or 'Kunde'},\n\n"
                f"vielen Dank für Ihre Reklamationsmeldung.\n\n"
                f"Für die zügige Bearbeitung benötigen wir noch folgende Informationen:\n\n"
                f"{missing_list}\n\n"
                f"Bitte antworten Sie auf diese E-Mail mit den fehlenden Angaben.\n\n"
                f"Mit freundlichen Grüßen\n"
                f"GÜHRING KG — Qualitätsmanagement"
            ),
            "tone": "professional",
            "missing_count": len(missing_descriptions),
            "_fallback": True
        }
