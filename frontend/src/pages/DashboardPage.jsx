import { useState, useEffect } from 'react';
import { documentsApi, analyticsApi } from '../services/api';
import { Download, LayoutDashboard } from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Legend
} from 'recharts';

// --- MOCK DATA ---
const topItemsData = [
  { name: 'Трубы стальные', value: 245000 },
  { name: 'Запорная арматура', value: 210000 },
  { name: 'Кабель ВВГнг', value: 195000 },
  { name: 'Насосные агрегаты', value: 180000 },
  { name: 'Спецодежда', value: 155000 },
  { name: 'КИПиА', value: 140000 },
  { name: 'Дизель-генераторы', value: 135000 },
  { name: 'Буровые реагенты', value: 120000 },
  { name: 'Метизы (болты/гайки)', value: 115000 },
  { name: 'Цемент тампонаж.', value: 105000 },
].reverse(); // Reverse for bottom-up horizontal bar

const regionStatusData = [
  { name: 'ЯНАО', 'Новые': 45, 'Действующие': 140 },
  { name: 'ХМАО', 'Новые': 30, 'Действующие': 150 },
  { name: 'Томск',  'Новые': 60, 'Действующие': 80 },
  { name: 'Сахалин',  'Новые': 25, 'Действующие': 110 },
  { name: 'Иркутск',  'Новые': 40, 'Действующие': 95 },
];

const activityTrendData = [
  { name: '01', new: 15, existing: 35 },
  { name: '02', new: 10, existing: 38 },
  { name: '03', new: 14, existing: 36 },
  { name: '04', new: 12, existing: 45 },
  { name: '05', new: 18, existing: 39 },
  { name: '06', new: 24, existing: 44 },
  { name: '07', new: 15, existing: 35 },
  { name: '08', new: 11, existing: 31 },
  { name: '09', new: 13, existing: 27 },
  { name: '10', new: 9,  existing: 35 },
  { name: '11', new: 14, existing: 32 },
  { name: '12', new: 10, existing: 25 },
];

const volumeTrendData = [
  { name: '01', prev: 180, curr: 200 },
  { name: '02', prev: 190, curr: 210 },
  { name: '03', prev: 175, curr: 185 },
  { name: '04', prev: 180, curr: 195 },
  { name: '05', prev: 200, curr: 215 },
  { name: '06', prev: 190, curr: 205 },
  { name: '07', prev: 210, curr: 230 },
  { name: '08', prev: 195, curr: 200 },
  { name: '09', prev: 215, curr: 220 },
  { name: '10', prev: 190, curr: 205 },
  { name: '11', prev: 200, curr: 240 },
  { name: '12', prev: 185, curr: 220 },
];

const COLORS = ['#eab308', '#60a5fa', '#003e92', '#f97316', '#10b981', '#cbd5e1', '#ef4444', '#8b5cf6'];
const PIE_COLORS = ['#3b82f6', '#f59e0b', '#ef4444', '#10b981', '#8b5cf6'];

