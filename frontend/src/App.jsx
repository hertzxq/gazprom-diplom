import { useState, useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './context/AuthContext';
import { notificationsApi } from './services/api';
import {
  Upload,
  FileSearch,
  Search,
  Settings,
  LogOut,
  User,
  Bell,
  Check,
  Users,
  Calculator,
  LayoutDashboard,
} from 'lucide-react';

import LoginPage from './pages/LoginPage';

import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import ProcessingPage from './pages/ProcessingPage';
import ManufacturerSearchPage from './pages/ManufacturerSearchPage';
import AdminPage from './pages/AdminPage';
import Task2Page from './pages/Task2Page';

function ProtectedRoute({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function NotificationBell() {
  const [notifications, setNotifications] = useState([]);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  const load = async () => {
    try {
      const res = await notificationsApi.list({ limit: 20 });
      setNotifications(res.data);
    } catch {
      // silently ignore
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleMarkRead = async (id) => {
    try {
      await notificationsApi.markRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
    } catch { /* ignore */ }
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch { /* ignore */ }
  };

  const typeIcon = (type) => {
    const map = {
      success: { cls: 'badge-success', text: '✓' },
      error: { cls: 'badge-danger', text: '✕' },
      warning: { cls: 'badge-warning', text: '!' },
      info: { cls: 'badge-info', text: 'i' },
    };
    return map[type] || map.info;
  };

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        id="notification-bell"
        className="btn btn-secondary btn-sm"
        onClick={() => setOpen(!open)}
        style={{
          position: 'relative',
          padding: '0.375rem',
          borderRadius: '50%',
          width: '36px',
          height: '36px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Bell size={18} />
        {unreadCount > 0 && (
          <span
            style={{
              position: 'absolute',
              top: '-2px',
              right: '-2px',
              background: '#ef4444',
              color: '#fff',
              borderRadius: '50%',
              width: '18px',
              height: '18px',
              fontSize: '10px',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: '-10px',
            marginBottom: '0.5rem',
            width: '320px',
            maxHeight: '400px',
            overflowY: 'auto',
            background: '#ffffff',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-lg)',
            border: '1px solid var(--color-border)',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.75rem 1rem',
              borderBottom: '1px solid var(--color-border)',
            }}
          >
            <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>Уведомления</span>
            {unreadCount > 0 && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleMarkAllRead}
                style={{ fontSize: '0.75rem', padding: '0.125rem 0.5rem' }}
              >
                <Check size={12} /> Прочитать все
              </button>
            )}
          </div>

          {notifications.length === 0 ? (
            <div
              style={{
                padding: '2rem',
                textAlign: 'center',
                color: 'var(--color-text-muted)',
                fontSize: '0.875rem',
              }}
            >
              Нет уведомлений
            </div>
          ) : (
            notifications.map((n) => {
              const ti = typeIcon(n.notification_type);
              return (
                <div
                  key={n.id}
                  onClick={() => !n.is_read && handleMarkRead(n.id)}
                  style={{
                    padding: '0.75rem 1rem',
                    borderBottom: '1px solid var(--color-border)',
                    cursor: n.is_read ? 'default' : 'pointer',
                    background: n.is_read ? 'transparent' : 'rgba(0, 62, 146, 0.03)',
                    display: 'flex',
                    gap: '0.75rem',
                    alignItems: 'flex-start',
                    transition: 'background 0.15s',
                  }}
                >
                  <span className={`badge ${ti.cls}`} style={{ flexShrink: 0, marginTop: '2px' }}>
                    {ti.text}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: n.is_read ? 400 : 600, fontSize: '0.825rem' }}>
                      {n.title}
                    </div>
                    <div
                      style={{
                        fontSize: '0.75rem',
                        color: 'var(--color-text-secondary)',
                        marginTop: '0.125rem',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                      }}
                    >
                      {n.message}
                    </div>
                    <div
                      style={{
                        fontSize: '0.675rem',
                        color: 'var(--color-text-muted)',
                        marginTop: '0.25rem',
                      }}
                    >
                      {new Date(n.created_at).toLocaleString('ru-RU', {
                        day: '2-digit',
                        month: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </div>
                  </div>
                  {!n.is_read && (
                    <div
                      style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        background: 'var(--color-primary)',
                        flexShrink: 0,
                        marginTop: '6px',
                      }}
                    />
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <img src="/logo.png" alt="Логотип системы закупок" className="sidebar-logo-img" />
            Система закупок
          </div>
          <div className="sidebar-subtitle">Поддержка закупочной деятельности</div>
        </div>

        <nav className="sidebar-nav">

          <NavLink
            to="/dashboard"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            id="nav-dashboard"
          >
            <LayoutDashboard size={18} />
            <span>Дашборд</span>
          </NavLink>
          <NavLink
            to="/upload"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            id="nav-upload"
          >
            <Upload size={18} />
            <span>Загрузка</span>
          </NavLink>
          <NavLink
            to="/processing"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            id="nav-processing"
          >
            <FileSearch size={18} />
            <span>Обработка</span>
          </NavLink>
          <NavLink
            to="/task2"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            id="nav-task2"
          >
            <Calculator size={18} />
            <span>Свод СМСП</span>
          </NavLink>
          <NavLink
            to="/manufacturers"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            id="nav-manufacturers"
          >
            <Search size={18} />
            <span>Поиск</span>
          </NavLink>
          {user?.role === 'admin' && (
            <NavLink
              to="/admin"
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              id="nav-admin"
            >
              <Users size={18} />
              <span>Пользователи</span>
            </NavLink>
          )}
        </nav>

        <div className="sidebar-footer">
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            marginBottom: '1rem',
            width: '100%',
          }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              background: 'var(--color-primary-dim)',
              color: 'var(--color-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0
            }}>
              <User size={18} />
            </div>
            <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
              <span style={{ 
                fontWeight: 600, 
                fontSize: '0.875rem',
                whiteSpace: 'nowrap', 
                overflow: 'hidden', 
                textOverflow: 'ellipsis',
                lineHeight: 1.2
              }}>
                {user?.full_name || user?.username}
              </span>
              <span style={{ 
                fontSize: '0.75rem',
                color: 'var(--color-primary)',
                fontWeight: 600,
                marginTop: '2px'
              }}>
                {user?.role === 'admin' ? 'Администратор' : 'Пользователь'}
              </span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <NotificationBell />
            <button
              id="logout-btn"
              className="btn btn-secondary btn-sm"
              style={{ flex: 1 }}
              onClick={logout}
            >
              <LogOut size={14} /> Выйти
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/processing" element={<ProcessingPage />} />
          <Route path="/task2" element={<Task2Page />} />
          <Route path="/manufacturers" element={<ManufacturerSearchPage />} />
          <Route path="/admin" element={<AdminPage />} />
          {/* Неизвестный URL — на главную, а не пустая страница */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster
          position="top-right"
          toastOptions={{
            className: 'toast-custom',
            duration: 4000,
          }}
        />
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
