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
      const res = await task2Api.buildPrimarySumup({
        payment_registry_id: paymentId,
        contract_registry_id: contractId,
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

      {step === 1 && (
        <StepOne
          loading={loading}
          paymentFiles={paymentFiles}
          contractFiles={contractFiles}
          paymentId={paymentId}
          setPaymentId={setPaymentId}
          contractId={contractId}
          setContractId={setContractId}
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
  );
}

function Stepper({ step }) {
  const labels = ['Загрузка и выбор', 'Первичный свод', 'Итоговый свод'];
  return (
    <div style={{ display: 'flex', gap: '0.5rem', marginBottom: 'var(--spacing-lg)' }}>
      {labels.map((label, i) => {
        const n = i + 1;
        const active = step === n;
        const done = step > n;
        return (
          <div
            key={label}
            style={{
              flex: 1,
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-md)',
              background: active
                ? 'var(--color-primary-dim)'
                : done
                ? '#e8f4ea'
                : 'var(--color-bg-secondary)',
              border: `1px solid ${active ? 'var(--color-primary)' : 'var(--color-border)'}`,
              fontWeight: active ? 700 : 500,
              color: active ? 'var(--color-primary)' : 'var(--color-text-secondary)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <span
              style={{
                width: 24,
                height: 24,
                borderRadius: '50%',
                background: active || done ? 'var(--color-primary)' : 'var(--color-bg-primary)',
                color: active || done ? '#fff' : 'var(--color-text-muted)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.75rem',
              }}
            >
              {done ? <CheckCircle size={14} /> : n}
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
          <p className="page-subtitle" style={{ marginTop: '0.25rem' }}>
            Строк: {task.rows_total} · Без сопоставления с реестром договоров: {unmatched}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={onBack}>
            Назад
          </button>
          <button className="btn btn-secondary" onClick={onDownload}>
            <Download size={14} /> Скачать xlsx
          </button>
          <button className="btn btn-secondary" onClick={onSave} disabled={saving}>
            {saving ? <div className="spinner" /> : <Save size={14} />} Сохранить правки
          </button>
          <button className="btn btn-primary" onClick={onNext} disabled={building}>
            {building ? <div className="spinner" /> : <ArrowRight size={14} />} К итоговому своду
          </button>
        </div>
      </div>

      <div style={{ overflow: 'auto', maxHeight: '65vh', border: '1px solid var(--color-border)' }}>
        <table className="task2-table" style={{ minWidth: 1400, width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
          <thead>
            <tr>
              <th>Дата</th>
              <th>Контрагент</th>
              <th>№ договора</th>
              <th>Дата дог.</th>
              <th>Сумма дог.</th>
              <th>Σ платежей</th>
              <th>Вид СМСП</th>
              <th>Закупка для СМСП</th>
              <th>Способ</th>
              <th>Исключение</th>
              <th>K — с</th>
              <th>L — по</th>
              <th>Длящ.</th>
              <th>Публ. ЕИС</th>
            </tr>
          </thead>
          <tbody>
            {task.rows.map((row, i) => (
              <tr
                key={i}
                style={{
                  background: row.has_contract_match
                    ? 'transparent'
                    : 'rgba(255, 165, 0, 0.05)',
                }}
              >
                <td>{fmtDate(row.date)}</td>
                <td style={{ maxWidth: 260, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={row.contragent}>
                  {row.contragent}
                </td>
                <td>{row.contract_number}</td>
                <td>{fmtDate(row.contract_date)}</td>
                <td style={{ textAlign: 'right' }}>{fmtMoney(row.contract_sum)}</td>
                <td style={{ textAlign: 'right', fontWeight: 600 }}>{fmtMoney(row.payment_sum)}</td>
                <td>{row.smsp_type}</td>
                <td>{row.smsp_purchase}</td>
                <td>{row.purchase_method}</td>
                <td>
                  <select
                    className="form-select"
                    style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
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
                <td>{fmtDate(row.action_from)}</td>
                <td>{fmtDate(row.action_to)}</td>
                <td>
                  <select
                    className="form-select"
                    style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
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
                <td>
                  <select
                    className="form-select"
                    style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
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
            ))}
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
            <Download size={16} /> Скачать xlsx (3 вкладки)
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 'var(--spacing-lg)' }}>
        {sheets.map(([name, metrics]) => (
          <div key={name}>
            <h3 style={{ marginBottom: '0.5rem' }}>{name}</h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
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
