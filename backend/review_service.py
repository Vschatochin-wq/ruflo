"""
Opus 4.6 Review Service for 8D-Report Quality Assessment
=========================================================
Evaluates completed 8D reports for completeness, consistency,
plausibility, and effectiveness using Claude Opus 4.6.

Integration: Import and register in server.py
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase
import uuid
import os

logger = logging.getLogger(__name__)

# Complaint ID validation pattern
COMPLAINT_ID_PATTERN = re.compile(r'^[a-zA-Z0-9\-]{1,64}$')

# Minimum seconds between reviews for same complaint (rate limiting)
REVIEW_COOLDOWN_SECONDS = 60


def _sanitize_for_prompt(text: str) -> str:
    """Sanitize user input before injecting into LLM prompts.
    Escapes curly braces and wraps in boundary markers."""
    if not text:
        return ""
    # Escape Python format-string braces
    text = text.replace("{", "{{").replace("}", "}}")
    # Strip common prompt injection patterns
    text = re.sub(r'(?i)(ignore|forget|disregard)\s+(all\s+)?(previous\s+)?(instructions|rules|prompts)', '[FILTERED]', text)
    return text


def _validate_complaint_id(complaint_id: str) -> str:
    """Validate complaint ID format."""
    if not complaint_id or not COMPLAINT_ID_PATTERN.match(complaint_id):
        raise ValueError(f"Ungültige Reklamations-ID: {complaint_id}")
    return complaint_id

# Opus 4.6 structured review prompt
OPUS_REVIEW_SYSTEM_PROMPT = """Du bist ein erfahrener Qualitätsmanagement-Experte bei GÜHRING KG,
spezialisiert auf die Bewertung von 8D-Reports nach VDA- und IATF-16949-Standards.

Deine Aufgabe ist es, einen fertiggestellten 8D-Report kritisch zu prüfen und eine
strukturierte Bewertung abzugeben.

Bewertungskriterien pro D-Schritt:
- Vollständigkeit: Sind alle erforderlichen Informationen vorhanden?
- Konsistenz: Passen die Inhalte logisch zusammen (D4→D5→D7)?
- Plausibilität: Sind die beschriebenen Maßnahmen realistisch und angemessen?
- Wirksamkeit: Ist nachvollziehbar, dass die Maßnahmen das Problem lösen?
- Fachliche Tiefe: Wurde systematisch gearbeitet (5-Why, Ishikawa, etc.)?

Scoring:
- 0-30: Unzureichend - Grundlegende Mängel
- 31-60: Schwach - Erheblicher Überarbeitungsbedarf
- 61-80: Akzeptabel - Kleinere Verbesserungen nötig
- 81-95: Gut - Nur Feinschliff erforderlich
- 96-100: Exzellent - Best Practice

WICHTIG:
- Sei kritisch aber konstruktiv
- Nenne konkrete Verbesserungsvorschläge
- Prüfe insbesondere ob D5 (Korrekturmaßnahmen) die Grundursache aus D4 adressiert
- Prüfe ob D7 (Prävention) systemische Verbesserungen enthält
- Bewerte die 5-Why-Analyse auf Tiefe (mindestens 5 Warum-Fragen)

Antworte AUSSCHLIESSLICH im folgenden JSON-Format:"""

OPUS_REVIEW_USER_PROMPT = """Bewerte den folgenden 8D-Report und gib deine Bewertung als JSON zurück.

REKLAMATION: {complaint_number}
KUNDE: {customer_name}
MELDUNGSTYP: {message_type}
REPORT-TYP: {report_type}

--- D0: STAMMDATEN ---
Kunde: {customer_name} ({customer_number})
Produkt: FA {fa_code}, Artikel {article_number}
Problem: {problem_description}
Fehlerort: {error_location}
Betroffene Menge: {affected_quantity} / Geliefert: {delivered_quantity}

--- D1: TEAM ---
{team_members}

--- D2: FEHLERBESCHREIBUNG ---
{errors}

--- D3: SOFORTMAßNAHMEN ---
{immediate_actions}

--- D4: URSACHENANALYSE ---
Ursachen: {causes}
5-Why-Analyse: {five_why}

