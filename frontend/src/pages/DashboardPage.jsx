import { useState, useEffect, useMemo } from 'react';
import { documentsApi, analyticsApi } from '../services/api';
import { CheckCircle2, Clock3, AlertTriangle } from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer
} from 'recharts';
import NumberTicker from '../components/magicui/NumberTicker';
import BlurFade from '../components/magicui/BlurFade';

// Палитра данных в духе системных цветов Apple — контраст с фоном ≥3:1
const CHART_COLORS = ['#0a84ff', '#5e5ce6', '#ff9f0a', '#ff453a', '#30d158', '#64d2ff', '#bf5af2', '#ffd60a', '#ac8e68'];

const AXIS_TICK = { fontSize: 11, fill: '#86868b' };

const FILE_TYPE_LABELS = {
  positions: 'Прайс-листы',
  upd: 'УПД',
  act: 'Акты',
  template: 'Шаблоны',
  generated: 'Результаты',
  payment_registry: 'Реестры платежей',
  contract_registry: 'Реестры договоров',
  primary_sumup: 'Первичный свод',
  report: 'Отчёты',
};

const STATUS_LABELS = {
  uploaded: 'Загружен',
  processing: 'В обработке',
  processed: 'Обработан',
  verified: 'Проверен',
  error: 'Ошибка',
};

const EMPTY_STATS = {
  total: 0,
  processed: 0,
  pending: 0,
  errors: 0,
  success_rate: 0,
  error_rate: 0,
  by_status: {},
  by_type: {},
  monthly: [],
  yearly: [],
  volume_trend: [],
  top_items: [],
  region_status: [],
};

