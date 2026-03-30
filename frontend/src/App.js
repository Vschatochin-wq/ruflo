/**
 * App — 8D-Reklamationsmanagement Hauptkomponente
 */
import React, { useState, useCallback, createContext } from 'react';
import './App.css';
import { Toaster } from 'sonner';
import AppLayout from './layout/AppLayout';
import Dashboard from './pages/Dashboard';
import ComplaintList from './pages/ComplaintList';
import ComplaintDetail from './pages/ComplaintDetail';
import ReviewQueue from './pages/ReviewQueue';
import AnalysisDashboard from './pages/AnalysisDashboard';

// API base URL - points to /api/v1
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
export const API = `${BACKEND_URL}/api/v1`;

// Auth context for sharing user state
export const AuthContext = createContext({
  user: null,
  setUser: () => {},
});

export default function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [pageParams, setPageParams] = useState({});
  const [user] = useState({
    id: 'user-1',
    name: 'Max Mustermann',
    role: 'admin',
    email: 'max.mustermann@guehring.de',
  });

  const handleNavigate = useCallback((page, params = {}) => {
    setCurrentPage(page);
    setPageParams(params);
  }, []);

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard onNavigate={handleNavigate} />;
      case 'complaints':
        return <ComplaintList onNavigate={handleNavigate} currentUser={user} />;
      case 'complaint-detail':
        return (
          <ComplaintDetail
            complaintId={pageParams.complaintId}
            onNavigateBack={() => handleNavigate('complaints')}
            currentUser={user}
          />
        );
      case 'review-queue':
        return <ReviewQueue onNavigate={handleNavigate} />;
      case 'analysis':
        return <AnalysisDashboard />;
      default:
        return <Dashboard onNavigate={handleNavigate} />;
    }
  };

  return (
    <AuthContext.Provider value={{ user, setUser: () => {} }}>
      <Toaster position="top-right" richColors closeButton />
      <AppLayout
        currentPage={currentPage}
        onNavigate={handleNavigate}
        currentUser={user}
      >
        {renderPage()}
      </AppLayout>
    </AuthContext.Provider>
  );
}
