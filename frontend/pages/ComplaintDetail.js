/**
 * ComplaintDetail — 8D Complaint Detail Page (D1-D8)
 * ====================================================
 * Complete view/edit of a single complaint with all D-steps,
 * documents, OCR, reviews, and status management.
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import {
  ArrowLeft, Save, X, Edit3, Plus, Trash2, Loader2,
  Users, AlertTriangle, ShieldAlert, Search, Wrench,
  CheckCircle, Shield, BookOpen, ChevronRight
} from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import CompletenessMeter from '../components/CompletenessMeter';
import DocumentUpload from '../components/DocumentUpload';
import OcrResultPanel from '../components/OcrResultPanel';
import OpusReviewPanel from '../components/OpusReviewPanel';

const TABS = [
  { key: 'D1', label: 'D1 Team', icon: Users },
  { key: 'D2', label: 'D2 Problem', icon: AlertTriangle },
  { key: 'D3', label: 'D3 Sofort', icon: ShieldAlert },
  { key: 'D4', label: 'D4 Ursache', icon: Search },
  { key: 'D5', label: 'D5 Abstell', icon: Wrench },
  { key: 'D6', label: 'D6 Verif.', icon: CheckCircle },
  { key: 'D7', label: 'D7 Vorbeu.', icon: Shield },
  { key: 'D8', label: 'D8 Abschluss', icon: BookOpen },
];

// ─── Action Row Component (reused in D3, D5, D7) ─────────────
function ActionTable({ actions = [], editing, onChange, addLabel }) {
  const handleChange = (idx, field, value) => {
    const updated = [...actions];
    updated[idx] = { ...updated[idx], [field]: value };
    onChange(updated);
  };
  const handleAdd = () => {
    onChange([...actions, { code: '', description: '', responsible: '', status: 'planned', deadline: '' }]);
  };
  const handleRemove = (idx) => {
    onChange(actions.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-2">
      {actions.length === 0 && !editing && (
        <p className="text-sm text-gray-400 italic">Keine Eintr\u00e4ge</p>
      )}
      {actions.map((a, idx) => (
        <div key={idx} className="grid grid-cols-12 gap-2 items-start p-2 rounded border bg-white">
          <input className="col-span-2 text-sm border rounded px-2 py-1" placeholder="Code" value={a.code || ''} disabled={!editing} onChange={(e) => handleChange(idx, 'code', e.target.value)} />
          <input className="col-span-4 text-sm border rounded px-2 py-1" placeholder="Beschreibung" value={a.description || ''} disabled={!editing} onChange={(e) => handleChange(idx, 'description', e.target.value)} />
          <input className="col-span-2 text-sm border rounded px-2 py-1" placeholder="Verantwortlich" value={a.responsible || ''} disabled={!editing} onChange={(e) => handleChange(idx, 'responsible', e.target.value)} />
          <select className="col-span-2 text-sm border rounded px-2 py-1" value={a.status || 'planned'} disabled={!editing} onChange={(e) => handleChange(idx, 'status', e.target.value)}>
            <option value="planned">Geplant</option>
            <option value="done">Erledigt</option>
          </select>
          <input className="col-span-1 text-sm border rounded px-2 py-1" type="date" value={a.deadline || ''} disabled={!editing} onChange={(e) => handleChange(idx, 'deadline', e.target.value)} />
          {editing && (
            <button className="col-span-1 text-red-500 hover:text-red-700 p-1" onClick={() => handleRemove(idx)}>
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      ))}
      {editing && (
        <Button variant="outline" size="sm" onClick={handleAdd}>
          <Plus className="w-3 h-3 mr-1" />{addLabel || 'Hinzuf\u00fcgen'}
        </Button>
      )}
    </div>
  );
}

// ─── 5-Why Component ─────────────────────────────────────────
function FiveWhyEditor({ items = [], editing, onChange }) {
  const handleChange = (idx, field, value) => {
    const updated = [...items];
    updated[idx] = { ...updated[idx], [field]: value };
    onChange(updated);
  };
  const handleAdd = () => {
    onChange([...items, { question: '', answer: '' }]);
  };

  return (
    <div className="space-y-2">
      <h5 className="text-sm font-semibold text-gray-600">5-Why Analyse</h5>
      {items.map((item, idx) => (
        <div key={idx} className="flex gap-2">
          <span className="text-sm font-bold text-gray-400 mt-1 w-6">{idx + 1}.</span>
          <div className="flex-1 space-y-1">
            <input className="w-full text-sm border rounded px-2 py-1" placeholder="Warum?" value={item.question || ''} disabled={!editing} onChange={(e) => handleChange(idx, 'question', e.target.value)} />
            <input className="w-full text-sm border rounded px-2 py-1 bg-gray-50" placeholder="Antwort" value={item.answer || ''} disabled={!editing} onChange={(e) => handleChange(idx, 'answer', e.target.value)} />
          </div>
        </div>
      ))}
      {editing && items.length < 7 && (
        <Button variant="ghost" size="sm" onClick={handleAdd}>
          <Plus className="w-3 h-3 mr-1" />Warum hinzuf\u00fcgen
        </Button>
      )}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────
export default function ComplaintDetail({ complaintId, onNavigateBack, currentUser }) {
  const [complaint, setComplaint] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('D1');
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [ocrResult, setOcrResult] = useState(null);
  const [allowedTransitions, setAllowedTransitions] = useState([]);

  const loadComplaint = useCallback(async () => {
    try {
      const [compRes, summRes, transRes] = await Promise.all([
        axios.get(`${API}/complaints/${complaintId}`),
        axios.get(`${API}/complaints/${complaintId}/summary`).catch(() => ({ data: null })),
        axios.get(`${API}/complaints/${complaintId}/allowed-transitions`).catch(() => ({ data: { transitions: [] } })),
      ]);
      setComplaint(compRes.data);
      setDraft(compRes.data);
      setSummary(summRes.data);
      setAllowedTransitions(transRes.data?.transitions || []);
    } catch (err) {
      toast.error('Reklamation konnte nicht geladen werden');
    } finally {
      setLoading(false);
    }
  }, [complaintId]);

  useEffect(() => { loadComplaint(); }, [loadComplaint]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.patch(`${API}/complaints/${complaintId}`, draft);
      toast.success('Gespeichert');
      setEditing(false);
      loadComplaint();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Speichern fehlgeschlagen');
    } finally {
      setSaving(false);
    }
  };

  const handleTransition = async (targetStatus) => {
    try {
      await axios.post(`${API}/complaints/${complaintId}/transition`, { target_status: targetStatus });
      toast.success(`Status ge\u00e4ndert: ${targetStatus}`);
      loadComplaint();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Status\u00e4nderung fehlgeschlagen');
    }
  };

  const updateDraft = (field, value) => {
    setDraft((prev) => ({ ...prev, [field]: value }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (!complaint) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Reklamation nicht gefunden</p>
        <Button variant="ghost" onClick={onNavigateBack} className="mt-4">
          <ArrowLeft className="w-4 h-4 mr-2" />Zur\u00fcck
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onNavigateBack}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-xl font-bold text-gray-800">{complaint.complaint_number || 'Neue Reklamation'}</h1>
            <p className="text-sm text-gray-500">{complaint.customer_name}</p>
          </div>
          <StatusBadge status={complaint.status} />
        </div>
        <div className="flex items-center gap-2">
          {allowedTransitions.length > 0 && (
            <div className="flex gap-1">
              {allowedTransitions.slice(0, 3).map((t) => (
                <Button key={t} variant="outline" size="sm" onClick={() => handleTransition(t)}>
                  <ChevronRight className="w-3 h-3 mr-1" />{t.replace(/_/g, ' ')}
                </Button>
              ))}
            </div>
          )}
          {editing ? (
            <>
              <Button variant="ghost" size="sm" onClick={() => { setEditing(false); setDraft(complaint); }}>
                <X className="w-4 h-4 mr-1" />Abbrechen
              </Button>
              <Button size="sm" onClick={handleSave} disabled={saving} className="bg-blue-600 hover:bg-blue-700">
                {saving ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Save className="w-4 h-4 mr-1" />}
                Speichern
              </Button>
            </>
          ) : (
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              <Edit3 className="w-4 h-4 mr-1" />Bearbeiten
            </Button>
          )}
        </div>
      </div>

      {/* Info Card */}
      <Card>
        <CardContent className="pt-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div><span className="text-gray-500 block">Kundennummer</span><span className="font-medium">{complaint.customer_number || '\u2014'}</span></div>
            <div><span className="text-gray-500 block">FA</span><span className="font-medium">{complaint.fa_code || '\u2014'}</span></div>
            <div><span className="text-gray-500 block">Art.-Nr.</span><span className="font-medium">{complaint.artikel_nummer || '\u2014'}</span></div>
            <div><span className="text-gray-500 block">Fehlerort</span><span className="font-medium">{complaint.error_location || '\u2014'}</span></div>
            <div><span className="text-gray-500 block">Feststellungsdatum</span><span className="font-medium">{complaint.detection_date || '\u2014'}</span></div>
            <div><span className="text-gray-500 block">Meldedatum</span><span className="font-medium">{complaint.report_date || '\u2014'}</span></div>
            <div><span className="text-gray-500 block">SAP Typ</span><span className="font-medium">{complaint.message_type || '\u2014'}</span></div>
            <div><span className="text-gray-500 block">Menge</span><span className="font-medium">{complaint.affected_quantity || '\u2014'}</span></div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main Content — D-Steps */}
        <div className="lg:col-span-3 space-y-4">
          {/* Tab Navigation */}
          <div className="flex gap-1 overflow-x-auto border-b pb-1">
            {TABS.map(({ key, label, icon: Icon }) => {
              const stepStatus = summary?.d_step_status?.[key];
              const isComplete = stepStatus?.complete || stepStatus?.status === 'complete';
              return (
                <button
                  key={key}
                  onClick={() => setActiveTab(key)}
                  className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-t whitespace-nowrap transition-colors ${
                    activeTab === key
                      ? 'bg-blue-50 text-blue-700 border-b-2 border-blue-600'
                      : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  {isComplete ? (
                    <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                  ) : (
                    <Icon className="w-3.5 h-3.5" />
                  )}
                  {label}
                </button>
              );
            })}
          </div>

          {/* Tab Content */}
          <Card>
            <CardContent className="pt-4">
              {activeTab === 'D1' && (
                <div className="space-y-3">
                  <h3 className="font-semibold text-gray-700">D1 \u2014 Teamzusammenstellung</h3>
                  {(draft.team_members || []).map((m, idx) => (
                    <div key={idx} className="flex gap-2 items-center">
                      <input className="flex-1 text-sm border rounded px-2 py-1" placeholder="Name" value={m.name || ''} disabled={!editing}
                        onChange={(e) => { const arr = [...(draft.team_members || [])]; arr[idx] = { ...arr[idx], name: e.target.value }; updateDraft('team_members', arr); }} />
                      <input className="w-32 text-sm border rounded px-2 py-1" placeholder="Rolle" value={m.role || ''} disabled={!editing}
                        onChange={(e) => { const arr = [...(draft.team_members || [])]; arr[idx] = { ...arr[idx], role: e.target.value }; updateDraft('team_members', arr); }} />
                      {editing && (
                        <button className="text-red-500 hover:text-red-700" onClick={() => updateDraft('team_members', (draft.team_members || []).filter((_, i) => i !== idx))}>
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  ))}
                  {editing && (
                    <Button variant="outline" size="sm" onClick={() => updateDraft('team_members', [...(draft.team_members || []), { name: '', role: '' }])}>
                      <Plus className="w-3 h-3 mr-1" />Mitglied
                    </Button>
                  )}
                  {!editing && (!draft.team_members || draft.team_members.length === 0) && (
                    <p className="text-sm text-gray-400 italic">Kein Team definiert</p>
                  )}
                </div>
              )}

              {activeTab === 'D2' && (
                <div className="space-y-4">
                  <h3 className="font-semibold text-gray-700">D2 \u2014 Problembeschreibung</h3>
                  <textarea className="w-full border rounded px-3 py-2 text-sm min-h-[100px]" placeholder="Problembeschreibung..." value={draft.problem_description || ''} disabled={!editing}
                    onChange={(e) => updateDraft('problem_description', e.target.value)} />
                  <div className="space-y-2">
                    <h4 className="text-sm font-semibold text-gray-600">Fehlercodes</h4>
                    {(draft.errors || []).map((err, idx) => (
                      <div key={idx} className="grid grid-cols-12 gap-2 items-center">
                        <input className="col-span-2 text-sm border rounded px-2 py-1" placeholder="Code" value={err.code || ''} disabled={!editing}
                          onChange={(e) => { const arr = [...(draft.errors || [])]; arr[idx] = { ...arr[idx], code: e.target.value }; updateDraft('errors', arr); }} />
                        <input className="col-span-5 text-sm border rounded px-2 py-1" placeholder="Beschreibung" value={err.description || ''} disabled={!editing}
                          onChange={(e) => { const arr = [...(draft.errors || [])]; arr[idx] = { ...arr[idx], description: e.target.value }; updateDraft('errors', arr); }} />
                        <input className="col-span-4 text-sm border rounded px-2 py-1" placeholder="Kategorie" value={err.category || ''} disabled={!editing}
                          onChange={(e) => { const arr = [...(draft.errors || [])]; arr[idx] = { ...arr[idx], category: e.target.value }; updateDraft('errors', arr); }} />
                        {editing && (
                          <button className="col-span-1 text-red-500" onClick={() => updateDraft('errors', (draft.errors || []).filter((_, i) => i !== idx))}>
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    ))}
                    {editing && (
                      <Button variant="outline" size="sm" onClick={() => updateDraft('errors', [...(draft.errors || []), { code: '', description: '', category: '' }])}>
                        <Plus className="w-3 h-3 mr-1" />Fehler
                      </Button>
                    )}
                  </div>
                </div>
              )}

              {activeTab === 'D3' && (
                <div className="space-y-3">
                  <h3 className="font-semibold text-gray-700">D3 \u2014 Sofortma\u00dfnahmen</h3>
                  <ActionTable actions={draft.immediate_actions || []} editing={editing}
                    onChange={(v) => updateDraft('immediate_actions', v)} addLabel="Sofortma\u00dfnahme" />
                </div>
              )}

              {activeTab === 'D4' && (
                <div className="space-y-4">
                  <h3 className="font-semibold text-gray-700">D4 \u2014 Ursachenanalyse</h3>
                  <div className="space-y-2">
                    <h4 className="text-sm font-semibold text-gray-600">Ursachen</h4>
                    {(draft.causes || []).map((c, idx) => (
                      <div key={idx} className="grid grid-cols-12 gap-2 items-center">
                        <input className="col-span-2 text-sm border rounded px-2 py-1" placeholder="Code" value={c.code || ''} disabled={!editing}
                          onChange={(e) => { const arr = [...(draft.causes || [])]; arr[idx] = { ...arr[idx], code: e.target.value }; updateDraft('causes', arr); }} />
                        <input className="col-span-5 text-sm border rounded px-2 py-1" placeholder="Beschreibung" value={c.description || ''} disabled={!editing}
                          onChange={(e) => { const arr = [...(draft.causes || [])]; arr[idx] = { ...arr[idx], description: e.target.value }; updateDraft('causes', arr); }} />
                        <input className="col-span-4 text-sm border rounded px-2 py-1" placeholder="Kategorie" value={c.category || ''} disabled={!editing}
                          onChange={(e) => { const arr = [...(draft.causes || [])]; arr[idx] = { ...arr[idx], category: e.target.value }; updateDraft('causes', arr); }} />
                        {editing && (
                          <button className="col-span-1 text-red-500" onClick={() => updateDraft('causes', (draft.causes || []).filter((_, i) => i !== idx))}>
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    ))}
                    {editing && (
                      <Button variant="outline" size="sm" onClick={() => updateDraft('causes', [...(draft.causes || []), { code: '', description: '', category: '' }])}>
                        <Plus className="w-3 h-3 mr-1" />Ursache
                      </Button>
                    )}
                  </div>
                  <FiveWhyEditor items={draft.five_why || []} editing={editing}
                    onChange={(v) => updateDraft('five_why', v)} />
                </div>
              )}

              {activeTab === 'D5' && (
                <div className="space-y-3">
                  <h3 className="font-semibold text-gray-700">D5 \u2014 Abstellma\u00dfnahmen</h3>
                  <ActionTable actions={draft.corrective_actions || []} editing={editing}
                    onChange={(v) => updateDraft('corrective_actions', v)} addLabel="Abstellma\u00dfnahme" />
                </div>
              )}

              {activeTab === 'D6' && (
                <div className="space-y-3">
                  <h3 className="font-semibold text-gray-700">D6 \u2014 Verifizierung</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs text-gray-500 block mb-1">Methode</label>
                      <input className="w-full text-sm border rounded px-2 py-1" value={draft.verification?.method || ''} disabled={!editing}
                        onChange={(e) => updateDraft('verification', { ...draft.verification, method: e.target.value })} />
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 block mb-1">Ergebnis</label>
                      <input className="w-full text-sm border rounded px-2 py-1" value={draft.verification?.result || ''} disabled={!editing}
                        onChange={(e) => updateDraft('verification', { ...draft.verification, result: e.target.value })} />
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 block mb-1">Gepr\u00fcft von</label>
                      <input className="w-full text-sm border rounded px-2 py-1" value={draft.verification?.verified_by || ''} disabled={!editing}
                        onChange={(e) => updateDraft('verification', { ...draft.verification, verified_by: e.target.value })} />
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 block mb-1">Datum</label>
                      <input type="date" className="w-full text-sm border rounded px-2 py-1" value={draft.verification?.date || ''} disabled={!editing}
                        onChange={(e) => updateDraft('verification', { ...draft.verification, date: e.target.value })} />
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'D7' && (
                <div className="space-y-3">
                  <h3 className="font-semibold text-gray-700">D7 \u2014 Vorbeugema\u00dfnahmen</h3>
                  <ActionTable actions={draft.preventive_actions || []} editing={editing}
                    onChange={(v) => updateDraft('preventive_actions', v)} addLabel="Vorbeugema\u00dfnahme" />
                </div>
              )}

              {activeTab === 'D8' && (
                <div className="space-y-3">
                  <h3 className="font-semibold text-gray-700">D8 \u2014 Abschluss</h3>
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">Lessons Learned</label>
                    <textarea className="w-full border rounded px-3 py-2 text-sm min-h-[80px]" value={draft.closure?.lessons_learned || ''} disabled={!editing}
                      onChange={(e) => updateDraft('closure', { ...draft.closure, lessons_learned: e.target.value })} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs text-gray-500 block mb-1">Geschlossen von</label>
                      <input className="w-full text-sm border rounded px-2 py-1" value={draft.closure?.closed_by || ''} disabled={!editing}
                        onChange={(e) => updateDraft('closure', { ...draft.closure, closed_by: e.target.value })} />
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 block mb-1">Datum</label>
                      <input type="date" className="w-full text-sm border rounded px-2 py-1" value={draft.closure?.closed_date || ''} disabled={!editing}
                        onChange={(e) => updateDraft('closure', { ...draft.closure, closed_date: e.target.value })} />
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Completeness */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Vollst\u00e4ndigkeit</CardTitle>
            </CardHeader>
            <CardContent>
              <CompletenessMeter summary={summary} />
            </CardContent>
          </Card>

          {/* Documents & OCR */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Dokumente</CardTitle>
            </CardHeader>
            <CardContent>
              <DocumentUpload complaintId={complaintId} onOcrResult={(result) => setOcrResult(result)} />
            </CardContent>
          </Card>

          {ocrResult && (
            <OcrResultPanel ocrResult={ocrResult} complaintId={complaintId} onApplyComplete={() => { setOcrResult(null); loadComplaint(); }} />
          )}

          {/* Review */}
          <OpusReviewPanel complaintId={complaintId} onReviewComplete={loadComplaint} />

          {/* Status History */}
          {complaint.status_history && complaint.status_history.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Verlauf</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {complaint.status_history.slice(-5).reverse().map((entry, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-xs">
                      <div className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-1.5 flex-shrink-0" />
                      <div>
                        <span className="font-medium">{entry.from_status} \u2192 {entry.to_status}</span>
                        <p className="text-gray-400">{entry.changed_by_name || entry.changed_by} \u2014 {new Date(entry.changed_at).toLocaleDateString('de-DE')}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
