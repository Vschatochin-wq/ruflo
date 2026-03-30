"""
Statistics & Analytics API Endpoints
======================================
FastAPI router for dashboard KPIs, charts, and trend analysis.

Integration:
    from statistics_endpoints import create_statistics_router
    stats_router = create_statistics_router(db, statistics_service, get_current_user)
    app.include_router(stats_router, prefix="/api/v1")
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional


def create_statistics_router(db, statistics_service, get_current_user):
    """
    Factory-Funktion fuer den Statistik-Router.

    Args:
        db: AsyncIOMotorDatabase Instanz
        statistics_service: StatisticsService Instanz
        get_current_user: FastAPI Dependency fuer Authentifizierung
    """
    router = APIRouter(tags=["Statistiken"])

    # ─── DASHBOARD KPIs ──────────────────────────────────────────

    @router.get("/statistics/dashboard")
    async def get_dashboard_kpis(
        current_user: dict = Depends(get_current_user)
    ):
        """
        Zentrale Dashboard-Kennzahlen: Gesamt, offen, abgeschlossen,
        Durchschnitts-Score, Bearbeitungszeit, Reklamationen diesen Monat.
        """
        return await statistics_service.get_dashboard_kpis()

    # ─── STATUS DISTRIBUTION ────────────────────────────────────

    @router.get("/statistics/status-distribution")
    async def get_status_distribution(
        current_user: dict = Depends(get_current_user)
    ):
        """Anzahl Reklamationen pro Status (Kreisdiagramm)."""
        data = await statistics_service.get_status_distribution()
        return {"distribution": data}

    # ─── MONTHLY COMPLAINTS ─────────────────────────────────────

    @router.get("/statistics/monthly")
    async def get_complaints_by_month(
        months: int = Query(default=12, ge=1, le=36),
        current_user: dict = Depends(get_current_user)
    ):
        """Monatliche Reklamationsanzahl (Balkendiagramm)."""
        data = await statistics_service.get_complaints_by_month(months=months)
        return {"months": data}

    # ─── TOP ERROR CODES ────────────────────────────────────────

    @router.get("/statistics/top-errors")
    async def get_top_error_codes(
        limit: int = Query(default=10, ge=1, le=50),
        current_user: dict = Depends(get_current_user)
    ):
        """Haeufigste Fehlercodes — Pareto-Analyse."""
        data = await statistics_service.get_top_error_codes(limit=limit)
        return {"error_codes": data}

    # ─── TOP CUSTOMERS ──────────────────────────────────────────

    @router.get("/statistics/top-customers")
    async def get_top_customers(
        limit: int = Query(default=10, ge=1, le=50),
        current_user: dict = Depends(get_current_user)
    ):
        """Kunden mit den meisten Reklamationen — Pareto-Analyse."""
        data = await statistics_service.get_top_customers(limit=limit)
        return {"customers": data}

    # ─── SCORE DISTRIBUTION ─────────────────────────────────────

    @router.get("/statistics/score-distribution")
    async def get_score_distribution(
        current_user: dict = Depends(get_current_user)
    ):
        """Verteilung der Opus-Review-Scores (Histogramm)."""
        data = await statistics_service.get_score_distribution()
        return {"distribution": data}

    # ─── PROCESSING TIME ────────────────────────────────────────

    @router.get("/statistics/processing-time")
    async def get_processing_time(
        months: int = Query(default=12, ge=1, le=36),
        current_user: dict = Depends(get_current_user)
    ):
        """Durchschnittliche Bearbeitungszeit pro Monat (Liniendiagramm)."""
        data = await statistics_service.get_avg_processing_time_by_month(months=months)
        return {"processing_time": data}

    # ─── ERROR LOCATIONS ────────────────────────────────────────

    @router.get("/statistics/error-locations")
    async def get_error_locations(
        current_user: dict = Depends(get_current_user)
    ):
        """Reklamationen gruppiert nach Fehlerort (Kreis-/Balkendiagramm)."""
        data = await statistics_service.get_error_location_distribution()
        return {"locations": data}

    # ─── TREND DATA ─────────────────────────────────────────────

    @router.get("/statistics/trends")
    async def get_trends(
        months: int = Query(default=6, ge=1, le=24),
        current_user: dict = Depends(get_current_user)
    ):
        """
        Kombinierte Trenddaten: neue Reklamationen, abgeschlossene
        Reklamationen, durchschnittlicher Opus-Score pro Monat.
        """
        data = await statistics_service.get_trend_data(months=months)
        return {"trends": data}

    return router
