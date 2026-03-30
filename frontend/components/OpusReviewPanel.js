/**
 * OpusReviewPanel — Opus 4.6 Quality Review Display
 * ===================================================
 * Displays the AI quality assessment of an 8D report with:
 * - Overall score gauge
 * - Per-section scores (D1-D8)
 * - Issues and recommendations
 * - Consistency and plausibility checks
 * - Action items
 * - Review history
 *
 * Usage:
 *   <OpusReviewPanel complaintId={id} onReviewComplete={callback} />
 *
 * Integration: Import in ComplaintViewNew.js or ComplaintEditNew.js
 */

import React, { useState, useEffect, useContext, useCallback, useMemo } from 'react';
import axios from 'axios';
import { API, AuthContext } from '../App';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { toast } from 'sonner';
import {
  Brain, CheckCircle, XCircle, AlertTriangle, Clock,
  ChevronDown, ChevronUp, RefreshCw, Loader2, FileText,
  Shield, Target, TrendingUp, Star
} from 'lucide-react';

// ─── SCORE GAUGE COMPONENT ──────────────────────────────────────────

const SCORE_THRESHOLDS = { good: 81, acceptable: 61, weak: 31 };

function getScoreColorInfo(s) {
  if (s >= SCORE_THRESHOLDS.good) return { ring: '#22c55e', bg: '#f0fdf4', text: 'text-green-700', label: 'Gut' };
  if (s >= SCORE_THRESHOLDS.acceptable) return { ring: '#f59e0b', bg: '#fffbeb', text: 'text-amber-700', label: 'Akzeptabel' };
  if (s >= SCORE_THRESHOLDS.weak) return { ring: '#f97316', bg: '#fff7ed', text: 'text-orange-700', label: 'Schwach' };
  return { ring: '#ef4444', bg: '#fef2f2', text: 'text-red-700', label: 'Unzureichend' };
}

const SECTION_LABELS = {
  D1_team: 'D1 — Team',
  D2_problem_description: 'D2 — Fehlerbeschreibung',
  D3_immediate_actions: 'D3 — Sofortmaßnahmen',
  D4_root_cause: 'D4 — Ursachenanalyse',
  D5_corrective_actions: 'D5 — Korrekturmaßnahmen',
  D6_verification: 'D6 — Wirksamkeitsprüfung',
  D7_preventive_actions: 'D7 — Vorbeugemaßnahmen',
  D8_closure: 'D8 — Abschluss',
};