--- D5: KORREKTURMAßNAHMEN ---
{corrective_actions}

--- D6: WIRKSAMKEITSPRÜFUNG ---
{verification}

--- D7: VORBEUGEMAßNAHMEN ---
{preventive_actions}

--- D8: ABSCHLUSS ---
{closure}

Antworte im folgenden JSON-Format:
{{
  "overall_score": <0-100>,
  "recommendation": "revision_needed" | "minor_revision" | "approval_recommended",
  "section_scores": {{
    "D1_team": {{
      "score": <0-100>,
      "status": "unzureichend|schwach|akzeptabel|gut|exzellent",
      "assessment": "<kurze Bewertung>",
      "issues": ["<konkrete Mängel>"],
      "recommendations": ["<konkrete Verbesserungsvorschläge>"]
    }},
    "D2_problem_description": {{ ... }},
    "D3_immediate_actions": {{ ... }},
    "D4_root_cause": {{ ... }},
    "D5_corrective_actions": {{ ... }},
    "D6_verification": {{ ... }},
    "D7_preventive_actions": {{ ... }},
    "D8_closure": {{ ... }}
  }},
  "consistency_check": {{
    "d4_d5_alignment": true|false,
    "d4_d7_alignment": true|false,
    "d2_d4_alignment": true|false,
    "detail": "<Erklärung der Konsistenzprüfung>"
  }},
  "plausibility_check": {{
    "passed": true|false,
    "detail": "<Erklärung der Plausibilitätsprüfung>"
  }},
  "overall_assessment": "<Gesamtbewertung in 2-3 Sätzen>",
  "action_items": ["<konkrete To-Dos für Überarbeitung>"],
  "strengths": ["<was gut gemacht wurde>"]
}}"""


class ReviewService:
    """
    Manages Opus 4.6 quality reviews for completed 8D reports.

    Usage:
        review_service = ReviewService(db)
        result = await review_service.request_review(complaint_id, requested_by)
        reviews = await review_service.get_reviews(complaint_id)
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.reviews_collection = db.opus_reviews
        self.complaints_collection = db.complaints
        self._client = None

    @property
    def _anthropic_client(self):
        """Lazy singleton Anthropic client for connection reuse."""
        if not self._client:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY ist nicht konfiguriert")
            self._client = anthropic.AsyncAnthropic(api_key=api_key)
        return self._client

    async def create_indexes(self):
        """Create database indexes for performance."""
        await self.reviews_collection.create_index("complaint_id")
        await self.reviews_collection.create_index("created_at")
        await self.reviews_collection.create_index("overall_score")
        await self.reviews_collection.create_index(
            [("complaint_id", 1), ("created_at", -1)]
        )

    async def request_review(
        self,
        complaint_id: str,
        requested_by: str,
        requested_by_name: str = "",
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Request an Opus 4.6 review for a complaint's 8D report.

        Args:
            complaint_id: The complaint document ID
            requested_by: User ID who requested the review
            requested_by_name: Display name of requester
            force: Force review even if minimum requirements not met

        Returns:
            Review result with scores, issues, and recommendations
        """
        # 0. Validate input
        _validate_complaint_id(complaint_id)

        # 1. Load complaint
        complaint = await self.complaints_collection.find_one({"id": complaint_id})
        if not complaint:
            raise ValueError(f"Reklamation {complaint_id} nicht gefunden")

        # 1b. Rate limiting — prevent rapid successive reviews
        last_review = await self.get_latest_review(complaint_id)
        if last_review and not force:
            last_time = datetime.fromisoformat(last_review["created_at"].replace("Z", "+00:00"))
            elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
            if elapsed < REVIEW_COOLDOWN_SECONDS:
                return {
                    "success": False,
                    "error": f"Bitte warten Sie {int(REVIEW_COOLDOWN_SECONDS - elapsed)} Sekunden vor dem nächsten Review",
                    "cooldown_remaining": int(REVIEW_COOLDOWN_SECONDS - elapsed)
                }

        # 2. Check readiness
        readiness = self._check_readiness(complaint)
        if not readiness["ready"] and not force:
            return {
                "success": False,
                "error": "8D-Report ist noch nicht bereit für die Qualitätsprüfung",
                "missing_sections": readiness["missing"],
                "completion_percentage": readiness["completion"]
            }

        # 3. Build prompt context
        prompt_data = self._build_prompt_data(complaint)

        # 4. Call Opus 4.6
        review_result = await self._call_opus(prompt_data)

        # 5. Store review
        review_record = {
            "id": str(uuid.uuid4()),
            "complaint_id": complaint_id,
            "complaint_number": complaint.get("complaint_number", ""),
            "model": "claude-opus-4-6",
            "requested_by": requested_by,
            "requested_by_name": requested_by_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "review_data": review_result,
            "overall_score": review_result.get("overall_score", 0),
            "recommendation": review_result.get("recommendation", "revision_needed"),
            "action_items_count": len(review_result.get("action_items", [])),
            "review_number": await self._get_next_review_number(complaint_id)
        }

        await self.reviews_collection.insert_one(review_record)

        # 6. Determine next status
        score = review_result.get("overall_score", 0)
        recommendation = review_result.get("recommendation", "revision_needed")

        # Score boundaries aligned with prompt rubric:
        # 81-100 = Gut/Exzellent → approval_pending
        # 61-80  = Akzeptabel → reviewed (minor revision)
        # 0-60   = Schwach/Unzureichend → revision_needed
        if recommendation == "approval_recommended" and score >= 81:
            new_status = "approval_pending"
        elif recommendation in ("approval_recommended", "minor_revision") and score >= 61:
            new_status = "reviewed"
        else:
            new_status = "revision_needed"

        # 7. Atomic update: status + review + history in ONE operation (prevents race conditions)
        now = datetime.now(timezone.utc).isoformat()
        update_result = await self.complaints_collection.update_one(
            {"id": complaint_id, "status": complaint.get("status", "")},  # Optimistic lock
            {
                "$set": {
                    "status": new_status,
                    "latest_opus_review": {
                        "review_id": review_record["id"],
                        "score": score,
                        "recommendation": recommendation,
                        "reviewed_at": review_record["created_at"],
                        "action_items_count": review_record["action_items_count"]
                    },
                    "updated_at": now
                },
                "$push": {
                    "status_history": {
                        "from": complaint.get("status", ""),
                        "to": new_status,
                        "changed_by": requested_by,
                        "changed_at": now,
                        "reason": f"Opus 4.6 Review: Score {score}/100 — {recommendation}"
                    }
                }
            }
        )

        if update_result.modified_count == 0:
            logger.warning(f"Concurrent modification detected for {complaint_id}")
            raise ValueError("Reklamation wurde gleichzeitig von einem anderen Benutzer geändert. Bitte erneut versuchen.")

        review_record["new_status"] = new_status
        review_record.pop("_id", None)

        logger.info(
            f"Opus 4.6 Review completed: {complaint.get('complaint_number', complaint_id)} "
            f"Score: {score}/100, Recommendation: {recommendation}"
        )

        return {"success": True, "review": review_record}

    async def get_reviews(
        self,
        complaint_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get all reviews for a complaint, newest first."""
        cursor = self.reviews_collection.find(
            {"complaint_id": complaint_id}
        ).sort("created_at", -1).limit(limit)

        reviews = await cursor.to_list(length=limit)
        for r in reviews:
            r.pop("_id", None)
        return reviews

    async def get_latest_review(self, complaint_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent review for a complaint."""
        review = await self.reviews_collection.find_one(
            {"complaint_id": complaint_id},
            sort=[("created_at", -1)]
        )
        if review:
            review.pop("_id", None)
        return review

    async def get_review_statistics(self) -> Dict[str, Any]:
        """Get aggregated review statistics."""
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_reviews": {"$sum": 1},
                    "avg_score": {"$avg": "$overall_score"},
                    "min_score": {"$min": "$overall_score"},
                    "max_score": {"$max": "$overall_score"},
                    "approved_count": {
                        "$sum": {"$cond": [{"$eq": ["$recommendation", "approval_recommended"]}, 1, 0]}
                    },
                    "revision_count": {
                        "$sum": {"$cond": [{"$eq": ["$recommendation", "revision_needed"]}, 1, 0]}
                    },
                    "minor_revision_count": {
                        "$sum": {"$cond": [{"$eq": ["$recommendation", "minor_revision"]}, 1, 0]}
                    }
                }
            }
        ]
        result = await self.reviews_collection.aggregate(pipeline).to_list(1)
        if result:
            stats = result[0]
            stats.pop("_id", None)
            stats["avg_score"] = round(stats.get("avg_score", 0), 1)
            return stats
        return {
            "total_reviews": 0, "avg_score": 0,
            "approved_count": 0, "revision_count": 0
        }

    async def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """Get complaints in review_pending status that need Opus review."""
        cursor = self.complaints_collection.find(
            {"status": {"$in": ["review_pending", "in_progress"]}},
            {"_id": 0, "id": 1, "complaint_number": 1, "customer_name": 1,
             "status": 1, "created_at": 1, "current_step": 1}
        ).sort("created_at", -1)
        return await cursor.to_list(length=100)

    def _check_readiness(self, complaint: Dict) -> Dict[str, Any]:
        """Check if a complaint is ready for Opus review."""
        checks = {
            "D1_team": bool(complaint.get("team_members")),
            "D2_errors": bool(complaint.get("errors")),
            "D3_immediate": bool(complaint.get("immediate_actions")),
            "D4_causes": bool(complaint.get("causes")),
            "D5_corrective": bool(complaint.get("corrective_actions")),
        }

        # D6, D7, D8 are optional but contribute to readiness
        optional = {
            "D6_verification": bool(complaint.get("verification_actions") or complaint.get("verification")),
            "D7_preventive": bool(complaint.get("preventive_actions")),
            "D8_closure": bool(complaint.get("closure_notes") or complaint.get("closure")),
        }

        required_complete = all(checks.values())
        missing = [k for k, v in {**checks, **optional}.items() if not v]
        total = len(checks) + len(optional)
        filled = total - len(missing)

        return {
            "ready": required_complete,
            "missing": missing,
            "completion": round(filled / total * 100)
        }

    def _build_prompt_data(self, complaint: Dict) -> Dict[str, str]:
        """Extract and format complaint data for the Opus prompt."""

        def format_list(items, fields=None):
            if not items:
                return "Keine Einträge"
            if isinstance(items, str):
                return items
            result = []
            for i, item in enumerate(items, 1):
                if isinstance(item, dict):
                    parts = []
                    for f in (fields or item.keys()):
                        val = item.get(f, "")
                        if val:
                            parts.append(f"{f}: {val}")
                    result.append(f"  {i}. {', '.join(parts)}")
                else:
                    result.append(f"  {i}. {item}")
            return "\n".join(result) if result else "Keine Einträge"

        def safe(key, default="Nicht angegeben"):
            val = complaint.get(key, default)
            return val if val else default

        five_why_data = complaint.get("five_why", {})
        if isinstance(five_why_data, dict):
            qa = five_why_data.get("question_answers", [])
            five_why_str = "\n".join(
                f"  Warum {i+1}: {q.get('question', '')} → {q.get('answer', '')}"
                for i, q in enumerate(qa)
            ) if qa else "Nicht durchgeführt"
            root = five_why_data.get("root_cause", "")
            if root:
                five_why_str += f"\n  Grundursache: {root}"
        else:
            five_why_str = str(five_why_data) if five_why_data else "Nicht durchgeführt"

        verification = complaint.get("verification_actions") or complaint.get("verification", {})
        if isinstance(verification, dict):
            verification_str = (
                f"Methode: {verification.get('method', 'N/A')}, "
                f"Ergebnis: {verification.get('result', 'N/A')}, "
                f"Geprüft von: {verification.get('verified_by', 'N/A')}"
            )
        elif isinstance(verification, list):
            verification_str = format_list(verification, ["description", "responsible", "status"])
        else:
            verification_str = str(verification) if verification else "Nicht durchgeführt"

        closure = complaint.get("closure_notes") or complaint.get("closure", {})
        if isinstance(closure, dict):
            closure_str = (
                f"Abschlussnotiz: {closure.get('notes', 'N/A')}, "
                f"Teamwürdigung: {closure.get('team_recognition', 'N/A')}"
            )
        else:
            closure_str = str(closure) if closure else "Nicht dokumentiert"

        return {
            "complaint_number": safe("complaint_number"),
            "customer_name": safe("customer_name"),
            "customer_number": safe("customer_number", ""),
            "message_type": safe("message_type", "Q3"),
            "report_type": safe("report_type", "8D"),
            "fa_code": safe("fa_code", safe("betroffener_fa", "")),
            "article_number": safe("artikel_nummer", safe("article_number", "")),
            "problem_description": safe("problem_description", safe("description", "")),
            "error_location": safe("error_location", ""),
            "affected_quantity": str(safe("affected_quantity", 0)),
            "delivered_quantity": str(safe("delivered_quantity", safe("bezugsmenge_kunde", 0))),
            "team_members": format_list(
                complaint.get("team_members", []),
                ["name", "role", "department"]
            ),
            "errors": format_list(
                complaint.get("errors", []),
                ["code", "description", "category"]
            ),
            "immediate_actions": format_list(
                complaint.get("immediate_actions", []),
                ["code", "description", "responsible", "status", "deadline"]
            ),
            "causes": format_list(
                complaint.get("causes", []),
                ["code", "description", "category"]
            ),
            "five_why": five_why_str,
            "corrective_actions": format_list(
                complaint.get("corrective_actions", []),
                ["code", "description", "responsible", "status", "deadline"]
            ),
            "verification": verification_str,
            "preventive_actions": format_list(
                complaint.get("preventive_actions", []),
                ["code", "description", "responsible", "status", "deadline"]
            ),
            "closure": closure_str,
        }

    async def _call_opus(self, prompt_data: Dict[str, str]) -> Dict[str, Any]:
        """Call Claude Opus 4.6 for 8D report review with timeout."""
        import asyncio
        import anthropic

        client = self._anthropic_client
        user_prompt = OPUS_REVIEW_USER_PROMPT.format(**prompt_data)

        try:
            response = await asyncio.wait_for(
                client.messages.create(
                    model="claude-opus-4-6",
                    max_tokens=4096,
                    system=OPUS_REVIEW_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}]
                ),
                timeout=60
            )

            response_text = response.content[0].text.strip()

            # Extract JSON from response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            review_data = json.loads(response_text)

            # Validate structure
            required_keys = ["overall_score", "recommendation", "section_scores"]
            for key in required_keys:
                if key not in review_data:
                    raise ValueError(f"Missing key in Opus response: {key}")

            # Clamp score
            review_data["overall_score"] = max(0, min(100, review_data["overall_score"]))

            return review_data

        except asyncio.TimeoutError:
            logger.error("Opus 4.6 call timed out after 60s")
            raise RuntimeError("Opus 4.6 Zeitüberschreitung — bitte erneut versuchen")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Opus 4.6 response as JSON: {e}")
            return self._fallback_review("JSON-Parsing fehlgeschlagen")
        except anthropic.APIError as e:
            logger.error(f"Opus 4.6 API error: {e}")
            raise RuntimeError("Qualitätsprüfung fehlgeschlagen — API-Fehler. Bitte versuchen Sie es später erneut.")
        except Exception as e:
            logger.error(f"Unexpected error calling Opus 4.6: {e}")
            raise RuntimeError("Qualitätsprüfung fehlgeschlagen. Bitte versuchen Sie es später erneut.")

    def _fallback_review(self, reason: str) -> Dict[str, Any]:
        """Generate a fallback review when Opus parsing fails."""
        return {
            "overall_score": 0,
            "recommendation": "revision_needed",
            "section_scores": {},
            "consistency_check": {"d4_d5_alignment": False, "detail": reason},
            "plausibility_check": {"passed": False, "detail": reason},
            "overall_assessment": f"Automatische Bewertung fehlgeschlagen: {reason}. Manuelle Prüfung erforderlich.",
            "action_items": ["Manuelle Prüfung durch ZQM durchführen"],
            "strengths": [],
            "_fallback": True,
        }

    async def _get_next_review_number(self, complaint_id: str) -> int:
        """Get the next review number for a complaint."""
        count = await self.reviews_collection.count_documents(
            {"complaint_id": complaint_id}
        )
        return count + 1
