import { useState, useEffect } from 'react';
import { documentsApi } from '../services/api';
import { Play, Download, CheckCircle, AlertTriangle, FileSpreadsheet } from 'lucide-react';
import toast from 'react-hot-toast';

const EMPTY_FORM = {
  template_document_id: '',
  document_number: '',
  document_date: '',
  contract_number: '',
  contract_date: '',
  inn_organization: '',
  inn_contractor: '',
  comments: '',
  scenario: '',
  // LLM-верификация выключена по умолчанию: на CPU каждый спорный матч
  // ждёт таймаут Ollama, обработка растягивается на минуты.
  use_llm: false,
};

const SCENARIOS = [
  { value: '', label: 'Автоопределение' },
  { value: 'leader_smi', label: 'Лидер СМИ' },
  { value: 'veneta', label: 'Венета' },
  { value: 'd_lux', label: 'Д-люкс' },
];

export default function ProcessingPage() {
  const [documents, setDocuments] = useState([]);
  const [positionsId, setPositionsId] = useState('');
  const [updId, setUpdId] = useState('');
  const [form, setForm] = useState(EMPTY_FORM);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const res = await documentsApi.list({ limit: 100 });
      const sorted = [...res.data].sort(
        (a, b) => new Date(b.created_at) - new Date(a.created_at)
      );

      setDocuments(sorted);
      setPositionsId((prev) => prev || sorted.find((doc) => doc.file_type === 'positions')?.id || '');
      setUpdId((prev) => prev || sorted.find((doc) => ['upd', 'act'].includes(doc.file_type))?.id || '');
      setForm((prev) => ({
        ...prev,
        template_document_id:
          prev.template_document_id || sorted.find((doc) => doc.file_type === 'template')?.id || '',
      }));
    } catch {
      toast.error('Не удалось загрузить документы');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleProcess = async () => {
    if (!positionsId || !updId) {
      toast.error('Выберите файл позиций и УПД/Акт');
      return;
    }

    setProcessing(true);
    setResult(null);

    try {
      const payload = {
        positions_document_id: positionsId,
        upd_document_id: updId,
        template_document_id: form.template_document_id || null,
        document_number: form.document_number || null,
        document_date: form.document_date || null,
        contract_number: form.contract_number || null,
        contract_date: form.contract_date || null,
        inn_organization: form.inn_organization || null,
        inn_contractor: form.inn_contractor || null,
        comments: form.comments || null,
        scenario: form.scenario || null,
        use_llm: form.use_llm,
      };

      const res = await documentsApi.process(payload);
      setResult(res.data);
      toast.success(res.data.message);
      loadDocuments();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка обработки');
    } finally {
      setProcessing(false);
    }
  };

  const handleDownloadResult = async () => {
    if (!result?.result_document_id) return;

    try {
      const res = await documentsApi.download(result.result_document_id);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', result.result_document_filename || 'filled_template.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      toast.error('Не удалось скачать результат');
    }
  };

  const positionsFiles = documents.filter((doc) => doc.file_type === 'positions');
  const sourceFiles = documents.filter((doc) => ['upd', 'act'].includes(doc.file_type));
  const templateFiles = documents.filter((doc) => doc.file_type === 'template');
  const reviewCount = result?.matches?.filter((match) => match.needs_review).length || 0;
  const matchedCount = result?.matches?.filter((match) => !match.needs_review).length || 0;

  const confidenceClass = (score) => {
    if (score >= 85) return 'confidence-high';
    if (score >= 50) return 'confidence-medium';
    return 'confidence-low';
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Обработка документов</h1>
        <p className="page-subtitle">
          Сопоставление позиций, заполнение шаблона ЕИС и сохранение версии результата
        </p>
      </div>

      <div className="card" style={{ marginBottom: 'var(--spacing-lg)' }}>
        <div className="card-header">
          <h2 className="card-title">Выбор документов</h2>
          <button
            id="process-btn"
            className="btn btn-primary btn-lg"
            onClick={handleProcess}
            disabled={processing || !positionsId || !updId || loading}
          >
            {processing ? (
              <>
                <div className="spinner" /> Обработка...
              </>
            ) : (
              <>
                <Play size={16} /> Обработать
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
          <>
            <div className="processing-grid">
              <div className="form-group">
                <label className="form-label">Файл позиций</label>
                <select
                  id="select-positions"
                  className="form-select"
                  value={positionsId}
                  onChange={(e) => setPositionsId(e.target.value)}
                >
                  <option value="">— Выберите файл —</option>
                  {positionsFiles.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.original_filename}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">УПД / Акт</label>
                <select
                  id="select-upd"
                  className="form-select"
                  value={updId}
                  onChange={(e) => setUpdId(e.target.value)}
                >
                  <option value="">— Выберите файл —</option>
                  {sourceFiles.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.original_filename}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Шаблон XLS</label>
                <select
                  className="form-select"
                  value={form.template_document_id}
                  onChange={(e) => handleChange('template_document_id', e.target.value)}
                >
                  <option value="">Создать стандартный шаблон</option>
                  {templateFiles.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.original_filename}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="processing-meta-grid">
              <div className="form-group">
                <label className="form-label">Номер документа</label>
                <input
                  className="form-input"
                  value={form.document_number}
                  onChange={(e) => handleChange('document_number', e.target.value)}
                  placeholder="Автоопределение, если оставить пустым"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Дата подписания</label>
                <input
                  className="form-input"
                  value={form.document_date}
                  onChange={(e) => handleChange('document_date', e.target.value)}
                  placeholder="ДД.ММ.ГГГГ"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Номер договора</label>
                <input
                  className="form-input"
                  value={form.contract_number}
                  onChange={(e) => handleChange('contract_number', e.target.value)}
                  placeholder="Необязательно"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Дата договора</label>
                <input
                  className="form-input"
                  value={form.contract_date}
                  onChange={(e) => handleChange('contract_date', e.target.value)}
                  placeholder="ДД.ММ.ГГГГ"
                />
              </div>

              <div className="form-group">
                <label className="form-label">ИНН организации</label>
                <input
                  className="form-input"
                  value={form.inn_organization}
                  onChange={(e) => handleChange('inn_organization', e.target.value)}
                  placeholder="Необязательно"
                />
              </div>

              <div className="form-group">
                <label className="form-label">ИНН контрагента</label>
                <input
                  className="form-input"
                  value={form.inn_contractor}
                  onChange={(e) => handleChange('inn_contractor', e.target.value)}
                  placeholder="Необязательно"
                />
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Комментарий</label>
              <textarea
                className="form-textarea"
                value={form.comments}
                onChange={(e) => handleChange('comments', e.target.value)}
                placeholder="Служебные пометки по обработке"
              />
            </div>

            <div className="form-group" style={{ marginBottom: 0, marginTop: 'var(--spacing-md)' }}>
              <label className="form-label">Сценарий обработки</label>
              <select
                id="select-scenario"
                className="form-select"
                value={form.scenario}
                onChange={(e) => handleChange('scenario', e.target.value)}
              >
                {SCENARIOS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>
                Выберите сценарий обработки или оставьте «Автоопределение» для универсальной логики
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: 0, marginTop: 'var(--spacing-md)' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  id="use-llm-checkbox"
                  type="checkbox"
                  checked={form.use_llm}
                  onChange={(e) => handleChange('use_llm', e.target.checked)}
                />
                <span className="form-label" style={{ marginBottom: 0 }}>
                  LLM-верификация спорных позиций
                </span>
              </label>
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>
                Позиции с уверенностью 50–85% дополнительно проверяются локальной LLM (Mistral 7B).
                На сервере без GPU это добавляет до 20 секунд на каждую спорную позицию.
              </div>
            </div>

            {processing && (
              <div className="loading-overlay" style={{ marginTop: 'var(--spacing-md)' }}>
                <div className="spinner" />
                <span>
                  Идёт обработка: парсинг файлов → сопоставление позиций → генерация XLS.
                  {form.use_llm
                    ? ' Включена LLM-верификация — обработка может занять несколько минут.'
                    : ' Обычно занимает несколько секунд.'}
                </span>
              </div>
            )}

            {(positionsFiles.length === 0 || sourceFiles.length === 0) && (
              <div className="review-note" style={{ marginTop: 'var(--spacing-md)' }}>
                Для обработки нужны файл позиций и УПД/Акт. Загрузите их на странице «Загрузка»,
                указав правильный тип каждого файла.
              </div>
            )}
          </>
        )}
      </div>

      {result && (
        <div className="card fade-in">
          <div className="card-header">
            <div>
              <h2 className="card-title">Результаты сопоставления</h2>
              <p className="page-subtitle" style={{ marginTop: '0.25rem' }}>
                {result.document_number ? `Документ № ${result.document_number}` : 'Номер документа не определён'}
                {result.document_date ? `, дата ${result.document_date}` : ''}
              </p>
            </div>

            <div className="result-toolbar">
              <span className="badge badge-success">
                <CheckCircle size={12} /> Совпало: {matchedCount}
              </span>
              <span className="badge badge-warning">
                <AlertTriangle size={12} /> На проверку: {reviewCount}
              </span>
              <button className="btn btn-secondary" onClick={handleDownloadResult}>
                <Download size={16} /> Скачать XLSX
              </button>
            </div>
          </div>

          {reviewCount > 0 && (
            <div className="review-note">
              Проверьте строки, помеченные жёлтым или красным. Для актов с мойкой сервис
              отдельно подсвечивает цены с коэффициентом 1.5 и цены с копейками.
            </div>
          )}

          <div className="table-container">
            <table className="match-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Наименование</th>
                  <th>№ позиции</th>
                  <th>Совпадение</th>
                  <th>Уверенность</th>
                  <th>Кол-во</th>
                  <th>Ед.</th>
                  <th>Цена</th>
                  <th>Сумма</th>
                </tr>
              </thead>
              <tbody>
                {result.matches.map((match, index) => (
                  <tr key={`${match.upd_row_index}-${index}`}>
                    <td>{index + 1}</td>
                    <td
                      className={
                        match.needs_review
                          ? match.matched_position_number
                            ? 'needs-review'
                            : 'no-match'
                          : ''
                      }
                    >
                      <div>{match.upd_item_name}</div>
                      {match.highlight_reason ? (
                        <div className="match-hint">{match.highlight_reason}</div>
                      ) : null}
                    </td>
                    <td style={{ fontWeight: 600 }}>{match.matched_position_number || '—'}</td>
                    <td>{match.matched_position_name || '—'}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div className="confidence-bar">
                          <div
                            className={`confidence-fill ${confidenceClass(match.confidence)}`}
                            style={{ width: `${match.confidence}%` }}
                          />
                        </div>
                        <span style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
                          {match.confidence.toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td>{match.quantity ?? '—'}</td>
                    <td>{match.unit || '—'}</td>
                    <td>{match.price ? match.price.toLocaleString('ru-RU') : '—'}</td>
                    <td>{match.total ? match.total.toLocaleString('ru-RU') : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {result.result_document_filename ? (
            <div className="generated-file-banner">
              <FileSpreadsheet size={18} />
              <span>{result.result_document_filename}</span>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
