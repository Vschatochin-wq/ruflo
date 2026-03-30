/**
 * NotificationCenter — In-App Notification Dropdown
 * ===================================================
 * Displays real-time notifications in a dropdown from the header.
 * Connects via WebSocket for instant updates.
 *
 * Usage in GruehringHeader.js or App.js:
 *   import NotificationCenter from './components/NotificationCenter';
 *   <NotificationCenter />
 */

import React, { useState, useEffect, useContext, useRef, useCallback } from 'react';
import axios from 'axios';
import { API, AuthContext } from '../App';
// Navigation handled via action_url window.location
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import {
  Bell, BellRing, Check, CheckCheck, Trash2, X,
  FilePlus, AlertTriangle, Mail, Brain, Eye,
  Edit, CheckCircle, XCircle, Clock, Shield, UserPlus
} from 'lucide-react';

const MAX_WS_RETRIES = 10;
const WS_BASE_DELAY_MS = 1000;

const TYPE_ICONS = {
  new_complaint: FilePlus,
  missing_info: AlertTriangle,
  response_received: Mail,
  status_change: Edit,
  review_required: Eye,
  opus_result: Brain,
  revision_needed: Edit,
  approval_needed: CheckCircle,
  approval: CheckCircle,
  rejection: XCircle,
  escalation: AlertTriangle,
  task_assigned: UserPlus,
  task_overdue: Clock,
  complaint_closed: Shield,
  system: Bell,
};

const TYPE_COLORS = {
  new_complaint: 'text-blue-600 bg-blue-50',
  missing_info: 'text-yellow-600 bg-yellow-50',
  response_received: 'text-green-600 bg-green-50',
  status_change: 'text-indigo-600 bg-indigo-50',
  review_required: 'text-purple-600 bg-purple-50',
  opus_result: 'text-violet-600 bg-violet-50',
  revision_needed: 'text-orange-600 bg-orange-50',
  approval_needed: 'text-amber-600 bg-amber-50',
  approval: 'text-green-600 bg-green-50',
  rejection: 'text-red-600 bg-red-50',
  escalation: 'text-red-600 bg-red-50',
  task_assigned: 'text-blue-600 bg-blue-50',
  task_overdue: 'text-red-600 bg-red-50',
  complaint_closed: 'text-green-600 bg-green-50',
  system: 'text-gray-600 bg-gray-50',
};

