/**
 * Dashboard — Enterprise KPI-Dashboard fuer 8D-Reklamationsmanagement
 * ====================================================================
 * Zeigt Uebersichtsdaten zu Reklamationen:
 * - KPI-Karten (offen, Bearbeitungszeit, Qualitaetsscore, abgeschlossen)
 * - Status-Verteilung als Donut-Diagramm (Recharts PieChart)
 * - Monatlicher Trend als Liniendiagramm (Recharts LineChart)
 * - Reklamationsvolumen als Flaechendiagramm (Recharts AreaChart)
 * - Letzte 5 Reklamationen
 * - Schnellaktionen
 *
 * Integration: Route in App.js:
 *   import Dashboard from './pages/Dashboard';
 *   <Route path="/dashboard" element={<Dashboard />} />
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import GruehringHeader from '../components/GruehringHeader';
import StatCard from '../components/charts/StatCard';
import DonutChart from '../components/charts/DonutChart';
import LineChart from '../components/charts/LineChart';
import AreaChart from '../components/charts/AreaChart';
import StatusBadge from '../components/StatusBadge';
import {
  AlertCircle, Clock, Star, CheckCircle, Plus,
  Eye, BarChart3, Loader2, RefreshCw, ChevronRight,
  ListChecks, TrendingUp
} from 'lucide-react';

// ─── STATUS COLORS FOR DONUT ───────────────────────────────────────
const STATUS_COLORS = {
  draft: '#9ca3af',
  open: '#3b82f6',
  in_progress: '#eab308',
  review_pending: '#f97316',
  approval_pending: '#a855f7',
  approved: '#22c55e',
  closed: '#059669',
  rejected: '#ef4444',
  archived: '#64748b',
};

// ─── LOADING SKELETON ──────────────────────────────────────────────
function DashboardSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i}>
            <CardContent className="p-5">
              <div className="space-y-3">
                <div className="h-3 w-28 bg-gray-200 rounded" />
                <div className="h-8 w-16 bg-gray-200 rounded" />
                <div className="h-3 w-20 bg-gray-100 rounded" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card><CardContent className="p-6 h-72" /></Card>
        <Card><CardContent className="p-6 h-72" /></Card>
      </div>
      <Card><CardContent className="p-6 h-48" /></Card>
    </div>
  );
}

// ─── MAIN COMPONENT ────────────────────────────────────────────────
export default function Dashboard({ onNavigate }) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);
  const [statusDistribution, setStatusDistribution] = useState([]);
  const [trends, setTrends] = useState([]);
  const [recentComplaints, setRecentComplaints] = useState([]);

  const fetchData = useCallback(async (signal) => {
    try {
      const [dashRes, statusRes, trendRes, complaintsRes] = await Promise.all([
        axios.get(`${API}/statistics/dashboard`, { signal }).catch(() => ({ data: null })),
        axios.get(`${API}/statistics/status-distribution`, { signal }).catch(() => ({ data: { distribution: [] } })),
        axios.get(`${API}/statistics/trends`, { signal }).catch(() => ({ data: { monthly: [] } })),
        axios.get(`${API}/complaints?page_size=5&sort_by=created_at&sort_dir=desc`, { signal }).catch(() => ({ data: { complaints: [] } })),
      ]);

      if (signal?.aborted) return;

      setDashboardData(dashRes.data);
      setStatusDistribution(statusRes.data?.distribution || []);
      setTrends(trendRes.data?.monthly || []);
      setRecentComplaints(complaintsRes.data?.complaints || complaintsRes.data?.items || []);
    } catch (error) {
      if (!axios.isCancel(error)) {
        toast.error('Fehler beim Laden des Dashboards');
      }
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchData(controller.signal);
    return () => controller.abort();
  }, [fetchData]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  // ─── Derive chart data ──────────────────────────────────────
  const donutData = statusDistribution.map((item) => ({
    label: item.label || item.status || 'Unbekannt',
    value: item.count || item.value || 0,
    color: STATUS_COLORS[item.status] || '#9ca3af',
  }));

  // LineChart data: transform trends to support two lines (Neu + Geschlossen)
  const trendLineData = trends.slice(-6).map((item) => ({
    label: item.month || item.label || '',
    neu: item.opened ?? item.count ?? item.value ?? 0,
    geschlossen: item.closed ?? 0,
  }));

  // AreaChart data: complaint volume trend
  const volumeAreaData = trends.slice(-6).map((item) => ({
    label: item.month || item.label || '',
    volumen: item.count || item.value || item.opened || 0,
  }));

  const kpi = dashboardData || {};

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <GruehringHeader />

      {/* ─── PAGE HEADER ──────────────────────────────────────── */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <BarChart3 className="w-6 h-6 text-blue-700" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
                <p className="text-sm text-gray-500 mt-0.5">
                  8D-Reklamationsmanagement — Uebersicht
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={refreshing}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
              Aktualisieren
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading ? (
          <DashboardSkeleton />
        ) : (
          <div className="space-y-6">
            {/* ─── KPI CARDS ────────────────────────────────────── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                title="Offene Reklamationen"
                value={kpi.open_complaints ?? 0}
                icon={AlertCircle}
                trend={kpi.open_complaints_trend ?? null}
                trendLabel="vs. Vormonat"
                color="blue"
                invertTrend={true}
              />
              <StatCard
                title="Durchschn. Bearbeitungszeit"
                value={`${kpi.avg_processing_days ?? 0} Tage`}
                icon={Clock}
                trend={kpi.avg_processing_trend ?? null}
                trendLabel="vs. Vormonat"
                color="amber"
                invertTrend={true}
              />
              <StatCard
                title="Durchschn. Qualitaetsscore"
                value={kpi.avg_quality_score ?? 0}
                icon={Star}
                trend={kpi.quality_score_trend ?? null}
                trendLabel="vs. Vormonat"
                color="purple"
                invertTrend={false}
              />
              <StatCard
                title="Abgeschlossen diesen Monat"
                value={kpi.closed_this_month ?? 0}
                icon={CheckCircle}
                trend={kpi.closed_trend ?? null}
                trendLabel="vs. Vormonat"
                color="green"
                invertTrend={false}
              />
            </div>

            {/* ─── CHARTS ROW ───────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Status Distribution */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <div className="w-1.5 h-5 bg-blue-500 rounded-full" />
                    Status-Verteilung
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex justify-center py-4">
                  {donutData.length > 0 ? (
                    <DonutChart
                      data={donutData}
                      size={220}
                      thickness={32}
                      showLegend={true}
                    />
                  ) : (
                    <div className="text-sm text-gray-400 py-8">
                      Keine Statusdaten verfuegbar
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Monthly Trend — LineChart with two lines */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <div className="w-1.5 h-5 bg-purple-500 rounded-full" />
                    Monatlicher Trend
                    <span className="text-xs text-gray-400 font-normal ml-auto">
                      Letzte 6 Monate
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="py-4">
                  {trendLineData.length > 0 ? (
                    <LineChart
                      data={trendLineData}
                      lines={[
                        { key: 'neu', color: '#3b82f6', label: 'Neu' },
                        { key: 'geschlossen', color: '#22c55e', label: 'Geschlossen' },
                      ]}
                      xKey="label"
                      height={220}
                      showGrid={true}
                    />
                  ) : (
                    <div className="text-sm text-gray-400 py-8 text-center">
                      Keine Trenddaten verfuegbar
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* ─── VOLUME AREA CHART ───────────────────────────── */}
            {volumeAreaData.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <div className="w-1.5 h-5 bg-indigo-500 rounded-full" />
                    Reklamationsvolumen
                    <span className="text-xs text-gray-400 font-normal ml-auto">
                      Letzte 6 Monate
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="py-4">
                  <AreaChart
                    data={volumeAreaData}
                    areas={[
                      { key: 'volumen', color: '#6366f1', label: 'Reklamationen' },
                    ]}
                    xKey="label"
                    height={180}
                    gradient={true}
                  />
                </CardContent>
              </Card>
            )}

            {/* ─── RECENT COMPLAINTS TABLE ──────────────────────── */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <div className="w-1.5 h-5 bg-green-500 rounded-full" />
                    Letzte Reklamationen
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onNavigate && onNavigate('complaints')}
                    className="text-xs"
                  >
                    Alle anzeigen <ChevronRight className="w-3 h-3 ml-1" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {recentComplaints.length === 0 ? (
                  <div className="text-sm text-gray-400 text-center py-6">
                    Keine Reklamationen vorhanden
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left">
                          <th className="pb-2 font-semibold text-gray-600 text-xs uppercase tracking-wide">Nr.</th>
                          <th className="pb-2 font-semibold text-gray-600 text-xs uppercase tracking-wide">Kunde</th>
                          <th className="pb-2 font-semibold text-gray-600 text-xs uppercase tracking-wide">Status</th>
                          <th className="pb-2 font-semibold text-gray-600 text-xs uppercase tracking-wide">Datum</th>
                          <th className="pb-2 font-semibold text-gray-600 text-xs uppercase tracking-wide text-right">Score</th>
                          <th className="pb-2 w-10" />
                        </tr>
                      </thead>
                      <tbody>
                        {recentComplaints.map((c) => (
                          <tr
                            key={c.id}
                            className="border-b last:border-0 hover:bg-gray-50 cursor-pointer transition-colors"
                            onClick={() => onNavigate && onNavigate('complaint-detail', { complaintId: c.id })}
                          >
                            <td className="py-3 font-medium text-gray-800">
                              {c.complaint_number || c.id?.substring(0, 8)}
                            </td>
                            <td className="py-3 text-gray-600">
                              {c.customer_name || '—'}
                            </td>
                            <td className="py-3">
                              <StatusBadge status={c.status} size="sm" />
                            </td>
                            <td className="py-3 text-gray-500 text-xs">
                              {c.created_at
                                ? new Date(c.created_at).toLocaleDateString('de-DE')
                                : '—'}
                            </td>
                            <td className="py-3 text-right">
                              {c.quality_score != null ? (
                                <span className={`font-semibold ${
                                  c.quality_score >= 80 ? 'text-green-700'
                                    : c.quality_score >= 60 ? 'text-amber-700'
                                    : 'text-red-700'
                                }`}>
                                  {c.quality_score}
                                </span>
                              ) : (
                                <span className="text-gray-300">{'—'}</span>
                              )}
                            </td>
                            <td className="py-3">
                              <ChevronRight className="w-4 h-4 text-gray-300" />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* ─── QUICK ACTIONS ─────────────────────────────────── */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Button
                onClick={() => onNavigate && onNavigate('complaints')}
                className="h-auto py-4 bg-blue-600 hover:bg-blue-700 flex flex-col items-center gap-2"
              >
                <Plus className="w-5 h-5" />
                <span className="text-sm font-semibold">Neue Reklamation</span>
              </Button>
              <Button
                variant="outline"
                onClick={() => onNavigate && onNavigate('review-queue')}
                className="h-auto py-4 flex flex-col items-center gap-2 hover:bg-purple-50 hover:border-purple-300"
              >
                <ListChecks className="w-5 h-5 text-purple-600" />
                <span className="text-sm font-semibold text-purple-700">Review-Queue</span>
              </Button>
              <Button
                variant="outline"
                onClick={() => onNavigate && onNavigate('analysis')}
                className="h-auto py-4 flex flex-col items-center gap-2 hover:bg-green-50 hover:border-green-300"
              >
                <TrendingUp className="w-5 h-5 text-green-600" />
                <span className="text-sm font-semibold text-green-700">Auswertungen</span>
              </Button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
