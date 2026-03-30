/**
 * App — 8D Reklamationsmanagement Entry Point
 * =============================================
 * Main application with state-based routing, layout, and providers.
 */

import React, { useState, useCallback, createContext } from 'react';
import { Toaster } from 'sonner';
import { I18nProvider } from './i18n';
import AppLayout from './layout/AppLayout';
import Dashboard from './pages/Dashboard';
import ComplaintList from './pages/ComplaintList';
import ComplaintDetail from './pages/ComplaintDetail';
import ReviewQueue from './pages/ReviewQueue';
import AnalysisDashboard from './pages/AnalysisDashboard';

export const API = process.env.REACT_APP_API_URL || '/api/v1';

export const AuthContext = createContext({
  user: null,
});

// Mock user for development — replace with real auth
const CURRENT_USER = {
  id: 'user-1',
  name: 'Max Mustermann',
  role: 'admin',
};

export default function App() {
  const [page, setPage] = useState('dashboard');
  const [selectedComplaintId, setSelectedComplaintId] = useState(null);

  const navigate = useCallback((target, params) => {
    if (target === 'complaint-detail' && params?.complaintId) {
      setSelectedComplaintId(params.complaintId);
      setPage('complaint-detail');
    } else {
      setPage(target);
      setSelectedComplaintId(null);
    }
  }, []);

  const renderPage = () => {
    switch (page) {
      case 'dashboard':
        return <Dashboard onNavigate={navigate} />;
      case 'complaints':
        return (
          <ComplaintList
            onNavigate={navigate}
            currentUser={CURRENT_USER}
          />
        );
      case 'complaint-detail':
        return (
          <ComplaintDetail
            complaintId={selectedComplaintId}
            onNavigateBack={() => navigate('complaints')}
            currentUser={CURRENT_USER}
          />
        );
      case 'review-queue':
        return <ReviewQueue onNavigate={navigate} />;
      case 'analysis':
        return <AnalysisDashboard onNavigate={navigate} />;
      default:
        return <Dashboard onNavigate={navigate} />;
    }
  };

  return (
    <AuthContext.Provider value={{ user: CURRENT_USER }}>
      <I18nProvider>
        <AppLayout
          currentPage={page}
          onNavigate={navigate}
          currentUser={CURRENT_USER}
        >
          {renderPage()}
        </AppLayout>
        <Toaster position="top-right" richColors />
      </I18nProvider>
    </AuthContext.Provider>
  );
}
