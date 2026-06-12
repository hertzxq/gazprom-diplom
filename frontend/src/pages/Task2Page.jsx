import { useState, useEffect, useMemo } from 'react';
import { documentsApi, task2Api } from '../services/api';
import { Play, Download, Save, ArrowRight, CheckCircle, AlertTriangle } from 'lucide-react';
import toast from 'react-hot-toast';

const EXCLUSION_OPTIONS = ['нет', 'авиа', 'страх', 'образов', 'аренда', 'почта'];
const YESNO_OPTIONS = ['да', 'нет'];

export default function Task2Page() {
  const [documents, setDocuments] = useState([]);
  const [paymentId, setPaymentId] = useState('');
  const [contractId, setContractId] = useState('');

  const [step, setStep] = useState(1); // 1: выбор, 2: правка, 3: итоговый свод
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [saving, setSaving] = useState(false);

  // Фильтры расчёта (Tech_doc.md, Block 1, item 2)
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [minAmount, setMinAmount] = useState('');

  const [task, setTask] = useState(null); // { task_id, document_id, rows, ... }
  const [finalResult, setFinalResult] = useState(null);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const res = await documentsApi.list({ limit: 200 });
      const sorted = [...res.data].sort(
        (a, b) => new Date(b.created_at) - new Date(a.created_at)
      );
      setDocuments(sorted);
      if (!paymentId) {
        setPaymentId(sorted.find((d) => d.file_type === 'payment_registry')?.id || '');
      }
      if (!contractId) {
        setContractId(sorted.find((d) => d.file_type === 'contract_registry')?.id || '');
      }
    } catch {
      toast.error('Не удалось загрузить список документов');
    } finally {
      setLoading(false);
    }
  };

  const paymentFiles = useMemo(
    () => documents.filter((d) => d.file_type === 'payment_registry'),
    [documents]
  );
  const contractFiles = useMemo(
    () => documents.filter((d) => d.file_type === 'contract_registry'),
    [documents]
  );

  const handleBuild = async () => {
    if (!paymentId || !contractId) {
      toast.error('Выберите оба реестра');
      return;
    }
    setBuilding(true);
    setTask(null);
    setFinalResult(null);
    try {
      const minAmountValue = minAmount ? Number(minAmount) : null;
      const res = await task2Api.buildPrimarySumup({
        payment_registry_id: paymentId,
        contract_registry_id: contractId,
        date_from: dateFrom || null,
        date_to: dateTo || null,
        min_amount: Number.isFinite(minAmountValue) ? minAmountValue : null,
      });
      setTask(res.data);
      setStep(2);
      toast.success(res.data.message);
      loadDocuments();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Не удалось построить первичный свод');
    } finally {
      setBuilding(false);
    }
  };

  const handleRowChange = (index, field, value) => {
    setTask((prev) => {
      const rows = prev.rows.map((r, i) => (i === index ? { ...r, [field]: value } : r));
      return { ...prev, rows };
    });
  };

  const handleSave = async () => {
    if (!task) return;
    setSaving(true);
    try {
      const res = await task2Api.updatePrimarySumup(task.task_id, { rows: task.rows });
      setTask(res.data);
      toast.success('Первичный свод обновлён');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const handleDownloadPrimary = async () => {
    if (!task?.document_id) return;
    try {
      const res = await documentsApi.download(task.document_id);
      downloadBlob(res.data, 'Первичный свод.xlsx');
    } catch {
      toast.error('Не удалось скачать файл');
    }
  };

  const handleDownloadFinal = async () => {
    if (!finalResult?.document_id) return;
    try {
      const res = await documentsApi.download(finalResult.document_id);
      downloadBlob(res.data, 'Второй свод_обобщение.xlsx');
    } catch {
      toast.error('Не удалось скачать файл');
    }
  };

  const handleBuildFinal = async () => {
    if (!task?.document_id) return;
    setBuilding(true);
    try {
      // Сначала фиксируем текущее состояние таблицы: бэкенд строит итоговый
      // свод из сохранённых данных задачи, и без этого правки селектов
      // (исключения, «длящийся», публикация) молча игнорировались бы.
      await task2Api.updatePrimarySumup(task.task_id, { rows: task.rows });
      const res = await task2Api.buildFinalSummary({ primary_sumup_id: task.document_id });
      setFinalResult(res.data);
      setStep(3);
      toast.success(res.data.message);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Не удалось построить итоговый свод');
    } finally {
      setBuilding(false);
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Свод СМСП (Задача 2)</h1>
        <p className="page-subtitle">
          Реестр платежей + реестр договоров → первичный свод → 3-вкладочный итоговый свод
        </p>
      </div>

      <Stepper step={step} />

      {/* key={step} перезапускает blur-fade при смене шага — плавный переход мастера */}
      <div key={step} className="fade-in">
      {step === 1 && (
        <StepOne
          loading={loading}
          paymentFiles={paymentFiles}
          contractFiles={contractFiles}
          paymentId={paymentId}
          setPaymentId={setPaymentId}
          contractId={contractId}
          setContractId={setContractId}
          dateFrom={dateFrom}
          setDateFrom={setDateFrom}
          dateTo={dateTo}
          setDateTo={setDateTo}
          minAmount={minAmount}
          setMinAmount={setMinAmount}
          building={building}
          onBuild={handleBuild}
        />
      )}

      {step === 2 && task && (
        <StepTwo
          task={task}
          onRowChange={handleRowChange}
          saving={saving}
          building={building}
          onSave={handleSave}
          onDownload={handleDownloadPrimary}
          onBack={() => setStep(1)}
          onNext={handleBuildFinal}
        />
      )}

      {step === 3 && finalResult && (
        <StepThree
          result={finalResult}
          onDownload={handleDownloadFinal}
          onBack={() => setStep(2)}
        />
      )}
      </div>
    </div>
  );
}

function Stepper({ step }) {
  const labels = ['Загрузка и выбор', 'Первичный свод', 'Итоговый свод'];
  return (
    <div className="t2-stepper">
      {labels.map((label, i) => {
        const n = i + 1;
        const active = step === n;
        const done = step > n;
        return (
          <div key={label} className={`t2-step ${active ? 'active' : ''} ${done ? 'done' : ''}`}>
            <span className="t2-step-num">
              {done ? <CheckCircle size={13} /> : n}
            </span>
            {label}
          </div>
        );
      })}
    </div>
  );
}

function StepOne({
  loading,
  paymentFiles,
  contractFiles,
  paymentId,
  setPaymentId,
  contractId,
  setContractId,
  dateFrom,
  setDateFrom,
  dateTo,
  setDateTo,
  minAmount,
  setMinAmount,
  building,
  onBuild,
}) {
  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title">Шаг 1. Выбор реестров</h2>
        <button
          className="btn btn-primary btn-lg"
          onClick={onBuild}
          disabled={building || !paymentId || !contractId || loading}
        >
          {building ? (
            <>
              <div className="spinner" /> Строим свод...
            </>
          ) : (
            <>
              <Play size={16} /> Построить первичный свод
            </>
          )}
        </button>
      </div>
      {loading ? (
        <div className="loading-overlay">
          <div className="spinner" />
          <span>Загрузка документов...</span>
        </div>
      ) : (
        <div className="processing-grid">
          <div className="form-group">
            <label className="form-label">Реестр платежей</label>
            <select
              className="form-select"
              value={paymentId}
              onChange={(e) => setPaymentId(e.target.value)}
            >
              <option value="">— Выберите файл —</option>
              {paymentFiles.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.original_filename}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Реестр договоров</label>
            <select
              className="form-select"
              value={contractId}
              onChange={(e) => setContractId(e.target.value)}
            >
              <option value="">— Выберите файл —</option>
              {contractFiles.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.original_filename}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Период с</label>
            <input
              type="date"
              className="form-input"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Период по</label>
            <input
              type="date"
              className="form-input"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Мин. сумма платежа, ₽</label>
            <input
              type="number"
              min="0"
              step="0.01"
              className="form-input"
              value={minAmount}
              onChange={(e) => setMinAmount(e.target.value)}
              placeholder="без порога"
            />
          </div>
        </div>
      )}
      {!loading && (paymentFiles.length === 0 || contractFiles.length === 0) && (
        <div
          style={{
            marginTop: 'var(--spacing-md)',
            padding: '0.75rem 1rem',
            background: '#fff7ed',
            border: '1px solid #fed7aa',
            borderRadius: 'var(--radius-md)',
            color: '#9a3412',
            fontSize: '0.875rem',
            display: 'flex',
            gap: '0.5rem',
            alignItems: 'center',
          }}
        >
          <AlertTriangle size={16} /> Сначала загрузите реестры на странице «Загрузка» —
          отдельно реестр платежей и реестр договоров.
        </div>
      )}
    </div>
  );
}

function StepTwo({ task, onRowChange, saving, building, onSave, onDownload, onBack, onNext }) {
  const unmatched = task.rows_unmatched || 0;
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2 className="card-title">Шаг 2. Первичный свод</h2>
          <p style={{ marginTop: '0.375rem', fontSize: '0.875rem', color: 'var(--color-text-secondary)', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            Строк: {task.rows_total}
            {unmatched > 0 && (
              <span className="badge badge-warning">
                <AlertTriangle size={11} /> без сопоставления: {unmatched}
              </span>
            )}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={onBack}>
            Назад
          </button>
          <button className="btn btn-secondary" onClick={onDownload}>
            <Download size={14} /> Скачать XLSX
          </button>
          <button className="btn btn-secondary" onClick={onSave} disabled={saving}>
            {saving ? <div className="spinner" /> : <Save size={14} />} Сохранить правки
          </button>
          <button className="btn btn-primary" onClick={onNext} disabled={building}>
            {building ? <div className="spinner" /> : <ArrowRight size={14} />} К итоговому своду
          </button>
        </div>
      </div>

      <div className="t2-scroll">
        <table className="task2-table">
          <thead>
            <tr>
              <th className="t2-stick t2-stick-1">Дата</th>
              <th className="t2-stick t2-stick-2">Контрагент</th>
              <th>Договор</th>
              <th style={{ textAlign: 'right' }}>Сумма дог.</th>
              <th style={{ textAlign: 'right' }}>Σ платежей</th>
              <th>СМСП</th>
              <th>Способ</th>
              <th>Действие, с–по</th>
              <th className="t2-edit t2-edit-first">Исключение</th>
              <th className="t2-edit">Длящ.</th>
              <th className="t2-edit">Публ. ЕИС</th>
            </tr>
          </thead>
          <tbody>
            {task.rows.map((row, i) => {
              const matched = row.has_contract_match;
              const rowBg = matched ? '#ffffff' : '#fffaf2';
              return (
                <tr key={i} style={{ background: rowBg }}>
                  <td
                    className="t2-stick t2-stick-1"
                    style={{
                      background: rowBg,
                      ...(matched ? {} : { borderLeft: '3px solid var(--color-warning)' }),
                    }}
                  >
                    {fmtDate(row.date)}
                  </td>
                  <td
                    className="t2-stick t2-stick-2"
                    style={{ background: rowBg }}
                    title={row.contragent}
                  >
                    <div className="t2-contragent">{row.contragent}</div>
                  </td>
                  <td>
                    <div className="t2-main">{row.contract_number || '—'}</div>
                    <div className="t2-sub">{fmtDate(row.contract_date)}</div>
                  </td>
                  <td style={{ textAlign: 'right' }}>{fmtMoney(row.contract_sum)}</td>
                  <td style={{ textAlign: 'right', fontWeight: 600 }}>{fmtMoney(row.payment_sum)}</td>
                  <td>
                    <div className="t2-main">{row.smsp_type}</div>
                    <div className="t2-sub">закупка: {row.smsp_purchase}</div>
                  </td>
                  <td>{row.purchase_method}</td>
                  <td>
                    <div className="t2-main">{fmtDate(row.action_from) || '—'}</div>
                    <div className="t2-sub">
                      {fmtDate(row.action_to) ? `– ${fmtDate(row.action_to)}` : ''}
                    </div>
                  </td>
                  <td className="t2-edit t2-edit-first">
                    <select
                      className="form-select"
                      value={row.exclusion_category}
                      onChange={(e) => onRowChange(i, 'exclusion_category', e.target.value)}
                    >
                      {EXCLUSION_OPTIONS.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="t2-edit">
                    <select
                      className="form-select"
                      value={row.is_continuing}
                      onChange={(e) => onRowChange(i, 'is_continuing', e.target.value)}
                    >
                      {YESNO_OPTIONS.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="t2-edit">
                    <select
                      className="form-select"
                      value={row.publication}
                      onChange={(e) => onRowChange(i, 'publication', e.target.value)}
                    >
                      {YESNO_OPTIONS.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StepThree({ result, onDownload, onBack }) {
  const sheets = Object.entries(result.sheets || {});
  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title">Шаг 3. Итоговый свод СМСП</h2>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={onBack}>
            Назад
          </button>
          <button className="btn btn-primary btn-lg" onClick={onDownload}>
            <Download size={16} /> Скачать XLSX (3 вкладки)
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 'var(--spacing-lg)' }}>
        {sheets.map(([name, metrics]) => (
          <div key={name}>
            <h3 style={{ marginBottom: '0.5rem' }}>{name}</h3>
            <div className="table-container">
              <table style={{ width: '100%', fontSize: '0.875rem' }}>
                <thead>
                  <tr>
                    <th>Показатель</th>
                    <th style={{ textAlign: 'right' }}>Сумма, ₽</th>
                    <th style={{ textAlign: 'right' }}>Кол-во договоров</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.map((m, i) => (
                    <tr key={i}>
                      <td>{m.label}</td>
                      <td style={{ textAlign: 'right' }}>{fmtMoney(m.total_sum)}</td>
                      <td style={{ textAlign: 'right' }}>{m.count == null ? '—' : m.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function fmtDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return `${d}.${m}.${y}`;
}

function fmtMoney(v) {
  if (v === null || v === undefined || v === '') return '';
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return n.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(new Blob([blob]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