function ScoreGauge({ score, size = 'large' }) {
  const color = getScoreColorInfo(score);
  const isLarge = size === 'large';
  const circumference = isLarge ? 2 * Math.PI * 54 : 2 * Math.PI * 28;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div
      className="flex flex-col items-center"
      role="meter"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Qualitaetsscore: ${score} von 100, ${color.label}`}
    >
      <div className="relative" style={{ width: isLarge ? 140 : 72, height: isLarge ? 140 : 72 }}>
        <svg className="transform -rotate-90" width="100%" height="100%" viewBox={isLarge ? "0 0 120 120" : "0 0 64 64"}>
          <circle
            cx={isLarge ? 60 : 32} cy={isLarge ? 60 : 32} r={isLarge ? 54 : 28}
            fill="none" stroke="#e5e7eb" strokeWidth={isLarge ? 8 : 5}
          />
          <circle
            cx={isLarge ? 60 : 32} cy={isLarge ? 60 : 32} r={isLarge ? 54 : 28}
            fill="none" stroke={color.ring} strokeWidth={isLarge ? 8 : 5}
            strokeDasharray={circumference} strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 1s ease-in-out' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`${isLarge ? 'text-3xl' : 'text-lg'} font-bold ${color.text}`}>
            {score}
          </span>
          {isLarge && <span className="text-xs text-gray-500">/ 100</span>}
        </div>
      </div>
      {isLarge && (
        <span className={`mt-2 text-sm font-semibold ${color.text}`}>{color.label}</span>
      )}
    </div>
  );
}

// ─── SECTION SCORE CARD ─────────────────────────────────────────────

function SectionScoreCard({ sectionKey, data, isExpanded, onToggle }) {
  const sectionId = `section-${sectionKey}`;

  const statusColors = {
    unzureichend: 'bg-red-100 text-red-800 border-red-200',
    schwach: 'bg-orange-100 text-orange-800 border-orange-200',
    akzeptabel: 'bg-amber-100 text-amber-800 border-amber-200',
    gut: 'bg-green-100 text-green-800 border-green-200',
    exzellent: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  };

  if (!data) return null;

  const score = data.score || 0;
  const issues = data.issues || [];
  const recommendations = data.recommendations || [];

  return (
    <div className={`border rounded-lg overflow-hidden transition-all ${
      score < 60 ? 'border-red-200' : score < 80 ? 'border-amber-200' : 'border-green-200'
    }`}>
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-3 hover:bg-gray-50 transition-colors"
        aria-expanded={isExpanded}
        aria-controls={sectionId}
      >
        <div className="flex items-center gap-3">
          <ScoreGauge score={score} size="small" />
          <div className="text-left">
            <span className="font-semibold text-sm">
              {SECTION_LABELS[sectionKey] || sectionKey}
            </span>
            <Badge className={`ml-2 text-xs ${statusColors[data.status] || 'bg-gray-100'}`}>
              {data.status || 'N/A'}
            </Badge>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {issues.length > 0 && (
            <Badge variant="destructive" className="text-xs">
              {issues.length} {issues.length === 1 ? 'Mangel' : 'Mängel'}
            </Badge>
          )}
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>

      {isExpanded && (
        <div id={sectionId} className="p-4 pt-0 border-t bg-gray-50 space-y-3">
          {/* Assessment */}
          <div>
            <p className="text-sm text-gray-700">{data.assessment}</p>
          </div>

          {/* Issues */}
          {issues.length > 0 && (
            <div>
              <h5 className="text-xs font-semibold text-red-700 uppercase mb-1 flex items-center gap-1">
                <XCircle className="w-3 h-3" /> Mängel
              </h5>
              <ul className="space-y-1">
                {issues.map((issue, i) => (
                  <li key={i} className="text-sm text-red-600 flex items-start gap-2">
                    <span className="text-red-400 mt-0.5">•</span>
                    <span>{issue}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommendations */}
          {recommendations.length > 0 && (
            <div>
              <h5 className="text-xs font-semibold text-blue-700 uppercase mb-1 flex items-center gap-1">
                <Target className="w-3 h-3" /> Empfehlungen
              </h5>
              <ul className="space-y-1">
                {recommendations.map((rec, i) => (
                  <li key={i} className="text-sm text-blue-600 flex items-start gap-2">
                    <span className="text-blue-400 mt-0.5">→</span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── MAIN COMPONENT ─────────────────────────────────────────────────

export default function OpusReviewPanel({ complaintId, onReviewComplete }) {
  const { user } = useContext(AuthContext);
  const [reviews, setReviews] = useState([]);
  const [latestReview, setLatestReview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState(false);
  const [expandedSections, setExpandedSections] = useState({});
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const fetchReviews = async () => {
      try {
        setLoading(true);
        const [latestRes, historyRes] = await Promise.all([
          axios.get(`${API}/complaints/${complaintId}/review/latest`, { signal: controller.signal }).catch((err) => {
            if (err.response?.status === 404) return null; // Expected for new complaints
            throw err;
          }),
          axios.get(`${API}/complaints/${complaintId}/reviews`, { signal: controller.signal }).catch(() => ({ data: { reviews: [] } }))
        ]);

        if (controller.signal.aborted) return;

        if (latestRes?.data) {
          setLatestReview(latestRes.data);
          const expanded = {};
          const sections = latestRes.data.review_data?.section_scores || {};
          Object.entries(sections).forEach(([key, val]) => {
            if (val.score < SCORE_THRESHOLDS.acceptable || (val.issues && val.issues.length > 0)) {
              expanded[key] = true;
            }
          });
          setExpandedSections(expanded);
        }

        setReviews(historyRes?.data?.reviews || []);
      } catch (error) {
        if (!axios.isCancel(error)) {
          toast.error('Fehler beim Laden der Bewertungen');
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    fetchReviews();
    return () => controller.abort();
  }, [complaintId]);

  const requestReview = async (force = false) => {
    setReviewing(true);
    try {
      const res = await axios.post(`${API}/complaints/${complaintId}/review`, { force });

      if (res.data.success) {
        toast.success(
          `Opus-Bewertung abgeschlossen: ${res.data.review.overall_score}/100`
        );
        await fetchReviews();
        if (onReviewComplete) onReviewComplete(res.data.review);
      } else {
        toast.error(res.data.error || 'Review konnte nicht durchgeführt werden');
        if (res.data.missing_sections) {
          toast.info(
            `Fehlende Abschnitte: ${res.data.missing_sections.join(', ')}`
          );
        }
      }
    } catch (error) {
      const detail = error.response?.data?.detail || 'Fehler bei der Opus-Bewertung';
      toast.error(detail);
    } finally {
      setReviewing(false);
    }
  };

  const toggleSection = (key) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="py-8 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-purple-500 mr-2" />
          <span className="text-gray-500">Opus-Bewertungen laden...</span>
        </CardContent>
      </Card>
    );
  }

  const reviewData = latestReview?.review_data;
  const sectionScores = reviewData?.section_scores || {};

  return (
    <div className="space-y-4">
      {/* ─── HEADER & TRIGGER ─────────────────────────────────────── */}
      <Card>
        <CardHeader className="bg-gradient-to-r from-purple-50 to-violet-50 border-b border-purple-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Brain className="w-6 h-6 text-purple-700" />
              </div>
              <div>
                <CardTitle className="text-purple-900">
                  Opus 4.6 — Qualitätsprüfung
                </CardTitle>
                <p className="text-xs text-purple-600 mt-0.5">
                  KI-gestützte Bewertung des 8D-Reports
                </p>
              </div>
            </div>

            <Button
              onClick={() => requestReview(false)}
              disabled={reviewing}
              className="bg-purple-600 hover:bg-purple-700"
            >
              {reviewing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Prüfe mit Opus 4.6...
                </>
              ) : latestReview ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Erneut prüfen
                </>
              ) : (
                <>
                  <Brain className="w-4 h-4 mr-2" />
                  Qualitätsprüfung starten
                </>
              )}
            </Button>
          </div>
        </CardHeader>

        {/* ─── NO REVIEW YET ──────────────────────────────────────── */}
        {!latestReview && !reviewing && (
          <CardContent className="py-12 text-center">
            <Brain className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-500 mb-2">
              Noch keine Opus-Bewertung vorhanden
            </h3>
            <p className="text-sm text-gray-400 max-w-md mx-auto">
              Starten Sie die Qualitätsprüfung, sobald die D-Schritte (D1-D5 mindestens)
              ausgefüllt sind. Opus 4.6 bewertet Vollständigkeit, Konsistenz und Plausibilität.
            </p>
          </CardContent>
        )}

        {/* ─── REVIEW RESULTS ─────────────────────────────────────── */}
        {latestReview && reviewData && (
          <CardContent className="pt-6 space-y-6">
            {/* Overall Score + Recommendation */}
            <div className="flex items-center gap-8 p-4 bg-white rounded-lg border">
              <ScoreGauge score={reviewData.overall_score || 0} size="large" />

              <div className="flex-1 space-y-3">
                {/* Recommendation Badge */}
                <div>
                  {reviewData.recommendation === 'approval_recommended' && (
                    <Badge className="bg-green-100 text-green-800 border-green-300 text-sm px-3 py-1">
                      <CheckCircle className="w-4 h-4 mr-1" /> Freigabe empfohlen
                    </Badge>
                  )}
                  {reviewData.recommendation === 'minor_revision' && (
                    <Badge className="bg-amber-100 text-amber-800 border-amber-300 text-sm px-3 py-1">
                      <AlertTriangle className="w-4 h-4 mr-1" /> Kleine Überarbeitung nötig
                    </Badge>
                  )}
                  {reviewData.recommendation === 'revision_needed' && (
                    <Badge className="bg-red-100 text-red-800 border-red-300 text-sm px-3 py-1">
                      <XCircle className="w-4 h-4 mr-1" /> Überarbeitung erforderlich
                    </Badge>
                  )}
                </div>

                {/* Overall Assessment */}
                <p className="text-sm text-gray-700 leading-relaxed">
                  {reviewData.overall_assessment}
                </p>

                {/* Meta */}
                <div className="flex items-center gap-4 text-xs text-gray-400">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(latestReview.created_at).toLocaleString('de-DE')}
                  </span>
                  <span>Review #{latestReview.review_number}</span>
                  <span>Modell: Claude Opus 4.6</span>
                </div>
              </div>
            </div>

            {/* Consistency & Plausibility Checks */}
            <div className="grid grid-cols-2 gap-4">
              {reviewData.consistency_check && (
                <div className={`p-3 rounded-lg border ${
                  reviewData.consistency_check.d4_d5_alignment
                    ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
                }`}>
                  <div className="flex items-center gap-2 mb-1">
                    <Shield className="w-4 h-4" />
                    <span className="font-semibold text-sm">Konsistenz-Check</span>
                    {reviewData.consistency_check.d4_d5_alignment
                      ? <CheckCircle className="w-4 h-4 text-green-600" />
                      : <XCircle className="w-4 h-4 text-red-600" />
                    }
                  </div>
                  <p className="text-xs text-gray-600">
                    {reviewData.consistency_check.detail}
                  </p>
                </div>
              )}

              {reviewData.plausibility_check && (
                <div className={`p-3 rounded-lg border ${
                  reviewData.plausibility_check.passed
                    ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
                }`}>
                  <div className="flex items-center gap-2 mb-1">
                    <Target className="w-4 h-4" />
                    <span className="font-semibold text-sm">Plausibilitäts-Check</span>
                    {reviewData.plausibility_check.passed
                      ? <CheckCircle className="w-4 h-4 text-green-600" />
                      : <XCircle className="w-4 h-4 text-red-600" />
                    }
                  </div>
                  <p className="text-xs text-gray-600">
                    {reviewData.plausibility_check.detail}
                  </p>
                </div>
              )}
            </div>

            {/* Section Scores */}
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Bewertung pro D-Schritt
              </h4>
              <div className="space-y-2">
                {Object.entries(sectionScores).map(([key, data]) => (
                  <SectionScoreCard
                    key={key}
                    sectionKey={key}
                    data={data}
                    isExpanded={expandedSections[key] || false}
                    onToggle={() => toggleSection(key)}
                  />
                ))}
              </div>
            </div>

            {/* Action Items */}
            {reviewData.action_items && reviewData.action_items.length > 0 && (
              <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                <h4 className="text-sm font-semibold text-orange-800 mb-2 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  Handlungsbedarf ({reviewData.action_items.length} Punkte)
                </h4>
                <ol className="space-y-1">
                  {reviewData.action_items.map((item, i) => (
                    <li key={i} className="text-sm text-orange-700 flex items-start gap-2">
                      <span className="font-semibold text-orange-500 min-w-[20px]">{i + 1}.</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* Strengths */}
            {reviewData.strengths && reviewData.strengths.length > 0 && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <h4 className="text-sm font-semibold text-green-800 mb-2 flex items-center gap-2">
                  <Star className="w-4 h-4" />
                  Stärken
                </h4>
                <ul className="space-y-1">
                  {reviewData.strengths.map((s, i) => (
                    <li key={i} className="text-sm text-green-700 flex items-start gap-2">
                      <CheckCircle className="w-3 h-3 text-green-500 mt-0.5 flex-shrink-0" />
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        )}
      </Card>

      {/* ─── REVIEW HISTORY ───────────────────────────────────────── */}
      {reviews.length > 1 && (
        <Card>
          <CardHeader>
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="flex items-center justify-between w-full"
            >
              <CardTitle className="text-sm">
                Bewertungs-Historie ({reviews.length} Reviews)
              </CardTitle>
              {showHistory ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          </CardHeader>
          {showHistory && (
            <CardContent>
              <div className="space-y-2">
                {reviews.map((review, i) => (
                  <div
                    key={review.id}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border"
                  >
                    <div className="flex items-center gap-3">
                      <ScoreGauge score={review.overall_score || 0} size="small" />
                      <div>
                        <span className="text-sm font-medium">Review #{review.review_number}</span>
                        <span className="text-xs text-gray-400 ml-2">
                          {new Date(review.created_at).toLocaleString('de-DE')}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className={`text-xs ${
                        review.recommendation === 'approval_recommended'
                          ? 'bg-green-100 text-green-700'
                          : review.recommendation === 'minor_revision'
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-red-100 text-red-700'
                      }`}>
                        {review.recommendation === 'approval_recommended' ? 'Freigabe empf.'
                          : review.recommendation === 'minor_revision' ? 'Kleine Korrekturen'
                          : 'Überarbeitung nötig'}
                      </Badge>
                      {review.action_items_count > 0 && (
                        <span className="text-xs text-gray-400">
                          {review.action_items_count} To-Dos
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Score Trend */}
              {reviews.length >= 2 && (
                <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="flex items-center gap-2 text-sm text-blue-700">
                    <TrendingUp className="w-4 h-4" />
                    <span className="font-semibold">Score-Entwicklung:</span>
                    {reviews.slice().reverse().map((r, i) => (
                      <span key={i}>
                        {i > 0 && ' → '}
                        <span className="font-bold">{r.overall_score}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          )}
        </Card>
      )}
    </div>
  );
}