function todayLabel() {
  const raw = new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' });
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

// Glass-тултип графиков — единый для всех чартов
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div style={{
      background: 'rgba(255, 255, 255, 0.85)',
      backdropFilter: 'saturate(180%) blur(12px)',
      WebkitBackdropFilter: 'saturate(180%) blur(12px)',
      border: '1px solid rgba(0,0,0,0.06)',
      padding: '8px 12px',
      borderRadius: '12px',
      fontSize: '12px',
      boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
    }}>
      {label && <p style={{ margin: 0, fontWeight: 600, marginBottom: '4px' }}>{label}</p>}
      {payload.map((p, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, margin: 0, color: '#1d1d1f' }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.color || p.payload?.fill, flexShrink: 0 }} />
          {p.name}: <strong>{p.value}</strong>
        </div>
      ))}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="dash-grid" style={{ gap: '1.5rem' }}>
      <div className="dash-grid dash-grid-kpi">
        {[0, 1, 2].map((i) => <div key={i} className="skeleton" style={{ height: 132 }} />)}
      </div>
      <div className="dash-grid dash-grid-main">
        <div className="skeleton" style={{ height: 280 }} />
        <div className="skeleton" style={{ height: 280 }} />
      </div>
      <div className="dash-grid dash-grid-three">
        {[0, 1, 2].map((i) => <div key={i} className="skeleton" style={{ height: 260 }} />)}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState(EMPTY_STATS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    setError(null);
    try {
      const [docsRes, analyticsRes] = await Promise.all([
        documentsApi.list({ limit: 12 }),
        analyticsApi.getSummary(),
      ]);
      setDocuments(docsRes.data || []);
      setStats({ ...EMPTY_STATS, ...(analyticsRes.data || {}) });
    } catch {
      setError('Не удалось загрузить статистику');
    } finally {
      setLoading(false);
    }
  };

  const byTypeData = useMemo(
    () => Object.entries(stats.by_type || {}).map(([key, value]) => ({
      name: FILE_TYPE_LABELS[key] || key,
      value,
    })),
    [stats.by_type]
  );

  const renderEmptyOr = (data, render) =>
    !data || data.length === 0 ? (
      <div className="dash-empty">Нет данных за выбранный период</div>
    ) : (
      <ResponsiveContainer>{render()}</ResponsiveContainer>
    );

  const kpiCards = [
    {
      icon: <CheckCircle2 size={20} strokeWidth={1.8} />,
      iconClass: 'kpi-icon-blue',
      label: 'Доля обработанных документов',
      value: <NumberTicker value={stats.success_rate} suffix="%" />,
      meta: [`Всего: ${stats.total}`, `Обработано: ${stats.processed}`],
    },
    {
      icon: <Clock3 size={20} strokeWidth={1.8} />,
      iconClass: 'kpi-icon-orange',
      label: 'В работе / в очереди',
      value: <NumberTicker value={stats.pending} />,
      meta: [
        `Загружено: ${stats.by_status?.uploaded || 0}`,
        `В обработке: ${stats.by_status?.processing || 0}`,
      ],
    },
    {
      icon: <AlertTriangle size={20} strokeWidth={1.8} />,
      iconClass: 'kpi-icon-red',
      label: 'Доля ошибок',
      value: <NumberTicker value={stats.error_rate} suffix="%" />,
      meta: [`С ошибками: ${stats.errors}`, `Из ${stats.total}`],
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <BlurFade>
        <div className="dash-header">
          <h1 className="dash-title">Аналитика закупочной деятельности</h1>
          <span className="dash-date">{todayLabel()}</span>
        </div>
      </BlurFade>

      {error && (
        <div role="alert" style={{
          padding: '0.75rem 1rem', background: '#fee2e2', border: '1px solid #fca5a5',
          borderRadius: 'var(--radius-md)', color: '#991b1b', fontSize: '0.875rem',
        }}>
          {error}
        </div>
      )}

      {loading ? <DashboardSkeleton /> : (
        <>
          {/* KPI */}
          <div className="dash-grid dash-grid-kpi stagger">
            {kpiCards.map((kpi) => (
              <div key={kpi.label} className="dash-card">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div className={`kpi-icon ${kpi.iconClass}`}>{kpi.icon}</div>
                  <div className="kpi-label">{kpi.label}</div>
                </div>
                <div className="kpi-value" style={{ marginTop: '0.75rem' }}>{kpi.value}</div>
                <div className="kpi-meta">
                  {kpi.meta.map((m) => <span key={m}>{m}</span>)}
                </div>
              </div>
            ))}
          </div>

          {/* Тренд + типы документов */}
          <div className="dash-grid dash-grid-main stagger">
            <div className="dash-card">
              <div>
                <div className="dash-card-title" style={{ marginBottom: 0 }}>Загрузки за последние 30 дней</div>
                <div className="dash-card-caption" style={{ marginBottom: '0.75rem' }}>Документов в день</div>
              </div>
              <div style={{ height: 230 }}>
                {renderEmptyOr(stats.volume_trend, () => (
                  <AreaChart data={stats.volume_trend} margin={{ top: 10, right: 0, left: -25, bottom: 0 }}>
                    <defs>
                      <linearGradient id="volumeGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#0a84ff" stopOpacity={0.25} />
                        <stop offset="95%" stopColor="#0a84ff" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#f0f0f2" vertical={false} />
                    <XAxis dataKey="name" tick={AXIS_TICK} axisLine={false} tickLine={false} />
                    <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} allowDecimals={false} />
                    <RechartsTooltip content={<ChartTooltip />} />
                    <Area type="monotone" dataKey="value" name="Документов" stroke="#0a84ff" fill="url(#volumeGrad)" strokeWidth={2.5} />
                  </AreaChart>
                ))}
              </div>
            </div>

            <div className="dash-card">
              <div className="dash-card-title">Типы документов</div>
              <div style={{ height: 170 }}>
                {renderEmptyOr(byTypeData, () => (
                  <PieChart>
                    <Pie
                      data={byTypeData}
                      cx="50%" cy="50%" innerRadius={52} outerRadius={78}
                      paddingAngle={3} cornerRadius={5} dataKey="value"
                      stroke="none"
                    >
                      {byTypeData.map((_, i) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <RechartsTooltip content={<ChartTooltip />} />
                  </PieChart>
                ))}
              </div>
              {byTypeData.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 12px', marginTop: '0.5rem' }}>
                  {byTypeData.map((t, i) => (
                    <span key={t.name} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.7rem', color: 'var(--color-text-secondary)' }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: CHART_COLORS[i % CHART_COLORS.length] }} />
                      {t.name} · {t.value}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Месяцы / годы / топ задач */}
          <div className="dash-grid dash-grid-three stagger">
            <div className="dash-card">
              <div className="dash-card-title">Документы по месяцам</div>
              <div style={{ height: 210 }}>
                {renderEmptyOr(stats.monthly, () => (
                  <BarChart data={stats.monthly} margin={{ top: 10, right: 0, left: -25, bottom: 0 }}>
                    <CartesianGrid stroke="#f0f0f2" vertical={false} />
                    <XAxis dataKey="name" tick={AXIS_TICK} axisLine={false} tickLine={false} />
                    <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} allowDecimals={false} />
                    <RechartsTooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(0,0,0,0.03)' }} />
                    <Bar dataKey="value" name="Документов" fill="#0a84ff" radius={[6, 6, 0, 0]} barSize={18} />
                  </BarChart>
                ))}
              </div>
            </div>

            <div className="dash-card">
              <div className="dash-card-title">По годам: всего и обработано</div>
              <div style={{ height: 190 }}>
                {renderEmptyOr(stats.yearly, () => (
                  <BarChart data={stats.yearly} margin={{ top: 10, right: 0, left: -25, bottom: 0 }}>
                    <CartesianGrid stroke="#f0f0f2" vertical={false} />
                    <XAxis dataKey="name" tick={AXIS_TICK} axisLine={false} tickLine={false} />
                    <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} allowDecimals={false} />
                    <RechartsTooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(0,0,0,0.03)' }} />
                    <Bar dataKey="Всего" fill="#d2d2d7" barSize={16} radius={[6, 6, 0, 0]} />
                    <Bar dataKey="Обработано" fill="#0a84ff" barSize={16} radius={[6, 6, 0, 0]} />
                  </BarChart>
                ))}
              </div>
              <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', fontSize: '0.7rem', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#d2d2d7' }} /> Всего
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#0a84ff' }} /> Обработано
                </span>
              </div>
            </div>

            <div className="dash-card">
              <div className="dash-card-title">Топ типов задач</div>
              <div style={{ height: 210 }}>
                {renderEmptyOr(stats.top_items, () => (
                  <BarChart layout="vertical" data={stats.top_items} margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                    <XAxis type="number" hide />
                    <YAxis dataKey="name" type="category" tick={{ fontSize: 11, fill: '#48484a' }} axisLine={false} tickLine={false} width={140} />
                    <RechartsTooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(0,0,0,0.03)' }} />
                    <Bar dataKey="value" name="Запусков" fill="#5e5ce6" radius={[0, 6, 6, 0]} barSize={14} />
                  </BarChart>
                ))}
              </div>
            </div>
          </div>

          {/* Последние документы */}
          <BlurFade delay={120}>
            <div className="dash-card">
              <div className="dash-card-title">Последние документы</div>
              {documents.length === 0 ? (
                <div className="dash-empty">Документов нет</div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table className="dash-table">
                    <thead>
                      <tr>
                        <th style={{ textAlign: 'left' }}>Файл</th>
                        <th style={{ textAlign: 'left' }}>Тип</th>
                        <th style={{ textAlign: 'left' }}>Статус</th>
                      </tr>
                    </thead>
                    <tbody>
                      {documents.slice(0, 8).map((doc) => (
                        <tr key={doc.id}>
                          <td
                            style={{ maxWidth: '380px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: 500 }}
                            title={doc.original_filename}
                          >
                            {doc.original_filename}
                          </td>
                          <td style={{ color: 'var(--color-text-secondary)' }}>
                            {FILE_TYPE_LABELS[doc.file_type] || doc.file_type}
                          </td>
                          <td>
                            <span className={`status-dot status-${doc.status}`}>
                              {STATUS_LABELS[doc.status] || doc.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </BlurFade>
        </>
      )}
    </div>
  );
}
