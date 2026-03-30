/**
 * OcrResultPanel — OCR Results Display & 8D Field Mapping
 * ========================================================
 * Shows OCR extraction results with:
 * - Extraction confidence indicator
 * - Mapped metadata fields
 * - Mapped 8D sections
 * - Field-by-field apply controls
 * - Bulk apply all fields
 *
 * Usage:
 *   <OcrResultPanel
 *     ocrResult={result}
 *     complaintId={id}
 *     onApplyComplete={callback}
 *   />
 *
 * Integration: Import alongside DocumentUpload.js
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { toast } from 'sonner';
import {
  Scan, CheckCircle, XCircle, AlertTriangle, Loader2,
  ArrowRight, FileText, Copy, ChevronDown, ChevronUp
} from 'lucide-react';

const SECTION_LABELS = {
  team_members: 'D1 — Team',
  problem_description: 'D2 — Problembeschreibung',
  immediate_actions: 'D3 — Sofortmaßnahmen',
  root_cause: 'D4 — Ursachenanalyse',
  corrective_actions: 'D5 — Abstellmaßnahmen',
  verification: 'D6 — Verifizierung',
  preventive_actions: 'D7 — Vorbeugemaßnahmen',
  closure: 'D8 — Abschluss',
};

const METADATA_LABELS = {
  complaint_number: 'Reklamations-Nr.',
  customer_name: 'Kundenname',
  customer_number: 'Kundennummer',
  created_by_name: 'Erstellt von',
  phone: 'Telefon',
  customer_order_number: 'Kundenauftragsnr.',
  delivery_note_number: 'Lieferscheinnr.',
  return_number: 'Retourennummer',
  fa_code: 'FA',
  artikel_nummer: 'Art.-/SOBO-Nr.',
  detection_date: 'Feststellungsdatum',
  report_date: 'Meldedatum',
  error_location: 'Fehlerort',
};

const TAD_FIELD_LABELS = {
  problem_type: 'Problemtyp (What?)',
  damage_category: 'Schadensbild (Hauptgruppe)',
  error_code: 'Fehlercode',
  problem_description: 'Detaillierte Problembeschreibung',
  error_location_type: 'Fehlerort (Where?)',
  specific_location: 'Spezifischer Ort',
  how_detected: 'Fehlererkennung (How?)',
  affected_quantity: 'Betroffene Menge (Stk.)',
  delivered_quantity: 'Gelieferte Menge (Stk.)',
  return_quantity: 'Rücksende-Menge (Stk.)',
  message_type: 'SAP Meldungstyp',
  tool_return: 'Werkzeuge zurück?',
  tool_return_reason: 'Begründung',
  discovered_by: 'Fehler entdeckt von',
};

function ConfidenceIndicator({ confidence }) {
  let color = 'text-red-600 bg-red-50 border-red-200';
  let label = 'Niedrig';

  if (confidence >= 0.7) {
    color = 'text-green-700 bg-green-50 border-green-200';
    label = 'Hoch';
  } else if (confidence >= 0.4) {
    color = 'text-yellow-700 bg-yellow-50 border-yellow-200';
    label = 'Mittel';
  }

  return (
    <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium ${color}`}>
      <div
        role="meter"
        aria-valuenow={Math.round(confidence * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`OCR Konfidenz: ${Math.round(confidence * 100)}%`}
        className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden"
      >
        <div
          className={`h-full rounded-full transition-all ${
            confidence >= 0.7 ? 'bg-green-500' : confidence >= 0.4 ? 'bg-yellow-500' : 'bg-red-500'
          }`}
          style={{ width: `${Math.round(confidence * 100)}%` }}
        />
      </div>
      {Math.round(confidence * 100)}% — {label}
    </div>
  );
}

export default function OcrResultPanel({ ocrResult, complaintId, onApplyComplete }) {
  const [result, setResult] = useState(ocrResult);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [selectedFields, setSelectedFields] = useState(new Set());
  const [showFullText, setShowFullText] = useState(false);

  // Load full OCR result if only ID was passed
  useEffect(() => {
    if (ocrResult?._load && ocrResult?.id) {
      loadResult(ocrResult.id);
    } else if (ocrResult && !ocrResult._load) {
      setResult(ocrResult);
      // Pre-select all mapped fields
      const fields = new Set([
        ...Object.keys(ocrResult.mapped_metadata || {}),
        ...Object.keys(ocrResult.mapped_sections || {}),
        ...Object.keys(ocrResult.mapped_tad_fields || {}),
      ]);
      setSelectedFields(fields);
    }
  }, [ocrResult]);

  const loadResult = useCallback(async (id) => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/ocr-results/${id}`);
      const data = res.data.ocr_result;
      setResult(data);
      const fields = new Set([
        ...Object.keys(data.mapped_metadata || {}),
        ...Object.keys(data.mapped_sections || {}),
      ]);
      setSelectedFields(fields);
    } catch (err) {
      toast.error('OCR-Ergebnis konnte nicht geladen werden');
    } finally {
      setLoading(false);
    }
  }, []);

  // ─── Toggle field selection ──────────────────────────────────
  function toggleField(field) {
    setSelectedFields((prev) => {
      const next = new Set(prev);
      if (next.has(field)) {
        next.delete(field);
      } else {
        next.add(field);
      }
      return next;
    });
  }

  function selectAll() {
    const fields = new Set([
      ...Object.keys(result?.mapped_metadata || {}),
      ...Object.keys(result?.mapped_sections || {}),
      ...Object.keys(result?.mapped_tad_fields || {}),
    ]);
    setSelectedFields(fields);
  }

  function selectNone() {
    setSelectedFields(new Set());
  }

  // ─── Apply selected fields to complaint ──────────────────────
  async function handleApply() {
    if (!result?.id || selectedFields.size === 0) return;

    setApplying(true);
    try {
      const res = await axios.post(`${API}/complaints/${complaintId}/ocr/apply`, {
        ocr_result_id: result.id,
        selected_fields: Array.from(selectedFields),
      });

      if (res.data.success) {
        toast.success(
          `${res.data.applied_count} Felder übertragen` +
          (res.data.skipped_count > 0
            ? ` (${res.data.skipped_count} übersprungen — bereits ausgefüllt)`
            : '')
        );
        onApplyComplete?.(res.data);
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Übertragung fehlgeschlagen';
      toast.error(msg);
    } finally {
      setApplying(false);
    }
  }

  // ─── Render ──────────────────────────────────────────────────
  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
          <span className="ml-2 text-sm text-gray-500">OCR-Ergebnis laden...</span>
        </CardContent>
      </Card>
    );
  }

  if (!result) return null;

  const metadata = result.mapped_metadata || {};
  const sections = result.mapped_sections || {};
  const tadFields = result.mapped_tad_fields || {};
  const hasFields = Object.keys(metadata).length > 0 || Object.keys(sections).length > 0 || Object.keys(tadFields).length > 0;
  const extractedText = result.extracted_text || result.extracted_text_preview || '';

  return (
    <Card className="border-blue-200 bg-blue-50/30">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Scan className="w-5 h-5 text-blue-600" />
            OCR-Ergebnis
          </CardTitle>
          <div className="flex items-center gap-3">
            <ConfidenceIndicator confidence={result.mapping_confidence || 0} />
            <Badge variant="outline">
              {result.mapped_field_count || 0}/{result.total_field_count || 0} Felder
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* OCR Info */}
        <div className="flex flex-wrap gap-3 text-xs text-gray-500">
          <span>Methode: {result.ocr_method || '—'}</span>
          <span>&bull;</span>
          <span>Seiten: {result.page_count || 0}</span>
          <span>&bull;</span>
          <span>Zeichen: {result.char_count || 0}</span>
          <span>&bull;</span>
          <span>OCR-Konfidenz: {Math.round((result.ocr_confidence || 0) * 100)}%</span>
        </div>

        {/* Extracted Text Preview */}
        {extractedText && (
          <div className="space-y-1">
            <button
              onClick={() => setShowFullText(!showFullText)}
              className="flex items-center gap-1 text-xs text-gray-600 hover:text-gray-800"
            >
              <FileText className="w-3 h-3" />
              Extrahierter Text
              {showFullText ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            {showFullText && (
              <pre className="text-xs bg-white p-3 rounded border max-h-48 overflow-auto whitespace-pre-wrap font-mono text-gray-700">
                {extractedText}
              </pre>
            )}
          </div>
        )}

        {/* No fields found */}
        {!hasFields && (
          <div className="text-center py-4">
            <AlertTriangle className="w-8 h-8 mx-auto text-yellow-500 mb-2" />
            <p className="text-sm text-gray-600">
              Keine 8D-Felder erkannt. Das Dokument enthält möglicherweise kein
              Standard-8D-Format oder die OCR-Qualität ist zu niedrig.
            </p>
          </div>
        )}

        {/* Mapped Metadata */}
        {Object.keys(metadata).length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-gray-700">Erkannte Stammdaten</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {Object.entries(metadata).map(([field, value]) => (
                <label
                  key={field}
                  className={`
                    flex items-start gap-2 p-2 rounded border cursor-pointer transition-colors
                    ${selectedFields.has(field)
                      ? 'border-blue-400 bg-blue-50'
                      : 'border-gray-200 bg-white hover:border-gray-300'
                    }
                  `}
                >
                  <input
                    type="checkbox"
                    checked={selectedFields.has(field)}
                    onChange={() => toggleField(field)}
                    className="mt-0.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-gray-500">
                      {METADATA_LABELS[field] || field}
                    </p>
                    <p className="text-sm text-gray-800 truncate">{value}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Mapped 8D Sections */}
        {Object.keys(sections).length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-gray-700">Erkannte 8D-Abschnitte</h4>
            <div className="space-y-2">
              {Object.entries(sections).map(([field, value]) => (
                <label
                  key={field}
                  className={`
                    flex items-start gap-2 p-3 rounded border cursor-pointer transition-colors
                    ${selectedFields.has(field)
                      ? 'border-blue-400 bg-blue-50'
                      : 'border-gray-200 bg-white hover:border-gray-300'
                    }
                  `}
                >
                  <input
                    type="checkbox"
                    checked={selectedFields.has(field)}
                    onChange={() => toggleField(field)}
                    className="mt-0.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-gray-600">
                      {SECTION_LABELS[field] || field}
                    </p>
                    <p className="text-sm text-gray-700 whitespace-pre-wrap line-clamp-3">
                      {value}
                    </p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* TAD-specific Fields */}
        {Object.keys(tadFields).length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-gray-700">TAD-Formular Felder</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {Object.entries(tadFields).map(([field, value]) => (
                <label
                  key={field}
                  className={`
                    flex items-start gap-2 p-2 rounded border cursor-pointer transition-colors
                    ${selectedFields.has(field)
                      ? 'border-blue-400 bg-blue-50'
                      : 'border-gray-200 bg-white hover:border-gray-300'
                    }
                  `}
                >
                  <input
                    type="checkbox"
                    checked={selectedFields.has(field)}
                    onChange={() => toggleField(field)}
                    className="mt-0.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-gray-500">
                      {TAD_FIELD_LABELS[field] || field}
                    </p>
                    <p className="text-sm text-gray-800">{value}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        {hasFields && (
          <div className="flex items-center justify-between pt-2 border-t">
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={selectAll}>
                Alle auswählen
              </Button>
              <Button variant="ghost" size="sm" onClick={selectNone}>
                Keine
              </Button>
            </div>
            <Button
              onClick={handleApply}
              disabled={applying || selectedFields.size === 0}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {applying ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Übertrage...
                </>
              ) : (
                <>
                  <ArrowRight className="w-4 h-4 mr-2" />
                  {selectedFields.size} Felder übertragen
                </>
              )}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
