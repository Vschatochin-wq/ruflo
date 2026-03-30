/**
 * ReviewQueue — Approval Queue for ZQM/Admin
 * ============================================
 * Shows all complaints pending review or approval.
 * Allows ZQM to approve or reject 8D reports.
 *
 * Integration: Add route in App.js:
 *   import ReviewQueue from './pages/ReviewQueue';
 *   <Route path="/review-queue" element={user ? <ReviewQueue /> : <Navigate to="/login" />} />
 */

import React, { useState, useEffect, useContext, useMemo, useCallback } from 'react';
import axios from 'axios';
import { API, AuthContext } from '../App';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import GruehringHeader from '../components/GruehringHeader';
import {
  Brain, CheckCircle, XCircle, AlertTriangle, Clock,
  Eye, Edit, Loader2, Filter, BarChart3, TrendingUp,
  ChevronRight, Search
} from 'lucide-react';

export default function ReviewQueue({ onNavigate }) {
  const { user } = useContext(AuthContext);
  const [queue, setQueue] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // all, approval_pending, reviewed, revision_needed
  const [searchTerm, setSearchTerm] = useState('');
  const [actionModal, setActionModal] = useState(null); // { type: 'approve'|'reject', complaintId }
  const [actionComment, setActionComment] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  // Client-side authorization guard
  const isAuthorized = user?.role === 'admin' || user?.role === 'zqm';

  useEffect(() => {
    if (!isAuthorized) {
      onNavigate && onNavigate('dashboard');
      return;
    }

    const controller = new AbortController();
    const fetchData = async () => {
      try {
        setLoading(true);
        const [queueRes, statsRes] = await Promise.all([
          axios.get(`${API}/reviews/queue`, { signal: controller.signal }),
          axios.get(`${API}/reviews/statistics`, { signal: controller.signal }).catch(() => ({ data: null }))
        ]);
        if (!controller.signal.aborted) {
          setQueue(queueRes.data.queue || []);
          setStats(statsRes.data);
        }
      } catch (error) {
        if (!axios.isCancel(error)) {
          toast.error('Fehler beim Laden der Review-Queue');
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    fetchData();
    return () => controller.abort();
  }, [isAuthorized, navigate]);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [queueRes, statsRes] = await Promise.all([
        axios.get(`${API}/reviews/queue`),
        axios.get(`${API}/reviews/statistics`).catch(() => ({ data: null }))
      ]);
      setQueue(queueRes.data.queue || []);
      setStats(statsRes.data);
    } catch (error) {
      toast.error('Fehler beim Laden der Review-Queue');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleApprove = async () => {
    if (!actionModal) return;
    setActionLoading(true);
    try {
      await axios.post(`${API}/complaints/${actionModal.complaintId}/approve`, {
        comment: actionComment
      });
      toast.success('Reklamation freigegeben');
      setActionModal(null);
      setActionComment('');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler bei der Freigabe');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!actionModal || !actionComment.trim()) {
      toast.error('Bitte geben Sie einen Ablehnungsgrund an');
      return;
    }
    setActionLoading(true);
    try {
      await axios.post(`${API}/complaints/${actionModal.complaintId}/reject`, {
        reason: actionComment
      });
      toast.success('Reklamation zur Überarbeitung zurückgewiesen');
      setActionModal(null);
      setActionComment('');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler bei der Ablehnung');
    } finally {
      setActionLoading(false);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 81) return 'text-green-700 bg-green-100';
    if (score >= 61) return 'text-amber-700 bg-amber-100';
    if (score >= 31) return 'text-orange-700 bg-orange-100';
    return 'text-red-700 bg-red-100';
  };

  const getRecommendationBadge = (rec) => {
    switch (rec) {
      case 'approval_recommended':
        return <Badge className="bg-green-100 text-green-700"><CheckCircle className="w-3 h-3 mr-1" />Freigabe empfohlen</Badge>;
      case 'minor_revision':
        return <Badge className="bg-amber-100 text-amber-700"><AlertTriangle className="w-3 h-3 mr-1" />Kleine Korrektur</Badge>;
      default:
        return <Badge className="bg-red-100 text-red-700"><XCircle className="w-3 h-3 mr-1" />Überarbeitung nötig</Badge>;
    }
  };

  const filterCounts = useMemo(() => ({
    all: queue.length,
    approval_pending: queue.filter(c => c.status === 'approval_pending').length,
    reviewed: queue.filter(c => c.status === 'reviewed').length,
  }), [queue]);

  const filteredQueue = useMemo(() => queue.filter(c => {
    if (filter !== 'all' && c.status !== filter) return false;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      return (
        (c.complaint_number || '').toLowerCase().includes(term) ||
        (c.customer_name || '').toLowerCase().includes(term)
      );
    }
    return true;
  }), [queue, filter, searchTerm]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-purple-50">
        <GruehringHeader />
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-purple-50">
      <GruehringHeader />

      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Brain className="w-6 h-6 text-purple-700" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Review & Freigabe-Queue</h1>
                <p className="text-sm text-gray-500 mt-0.5">
                  Opus 4.6 Bewertungen prüfen und Reklamationen freigeben
                </p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Statistics Cards */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
            <Card className="bg-white">
              <CardContent className="p-4 text-center">
                <BarChart3 className="w-5 h-5 text-purple-500 mx-auto mb-1" />
                <p className="text-2xl font-bold">{stats.total_reviews || 0}</p>
                <p className="text-xs text-gray-500">Reviews gesamt</p>
              </CardContent>
            </Card>
            <Card className="bg-white">
              <CardContent className="p-4 text-center">
                <TrendingUp className="w-5 h-5 text-blue-500 mx-auto mb-1" />
                <p className="text-2xl font-bold">{stats.avg_score || 0}</p>
                <p className="text-xs text-gray-500">Durchschn. Score</p>
              </CardContent>
            </Card>
            <Card className="bg-white">
              <CardContent className="p-4 text-center">
                <CheckCircle className="w-5 h-5 text-green-500 mx-auto mb-1" />
                <p className="text-2xl font-bold">{stats.approved_count || 0}</p>
                <p className="text-xs text-gray-500">Freigegeben</p>
              </CardContent>
            </Card>
            <Card className="bg-white">
              <CardContent className="p-4 text-center">
                <AlertTriangle className="w-5 h-5 text-amber-500 mx-auto mb-1" />
                <p className="text-2xl font-bold">{stats.minor_revision_count || 0}</p>
                <p className="text-xs text-gray-500">Kleine Korrektur</p>
              </CardContent>
            </Card>
            <Card className="bg-white">
              <CardContent className="p-4 text-center">
                <XCircle className="w-5 h-5 text-red-500 mx-auto mb-1" />
                <p className="text-2xl font-bold">{stats.revision_count || 0}</p>
                <p className="text-xs text-gray-500">Zurückgewiesen</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Filters */}
        <div className="flex items-center gap-4 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              placeholder="Suche nach Reklamationsnummer oder Kunde..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
          <div className="flex gap-2">
            {[
              { key: 'all', label: 'Alle', count: filterCounts.all },
              { key: 'approval_pending', label: 'Freigabe', count: filterCounts.approval_pending },
              { key: 'reviewed', label: 'Bewertet', count: filterCounts.reviewed },
            ].map(f => (
              <Button
                key={f.key}
                variant={filter === f.key ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilter(f.key)}
              >
                {f.label} ({f.count})
              </Button>
            ))}
          </div>
        </div>

        {/* Queue List */}
        {filteredQueue.length === 0 ? (
          <Card>
            <CardContent className="py-16 text-center">
              <CheckCircle className="w-16 h-16 text-green-300 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-400">Keine offenen Reviews</h3>
              <p className="text-sm text-gray-400 mt-1">
                Alle Reklamationen sind bearbeitet.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {filteredQueue.map(complaint => (
              <Card key={complaint.id} className="hover:shadow-md transition-shadow">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      {/* Score Badge */}
                      {complaint.latest_review ? (
                        <div className={`w-14 h-14 rounded-lg flex flex-col items-center justify-center ${
                          getScoreColor(complaint.latest_review.score)
                        }`}>
                          <span className="text-lg font-bold">{complaint.latest_review.score}</span>
                          <span className="text-[10px]">/ 100</span>
                        </div>
                      ) : (
                        <div className="w-14 h-14 rounded-lg bg-gray-100 flex items-center justify-center">
                          <Brain className="w-6 h-6 text-gray-400" />
                        </div>
                      )}

                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-lg">{complaint.complaint_number || complaint.id?.substring(0, 8)}</span>
                          {complaint.latest_review && getRecommendationBadge(complaint.latest_review.recommendation)}
                        </div>
                        <div className="flex items-center gap-4 text-sm text-gray-500 mt-1">
                          <span>{complaint.customer_name || 'Unbekannter Kunde'}</span>
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {complaint.latest_review?.reviewed_at
                              ? new Date(complaint.latest_review.reviewed_at).toLocaleDateString('de-DE')
                              : 'Nicht bewertet'}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline" size="sm"
                        onClick={() => onNavigate && onNavigate('complaint-detail', { complaintId: complaint.id })}
                      >
                        <Eye className="w-4 h-4 mr-1" /> Ansehen
                      </Button>

                      {complaint.status === 'approval_pending' && (
                        <>
                          <Button
                            size="sm"
                            className="bg-green-600 hover:bg-green-700"
                            onClick={() => { setActionModal({ type: 'approve', complaintId: complaint.id }); setActionComment(''); }}
                          >
                            <CheckCircle className="w-4 h-4 mr-1" /> Freigeben
                          </Button>
                          <Button
                            variant="destructive" size="sm"
                            onClick={() => { setActionModal({ type: 'reject', complaintId: complaint.id }); setActionComment(''); }}
                          >
                            <XCircle className="w-4 h-4 mr-1" /> Ablehnen
                          </Button>
                        </>
                      )}

                      {complaint.status === 'reviewed' && (
                        <Button
                          size="sm"
                          onClick={() => onNavigate && onNavigate('complaint-detail', { complaintId: complaint.id })}
                        >
                          <Edit className="w-4 h-4 mr-1" /> Bearbeiten
                        </Button>
                      )}

                      <ChevronRight className="w-4 h-4 text-gray-400" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>

      {/* ─── APPROVAL / REJECTION MODAL ──────────────────────────── */}
      {actionModal && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="action-modal-title"
          onKeyDown={(e) => { if (e.key === 'Escape' && !actionLoading) setActionModal(null); }}
        >
          <Card className="w-full max-w-lg">
            <CardHeader className={
              actionModal.type === 'approve'
                ? 'bg-green-50 border-b border-green-200'
                : 'bg-red-50 border-b border-red-200'
            }>
              <CardTitle
                id="action-modal-title"
                className={actionModal.type === 'approve' ? 'text-green-800' : 'text-red-800'}
              >
                {actionModal.type === 'approve'
                  ? '8D-Report freigeben'
                  : '8D-Report ablehnen'}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-700">
                  {actionModal.type === 'approve'
                    ? 'Kommentar (optional)'
                    : 'Ablehnungsgrund (erforderlich)'}
                </label>
                <Textarea
                  value={actionComment}
                  onChange={(e) => setActionComment(e.target.value)}
                  placeholder={
                    actionModal.type === 'approve'
                      ? 'Optionaler Kommentar zur Freigabe...'
                      : 'Bitte begründen Sie die Ablehnung...'
                  }
                  rows={4}
                  className="mt-1"
                />
              </div>

              <div className="flex gap-3 justify-end">
                <Button variant="outline" onClick={() => setActionModal(null)} disabled={actionLoading}>
                  Abbrechen
                </Button>
                <Button
                  onClick={actionModal.type === 'approve' ? handleApprove : handleReject}
                  disabled={actionLoading || (actionModal.type === 'reject' && !actionComment.trim())}
                  className={
                    actionModal.type === 'approve'
                      ? 'bg-green-600 hover:bg-green-700'
                      : 'bg-red-600 hover:bg-red-700'
                  }
                >
                  {actionLoading ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : actionModal.type === 'approve' ? (
                    <CheckCircle className="w-4 h-4 mr-2" />
                  ) : (
                    <XCircle className="w-4 h-4 mr-2" />
                  )}
                  {actionModal.type === 'approve' ? 'Freigeben' : 'Ablehnen'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
