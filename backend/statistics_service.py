"""
Statistics & Analytics Service
===============================
Aggregierte Kennzahlen und Analysen fuer das Reklamationsmanagement.
Liefert Daten fuer Dashboard-KPIs, Diagramme und Trendanalysen.

Integration:
    from statistics_service import StatisticsService
    stats_service = StatisticsService(db)
    kpis = await stats_service.get_dashboard_kpis()
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Status-Gruppen fuer KPI-Berechnung
OPEN_STATUSES = {
    "draft", "intake", "waiting_info", "open", "in_progress",
    "review_pending", "reviewed", "revision_needed",
    "approval_pending",
}
CLOSED_STATUSES = {"approved", "closed", "archived"}


class StatisticsService:
    """
    Analyse-Service fuer Reklamationsstatistiken.

    Usage:
        service = StatisticsService(db)
        kpis = await service.get_dashboard_kpis()
        distribution = await service.get_status_distribution()
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.complaints = db.complaints
        self.reviews = db.opus_reviews

    # ─── DASHBOARD KPIs ──────────────────────────────────────────────

    async def get_dashboard_kpis(self) -> Dict[str, Any]:
        """
        Zentrale Dashboard-Kennzahlen:
        - Gesamt, offen, abgeschlossen
        - Durchschnittlicher Opus-Score
        - Durchschnittliche Bearbeitungszeit (Tage)
        - Reklamationen diesen Monat
        """
        base_query = {"deleted": {"$ne": True}}

        total = await self.complaints.count_documents(base_query)

        open_query = {**base_query, "status": {"$in": list(OPEN_STATUSES)}}
        open_count = await self.complaints.count_documents(open_query)

        closed_query = {**base_query, "status": {"$in": list(CLOSED_STATUSES)}}
        closed_count = await self.complaints.count_documents(closed_query)

        # Durchschnittlicher Opus-Score
        score_pipeline = [
            {"$match": {}},
            {"$group": {
                "_id": None,
                "avg_score": {"$avg": "$overall_score"},
            }}
        ]
        score_result = await self.reviews.aggregate(score_pipeline).to_list(1)
        avg_score = round(score_result[0]["avg_score"], 1) if score_result and score_result[0].get("avg_score") else 0

        # Durchschnittliche Bearbeitungszeit (created_at bis closed/approved)
        time_pipeline = [
            {"$match": {
                **base_query,
                "status": {"$in": ["closed", "approved", "archived"]},
            }},
            {"$project": {
                "created_at": 1,
                "updated_at": 1,
            }}
        ]
        time_docs = await self.complaints.aggregate(time_pipeline).to_list(1000)
        avg_days = 0
        if time_docs:
            total_days = 0
            count = 0
            for doc in time_docs:
                try:
                    created = datetime.fromisoformat(doc["created_at"].replace("Z", "+00:00"))
                    updated = datetime.fromisoformat(doc["updated_at"].replace("Z", "+00:00"))
                    delta = (updated - created).days
                    total_days += max(0, delta)
                    count += 1
                except (ValueError, KeyError, TypeError):
                    continue
            avg_days = round(total_days / count, 1) if count > 0 else 0

        # Reklamationen diesen Monat
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        this_month_query = {
            **base_query,
            "created_at": {"$gte": month_start}
        }
        this_month = await self.complaints.count_documents(this_month_query)

        return {
            "total_complaints": total,
            "open_complaints": open_count,
            "closed_complaints": closed_count,
            "avg_opus_score": avg_score,
            "avg_processing_time_days": avg_days,
            "complaints_this_month": this_month,
        }

    # ─── STATUS DISTRIBUTION ─────────────────────────────────────────

    async def get_status_distribution(self) -> List[Dict[str, Any]]:
        """Anzahl Reklamationen pro Status (fuer Kreisdiagramm)."""
        pipeline = [
            {"$match": {"deleted": {"$ne": True}}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1},
            }},
            {"$sort": {"count": -1}},
        ]
        result = await self.complaints.aggregate(pipeline).to_list(50)
        return [
            {"status": r["_id"], "count": r["count"]}
            for r in result if r["_id"]
        ]

    # ─── COMPLAINTS BY MONTH ─────────────────────────────────────────

    async def get_complaints_by_month(self, months: int = 12) -> List[Dict[str, Any]]:
        """
        Monatliche Reklamationsanzahl (fuer Balkendiagramm).

        Args:
            months: Anzahl Monate zurueck (Standard 12)
        """
        months = max(1, min(36, months))
        now = datetime.now(timezone.utc)

        # Monate rueckwaerts berechnen
        month_data = []
        for i in range(months - 1, -1, -1):
            year = now.year
            month = now.month - i
            while month <= 0:
                month += 12
                year -= 1

            month_start = datetime(year, month, 1, tzinfo=timezone.utc).isoformat()
            if month == 12:
                month_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc).isoformat()
            else:
                month_end = datetime(year, month + 1, 1, tzinfo=timezone.utc).isoformat()

            count = await self.complaints.count_documents({
                "deleted": {"$ne": True},
                "created_at": {"$gte": month_start, "$lt": month_end}
            })

            month_data.append({
                "year": year,
                "month": month,
                "label": f"{year}-{month:02d}",
                "count": count,
            })

        return month_data

    # ─── TOP ERROR CODES (PARETO) ────────────────────────────────────

    async def get_top_error_codes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Haeufigste Fehlercodes (Pareto-Analyse).

        Args:
            limit: Maximale Anzahl zurueckgegebener Codes
        """
        limit = max(1, min(50, limit))

        pipeline = [
            {"$match": {"deleted": {"$ne": True}, "errors": {"$exists": True}}},
            {"$unwind": "$errors"},
            {"$group": {
                "_id": "$errors.code",
                "description": {"$first": "$errors.description"},
                "count": {"$sum": 1},
            }},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
        result = await self.complaints.aggregate(pipeline).to_list(limit)
        return [
            {
                "code": r["_id"],
                "description": r.get("description", ""),
                "count": r["count"],
            }
            for r in result if r["_id"]
        ]

    # ─── TOP CUSTOMERS ───────────────────────────────────────────────

    async def get_top_customers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Kunden mit den meisten Reklamationen (Pareto-Analyse).

        Args:
            limit: Maximale Anzahl zurueckgegebener Kunden
        """
        limit = max(1, min(50, limit))

        pipeline = [
            {"$match": {"deleted": {"$ne": True}}},
            {"$group": {
                "_id": "$customer_name",
                "count": {"$sum": 1},
            }},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
        result = await self.complaints.aggregate(pipeline).to_list(limit)
        return [
            {"customer_name": r["_id"], "count": r["count"]}
            for r in result if r["_id"]
        ]

    # ─── SCORE DISTRIBUTION ──────────────────────────────────────────

    async def get_score_distribution(self) -> List[Dict[str, Any]]:
        """
        Verteilung der Opus-Review-Scores in Buckets
        (0-20, 20-40, 40-60, 60-80, 80-100) fuer Histogramm.
        """
        buckets = [
            {"label": "0-20", "min": 0, "max": 20},
            {"label": "20-40", "min": 20, "max": 40},
            {"label": "40-60", "min": 40, "max": 60},
            {"label": "60-80", "min": 60, "max": 80},
            {"label": "80-100", "min": 80, "max": 101},  # 101 um 100 einzuschliessen
        ]

        result = []
        for bucket in buckets:
            count = await self.reviews.count_documents({
                "overall_score": {"$gte": bucket["min"], "$lt": bucket["max"]}
            })
            result.append({
                "label": bucket["label"],
                "min_score": bucket["min"],
                "max_score": bucket["max"] if bucket["max"] <= 100 else 100,
                "count": count,
            })

        return result

    # ─── AVG PROCESSING TIME BY MONTH ────────────────────────────────

    async def get_avg_processing_time_by_month(self, months: int = 12) -> List[Dict[str, Any]]:
        """
        Durchschnittliche Bearbeitungszeit (Tage) pro Monat
        fuer abgeschlossene Reklamationen (Liniendiagramm).
        """
        months = max(1, min(36, months))
        now = datetime.now(timezone.utc)
        month_data = []

        for i in range(months - 1, -1, -1):
            year = now.year
            month = now.month - i
            while month <= 0:
                month += 12
                year -= 1

            month_start = datetime(year, month, 1, tzinfo=timezone.utc).isoformat()
            if month == 12:
                month_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc).isoformat()
            else:
                month_end = datetime(year, month + 1, 1, tzinfo=timezone.utc).isoformat()

            # Abgeschlossene Reklamationen in diesem Monat
            pipeline = [
                {"$match": {
                    "deleted": {"$ne": True},
                    "status": {"$in": ["closed", "approved", "archived"]},
                    "updated_at": {"$gte": month_start, "$lt": month_end},
                }},
                {"$project": {"created_at": 1, "updated_at": 1}},
            ]
            docs = await self.complaints.aggregate(pipeline).to_list(1000)

            avg_days = 0
            if docs:
                total_days = 0
                count = 0
                for doc in docs:
                    try:
                        created = datetime.fromisoformat(doc["created_at"].replace("Z", "+00:00"))
                        updated = datetime.fromisoformat(doc["updated_at"].replace("Z", "+00:00"))
                        total_days += max(0, (updated - created).days)
                        count += 1
                    except (ValueError, KeyError, TypeError):
                        continue
                avg_days = round(total_days / count, 1) if count > 0 else 0

            month_data.append({
                "year": year,
                "month": month,
                "label": f"{year}-{month:02d}",
                "avg_days": avg_days,
                "closed_count": len(docs),
            })

        return month_data

    # ─── ERROR LOCATION DISTRIBUTION ─────────────────────────────────

    async def get_error_location_distribution(self) -> List[Dict[str, Any]]:
        """Reklamationen gruppiert nach Fehlerort (Kreis-/Balkendiagramm)."""
        pipeline = [
            {"$match": {
                "deleted": {"$ne": True},
                "error_location": {"$exists": True, "$ne": ""},
            }},
            {"$group": {
                "_id": "$error_location",
                "count": {"$sum": 1},
            }},
            {"$sort": {"count": -1}},
        ]
        result = await self.complaints.aggregate(pipeline).to_list(50)
        return [
            {"error_location": r["_id"], "count": r["count"]}
            for r in result if r["_id"]
        ]

    # ─── TREND DATA ──────────────────────────────────────────────────

    async def get_trend_data(self, months: int = 6) -> List[Dict[str, Any]]:
        """
        Kombinierte Trenddaten pro Monat:
        - Neue Reklamationen
        - Abgeschlossene Reklamationen
        - Durchschnittlicher Opus-Score

        Args:
            months: Anzahl Monate (Standard 6)
        """
        months = max(1, min(24, months))
        now = datetime.now(timezone.utc)
        trend = []

        for i in range(months - 1, -1, -1):
            year = now.year
            month = now.month - i
            while month <= 0:
                month += 12
                year -= 1

            month_start = datetime(year, month, 1, tzinfo=timezone.utc).isoformat()
            if month == 12:
                month_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc).isoformat()
            else:
                month_end = datetime(year, month + 1, 1, tzinfo=timezone.utc).isoformat()

            # Neue Reklamationen
            new_count = await self.complaints.count_documents({
                "deleted": {"$ne": True},
                "created_at": {"$gte": month_start, "$lt": month_end},
            })

            # Abgeschlossene Reklamationen (Status-Wechsel in diesem Monat)
            closed_count = await self.complaints.count_documents({
                "deleted": {"$ne": True},
                "status": {"$in": ["closed", "approved", "archived"]},
                "updated_at": {"$gte": month_start, "$lt": month_end},
            })

            # Durchschnittlicher Review-Score in diesem Monat
            score_pipeline = [
                {"$match": {
                    "created_at": {"$gte": month_start, "$lt": month_end},
                }},
                {"$group": {
                    "_id": None,
                    "avg_score": {"$avg": "$overall_score"},
                    "review_count": {"$sum": 1},
                }}
            ]
            score_result = await self.reviews.aggregate(score_pipeline).to_list(1)
            avg_score = 0
            review_count = 0
            if score_result and score_result[0].get("avg_score") is not None:
                avg_score = round(score_result[0]["avg_score"], 1)
                review_count = score_result[0].get("review_count", 0)

            trend.append({
                "year": year,
                "month": month,
                "label": f"{year}-{month:02d}",
                "new_complaints": new_count,
                "closed_complaints": closed_count,
                "avg_score": avg_score,
                "review_count": review_count,
            })

        return trend
