/**
 * DocumentUpload — TAD Document Upload with Drag & Drop
 * ======================================================
 * Handles file upload for TAD documents (PDF, images) with:
 * - Drag & drop zone
 * - File type and size validation
 * - Upload progress indicator
 * - Document list with OCR status
 * - Delete functionality
 *
 * Usage:
 *   <DocumentUpload complaintId={id} onUploadComplete={callback} />
 *
 * Integration: Import in ComplaintEditNew.js
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { API, AuthContext } from '../App';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { toast } from 'sonner';
import {
  Upload, FileText, Image, Trash2, Loader2, CheckCircle,
  XCircle, AlertTriangle, Eye, Scan, File
} from 'lucide-react';

const ALLOWED_TYPES = [
  'application/pdf',
  'image/png',
  'image/jpeg',
  'image/tiff',
  'image/bmp',
  'image/webp',
];

const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB
const MAX_FILES = 20;

const FILE_TYPE_LABELS = {
  'application/pdf': 'PDF',
  'image/png': 'PNG',
  'image/jpeg': 'JPEG',
  'image/tiff': 'TIFF',
  'image/bmp': 'BMP',
  'image/webp': 'WebP',
};

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(mimeType) {
  if (mimeType === 'application/pdf') return FileText;
  if (mimeType?.startsWith('image/')) return Image;
  return File;
}

function OcrStatusBadge({ status }) {
  switch (status) {
    case 'completed':
      return (
        <Badge variant="outline" className="text-green-700 border-green-300 bg-green-50">
          <CheckCircle className="w-3 h-3 mr-1" />
          OCR fertig
        </Badge>
      );
    case 'processing':
      return (
        <Badge variant="outline" className="text-blue-700 border-blue-300 bg-blue-50">
          <Loader2 className="w-3 h-3 mr-1 animate-spin" />
          OCR läuft
        </Badge>
      );
    case 'failed':
      return (
        <Badge variant="outline" className="text-red-700 border-red-300 bg-red-50">
          <XCircle className="w-3 h-3 mr-1" />
          OCR Fehler
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="text-gray-500 border-gray-300">
          <AlertTriangle className="w-3 h-3 mr-1" />
          Ausstehend
        </Badge>
      );
  }
}

export default function DocumentUpload({ complaintId, onUploadComplete, onOcrResult }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const fileInputRef = useRef(null);
  const abortControllerRef = useRef(null);

  // ─── Load documents ──────────────────────────────────────────
  const fetchDocuments = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/complaints/${complaintId}/documents`);
      setDocuments(res.data.documents || []);
    } catch (err) {
      if (err.name !== 'CanceledError') {
        console.error('Fehler beim Laden der Dokumente:', err);
      }
    } finally {
      setLoading(false);
    }
  }, [complaintId]);

  useEffect(() => {
    const controller = new AbortController();
    abortControllerRef.current = controller;
    fetchDocuments();
    return () => controller.abort();
  }, [fetchDocuments]);

  // ─── File validation ─────────────────────────────────────────
  function validateFile(file) {
    if (!ALLOWED_TYPES.includes(file.type)) {
      toast.error(`Dateityp "${file.type || 'unbekannt'}" nicht erlaubt. Erlaubt: PDF, PNG, JPEG, TIFF, BMP, WebP`);
      return false;
    }
    if (file.size > MAX_FILE_SIZE) {
      toast.error(`Datei "${file.name}" ist zu groß (${formatFileSize(file.size)}). Maximum: 20 MB`);
      return false;
    }
    if (file.size === 0) {
      toast.error('Leere Dateien können nicht hochgeladen werden');
      return false;
    }
    if (documents.length >= MAX_FILES) {
      toast.error(`Maximum von ${MAX_FILES} Dateien pro Reklamation erreicht`);
      return false;
    }
    return true;
  }

  // ─── Upload handler ──────────────────────────────────────────
  async function handleUpload(files) {
    const validFiles = Array.from(files).filter(validateFile);
    if (validFiles.length === 0) return;

    setUploading(true);
    setUploadProgress(0);

    for (let i = 0; i < validFiles.length; i++) {
      const file = validFiles[i];
      const formData = new FormData();
      formData.append('file', file);
      formData.append('document_type', 'tad');

      try {
        const res = await axios.post(
          `${API}/complaints/${complaintId}/documents`,
          formData,
          {
            headers: { 'Content-Type': 'multipart/form-data' },
            onUploadProgress: (e) => {
              const fileProgress = (i / validFiles.length) + (e.loaded / e.total / validFiles.length);
              setUploadProgress(Math.round(fileProgress * 100));
            },
          }
        );

        if (res.data.success) {
          toast.success(`"${file.name}" hochgeladen`);

          if (res.data.ocr_result && !res.data.ocr_result.error) {
            const mapped = res.data.ocr_result.mapped_field_count || 0;
            const total = res.data.ocr_result.total_field_count || 0;
            toast.info(
              `OCR: ${mapped}/${total} Felder erkannt (${Math.round((res.data.ocr_result.mapping_confidence || 0) * 100)}% Konfidenz)`,
              { duration: 5000 }
            );
            onOcrResult?.(res.data.ocr_result);
          }

          onUploadComplete?.(res.data.document);
        }
      } catch (err) {
        const msg = err.response?.data?.detail || 'Upload fehlgeschlagen';
        toast.error(`"${file.name}": ${msg}`);
      }
    }

    setUploading(false);
    setUploadProgress(0);
    fetchDocuments();
  }

  // ─── Drag & Drop handlers ────────────────────────────────────
  function handleDrag(e) {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.length > 0) {
      handleUpload(e.dataTransfer.files);
    }
  }

  function handleFileInput(e) {
    if (e.target.files?.length > 0) {
      handleUpload(e.target.files);
      e.target.value = '';
    }
  }

  // ─── Delete document ─────────────────────────────────────────
  async function handleDelete(docId, filename) {
    if (!window.confirm(`Dokument "${filename}" wirklich löschen?`)) return;

    try {
      await axios.delete(`${API}/documents/${docId}`);
      toast.success('Dokument gelöscht');
      fetchDocuments();
    } catch (err) {
      toast.error('Löschen fehlgeschlagen');
    }
  }

  // ─── Re-trigger OCR ──────────────────────────────────────────
  async function handleRetriggerOcr(docId) {
    try {
      const res = await axios.post(`${API}/complaints/${complaintId}/ocr`, {
        document_id: docId,
      });
      if (res.data.success) {
        toast.success('OCR erfolgreich');
        onOcrResult?.(res.data.ocr_result);
        fetchDocuments();
      }
    } catch (err) {
      toast.error('OCR-Verarbeitung fehlgeschlagen');
    }
  }

  // ─── Render ──────────────────────────────────────────────────
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Upload className="w-5 h-5 text-blue-600" />
          TAD-Dokumente
          {documents.length > 0 && (
            <Badge variant="secondary" className="ml-2">
              {documents.length}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Drop Zone */}
        <div
          role="button"
          tabIndex={0}
          aria-label="Dateien per Drag & Drop hochladen oder klicken zum Auswählen"
          className={`
            relative border-2 border-dashed rounded-lg p-8 text-center
            transition-colors duration-200 cursor-pointer
            ${dragActive
              ? 'border-blue-500 bg-blue-50'
              : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
            }
            ${uploading ? 'pointer-events-none opacity-60' : ''}
          `}
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onClick={() => !uploading && fileInputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={ALLOWED_TYPES.join(',')}
            onChange={handleFileInput}
            className="hidden"
            aria-hidden="true"
          />

          {uploading ? (
            <div className="space-y-3">
              <Loader2 className="w-10 h-10 mx-auto text-blue-500 animate-spin" />
              <p className="text-sm text-gray-600">Hochladen... {uploadProgress}%</p>
              <div className="w-48 mx-auto bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                  role="progressbar"
                  aria-valuenow={uploadProgress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                />
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <Upload className={`w-10 h-10 mx-auto ${dragActive ? 'text-blue-500' : 'text-gray-400'}`} />
              <p className="text-sm font-medium text-gray-700">
                {dragActive ? 'Dateien hier ablegen' : 'Dateien hier ablegen oder klicken'}
              </p>
              <p className="text-xs text-gray-500">
                PDF, PNG, JPEG, TIFF, BMP, WebP &bull; Max. 20 MB
              </p>
            </div>
          )}
        </div>

        {/* Document List */}
        {loading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
            <span className="ml-2 text-sm text-gray-500">Dokumente laden...</span>
          </div>
        ) : documents.length > 0 ? (
          <div className="space-y-2">
            {documents.map((doc) => {
              const IconComponent = getFileIcon(doc.mime_type);
              return (
                <div
                  key={doc.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border"
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <IconComponent className="w-5 h-5 text-gray-500 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">
                        {doc.original_filename}
                      </p>
                      <div className="flex items-center gap-2 text-xs text-gray-500">
                        <span>{FILE_TYPE_LABELS[doc.mime_type] || doc.mime_type}</span>
                        <span>&bull;</span>
                        <span>{formatFileSize(doc.file_size)}</span>
                        <span>&bull;</span>
                        <span>{new Date(doc.created_at).toLocaleDateString('de-DE')}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 ml-3 flex-shrink-0">
                    <OcrStatusBadge status={doc.ocr_status} />

                    {doc.ocr_status === 'failed' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRetriggerOcr(doc.id)}
                        title="OCR erneut starten"
                      >
                        <Scan className="w-4 h-4" />
                      </Button>
                    )}

                    {doc.ocr_result_id && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onOcrResult?.({ id: doc.ocr_result_id, _load: true })}
                        title="OCR-Ergebnis anzeigen"
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                    )}

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(doc.id, doc.original_filename)}
                      className="text-red-500 hover:text-red-700 hover:bg-red-50"
                      title="Dokument löschen"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-gray-500 text-center py-2">
            Noch keine Dokumente hochgeladen
          </p>
        )}
      </CardContent>
    </Card>
  );
}
