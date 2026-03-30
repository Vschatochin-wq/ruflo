"""
Tests for StatisticsService -- Dashboard KPIs & Analytics
==========================================================
Covers: KPI aggregation, status distribution, top error codes, top customers,
score distribution, monthly trends.

NOTE: The MockDB has limited query support ($ne only). Tests that rely on
complex aggregation pipelines ($group, $unwind, $in, $gte) validate the
service interface and return structure rather than full aggregation logic.
Integration tests against a real MongoDB cover aggregation correctness.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from collections import Counter

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from conftest import MockDB, MockCollection, MockCursor, make_complaint, make_review
from statistics_service import StatisticsService, OPEN_STATUSES, CLOSED_STATUSES


# ─── ENHANCED MOCK FOR AGGREGATION ──────────────────────────────────────
# The default MockCollection.aggregate returns all data as-is.
# We patch specific methods where needed to return realistic pipeline output.


@pytest.fixture
def svc(mock_db):
    return StatisticsService(mock_db)


# ---- DASHBOARD KPIs --------------------------------------------------------

class TestDashboardKPIs:

    @pytest.mark.asyncio
    async def test_returns_all_kpi_fields(self, svc, mock_db):
        mock_db.add_complaint(make_complaint(status="open", complaint_id="kpi-1"))

        result = await svc.get_dashboard_kpis()

        expected_keys = {
            "total_complaints", "open_complaints", "closed_complaints",
            "avg_opus_score", "avg_processing_time_days", "complaints_this_month",
        }
        assert expected_keys.issubset(set(result.keys())), \
            f"KPI result must contain keys: {expected_keys}. Got: {set(result.keys())}"

    @pytest.mark.asyncio
    async def test_empty_db_returns_zeros(self, svc):
        result = await svc.get_dashboard_kpis()

        assert result["total_complaints"] == 0, "Empty DB should have total=0"
        assert result["open_complaints"] == 0, "Empty DB should have open=0"
        assert result["closed_complaints"] == 0, "Empty DB should have closed=0"
        assert result["avg_opus_score"] == 0, "Empty DB should have avg_score=0"
        assert result["complaints_this_month"] == 0, "Empty DB should have this_month=0"

    @pytest.mark.asyncio
    async def test_total_counts_all_non_deleted(self, svc, mock_db):
        mock_db.add_complaint(make_complaint(status="open", complaint_id="t-1"))
        mock_db.add_complaint(make_complaint(status="closed", complaint_id="t-2"))
        mock_db.add_complaint(make_complaint(status="draft", complaint_id="t-3"))

        # Deleted complaint should not count
        deleted = make_complaint(status="open", complaint_id="t-4")
        deleted["deleted"] = True
        mock_db.add_complaint(deleted)

        result = await svc.get_dashboard_kpis()

        assert result["total_complaints"] == 3, \
            "Total should count only non-deleted complaints (3 of 4)"


# ---- STATUS DISTRIBUTION ---------------------------------------------------

class TestStatusDistribution:

    @pytest.mark.asyncio
    async def test_returns_list_structure(self, svc, mock_db):
        # Patch aggregate to return realistic $group output
        async def mock_aggregate_to_list(length=50):
            return [
                {"_id": "draft", "count": 2},
                {"_id": "open", "count": 1},
            ]
        mock_db.complaints.aggregate = lambda pipeline: MagicMock(
            to_list=mock_aggregate_to_list
        )

        result = await svc.get_status_distribution()

        assert isinstance(result, list), "Must return a list"
        assert len(result) == 2, "Should return 2 status groups"
        assert result[0]["status"] == "draft", "First entry should be 'draft'"
        assert result[0]["count"] == 2, "Draft count should be 2"
        assert result[1]["status"] == "open", "Second entry should be 'open'"

    @pytest.mark.asyncio
    async def test_empty_returns_empty_list(self, svc):
        result = await svc.get_status_distribution()

        assert isinstance(result, list), "Must return a list even when empty"


# ---- TOP ERROR CODES -------------------------------------------------------

class TestTopErrors:

    @pytest.mark.asyncio
    async def test_returns_list_of_error_dicts(self, svc, mock_db):
        # Patch aggregate to simulate $unwind + $group output
        async def mock_agg_to_list(length=10):
            return [
                {"_id": "F-002", "description": "Riss", "count": 5},
                {"_id": "F-001", "description": "Verschleiss", "count": 3},
                {"_id": "F-003", "description": "Bruch", "count": 1},
            ]
        mock_db.complaints.aggregate = lambda pipeline: MagicMock(
            to_list=mock_agg_to_list
        )

        result = await svc.get_top_error_codes()

        assert isinstance(result, list), "Must return a list"
        assert len(result) == 3, "Should return 3 error codes"
        assert result[0]["code"] == "F-002", "Most frequent error should be first"
        assert result[0]["count"] == 5, "Top error count should be 5"
        assert "description" in result[0], "Each entry must have 'description'"

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self, svc, mock_db):
        # Patch aggregate with 10 entries
        async def mock_agg_to_list(length=10):
            return [
                {"_id": f"F-{i:03d}", "description": f"Error {i}", "count": 10 - i}
                for i in range(min(length, 5))
            ]
        mock_db.complaints.aggregate = lambda pipeline: MagicMock(
            to_list=mock_agg_to_list
        )

        result = await svc.get_top_error_codes(limit=5)

        assert isinstance(result, list), "Must return a list"
        assert len(result) <= 5, "Should respect the limit parameter"

    @pytest.mark.asyncio
    async def test_empty_returns_empty_list(self, svc):
        result = await svc.get_top_error_codes()

        assert isinstance(result, list), "Must return list when no data"
        assert len(result) == 0, "No complaints means no error codes"


# ---- TOP CUSTOMERS ---------------------------------------------------------

class TestTopCustomers:

    @pytest.mark.asyncio
    async def test_returns_list_of_customer_dicts(self, svc, mock_db):
        # Patch aggregate to simulate $group output
        async def mock_agg_to_list(length=10):
            return [
                {"_id": "Kunde A GmbH", "count": 4},
                {"_id": "Kunde B AG", "count": 2},
                {"_id": "Kunde C KG", "count": 1},
            ]
        mock_db.complaints.aggregate = lambda pipeline: MagicMock(
            to_list=mock_agg_to_list
        )

        result = await svc.get_top_customers()

        assert isinstance(result, list), "Must return a list"
        assert len(result) == 3, "Should return 3 customers"
        assert result[0]["customer_name"] == "Kunde A GmbH", \
            "Customer with most complaints should be first"
        assert result[0]["count"] == 4, "Top customer should have count=4"

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self, svc, mock_db):
        async def mock_agg_to_list(length=10):
            return [
                {"_id": f"Firma {i} GmbH", "count": 10 - i}
                for i in range(min(length, 3))
            ]
        mock_db.complaints.aggregate = lambda pipeline: MagicMock(
            to_list=mock_agg_to_list
        )

        result = await svc.get_top_customers(limit=3)

        assert isinstance(result, list), "Must return a list"
        assert len(result) <= 3, "Should respect the limit parameter"

    @pytest.mark.asyncio
    async def test_empty_returns_empty_list(self, svc):
        result = await svc.get_top_customers()

        assert isinstance(result, list), "Must return list when no data"


# ---- SCORE DISTRIBUTION ----------------------------------------------------

class TestScoreDistribution:

    @pytest.mark.asyncio
    async def test_returns_five_buckets(self, svc):
        result = await svc.get_score_distribution()

        assert isinstance(result, list), "Must return a list"
        assert len(result) == 5, \
            "Should return exactly 5 score buckets (0-20, 20-40, 40-60, 60-80, 80-100)"

    @pytest.mark.asyncio
    async def test_bucket_structure(self, svc):
        result = await svc.get_score_distribution()

        for bucket in result:
            assert "label" in bucket, "Each bucket must have a 'label'"
            assert "count" in bucket, "Each bucket must have a 'count'"
            assert "min_score" in bucket, "Each bucket must have 'min_score'"
            assert "max_score" in bucket, "Each bucket must have 'max_score'"

    @pytest.mark.asyncio
    async def test_empty_all_zero_counts(self, svc):
        result = await svc.get_score_distribution()

        total = sum(b["count"] for b in result)
        assert total == 0, "No reviews should give zero total across all buckets"

    @pytest.mark.asyncio
    async def test_labels_cover_full_range(self, svc):
        result = await svc.get_score_distribution()

        labels = [b["label"] for b in result]
        assert "0-20" in labels, "Must have 0-20 bucket"
        assert "80-100" in labels, "Must have 80-100 bucket"


# ---- TRENDS ----------------------------------------------------------------

class TestTrends:

    @pytest.mark.asyncio
    async def test_returns_monthly_list(self, svc):
        result = await svc.get_trend_data(months=6)

        assert isinstance(result, list), "Trends must return a list"
        assert len(result) == 6, "Should return entries for requested months"

    @pytest.mark.asyncio
    async def test_monthly_entry_structure(self, svc):
        result = await svc.get_trend_data(months=3)

        for entry in result:
            assert "year" in entry, "Each trend entry must have 'year'"
            assert "month" in entry, "Each trend entry must have 'month'"
            assert "label" in entry, "Each trend entry must have 'label'"
            assert "new_complaints" in entry, "Each trend entry must have 'new_complaints'"
            assert "closed_complaints" in entry, "Each trend entry must have 'closed_complaints'"
            assert "avg_score" in entry, "Each trend entry must have 'avg_score'"

    @pytest.mark.asyncio
    async def test_empty_db_returns_zero_counts(self, svc):
        result = await svc.get_trend_data(months=3)

        for entry in result:
            assert entry["new_complaints"] == 0, \
                f"Month {entry['label']} should have 0 new complaints on empty DB"
            assert entry["closed_complaints"] == 0, \
                f"Month {entry['label']} should have 0 closed complaints on empty DB"
            assert entry["avg_score"] == 0, \
                f"Month {entry['label']} should have 0 avg_score on empty DB"

    @pytest.mark.asyncio
    async def test_respects_months_parameter(self, svc):
        result_3 = await svc.get_trend_data(months=3)
        result_12 = await svc.get_trend_data(months=12)

        assert len(result_3) == 3, "months=3 should return 3 entries"
        assert len(result_12) == 12, "months=12 should return 12 entries"


# ---- COMPLAINTS BY MONTH ---------------------------------------------------

class TestComplaintsByMonth:

    @pytest.mark.asyncio
    async def test_returns_monthly_list(self, svc):
        result = await svc.get_complaints_by_month(months=6)

        assert isinstance(result, list), "Must return a list"
        assert len(result) == 6, "Should return entries for requested months"

    @pytest.mark.asyncio
    async def test_monthly_entry_structure(self, svc):
        result = await svc.get_complaints_by_month(months=1)

        entry = result[0]
        assert "year" in entry, "Each entry must have 'year'"
        assert "month" in entry, "Each entry must have 'month'"
        assert "label" in entry, "Each entry must have 'label'"
        assert "count" in entry, "Each entry must have 'count'"

    @pytest.mark.asyncio
    async def test_empty_db_zero_counts(self, svc):
        result = await svc.get_complaints_by_month(months=3)

        for entry in result:
            assert entry["count"] == 0, \
                f"Month {entry['label']} should have count=0 on empty DB"


# ---- ERROR LOCATION DISTRIBUTION -------------------------------------------

class TestErrorLocationDistribution:

    @pytest.mark.asyncio
    async def test_returns_list(self, svc):
        result = await svc.get_error_location_distribution()

        assert isinstance(result, list), "Must return a list"

    @pytest.mark.asyncio
    async def test_empty_returns_empty_list(self, svc):
        result = await svc.get_error_location_distribution()

        assert len(result) == 0, "Empty DB should return empty list"


# ---- AVG PROCESSING TIME BY MONTH ------------------------------------------

class TestAvgProcessingTimeByMonth:

    @pytest.mark.asyncio
    async def test_returns_monthly_list(self, svc):
        result = await svc.get_avg_processing_time_by_month(months=3)

        assert isinstance(result, list), "Must return a list"
        assert len(result) == 3, "Should return entries for requested months"

    @pytest.mark.asyncio
    async def test_entry_structure(self, svc):
        result = await svc.get_avg_processing_time_by_month(months=1)

        entry = result[0]
        assert "year" in entry, "Must have 'year'"
        assert "month" in entry, "Must have 'month'"
        assert "label" in entry, "Must have 'label'"
        assert "avg_days" in entry, "Must have 'avg_days'"
        assert "closed_count" in entry, "Must have 'closed_count'"

    @pytest.mark.asyncio
    async def test_empty_db_zero_days(self, svc):
        result = await svc.get_avg_processing_time_by_month(months=1)

        assert result[0]["avg_days"] == 0, "Empty DB should have avg_days=0"
        assert result[0]["closed_count"] == 0, "Empty DB should have closed_count=0"