export default function DashboardPage() {
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState({ total: 124, processed: 98, pending: 26 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    try {
      const docsRes = await documentsApi.list({ limit: 12 });
      setDocuments(docsRes.data);
      const analyticsRes = await analyticsApi.getSummary();
      const data = analyticsRes.data;
      setStats({
        total: data.total || 124,
        processed: data.processed || 98,
        pending: data.pending || 26,
      });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const dashboardStyles = {
    layout: { display: 'flex', flexDirection: 'column', gap: '1.25rem' },
    headerRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
    title: { fontSize: '1.5rem', fontWeight: 800, color: 'var(--color-primary)', fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: '0.5rem' },
    filters: { display: 'flex', gap: '1rem', alignItems: 'center', fontSize: '0.875rem' },
    select: { padding: '4px 12px', borderRadius: '4px', border: '1px solid #ccc', fontSize: '0.875rem', background: '#fff' },
    radioGroup: { display: 'flex', gap: '1.5rem', alignItems: 'center', fontSize: '0.875rem', padding: '0.5rem 0' },
    threeCols: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.25rem' },
    
    kpiCard: { padding: '1.25rem', borderRadius: '8px', color: '#fff', boxShadow: 'var(--shadow-md)', position: 'relative', overflow: 'hidden' },
    kpiTitle: { fontSize: '0.9rem', fontWeight: 600, opacity: 0.9, marginBottom: '0.75rem' },
    kpiValue: { fontSize: '2.5rem', fontWeight: 700, margin: '0.5rem 0' },
    kpiRow: { display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', opacity: 0.9, marginTop: '4px' },
    
    chartCard: { background: '#fff', borderRadius: '8px', padding: '1rem', boxShadow: '0 2px 8px rgba(0,0,0,0.06)', border: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column' },
    chartTitle: { fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px' },
    titleIcon: { width: '4px', height: '14px', background: 'var(--color-primary)', borderRadius: '2px' },
    
    tableContainer: { overflowX: 'auto', flex: 1 },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem', textAlign: 'center' },
    th: { background: '#f8fafc', padding: '6px 8px', borderBottom: '1px solid #e2e8f0', color: '#64748b', fontWeight: 600 },
    td: { padding: '6px 8px', borderBottom: '1px solid #f1f5f9', color: '#334155' }
  };

  const getKPIStyle = (type) => {
    if (type === 'blue') return { background: 'linear-gradient(135deg, #1d4ed8 0%, #1e3a8a 100%)' };
    if (type === 'orange') return { background: 'linear-gradient(135deg, #f97316 0%, #c2410c 100%)' };
    if (type === 'yellow') return { background: 'linear-gradient(135deg, #eab308 0%, #a16207 100%)' };
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{ background: '#fff', border: '1px solid #ccc', padding: '8px', borderRadius: '4px', fontSize: '12px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
          <p style={{ margin: 0, fontWeight: 600, marginBottom: '4px' }}>{label}</p>
          {payload.map((p, i) => (
            <div key={i} style={{ color: p.color, margin: 0 }}>
              {p.name}: {p.value}
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="fade-in" style={{ background: '#f8f9fa', minHeight: '100%', padding: '0 0.5rem' }}>
      
      {/* Header */}
      <div style={dashboardStyles.headerRow}>
        <div style={dashboardStyles.title}>
          Аналитика закупочной деятельности (Dashboard)
        </div>
        <div style={dashboardStyles.filters}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>Выбор даты:</span>
            <select style={dashboardStyles.select} defaultValue="2024">
              <option value="2023">2023</option>
              <option value="2024">2024</option>
            </select>
            <select style={dashboardStyles.select} defaultValue="03">
              <option value="01">Январь</option>
              <option value="02">Февраль</option>
              <option value="03">Март</option>
            </select>
          </label>
        </div>
      </div>

      {/* Regions / Tabs */}
      <div style={dashboardStyles.radioGroup}>
        {['Полный контур', 'ЦФО', 'СЗФО', 'УФО', 'СФО', 'ДФО'].map((r, i) => (
          <label key={r} style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', color: i === 0 ? 'var(--color-primary)' : '#64748b', fontWeight: i===0 ? 600 : 400 }}>
            <input type="radio" name="region" defaultChecked={i === 0} style={{ accentColor: 'var(--color-primary)' }} />
            {r}
          </label>
        ))}
      </div>

      <div style={dashboardStyles.layout}>
        {/* ROW 1: KPI Cards */}
        <div style={dashboardStyles.threeCols}>
          <div style={{...dashboardStyles.kpiCard, ...getKPIStyle('blue')}}>
            <div style={dashboardStyles.kpiTitle}>Выполнение плана обработки</div>
            <div style={dashboardStyles.kpiValue}>
              {Math.round((stats.processed / (stats.total || 1)) * 100)}%
            </div>
            <div style={dashboardStyles.kpiRow}>
              <span>Целевой показатель: {stats.total}</span>
            </div>
            <div style={dashboardStyles.kpiRow}>
              <span>Фактически обработано: {stats.processed}</span>
            </div>
          </div>
          <div style={{...dashboardStyles.kpiCard, ...getKPIStyle('orange')}}>
            <div style={dashboardStyles.kpiTitle}>Аналитика: Новые поставщики</div>
            <div style={dashboardStyles.kpiValue}>39.32%</div>
            <div style={dashboardStyles.kpiRow}>
              <span>Целевой охват: 1063</span>
            </div>
            <div style={dashboardStyles.kpiRow}>
              <span>Фактический охват: 418</span>
            </div>
          </div>
          <div style={{...dashboardStyles.kpiCard, ...getKPIStyle('yellow')}}>
            <div style={dashboardStyles.kpiTitle}>Аналитика: Действующие поставщики</div>
            <div style={dashboardStyles.kpiValue}>29.30%</div>
            <div style={dashboardStyles.kpiRow}>
              <span>Целевой охват: 372</span>
            </div>
            <div style={dashboardStyles.kpiRow}>
              <span>Фактический охват: 109</span>
            </div>
          </div>
        </div>

        {/* ROW 2: Mixed Charts */}
        <div style={dashboardStyles.threeCols}>
          <div style={dashboardStyles.chartCard}>
            <div style={dashboardStyles.chartTitle}><div style={dashboardStyles.titleIcon} /> Динамика загрузки документов (Тренд)</div>
            <div style={{ height: 220 }}>
              <ResponsiveContainer>
                <BarChart data={volumeTrendData} margin={{ top: 10, right: 0, left: -25, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <RechartsTooltip content={<CustomTooltip />} />
                  <Bar dataKey="prev" name="2023" fill="#60a5fa" barSize={12} radius={[2,2,0,0]} />
                  <Bar dataKey="curr" name="2024" fill="#3b82f6" barSize={12} radius={[2,2,0,0]} />
                  <LineChart data={volumeTrendData}>
                     <Line type="monotone" dataKey="curr" stroke="#1d4ed8" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                  </LineChart>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div style={dashboardStyles.chartCard}>
            <div style={dashboardStyles.chartTitle}><div style={dashboardStyles.titleIcon} /> Активность взаимодействия с контрагентами</div>
            <div style={{ height: 220 }}>
              <ResponsiveContainer>
                <AreaChart data={activityTrendData} margin={{ top: 10, right: 0, left: -25, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorNew" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorEx" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <RechartsTooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="existing" stroke="#3b82f6" fill="url(#colorNew)" strokeWidth={2} />
                  <Area type="monotone" dataKey="new" stroke="#f59e0b" fill="url(#colorEx)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', fontSize: '10px', marginTop: '4px' }}>
               <span style={{ color: '#3b82f6', fontWeight: 600 }}>— Действующие клиенты</span>
               <span style={{ color: '#f59e0b', fontWeight: 600 }}>— Новые клиенты</span>
            </div>
          </div>

          <div style={dashboardStyles.chartCard}>
            <div style={dashboardStyles.chartTitle}><div style={dashboardStyles.titleIcon} /> Структура категорий закупок</div>
            <div style={{ height: 240, position: 'relative' }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={[
                      { name: 'Услуги', value: 58269 },
                      { name: 'Оборудование', value: 30630 },
                      { name: 'Материалы', value: 22594 },
                      { name: 'Транспорт', value: 22078 },
                      { name: 'Прочее', value: 9462 },
                    ]} 
                    cx="50%" cy="50%" innerRadius={50} outerRadius={80} 
                    paddingAngle={2} dataKey="value"
                    labelLine={true}
                    label={({ name, value }) => `${name}\n${value}`}
                    stroke="none"
                  >
                    {PIE_COLORS.map((color, i) => <Cell key={i} fill={color} />)}
                  </Pie>
                  <RechartsTooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* ROW 3: More Charts & Tables */}
        <div style={dashboardStyles.threeCols}>
          <div style={dashboardStyles.chartCard}>
            <div style={dashboardStyles.chartTitle}><div style={dashboardStyles.titleIcon} /> Топ-10 закупаемых позиций</div>
            <div style={{ height: 280 }}>
              <ResponsiveContainer>
                <BarChart layout="vertical" data={topItemsData} margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} />
                  <XAxis type="number" hide />
                  <YAxis dataKey="name" type="category" tick={{ fontSize: 10, fill: '#475569' }} axisLine={false} tickLine={false} width={110} />
                  <RechartsTooltip content={<CustomTooltip />} cursor={{fill: 'transparent'}} />
                  <Bar dataKey="value" fill="#60a5fa" radius={[0, 4, 4, 0]} barSize={12} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div style={dashboardStyles.chartCard}>
            <div style={dashboardStyles.chartTitle}><div style={dashboardStyles.titleIcon} /> Распределение по ДО (Регионам)</div>
            <div style={{ height: 260 }}>
              <ResponsiveContainer>
                <BarChart data={regionStatusData} margin={{ top: 20, right: 0, left: -25, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <RechartsTooltip content={<CustomTooltip />} cursor={{fill: 'transparent'}} />
                  <Bar dataKey="Действующие" stackId="a" fill="#3b82f6" barSize={20} />
                  <Bar dataKey="Новые" stackId="a" fill="#facc15" barSize={20} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', fontSize: '10px', marginTop: '4px' }}>
               <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{ width: 8, height: 8, background: '#3b82f6' }}/> Действующие контрагенты</span>
               <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{ width: 8, height: 8, background: '#facc15' }}/> Новые контрагенты</span>
            </div>
          </div>

          <div style={dashboardStyles.chartCard}>
            <div style={dashboardStyles.chartTitle}><div style={dashboardStyles.titleIcon} /> Последние обработанные документы</div>
            <div style={dashboardStyles.tableContainer}>
              <table style={dashboardStyles.table}>
                <thead>
                  <tr>
                    <th style={dashboardStyles.th}>Файл</th>
                    <th style={dashboardStyles.th}>Тип</th>
                    <th style={dashboardStyles.th}>Инициатор</th>
                    <th style={dashboardStyles.th}>Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.slice(0, 8).map((doc, idx) => (
                    <tr key={doc.id || idx}>
                      <td style={{ ...dashboardStyles.td, textAlign: 'left', maxWidth: '100px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={doc.original_filename}>
                        {doc.original_filename}
                      </td>
                      <td style={dashboardStyles.td}>{doc.file_type}</td>
                      <td style={dashboardStyles.td}>user_{doc.created_by?.split('-')[0] || 'admin'}</td>
                      <td style={dashboardStyles.td}>
                        {doc.status === 'processed' ? '100%' : 'В раб.'}
                      </td>
                    </tr>
                  ))}
                  {/* Fill empty rows if needed */}
                  {Array.from({ length: Math.max(0, 8 - documents.length) }).map((_, i) => (
                    <tr key={`empty-${i}`}>
                      <td style={dashboardStyles.td}>-</td>
                      <td style={dashboardStyles.td}>-</td>
                      <td style={dashboardStyles.td}>-</td>
                      <td style={dashboardStyles.td}>-</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
