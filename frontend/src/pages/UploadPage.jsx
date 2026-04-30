import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate } from 'react-router-dom';
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

export default function UploadPage() {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const navigate = useNavigate();

  const onDrop = useCallback((acceptedFiles) => {
    const newFiles = acceptedFiles.map((file) => ({
      file,
      fileType: 'positions',
      status: 'pending',
      id: Math.random().toString(36).slice(2),
    }));
    setFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
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
        setFiles((prev) =>
          prev.map((f) =>
            f.id === item.id
              ? { ...f, status: 'error', error: err.response?.data?.detail || 'Ошибка' }
              : f
          )
        );
      }
    }

    setUploading(false);

    if (successCount > 0) {
      toast.success(`Загружено ${successCount} файл(ов)`);
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
