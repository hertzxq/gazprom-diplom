import { useState, useEffect } from 'react';
import { adminApi, authApi, task2Api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import {
  Users,
  UserPlus,
  Trash2,
  Shield,
  ShieldOff,
  Save,
  Plus,
  Filter,
} from 'lucide-react';
import toast from 'react-hot-toast';

const ROLES = [
  { value: 'admin', label: 'Администратор' },
  { value: 'user', label: 'Пользователь' },
];

const EMPTY_FORM = {
  username: '',
  email: '',
  password: '',
  full_name: '',
  role: 'user',
};

export default function AdminPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const res = await adminApi.listUsers();
      setUsers(res.data);
    } catch (err) {
      toast.error('Не удалось загрузить пользователей');
    } finally {
      setLoading(false);
    }
  };

  const handleRoleChange = async (userId, newRole) => {
    try {
      await adminApi.updateUser(userId, { role: newRole });
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u))
      );
      toast.success('Роль обновлена');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка обновления');
    }
  };

  const handleToggleActive = async (userId, currentActive) => {
    try {
      await adminApi.updateUser(userId, { is_active: !currentActive });
      setUsers((prev) =>
        prev.map((u) =>
          u.id === userId ? { ...u, is_active: !currentActive } : u
        )
      );
      toast.success(currentActive ? 'Пользователь заблокирован' : 'Пользователь разблокирован');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка');
    }
  };

  const handleDelete = async (userId, username) => {
    if (!window.confirm(`Удалить пользователя ${username}?`)) return;
    try {
      await adminApi.deleteUser(userId);
      setUsers((prev) => prev.filter((u) => u.id !== userId));
      toast.success('Пользователь удалён');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка удаления');
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.username || !form.email || !form.password) {
      toast.error('Заполните обязательные поля');
      return;
    }
    setCreating(true);
    try {
      await authApi.register(form);
      toast.success('Пользователь создан');
      setForm(EMPTY_FORM);
      setShowForm(false);
      loadUsers();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка создания');
    } finally {
      setCreating(false);
    }
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Управление пользователями</h1>
        <p className="page-subtitle">Создание, роли и блокировка учётных записей</p>
      </div>

      <div className="card" style={{ marginBottom: 'var(--spacing-lg)' }}>
        <div className="card-header">
          <h2 className="card-title">
            <Users size={20} style={{ marginRight: '0.5rem', verticalAlign: 'text-bottom' }} />
            Пользователи
          </h2>
          <button
            id="add-user-btn"
            className="btn btn-primary"
            onClick={() => setShowForm(!showForm)}
          >
            <UserPlus size={16} /> {showForm ? 'Отмена' : 'Добавить'}
          </button>
        </div>

        {showForm && (
          <form
            onSubmit={handleCreate}
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: 'var(--spacing-md)',
              marginBottom: 'var(--spacing-lg)',
              padding: 'var(--spacing-lg)',
              background: 'var(--color-surface-alt)',
              borderRadius: 'var(--radius-lg)',
            }}
          >
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Логин *</label>
              <input
                className="form-input"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                placeholder="username"
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Email *</label>
              <input
                className="form-input"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="user@example.com"
                type="email"
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Пароль *</label>
              <input
                className="form-input"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="••••••"
                type="password"
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">ФИО</label>
              <input
                className="form-input"
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                placeholder="Иванов И.И."
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Роль</label>
              <select
                className="form-select"
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={creating}
                style={{ width: '100%' }}
              >
                {creating ? (
                  <><div className="spinner" /> Создание...</>
                ) : (
                  <><Save size={16} /> Создать</>
                )}
              </button>
            </div>
          </form>
        )}

        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
            <div className="spinner" />
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Пользователь</th>
                  <th>Email</th>
                  <th>Роль</th>
                  <th>Статус</th>
                  <th>Создан</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} style={{ opacity: u.is_active ? 1 : 0.5 }}>
                    <td>
                      <div>
                        <span style={{ fontWeight: 600 }}>
                          {u.full_name || u.username}
                        </span>
                        {u.full_name && (
                          <div
                            style={{
                              fontSize: 'var(--font-size-xs)',
                              color: 'var(--color-text-muted)',
                            }}
                          >
                            @{u.username}
                          </div>
                        )}
                      </div>
                    </td>
                    <td style={{ color: 'var(--color-text-secondary)' }}>{u.email}</td>
                    <td>
                      <select
                        className="form-select"
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                        disabled={u.id === currentUser?.id}
                        title={u.id === currentUser?.id ? 'Нельзя изменить свою роль' : ''}
                        style={{
                          padding: '0.25rem 0.5rem',
                          fontSize: 'var(--font-size-xs)',
                          minWidth: '130px',
                          opacity: u.id === currentUser?.id ? 0.5 : 1,
                        }}
                      >
                        {ROLES.map((r) => (
                          <option key={r.value} value={r.value}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <button
                        className={`btn btn-sm ${u.is_active ? 'btn-secondary' : 'btn-primary'}`}
                        onClick={() => handleToggleActive(u.id, u.is_active)}
                        disabled={u.id === currentUser?.id}
                        title={u.id === currentUser?.id ? 'Нельзя заблокировать себя' : u.is_active ? 'Заблокировать' : 'Разблокировать'}
                        style={{ padding: '0.25rem 0.75rem' }}
                      >
                        {u.is_active ? (
                          <><Shield size={12} /> Активен</>
                        ) : (
                          <><ShieldOff size={12} /> Заблокирован</>
                        )}
                      </button>
                    </td>
                    <td style={{ color: 'var(--color-text-secondary)' }}>
                      {formatDate(u.created_at)}
                    </td>
                    <td>
                      {u.id !== currentUser?.id && (
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => handleDelete(u.id, u.username)}
                          title="Удалить"
                          style={{ padding: '0.25rem 0.5rem' }}
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <SmspExclusionRulesCard />
    </div>
  );
}


function SmspExclusionRulesCard() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await task2Api.listExclusionRules();
        setRules(res.data);
      } catch {
        toast.error('Не удалось загрузить правила');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const update = (idx, field, value) => {
    setRules((prev) => prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));
  };

  const updateKeywords = (idx, text) => {
    const kws = text
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    update(idx, 'keywords', kws);
  };

  const addRow = () => {
    setRules((prev) => [
      ...prev,
      {
        id: null,
        category: 'новая',
        keywords: [],
        point_letter: null,
        enabled: true,
        order_idx: (prev.length + 1) * 10,
      },
    ]);
  };

  const removeRow = (idx) => {
    setRules((prev) => prev.filter((_, i) => i !== idx));
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload = rules.map((r) => ({
        id: r.id,
        category: r.category,
        keywords: r.keywords || [],
        point_letter: r.point_letter || null,
        enabled: !!r.enabled,
        order_idx: Number(r.order_idx) || 100,
      }));
      const res = await task2Api.updateExclusionRules(payload);
      setRules(res.data);
      toast.success('Правила обновлены');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title">
          <Filter size={20} style={{ marginRight: '0.5rem', verticalAlign: 'text-bottom' }} />
          Правила исключений СМСП
        </h2>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={addRow}>
            <Plus size={14} /> Добавить
          </button>
          <button className="btn btn-primary" onClick={save} disabled={saving}>
            {saving ? <><div className="spinner" /> Сохранение...</> : <><Save size={14} /> Сохранить</>}
          </button>
        </div>
      </div>

      <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--spacing-md)', fontSize: '0.875rem' }}>
        Сопоставляет формулировку пункта из столбца «Исключение из СМСП» реестра договоров с короткой
        меткой категории. Первое сработавшее правило выигрывает — правила упорядочиваются по «Порядок».
        Ключевые слова — через запятую; ищется подстрока в нормализованном тексте.
      </p>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
          <div className="spinner" />
        </div>
      ) : (
        <div className="table-container">
          <table style={{ width: '100%', fontSize: '0.875rem' }}>
            <thead>
              <tr>
                <th>Порядок</th>
                <th>Категория</th>
                <th>Ключевые слова (через запятую)</th>
                <th>Пункт (а-я)</th>
                <th>Активно</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r, i) => (
                <tr key={r.id ?? `new-${i}`}>
                  <td style={{ width: 80 }}>
                    <input
                      type="number"
                      className="form-input"
                      style={{ width: 70, padding: '0.25rem 0.5rem' }}
                      value={r.order_idx}
                      onChange={(e) => update(i, 'order_idx', Number(e.target.value))}
                    />
                  </td>
                  <td>
                    <input
                      className="form-input"
                      style={{ padding: '0.25rem 0.5rem' }}
                      value={r.category}
                      onChange={(e) => update(i, 'category', e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      className="form-input"
                      style={{ padding: '0.25rem 0.5rem', width: '100%' }}
                      value={(r.keywords || []).join(', ')}
                      onChange={(e) => updateKeywords(i, e.target.value)}
                      placeholder="страхов, банковск"
                    />
                  </td>
                  <td style={{ width: 90 }}>
                    <input
                      className="form-input"
                      style={{ width: 70, padding: '0.25rem 0.5rem' }}
                      value={r.point_letter || ''}
                      onChange={(e) => update(i, 'point_letter', e.target.value || null)}
                      placeholder="р"
                    />
                  </td>
                  <td style={{ width: 80 }}>
                    <input
                      type="checkbox"
                      checked={r.enabled}
                      onChange={(e) => update(i, 'enabled', e.target.checked)}
                    />
                  </td>
                  <td style={{ width: 60 }}>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => removeRow(i)}
                      style={{ padding: '0.25rem 0.5rem' }}
                      title="Удалить"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
