/**
 * AppLayout — Enterprise Sidebar Navigation Layout
 * ==================================================
 * Collapsible sidebar with navigation, user info, and main content area.
 */

import React, { useState, useEffect } from 'react';
import { Badge } from '../components/ui/badge';
import NotificationCenter from '../components/NotificationCenter';
import LanguageSwitch from '../components/LanguageSwitch';
import LiveIndicator from '../components/LiveIndicator';
import {
  LayoutDashboard, FileText, ClipboardCheck, BarChart3,
  ChevronLeft, ChevronRight, Menu, LogOut, User
} from 'lucide-react';

const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { key: 'complaints', label: 'Reklamationen', icon: FileText },
  { key: 'review-queue', label: 'Review-Queue', icon: ClipboardCheck },
  { key: 'analysis', label: 'Auswertungen', icon: BarChart3 },
];

const ROLE_LABELS = {
  admin: 'Administrator',
  zqm: 'ZQM',
  bearbeiter: 'Bearbeiter',
  viewer: 'Betrachter',
};

const ROLE_COLORS = {
  admin: 'bg-red-100 text-red-700',
  zqm: 'bg-purple-100 text-purple-700',
  bearbeiter: 'bg-blue-100 text-blue-700',
  viewer: 'bg-gray-100 text-gray-600',
};

export default function AppLayout({ currentPage, onNavigate, currentUser, children }) {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('sidebar-collapsed') === 'true'; } catch { return false; }
  });

  useEffect(() => {
    try { localStorage.setItem('sidebar-collapsed', String(collapsed)); } catch {}
  }, [collapsed]);

  const userInitials = (currentUser?.name || 'U')
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside
        className={`flex flex-col bg-white border-r border-gray-200 transition-all duration-300 ${
          collapsed ? 'w-16' : 'w-60'
        }`}
      >
        {/* Logo */}
        <div className="flex items-center gap-2 px-4 py-5 border-b border-gray-100">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">8D</span>
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="text-sm font-bold text-gray-800 truncate">G\u00dcHRING</p>
              <p className="text-[10px] text-gray-400 truncate">Reklamationsmanagement</p>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 px-2 space-y-1">
          {NAV_ITEMS.map(({ key, label, icon: Icon }) => {
            const isActive = currentPage === key;
            return (
              <button
                key={key}
                onClick={() => onNavigate(key)}
                title={collapsed ? label : undefined}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-800'
                }`}
              >
                <Icon className={`w-5 h-5 flex-shrink-0 ${isActive ? 'text-blue-600' : 'text-gray-400'}`} />
                {!collapsed && <span className="truncate">{label}</span>}
              </button>
            );
          })}
        </nav>

        {/* User Info */}
        <div className="border-t border-gray-100 p-3">
          {collapsed ? (
            <div className="flex justify-center">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-xs font-bold text-blue-700">
                {userInitials}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-xs font-bold text-blue-700 flex-shrink-0">
                {userInitials}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-700 truncate">{currentUser?.name || 'Benutzer'}</p>
                <Badge className={`text-[10px] px-1.5 py-0 ${ROLE_COLORS[currentUser?.role] || 'bg-gray-100 text-gray-600'}`}>
                  {ROLE_LABELS[currentUser?.role] || currentUser?.role}
                </Badge>
              </div>
            </div>
          )}
        </div>

        {/* Collapse Toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="border-t border-gray-100 p-3 text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors"
          title={collapsed ? 'Erweitern' : 'Einklappen'}
        >
          {collapsed ? <ChevronRight className="w-4 h-4 mx-auto" /> : (
            <div className="flex items-center gap-2 text-xs">
              <ChevronLeft className="w-4 h-4" />
              <span>Einklappen</span>
            </div>
          )}
        </button>
      </aside>

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-gray-800">
              {NAV_ITEMS.find((n) => n.key === currentPage)?.label || currentPage}
            </h2>
            <LiveIndicator />
          </div>
          <div className="flex items-center gap-3">
            <LanguageSwitch />
            <NotificationCenter currentUser={currentUser} />
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
