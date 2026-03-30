/**
 * ComplaintList — Enterprise Complaint List Page
 * ================================================
 * Displays all 8D complaints with filtering, sorting,
 * pagination, and inline create dialog.
 *
 * Usage:
 *   <ComplaintList onNavigate={fn} currentUser={user} />
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import StatusBadge from '../components/StatusBadge';
import { toast } from 'sonner';
import {
  Plus, Search, Filter, X, Loader2, ChevronUp, ChevronDown,
  ChevronLeft, ChevronRight, FileText, RefreshCw, RotateCcw
} from 'lucide-react';

const STATUS_OPTIONS = [
  { value: '', label: 'Alle Status' },
  { value: 'draft', label: 'Entwurf' },
  { value: 'open', label: 'Offen' },
  { value: 'in_progress', label: 'In Bearbeitung' },
  { value: 'review_pending', label: 'Review ausstehend' },
  { value: 'approval_pending', label: 'Freigabe ausstehend' },
  { value: 'approved', label: 'Freigegeben' },
  { value: 'closed', label: 'Abgeschlossen' },
  { value: 'rejected', label: 'Abgelehnt' },
];

const MELDUNGSTYP_OPTIONS = [
  { value: '', label: 'Meldungstyp waehlen' },
  { value: 'Q1', label: 'Q1 — Kundenreklamation' },
  { value: 'Q2', label: 'Q2 — Interne Reklamation' },
  { value: 'Q3', label: 'Q3 — Lieferantenreklamation' },
];

const PAGE_SIZE_OPTIONS = [10, 25, 50];

export default function ComplaintList({ onNavigate, currentUser }) {
  // Data state
  const [complaints, setComplaints] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filter state
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Sort state
  const [sortBy, setSortBy] = useState('created_at');
  const [sortDir, setSortDir] = useState('desc');

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Create dialog state
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState({
    customer_name: '',
    customer_number: '',
    problem_description: '',
    error_location: '',
    message_type: '',
  });

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  // ─── Fetch complaints ──────────────────────────────────────────
  const fetchComplaints = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      if (search) params.set('search', search);
      if (statusFilter) params.set('status', statusFilter);
      if (dateFrom) params.set('date_from', dateFrom);
      if (dateTo) params.set('date_to', dateTo);

      const res = await axios.get(`${API}/complaints?${params.toString()}`);
      setComplaints(res.data.complaints || res.data.items || []);
      setTotalCount(res.data.total || res.data.total_count || 0);
    } catch (error) {
      toast.error('Fehler beim Laden der Reklamationen');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, sortBy, sortDir, search, statusFilter, dateFrom, dateTo]);

  useEffect(() => {
    const timer = setTimeout(fetchComplaints, 300);
    return () => clearTimeout(timer);
  }, [fetchComplaints]);

  // ─── Sorting ───────────────────────────────────────────────────
  function handleSort(column) {
    if (sortBy === column) {
      setSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortDir('asc');
    }
    setPage(1);
  }

  function SortIcon({ column }) {
    if (sortBy !== column) return <ChevronUp className="w-3 h-3 text-gray-300" />;
    return sortDir === 'asc'
      ? <ChevronUp className="w-3 h-3 text-blue-600" />
      : <ChevronDown className="w-3 h-3 text-blue-600" />;
  }

  // ─── Reset filters ────────────────────────────────────────────
  function resetFilters() {
    setSearch('');
    setStatusFilter('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  }

  const hasActiveFilters = search || statusFilter || dateFrom || dateTo;

  // ─── Create complaint ──────────────────────────────────────────
  async function handleCreate(e) {
    e.preventDefault();
    if (!createForm.customer_name.trim() || !createForm.problem_description.trim()) {
      toast.error('Bitte fuellen Sie alle Pflichtfelder aus');
      return;
    }

    setCreating(true);
    try {
      const payload = {
        customer_name: createForm.customer_name.trim(),
        problem_description: createForm.problem_description.trim(),
      };
      if (createForm.customer_number.trim()) payload.customer_number = createForm.customer_number.trim();
      if (createForm.error_location.trim()) payload.error_location = createForm.error_location.trim();
      if (createForm.message_type) payload.message_type = createForm.message_type;

      await axios.post(`${API}/complaints`, payload);
      toast.success('Reklamation erfolgreich erstellt');
      setShowCreate(false);
      setCreateForm({ customer_name: '', customer_number: '', problem_description: '', error_location: '', message_type: '' });
      setPage(1);
      fetchComplaints();
    } catch (error) {
      const msg = error.response?.data?.detail || 'Fehler beim Erstellen der Reklamation';
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  }

  // ─── Render ────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <FileText className="w-6 h-6 text-blue-700" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Reklamationen</h1>
            <p className="text-sm text-gray-500">
              {totalCount} Reklamation{totalCount !== 1 ? 'en' : ''} gesamt
            </p>
          </div>
        </div>
        <Button onClick={() => setShowCreate(true)} className="bg-blue-600 hover:bg-blue-700">
          <Plus className="w-4 h-4 mr-2" />
          Neue Reklamation
        </Button>
      </div>

      {/* Filter Bar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-end gap-4">
            {/* Search */}
            <div className="flex-1 min-w-[200px]">
              <label className="text-xs font-medium text-gray-500 mb-1 block">Suche</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  placeholder="Rekl.-Nr., Kunde, Problem..."
                  value={search}
                  onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Status */}
            <div className="min-w-[180px]">
              <label className="text-xs font-medium text-gray-500 mb-1 block">Status</label>
              <select
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {STATUS_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            {/* Date From */}
            <div className="min-w-[150px]">
              <label className="text-xs font-medium text-gray-500 mb-1 block">Von</label>
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
              />
            </div>

            {/* Date To */}
            <div className="min-w-[150px]">
              <label className="text-xs font-medium text-gray-500 mb-1 block">Bis</label>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
              />
            </div>

            {/* Reset */}
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={resetFilters} className="text-gray-500">
                <RotateCcw className="w-4 h-4 mr-1" />
                Filter zuruecksetzen
              </Button>
            )}

            {/* Refresh */}
            <Button variant="outline" size="sm" onClick={fetchComplaints} disabled={loading}>
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-6 h-6 animate-spin text-blue-500 mr-2" />
              <span className="text-gray-500">Lade Reklamationen...</span>
            </div>
          ) : complaints.length === 0 ? (
            <div className="text-center py-16">
              <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-gray-400">Keine Reklamationen gefunden</h3>
              <p className="text-sm text-gray-400 mt-1">
                {hasActiveFilters
                  ? 'Passen Sie Ihre Filterkriterien an.'
                  : 'Erstellen Sie Ihre erste Reklamation.'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b bg-gray-50">
                    {[
                      { key: 'complaint_number', label: 'Rekl.-Nr.' },
                      { key: 'customer_name', label: 'Kunde' },
                      { key: 'status', label: 'Status' },
                      { key: 'created_at', label: 'Erstellt am' },
                      { key: 'assigned_to', label: 'Bearbeiter' },
                      { key: 'overall_score', label: 'Score' },
                    ].map(col => (
                      <th
                        key={col.key}
                        className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none"
                        onClick={() => handleSort(col.key)}
                      >
                        <div className="flex items-center gap-1">
                          {col.label}
                          <SortIcon column={col.key} />
                        </div>
                      </th>
                    ))}
                    <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Aktionen
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {complaints.map(complaint => (
                    <tr
                      key={complaint.id}
                      className="hover:bg-blue-50/50 cursor-pointer transition-colors"
                      onClick={() => onNavigate?.('complaint-detail', { complaintId: complaint.id })}
                    >
                      <td className="px-4 py-3">
                        <span className="font-mono font-semibold text-sm text-blue-700">
                          {complaint.complaint_number || complaint.id?.substring(0, 8)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div>
                          <span className="text-sm font-medium text-gray-800">
                            {complaint.customer_name || '—'}
                          </span>
                          {complaint.customer_number && (
                            <span className="text-xs text-gray-400 ml-2">
                              ({complaint.customer_number})
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={complaint.status} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {complaint.created_at
                          ? new Date(complaint.created_at).toLocaleDateString('de-DE')
                          : '—'}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {complaint.assigned_to_name || complaint.assigned_to || '—'}
                      </td>
                      <td className="px-4 py-3">
                        {complaint.overall_score != null ? (
                          <Badge className={`text-xs ${
                            complaint.overall_score >= 81 ? 'bg-green-100 text-green-700' :
                            complaint.overall_score >= 61 ? 'bg-amber-100 text-amber-700' :
                            complaint.overall_score >= 31 ? 'bg-orange-100 text-orange-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {complaint.overall_score}/100
                          </Badge>
                        ) : (
                          <span className="text-xs text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            onNavigate?.('complaint-detail', { complaintId: complaint.id });
                          }}
                        >
                          Oeffnen
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {complaints.length > 0 && (
            <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50">
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <span>Zeilen pro Seite:</span>
                <select
                  value={pageSize}
                  onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
                  className="h-8 rounded border border-gray-300 bg-white px-2 text-sm"
                >
                  {PAGE_SIZE_OPTIONS.map(size => (
                    <option key={size} value={size}>{size}</option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-4">
                <span className="text-sm text-gray-600">
                  Seite {page} von {totalPages}
                </span>
                <div className="flex gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  >
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ─── CREATE DIALOG ────────────────────────────────────────── */}
      {showCreate && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-dialog-title"
          onKeyDown={(e) => { if (e.key === 'Escape' && !creating) setShowCreate(false); }}
        >
          <Card className="w-full max-w-lg">
            <CardHeader className="bg-blue-50 border-b border-blue-200">
              <div className="flex items-center justify-between">
                <CardTitle id="create-dialog-title" className="text-blue-900">
                  Neue Reklamation erstellen
                </CardTitle>
                <button
                  onClick={() => setShowCreate(false)}
                  disabled={creating}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </CardHeader>
            <CardContent className="pt-4">
              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-gray-700">
                    Kundenname <span className="text-red-500">*</span>
                  </label>
                  <Input
                    value={createForm.customer_name}
                    onChange={(e) => setCreateForm(f => ({ ...f, customer_name: e.target.value }))}
                    placeholder="Name des Kunden"
                    required
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-700">Kundennummer</label>
                  <Input
                    value={createForm.customer_number}
                    onChange={(e) => setCreateForm(f => ({ ...f, customer_number: e.target.value }))}
                    placeholder="z.B. K-12345"
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-700">
                    Problembeschreibung <span className="text-red-500">*</span>
                  </label>
                  <Textarea
                    value={createForm.problem_description}
                    onChange={(e) => setCreateForm(f => ({ ...f, problem_description: e.target.value }))}
                    placeholder="Beschreiben Sie das Problem..."
                    rows={4}
                    required
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-700">Fehlerort</label>
                  <Input
                    value={createForm.error_location}
                    onChange={(e) => setCreateForm(f => ({ ...f, error_location: e.target.value }))}
                    placeholder="z.B. Endkontrolle, Wareneingang"
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-700">Meldungstyp</label>
                  <select
                    value={createForm.message_type}
                    onChange={(e) => setCreateForm(f => ({ ...f, message_type: e.target.value }))}
                    className="mt-1 w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {MELDUNGSTYP_OPTIONS.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>

                <div className="flex gap-3 justify-end pt-2 border-t">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowCreate(false)}
                    disabled={creating}
                  >
                    Abbrechen
                  </Button>
                  <Button type="submit" disabled={creating} className="bg-blue-600 hover:bg-blue-700">
                    {creating ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Erstelle...
                      </>
                    ) : (
                      <>
                        <Plus className="w-4 h-4 mr-2" />
                        Reklamation erstellen
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
