/**
 * AnalysisDashboard — Auswertungen & Berichte fuer 8D-Reklamationsmanagement
 * ============================================================================
 * Detaillierte Analysen mit Tabs:
 * - Uebersicht: Score-Verteilung (BarChart+Brush), Bearbeitungszeit-Trend (LineChart)
 * - Fehleranalyse: Pareto-Chart (BarChart + kumulative Linie), Fehlerort (DonutChart)
 * - Kundenanalyse: Top-Kunden (horizontaler BarChart), monatliche Trends (LineChart)
 * - Zeitanalyse: Bearbeitungszeiten (LineChart+Referenzlinie), Oeffnung vs. Schliessung (LineChart)
 *
 * Alle Charts sind Recharts-basiert mit interaktiven Tooltips, Zoom und Drill-Down.
 *
 * Integration: Route in App.js:
 *   import AnalysisDashboard from './pages/AnalysisDashboard';
 *   <Route path="/analysis" element={<AnalysisDashboard />} />
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import GruehringHeader from '../components/GruehringHeader';
import BarChart from '../components/charts/BarChart';
import DonutChart from '../components/charts/DonutChart';
import LineChart from '../components/charts/LineChart';
import StatCard from '../components/charts/StatCard';
import {
  ComposedChart,
  Bar as ComposedBar,
  Line as ComposedLine,
  XAxis as ComposedXAxis,
  YAxis as ComposedYAxis,
  CartesianGrid as ComposedGrid,
  Tooltip as ComposedTooltip,
  ResponsiveContainer as ComposedContainer,
  Legend as ComposedLegend,
  Cell,
} from 'recharts';
import {
  TrendingUp, BarChart3, Users, Clock, Loader2,
  RefreshCw, AlertTriangle, Target, PieChart, Calendar
} from 'lucide-react';

// ─── TAB DEFINITIONS ───────────────────────────────────────────────
const TABS = [
  { key: 'overview', label: 'Uebersicht', icon: PieChart },
  { key: 'errors', label: 'Fehleranalyse', icon: AlertTriangle },
  { key: 'customers', label: 'Kundenanalyse', icon: Users },
  { key: 'time', label: 'Zeitanalyse', icon: Clock },
];

// ─── COLOR PALETTE ─────────────────────────────────────────────────
const SCORE_COLORS = {
  excellent: '#059669',
  good: '#22c55e',
  acceptable: '#eab308',
  weak: '#f97316',
  insufficient: '#ef4444',
};

const CUSTOMER_COLORS = [
  '#3b82f6', '#8b5cf6', '#06b6d4', '#f59e0b', '#ef4444',
  '#10b981', '#f97316', '#6366f1', '#ec4899', '#14b8a6',
];

const ERROR_LOCATION_COLORS = [
  '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7',
  '#06b6d4', '#f97316', '#6366f1',
];

// ─── LOADING SKELETON ──────────────────────────────────────────────
function AnalysisSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card><CardContent className="p-6 h-72" /></Card>
        <Card><CardContent className="p-6 h-72" /></Card>
      </div>
      <Card><CardContent className="p-6 h-64" /></Card>
    </div>
  );
}

// ─── PARETO CHART (BarChart + Line overlay) ─────────────────────────
// Uses Recharts ComposedChart for combined Bar + Line

function ParetoTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="bg-gray-900 text-white text-xs px-3 py-2 rounded-lg shadow-xl border border-gray-700">
      <p className="font-semibold mb-1">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="flex items-center gap-1.5">
          <span
            className="w-2 h-2 rounded-full inline-block"
            style={{ backgroundColor: entry.color }}
          />
          <span>
            {entry.name === 'anzahl'
              ? `Anzahl: ${Number(entry.value).toLocaleString('de-DE')}`
              : `Kumulativ: ${entry.value}%`}
          </span>
        </p>
      ))}
    </div>
  );
}

function ParetoChart({ data }) {
  if (!data || data.length === 0) return null;

  return (
    <ComposedContainer width="100%" height={280}>
      <ComposedChart
        data={data}
        margin={{ top: 20, right: 40, left: 10, bottom: 5 }}
      >
        <ComposedGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
        <ComposedXAxis
          dataKey="label"
          tick={{ fontSize: 11, fill: '#6b7280' }}
          axisLine={{ stroke: '#e5e7eb' }}
          tickLine={false}
        />
        <ComposedYAxis
          yAxisId="left"
          tick={{ fontSize: 11, fill: '#6b7280' }}
          axisLine={{ stroke: '#e5e7eb' }}
          tickFormatter={(v) => v.toLocaleString('de-DE')}
        />
        <ComposedYAxis
          yAxisId="right"
          orientation="right"
          domain={[0, 100]}
          tick={{ fontSize: 11, fill: '#ef4444' }}
          axisLine={{ stroke: '#fca5a5' }}
          tickFormatter={(v) => `${v}%`}
        />
        <ComposedTooltip content={<ParetoTooltip />} />
        <ComposedLegend
          iconType="circle"
          iconSize={8}
          wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
          formatter={(value) =>
            value === 'anzahl' ? 'Anzahl' : 'Kumulativ %'
          }
        />
        <ComposedBar
          yAxisId="left"
          dataKey="anzahl"
          name="anzahl"
          radius={[4, 4, 0, 0]}
          animationDuration={500}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={i < 3 ? '#ef4444' : i < 6 ? '#f97316' : '#fbbf24'} />
          ))}
        </ComposedBar>
        <ComposedLine
          yAxisId="right"
          type="monotone"
          dataKey="kumulativ"
          name="kumulativ"
          stroke="#ef4444"
          strokeWidth={2}
          dot={{ r: 4, fill: '#ef4444', strokeWidth: 0 }}
          activeDot={{ r: 6, stroke: '#fff', strokeWidth: 2 }}
          animationDuration={500}
        />
      </ComposedChart>
    </ComposedContainer>
  );
}

// ─── MAIN COMPONENT ────────────────────────────────────────────────
export default function AnalysisDashboard() {
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Data states
  const [overviewData, setOverviewData] = useState(null);
  const [errorData, setErrorData] = useState(null);
  const [customerData, setCustomerData] = useState(null);
  const [timeData, setTimeData] = useState(null);

  const fetchData = useCallback(async (signal) => {
    try {
      // Fetch from individual statistics endpoints and compose
      const [scoreRes, procTimeRes, topErrorsRes, errLocRes, topCustRes, monthlyRes, trendsRes] = await Promise.all([
        axios.get(`${API}/statistics/score-distribution`, { signal }).catch(() => ({ data: {} })),
        axios.get(`${API}/statistics/processing-time`, { signal }).catch(() => ({ data: {} })),
        axios.get(`${API}/statistics/top-errors`, { signal }).catch(() => ({ data: {} })),
        axios.get(`${API}/statistics/error-locations`, { signal }).catch(() => ({ data: {} })),
        axios.get(`${API}/statistics/top-customers`, { signal }).catch(() => ({ data: {} })),
        axios.get(`${API}/statistics/monthly`, { signal }).catch(() => ({ data: {} })),
        axios.get(`${API}/statistics/trends`, { signal }).catch(() => ({ data: {} })),
      ]);

      if (signal?.aborted) return;

      setOverviewData({
        score_distribution: scoreRes.data?.buckets || scoreRes.data?.distribution || [],
        processing_time_trend: procTimeRes.data?.monthly || [],
      });
      setErrorData({
        top_errors: topErrorsRes.data?.errors || topErrorsRes.data?.top_errors || [],
        error_locations: errLocRes.data?.locations || errLocRes.data?.distribution || [],
      });
      setCustomerData({
        top_customers: topCustRes.data?.customers || topCustRes.data?.top_customers || [],
        monthly: monthlyRes.data?.monthly || [],
      });
      setTimeData({
        processing_time: procTimeRes.data?.monthly || [],
        trends: trendsRes.data?.monthly || [],
      });
    } catch (error) {
      if (!axios.isCancel(error)) {
        toast.error('Fehler beim Laden der Analysedaten');
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

  // ─── OVERVIEW TAB ───────────────────────────────────────────
  const renderOverview = () => {
    const scoreDistribution = overviewData?.score_distribution || [];
    const processingTrend = overviewData?.processing_time_trend || [];

    const scoreBarData = scoreDistribution.map((item) => ({
      label: item.range || item.label || '',
      value: item.count || item.value || 0,
      color: item.range?.includes('90') || item.range?.includes('100')
        ? SCORE_COLORS.excellent
        : item.range?.includes('80')
        ? SCORE_COLORS.good
        : item.range?.includes('60') || item.range?.includes('70')
        ? SCORE_COLORS.acceptable
        : item.range?.includes('40') || item.range?.includes('50')
        ? SCORE_COLORS.weak
        : SCORE_COLORS.insufficient,
    }));

    // LineChart data for processing time trend
    const processingLineData = processingTrend.map((item) => ({
      label: item.month || item.label || '',
      tage: item.avg_days || item.value || 0,
    }));

    return (
      <div className="space-y-6">
        {/* KPI summary row */}
        {overviewData && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Gesamt Reklamationen"
              value={overviewData.total_complaints ?? 0}
              icon={BarChart3}
              color="blue"
            />
            <StatCard
              title="Durchschn. Score"
              value={overviewData.avg_score ?? 0}
              icon={Target}
              color="purple"
            />
            <StatCard
              title="Bewertete Reports"
              value={overviewData.reviewed_count ?? 0}
              icon={TrendingUp}
              color="green"
            />
            <StatCard
              title="Durchschn. Bearbeitungszeit"
              value={`${overviewData.avg_processing_days ?? 0} Tage`}
              icon={Clock}
              color="amber"
            />
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Score Distribution — BarChart with Brush */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <div className="w-1.5 h-5 bg-purple-500 rounded-full" />
                Score-Verteilung
              </CardTitle>
              <p className="text-xs text-gray-500">
                Verteilung der Opus-Qualitaetsbewertungen nach Bereich
              </p>
            </CardHeader>
            <CardContent>
              {scoreBarData.length > 0 ? (
                <BarChart
                  data={scoreBarData}
                  maxHeight={220}
                  showValues={true}
                  orientation="vertical"
                />
              ) : (
                <div className="text-sm text-gray-400 text-center py-12">
                  Keine Score-Daten verfuegbar
                </div>
              )}
            </CardContent>
          </Card>

          {/* Processing Time Trend — LineChart with reference line */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <div className="w-1.5 h-5 bg-amber-500 rounded-full" />
                Bearbeitungszeit-Trend
              </CardTitle>
              <p className="text-xs text-gray-500">
                Durchschnittliche Bearbeitungsdauer pro Monat (in Tagen)
              </p>
            </CardHeader>
            <CardContent>
              {processingLineData.length > 0 ? (
                <LineChart
                  data={processingLineData}
                  lines={[
                    { key: 'tage', color: '#f59e0b', label: 'Bearbeitungstage' },
                  ]}
                  xKey="label"
                  height={220}
                  showGrid={true}
                  referenceLine={{
                    y: overviewData?.target_processing_days || 14,
                    label: 'Ziel',
                    color: '#ef4444',
                  }}
                />
              ) : (
                <div className="text-sm text-gray-400 text-center py-12">
                  Keine Zeitdaten verfuegbar
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  };

  // ─── ERROR ANALYSIS TAB ─────────────────────────────────────
  const renderErrorAnalysis = () => {
    const topErrors = (errorData?.top_error_codes || []).slice(0, 10);
    const errorLocations = errorData?.error_locations || [];

    // Pareto data: sorted descending
    const paretoSorted = [...topErrors]
      .sort((a, b) => (b.count || b.value || 0) - (a.count || a.value || 0));

    const paretoBarData = paretoSorted.map((item) => ({
      label: item.code || item.label || 'Unbekannt',
      value: item.count || item.value || 0,
    }));

    // Compute cumulative percentage for Pareto overlay using a combined chart
    const paretoTotal = paretoBarData.reduce((s, d) => s + d.value, 0);
    let cumulative = 0;
    const paretoComboData = paretoBarData.map((item) => {
      cumulative += item.value;
      return {
        label: item.label,
        anzahl: item.value,
        kumulativ: paretoTotal > 0 ? Math.round((cumulative / paretoTotal) * 100) : 0,
      };
    });

    const locationDonutData = errorLocations.map((item, i) => ({
      label: item.location || item.label || 'Unbekannt',
      value: item.count || item.value || 0,
      color: ERROR_LOCATION_COLORS[i % ERROR_LOCATION_COLORS.length],
    }));

    return (
      <div className="space-y-6">
        {/* Pareto Chart — BarChart + cumulative line */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <div className="w-1.5 h-5 bg-red-500 rounded-full" />
              Pareto-Analyse — Top 10 Fehlercodes
            </CardTitle>
            <p className="text-xs text-gray-500">
              Haeufigste Fehlercodes sortiert nach Vorkommen. Rote Linie zeigt kumulative Verteilung (%).
            </p>
          </CardHeader>
          <CardContent>
            {paretoComboData.length > 0 ? (
              <div>
                <ParetoChart data={paretoComboData} />
                {/* Cumulative % badges */}
                <div className="mt-3 flex flex-wrap gap-2">
                  {paretoComboData.slice(0, 5).map((item, i) => (
                    <span key={i} className="text-[10px] text-red-600 bg-red-50 px-2 py-0.5 rounded-full">
                      Top {i + 1}: {item.kumulativ}% kumulativ
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-400 text-center py-12">
                Keine Fehlercode-Daten verfuegbar
              </div>
            )}
          </CardContent>
        </Card>

        {/* Error Location Distribution — DonutChart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <div className="w-1.5 h-5 bg-orange-500 rounded-full" />
              Fehlerort-Verteilung
            </CardTitle>
            <p className="text-xs text-gray-500">
              Verteilung der Reklamationen nach Fehlerort
            </p>
          </CardHeader>
          <CardContent className="flex justify-center py-4">
            {locationDonutData.length > 0 ? (
              <DonutChart
                data={locationDonutData}
                size={240}
                thickness={35}
                showLegend={true}
              />
            ) : (
              <div className="text-sm text-gray-400 py-12">
                Keine Fehlerort-Daten verfuegbar
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  };

  // ─── CUSTOMER ANALYSIS TAB ──────────────────────────────────
  const renderCustomerAnalysis = () => {
    const topCustomers = (customerData?.top_customers || []).slice(0, 10);
    const customerTrends = customerData?.customer_trends || [];

    const customerBarData = topCustomers.map((item, i) => ({
      label: item.name || item.customer_name || `Kunde ${i + 1}`,
      value: item.count || item.complaint_count || item.value || 0,
      color: CUSTOMER_COLORS[i % CUSTOMER_COLORS.length],
    }));

    // Build LineChart data from customer trends (combine all top customers into one dataset)
    const customerLineData = [];
    const customerLines = [];
    if (customerTrends.length > 0) {
      const topTrends = customerTrends.slice(0, 5);
      // Collect all unique months
      const monthSet = new Set();
      topTrends.forEach((customer) => {
        (customer.months || []).forEach((m) => {
          monthSet.add(m.month || m.label || '');
        });
      });
      const months = Array.from(monthSet).sort();

      // Build combined data
      months.forEach((month) => {
        const row = { label: month };
        topTrends.forEach((customer, idx) => {
          const key = `kunde_${idx}`;
          const monthEntry = (customer.months || []).find(
            (m) => (m.month || m.label || '') === month
          );
          row[key] = monthEntry ? (monthEntry.count || monthEntry.value || 0) : 0;
        });
        customerLineData.push(row);
      });

      topTrends.forEach((customer, idx) => {
        customerLines.push({
          key: `kunde_${idx}`,
          color: CUSTOMER_COLORS[idx % CUSTOMER_COLORS.length],
          label: customer.name || customer.customer_name || `Kunde ${idx + 1}`,
        });
      });
    }

    return (
      <div className="space-y-6">
        {/* Top Customers — Horizontal BarChart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <div className="w-1.5 h-5 bg-blue-500 rounded-full" />
              Top 10 Kunden nach Reklamationen
            </CardTitle>
            <p className="text-xs text-gray-500">
              Kunden mit den meisten Reklamationen
            </p>
          </CardHeader>
          <CardContent>
            {customerBarData.length > 0 ? (
              <BarChart
                data={customerBarData}
                color="blue"
                maxHeight={300}
                showValues={true}
                orientation="horizontal"
              />
            ) : (
              <div className="text-sm text-gray-400 text-center py-12">
                Keine Kundendaten verfuegbar
              </div>
            )}
          </CardContent>
        </Card>

        {/* Customer Monthly Trend — LineChart */}
        {customerLineData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <div className="w-1.5 h-5 bg-indigo-500 rounded-full" />
                Monatlicher Trend — Top-Kunden
              </CardTitle>
              <p className="text-xs text-gray-500">
                Reklamationsentwicklung der wichtigsten Kunden
              </p>
            </CardHeader>
            <CardContent>
              <LineChart
                data={customerLineData}
                lines={customerLines}
                xKey="label"
                height={280}
                showGrid={true}
                showBrush={customerLineData.length > 8}
              />
            </CardContent>
          </Card>
        )}
      </div>
    );
  };

  // ─── TIME ANALYSIS TAB ──────────────────────────────────────
  const renderTimeAnalysis = () => {
    const avgTimeByMonth = timeData?.avg_time_by_month || [];
    const openVsClosed = timeData?.open_vs_closed || [];

    // LineChart data for average processing time
    const avgTimeLineData = avgTimeByMonth.map((item) => ({
      label: item.month || item.label || '',
      tage: item.avg_days || item.value || 0,
    }));

    // LineChart data for opened vs closed
    const openClosedLineData = openVsClosed.map((item) => ({
      label: item.month || item.label || '',
      geoeffnet: item.opened ?? item.open ?? 0,
      abgeschlossen: item.closed ?? 0,
    }));

    return (
      <div className="space-y-6">
        {/* Average Processing Time — LineChart with reference line */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <div className="w-1.5 h-5 bg-amber-500 rounded-full" />
              Durchschnittliche Bearbeitungszeit pro Monat
            </CardTitle>
            <p className="text-xs text-gray-500">
              Mittlere Bearbeitungsdauer in Tagen, vom Eingang bis zur Schliessung
            </p>
          </CardHeader>
          <CardContent>
            {avgTimeLineData.length > 0 ? (
              <LineChart
                data={avgTimeLineData}
                lines={[
                  { key: 'tage', color: '#f59e0b', label: 'Bearbeitungstage' },
                ]}
                xKey="label"
                height={240}
                showGrid={true}
                referenceLine={{
                  y: timeData?.target_days || 14,
                  label: 'Ziel',
                  color: '#ef4444',
                }}
              />
            ) : (
              <div className="text-sm text-gray-400 text-center py-12">
                Keine Zeitdaten verfuegbar
              </div>
            )}
          </CardContent>
        </Card>

        {/* Opened vs Closed Per Month — LineChart with two lines */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <div className="w-1.5 h-5 bg-green-500 rounded-full" />
              Geoeffnet vs. Abgeschlossen pro Monat
            </CardTitle>
            <p className="text-xs text-gray-500">
              Vergleich der neu eroeffneten und abgeschlossenen Reklamationen
            </p>
          </CardHeader>
          <CardContent>
            {openClosedLineData.length > 0 ? (
              <LineChart
                data={openClosedLineData}
                lines={[
                  { key: 'geoeffnet', color: '#3b82f6', label: 'Geoeffnet' },
                  { key: 'abgeschlossen', color: '#22c55e', label: 'Abgeschlossen' },
                ]}
                xKey="label"
                height={280}
                showGrid={true}
                showBrush={openClosedLineData.length > 8}
              />
            ) : (
              <div className="text-sm text-gray-400 text-center py-12">
                Keine Vergleichsdaten verfuegbar
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  };

  // ─── TAB CONTENT MAP ────────────────────────────────────────
  const tabContent = {
    overview: renderOverview,
    errors: renderErrorAnalysis,
    customers: renderCustomerAnalysis,
    time: renderTimeAnalysis,
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-green-50">
      <GruehringHeader />

      {/* ─── PAGE HEADER ──────────────────────────────────────── */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <TrendingUp className="w-6 h-6 text-green-700" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Auswertungen</h1>
                <p className="text-sm text-gray-500 mt-0.5">
                  Detaillierte Analysen und Berichte
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
        {/* ─── TAB NAVIGATION ─────────────────────────────────── */}
        <div className="flex gap-1 mb-6 bg-white rounded-lg border p-1 overflow-x-auto">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-md text-sm font-medium transition-colors flex-shrink-0 ${
                  isActive
                    ? 'bg-green-600 text-white shadow-sm'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* ─── TAB CONTENT ────────────────────────────────────── */}
        {loading ? (
          <AnalysisSkeleton />
        ) : (
          tabContent[activeTab]?.() || null
        )}
      </main>
    </div>
  );
}