export default function NotificationCenter() {
  const { user } = useContext(AuthContext);
  // No react-router — navigation via callbacks or action_url
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef(null);
  const wsRef = useRef(null);
  const wsRetryRef = useRef(0);
  const wsTimerRef = useRef(null);
  const pollingRef = useRef(null);
  const userRef = useRef(user);

  // Keep user ref current for WebSocket callbacks
  useEffect(() => { userRef.current = user; }, [user]);

  const fetchNotifications = useCallback(async (signal) => {
    try {
      setLoading(true);
      const res = await axios.get(`${API}/notifications?limit=20`, { signal });
      setNotifications(res.data || []);
    } catch (error) {
      if (!axios.isCancel(error) && error.response?.status === 401) {
        // Auth expired — don't silently ignore
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchUnreadCount = useCallback(async (signal) => {
    try {
      const res = await axios.get(`${API}/notifications/unread-count`, { signal });
      setUnreadCount(res.data?.count || 0);
    } catch (error) {
      // Silently fail for non-auth errors
    }
  }, []);

  const connectWebSocket = useCallback(() => {
    // Clean up previous connection
    if (wsRef.current) {
      wsRef.current.onclose = null; // Prevent reconnect on intentional close
      wsRef.current.close();
      wsRef.current = null;
    }

    if (wsRetryRef.current >= MAX_WS_RETRIES) {
      // Fall back to polling after max retries
      if (!pollingRef.current) {
        pollingRef.current = setInterval(() => fetchUnreadCount(), 30000);
      }
      return;
    }

    try {
      const wsUrl = API.replace('http', 'ws').replace('/api', '') + '/ws/notifications';
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        // Send token as first message instead of URL query param
        const token = localStorage.getItem('token');
        ws.send(JSON.stringify({ type: 'auth', token }));
        wsRetryRef.current = 0; // Reset retry count on success
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'notification') {
            // Deduplicate by ID
            setNotifications(prev => {
              const existing = new Set(prev.map(n => n.id));
              if (existing.has(data.data?.id)) return prev;
              return [data.data, ...prev].slice(0, 50);
            });
            setUnreadCount(prev => prev + 1);
          }
        } catch (e) {
          // Invalid message
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (!userRef.current) return; // User logged out

        // Exponential backoff with jitter
        wsRetryRef.current += 1;
        const delay = Math.min(
          WS_BASE_DELAY_MS * Math.pow(2, wsRetryRef.current) + Math.random() * 1000,
          30000
        );
        wsTimerRef.current = setTimeout(connectWebSocket, delay);
      };

      ws.onerror = () => {
        // onclose will fire after onerror
      };
    } catch (error) {
      // WebSocket not available — fall back to polling
      if (!pollingRef.current) {
        pollingRef.current = setInterval(() => fetchUnreadCount(), 30000);
      }
    }
  }, [fetchUnreadCount]);

  // Fetch notifications on mount
  useEffect(() => {
    if (!user) return;

    const controller = new AbortController();
    fetchNotifications(controller.signal);
    fetchUnreadCount(controller.signal);
    connectWebSocket();

    return () => {
      controller.abort();
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
      if (wsTimerRef.current) clearTimeout(wsTimerRef.current);
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [user, fetchNotifications, fetchUnreadCount, connectWebSocket]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('pointerdown', handleClickOutside);
    return () => document.removeEventListener('pointerdown', handleClickOutside);
  }, []);

  const markAsRead = async (notificationId) => {
    try {
      await axios.patch(`${API}/notifications/${notificationId}/read`);
      setNotifications(prev =>
        prev.map(n => n.id === notificationId ? { ...n, read: true } : n)
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (error) {
      // Silently fail
    }
  };

  const markAllAsRead = async () => {
    try {
      await axios.patch(`${API}/notifications/read-all`);
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
      setUnreadCount(0);
    } catch (error) {
      // Silently fail
    }
  };

  const handleNotificationClick = (notification) => {
    if (!notification.read) {
      markAsRead(notification.id);
    }
    if (notification.action_url) {
      // Navigate via action_url if available
      if (notification.action_url) window.location.hash = notification.action_url;
      setOpen(false);
    }
  };

  const formatTime = (isoString) => {
    if (!isoString) return '';
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Gerade eben';
    if (diffMins < 60) return `vor ${diffMins} Min.`;
    if (diffHours < 24) return `vor ${diffHours} Std.`;
    if (diffDays < 7) return `vor ${diffDays} Tag${diffDays > 1 ? 'en' : ''}`;
    return date.toLocaleDateString('de-DE');
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Button */}
      <button
        onClick={() => { setOpen(!open); if (!open) fetchNotifications(); }}
        className="relative p-2 rounded-lg hover:bg-gray-100 transition-colors"
        aria-label="Benachrichtigungen"
        aria-haspopup="true"
        aria-expanded={open}
      >
        {unreadCount > 0 ? (
          <BellRing className="w-5 h-5 text-purple-600" />
        ) : (
          <Bell className="w-5 h-5 text-gray-500" />
        )}

        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center motion-safe:animate-pulse">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 mt-2 w-96 bg-white rounded-xl shadow-2xl border border-gray-200 z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b">
            <h3 className="font-semibold text-sm text-gray-700">Benachrichtigungen</h3>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button
                  onClick={markAllAsRead}
                  className="text-xs text-purple-600 hover:text-purple-800 flex items-center gap-1"
                >
                  <CheckCheck className="w-3 h-3" /> Alle gelesen
                </button>
              )}
              <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Notification List */}
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="py-12 text-center">
                <Bell className="w-10 h-10 text-gray-200 mx-auto mb-2" />
                <p className="text-sm text-gray-400">Keine Benachrichtigungen</p>
              </div>
            ) : (
              notifications.map(notification => {
                const IconComponent = TYPE_ICONS[notification.type] || Bell;
                const colorClass = TYPE_COLORS[notification.type] || TYPE_COLORS.system;

                return (
                  <button
                    key={notification.id}
                    onClick={() => handleNotificationClick(notification)}
                    className={`w-full text-left px-4 py-3 border-b border-gray-100 hover:bg-gray-50 transition-colors flex items-start gap-3 ${
                      !notification.read ? 'bg-purple-50/50' : ''
                    }`}
                  >
                    {/* Icon */}
                    <div className={`p-1.5 rounded-lg flex-shrink-0 mt-0.5 ${colorClass}`}>
                      <IconComponent className="w-4 h-4" />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm ${!notification.read ? 'font-semibold' : 'font-medium'} text-gray-800 truncate`}>
                          {notification.title}
                        </span>
                        {!notification.read && (
                          <span className="w-2 h-2 bg-purple-500 rounded-full flex-shrink-0" />
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                        {notification.message}
                      </p>
                      <span className="text-[10px] text-gray-400 mt-1 block">
                        {formatTime(notification.created_at)}
                      </span>
                    </div>

                    {/* Priority indicator */}
                    {notification.priority === 'urgent' && (
                      <span className="w-2 h-2 bg-red-500 rounded-full flex-shrink-0 mt-2 animate-pulse" />
                    )}
                    {notification.priority === 'high' && (
                      <span className="w-2 h-2 bg-orange-500 rounded-full flex-shrink-0 mt-2" />
                    )}
                  </button>
                );
              })
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="px-4 py-2 bg-gray-50 border-t text-center">
              <button
                onClick={() => { setOpen(false); }}
                className="text-xs text-purple-600 hover:text-purple-800 font-medium"
              >
                Alle Benachrichtigungen anzeigen
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
