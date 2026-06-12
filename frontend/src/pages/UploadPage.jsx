import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { documentsApi } from '../services/api';
import { Upload, FileText, X, CheckCircle, AlertCircle } from 'lucide-react';
import toast from 'react-hot-toast';

const FILE_TYPES = [
  { value: 'positions', label: 'Позиции (прайс-лист)' },
  { value: 'upd', label: 'УПД' },
  { value: 'act', label: 'Акт оказания услуг' },
  { value: 'template', label: 'Шаблон для заполнения' },
  { value: 'payment_registry', label: 'Реестр платежей' },
  { value: 'contract_registry', label: 'Реестр договоров' },
];

// Эвристика типа по имени файла — чтобы не выставлять каждый селект вручную.
// Порядок важен: более специфичные шаблоны проверяются раньше.
const TYPE_PATTERNS = [
  { re: /(реестр[\s_-]*платеж|payment)/i, type: 'payment_registry' },
  { re: /(реестр[\s_-]*договор|contract)/i, type: 'contract_registry' },
  { re: /(шаблон|template)/i, type: 'template' },
  { re: /(упд|upd|счет[\s_-]*фактур)/i, type: 'upd' },
  { re: /(^|[\s_-])(акт|act)([\s_-]|\.|$)/i, type: 'act' },
  { re: /(позици|прайс|price)/i, type: 'positions' },
];

const detectFileType = (filename) => {
  for (const { re, type } of TYPE_PATTERNS) {
    if (re.test(filename)) return type;
  }
  return 'positions';
};

const fileWord = (n) => {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return 'файл';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'файла';
  return 'файлов';
};

export default function UploadPage() {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);

  const onDrop = useCallback((acceptedFiles) => {
    const newFiles = acceptedFiles.map((file) => ({
      file,
      fileType: detectFileType(file.name),
      status: 'pending',
      id: Math.random().toString(36).slice(2),
    }));
    setFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const onDropRejected = useCallback((rejections) => {
    rejections.forEach(({ file }) => {
      toast.error(`«${file.name}» не подходит: только XLS, XLSX или PDF до 50 МБ`);
    });
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'application/pdf': ['.pdf'],
    },
    maxSize: 50 * 1024 * 1024, // 50MB
  });

  const removeFile = (id) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const updateFileType = (id, fileType) => {
    setFiles((prev) =>
      prev.map((f) => (f.id === id ? { ...f, fileType } : f))
    );
  };

  const uploadAll = async () => {
    if (files.length === 0) {
      toast.error('Добавьте файлы для загрузки');
      return;
    }

    setUploading(true);
    let successCount = 0;
    let errorCount = 0;

    for (const item of files) {
      if (item.status === 'uploaded') continue;

      try {
        setFiles((prev) =>
          prev.map((f) => (f.id === item.id ? { ...f, status: 'uploading' } : f))
        );

        await documentsApi.upload(item.file, item.fileType);

        setFiles((prev) =>
          prev.map((f) => (f.id === item.id ? { ...f, status: 'uploaded' } : f))
        );
        successCount++;
      } catch (err) {
        errorCount++;
        setFiles((prev) =>
          prev.map((f) =>
            f.id === item.id
              ? { ...f, status: 'error', error: err.response?.data?.detail || 'Ошибка загрузки' }
              : f
          )
        );
      }
    }

    setUploading(false);

    if (successCount > 0) {
      toast.success(`Загружено ${successCount} ${fileWord(successCount)}`);
    }
    if (errorCount > 0) {
      toast.error('Часть файлов не загрузилась — причина указана под именем файла');
    }
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
    return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
  };

  const statusIcon = (status) => {
    switch (status) {
      case 'uploaded':
        return <CheckCircle size={16} style={{ color: 'var(--color-accent)' }} />;
      case 'error':
        return <AlertCircle size={16} style={{ color: 'var(--color-danger)' }} />;
      case 'uploading':
        return <div className="spinner" />;
      default:
        return null;
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Загрузка документов</h1>
        <p className="page-subtitle">Загрузите файлы позиций, УПД, актов или шаблонов</p>
      </div>

      <div className="card" style={{ marginBottom: 'var(--spacing-lg)' }}>
        <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`} id="file-dropzone">
          <input {...getInputProps()} />
          <div className="dropzone-icon">
            <Upload size={48} />
          </div>
          <p className="dropzone-text">
            {isDragActive
              ? 'Отпустите файлы для загрузки'
              : 'Перетащите файлы сюда или нажмите для выбора'}
          </p>
          <p className="dropzone-hint">Поддерживаемые форматы: XLS, XLSX, PDF (до 50 МБ)</p>
        </div>
      </div>

      {files.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Файлы ({files.length})</h2>
            <button
              id="upload-all-btn"
              className="btn btn-primary"
              onClick={uploadAll}
              disabled={uploading}
            >
              {uploading ? (
                <>
                  <div className="spinner" /> Загрузка...
                </>
              ) : (
                <>
                  <Upload size={16} /> Загрузить все
                </>
              )}
            </button>
          </div>

          {files.map((item) => (
            <div key={item.id} className="file-item slide-in">
              <div className="file-icon">
                <FileText size={20} />
              </div>
              <div className="file-info">
                <div className="file-name">{item.file.name}</div>
                <div className="file-meta">{formatSize(item.file.size)}</div>
                {item.status === 'error' && item.error && (
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-danger)', marginTop: '2px' }}>
                    {item.error}
                  </div>
                )}
              </div>
              <select
                className="form-select"
                style={{ width: '220px' }}
                value={item.fileType}
                onChange={(e) => updateFileType(item.id, e.target.value)}
                disabled={item.status === 'uploaded'}
              >
                {FILE_TYPES.map((ft) => (
                  <option key={ft.value} value={ft.value}>{ft.label}</option>
                ))}
              </select>
              <div className="file-actions">
                {statusIcon(item.status)}
                {item.status !== 'uploaded' && (
                  <button
                    className="btn btn-icon btn-secondary btn-sm"
                    onClick={() => removeFile(item.id)}
                    title="Удалить"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
