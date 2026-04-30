import { useState } from 'react';
import { manufacturersApi } from '../services/api';
import toast from 'react-hot-toast';
import {
  Search,
  Plus,
  Trash2,
  Factory,
  FileText,
  Loader,
  ExternalLink,
  Award,
  Phone,
  Globe,
  Download,
} from 'lucide-react';

const TABS = [
  { id: 'specs', label: 'По характеристикам', icon: Search },
  { id: 'name', label: 'По наименованию', icon: FileText },
];

const handleExport = async (results, productName) => {
  if (!results || results.length === 0) {
    toast.error('Нет данных для экспорта');
    return;
  }
  try {
    const res = await manufacturersApi.export({
      results,
      product_name: productName,
    });
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `Производители_${(productName || 'results').replace(/\s/g, '_')}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    toast.success('Файл экспортирован');
  } catch (err) {
    toast.error('Ошибка экспорта');
  }
};

export default function ManufacturerSearchPage() {
  const [activeTab, setActiveTab] = useState('specs');

  // ─── Search by specs ───
  const [specsForm, setSpecsForm] = useState({
    product_name: '',
    characteristics: [{ key: '', value: '' }],
    sources: '',
  });
  const [specsResults, setSpecsResults] = useState(null);
  const [specsLoading, setSpecsLoading] = useState(false);

  // ─── Search by name ───
  const [nameForm, setNameForm] = useState({
    product_name: '',
    sources: '',
  });
  const [nameResults, setNameResults] = useState(null);
  const [nameLoading, setNameLoading] = useState(false);

  // ─── Specs helpers ───
  const addCharacteristic = () => {
    setSpecsForm((prev) => ({
      ...prev,
      characteristics: [...prev.characteristics, { key: '', value: '' }],
    }));
  };

  const removeCharacteristic = (index) => {
    setSpecsForm((prev) => ({
      ...prev,
      characteristics: prev.characteristics.filter((_, i) => i !== index),
    }));
  };

  const updateCharacteristic = (index, field, value) => {
    setSpecsForm((prev) => ({
      ...prev,
      characteristics: prev.characteristics.map((c, i) =>
        i === index ? { ...c, [field]: value } : c
      ),
    }));
  };

  // ─── Search handlers ───
  const handleSearchBySpecs = async () => {
    if (!specsForm.product_name.trim()) {
      toast.error('Укажите наименование товара');
      return;
    }

    const validChars = specsForm.characteristics.filter(
      (c) => c.key.trim() && c.value.trim()
    );

    setSpecsLoading(true);
    setSpecsResults(null);

    try {
      const payload = {
        product_name: specsForm.product_name,
        characteristics: validChars,
        sources: specsForm.sources
          ? specsForm.sources.split(',').map((s) => s.trim()).filter(Boolean)
          : null,
      };
      const res = await manufacturersApi.searchBySpecs(payload);
      setSpecsResults(res.data);
      toast.success(res.data.message);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка поиска');
    } finally {
      setSpecsLoading(false);
    }
  };

  const handleSearchByName = async () => {
    if (!nameForm.product_name.trim()) {
      toast.error('Укажите наименование товара');
      return;
    }

    setNameLoading(true);
    setNameResults(null);

    try {
      const payload = {
        product_name: nameForm.product_name,
        sources: nameForm.sources
          ? nameForm.sources.split(',').map((s) => s.trim()).filter(Boolean)
          : null,
      };
      const res = await manufacturersApi.searchByName(payload);
      setNameResults(res.data);
      toast.success(res.data.message);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка поиска');
    } finally {
      setNameLoading(false);
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Поиск производителей</h1>
        <p className="page-subtitle">
          Поиск производителей товаров и документации в открытых источниках
        </p>
      </div>

      {/* Tabs */}
      <div className="search-tabs" style={{ marginBottom: 'var(--spacing-xl)' }}>
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              className={`search-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ─── Tab: Search by specs ─── */}
      {activeTab === 'specs' && (
        <>
          <div className="card" style={{ marginBottom: 'var(--spacing-lg)' }}>
            <div className="card-header">
              <h2 className="card-title">Поиск по характеристикам</h2>
              <button
                id="search-specs-btn"
                className="btn btn-primary btn-lg"
                onClick={handleSearchBySpecs}
                disabled={specsLoading}
              >
                {specsLoading ? (
                  <>
                    <div className="spinner" /> Поиск...
                  </>
                ) : (
                  <>
                    <Search size={16} /> Найти производителей
                  </>
                )}
              </button>
            </div>

            <div className="form-group">
              <label className="form-label">Наименование товара</label>
              <input
                id="specs-product-name"
                className="form-input"
                value={specsForm.product_name}
                onChange={(e) =>
                  setSpecsForm((prev) => ({ ...prev, product_name: e.target.value }))
                }
                placeholder="Например: Труба стальная бесшовная"
              />
            </div>

            <div className="form-group">
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 'var(--spacing-sm)',
                }}
              >
                <label className="form-label" style={{ marginBottom: 0 }}>
                  Характеристики
                </label>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={addCharacteristic}
                >
                  <Plus size={14} /> Добавить
                </button>
              </div>

              {specsForm.characteristics.map((char, index) => (
                <div className="char-row" key={index}>
                  <input
                    className="form-input"
                    placeholder="Параметр (например: материал)"
                    value={char.key}
                    onChange={(e) =>
                      updateCharacteristic(index, 'key', e.target.value)
                    }
                  />
                  <input
                    className="form-input"
                    placeholder="Значение (например: сталь 20)"
                    value={char.value}
                    onChange={(e) =>
                      updateCharacteristic(index, 'value', e.target.value)
                    }
                  />
                  {specsForm.characteristics.length > 1 && (
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => removeCharacteristic(index)}
                      style={{ flexShrink: 0 }}
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              ))}
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">
                Источники{' '}
                <span style={{ fontWeight: 400, color: 'var(--color-text-muted)' }}>
                  (необязательно, через запятую)
                </span>
              </label>
              <input
                className="form-input"
                value={specsForm.sources}
                onChange={(e) =>
                  setSpecsForm((prev) => ({ ...prev, sources: e.target.value }))
                }
                placeholder="Реестр РФ, сайт производителя, каталог ЕАЭС..."
              />
            </div>
          </div>

          {/* Specs Results */}
          {specsResults && (
            <div className="card fade-in">
              <div className="card-header">
                <h2 className="card-title">
                  <Factory size={20} style={{ marginRight: '0.5rem', verticalAlign: 'text-bottom' }} />
                  Результаты поиска
                </h2>
                <span className="badge badge-info">
                  {specsResults.results.length} производителей
                </span>
                {specsResults.results.length > 0 && (
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleExport(specsResults.results, specsForm.product_name)}
                    style={{ marginLeft: '0.5rem' }}
                  >
                    <Download size={14} /> Экспорт XLSX
                  </button>
                )}
              </div>

              {specsResults.results.length === 0 ? (
                <div className="search-empty">
                  Производители не найдены. Попробуйте изменить параметры поиска.
                </div>
              ) : (
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Производитель</th>
                        <th>Страна</th>
                        <th>Продукция</th>
                        <th>Сертификаты</th>
                        <th>Контакты</th>
                        <th>Сайт</th>
                        <th>Источник</th>
                      </tr>
                    </thead>
                    <tbody>
                      {specsResults.results.map((r, i) => (
                        <tr key={i}>
                          <td>{i + 1}</td>
                          <td style={{ fontWeight: 600 }}>{r.name}</td>
                          <td>{r.country || '—'}</td>
                          <td>{r.products || '—'}</td>
                          <td>
                            {r.certificates ? (
                              <span className="badge badge-success">
                                <Award size={12} /> {r.certificates}
                              </span>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td>
                            {r.contacts ? (
                              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                <Phone size={12} /> {r.contacts}
                              </span>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td>
                            {r.website ? (
                              <a
                                href={r.website.startsWith('http') ? r.website : `https://${r.website}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                              >
                                <Globe size={12} /> Сайт
                              </a>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td>
                            <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)' }}>
                              {r.source || '—'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* ─── Tab: Search by name ─── */}
      {activeTab === 'name' && (
        <>
          <div className="card" style={{ marginBottom: 'var(--spacing-lg)' }}>
            <div className="card-header">
              <h2 className="card-title">Поиск по наименованию</h2>
              <button
                id="search-name-btn"
                className="btn btn-primary btn-lg"
                onClick={handleSearchByName}
                disabled={nameLoading}
              >
                {nameLoading ? (
                  <>
                    <div className="spinner" /> Поиск...
                  </>
                ) : (
                  <>
                    <Search size={16} /> Найти информацию
                  </>
                )}
              </button>
            </div>

            <div className="form-group">
              <label className="form-label">Наименование товара</label>
              <input
                id="name-product-name"
                className="form-input"
                value={nameForm.product_name}
                onChange={(e) =>
                  setNameForm((prev) => ({ ...prev, product_name: e.target.value }))
                }
                placeholder="Например: Кран шаровый LD КШЦФ 150/125"
              />
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">
                Источники{' '}
                <span style={{ fontWeight: 400, color: 'var(--color-text-muted)' }}>
                  (необязательно, через запятую)
                </span>
              </label>
              <input
                className="form-input"
                value={nameForm.sources}
                onChange={(e) =>
                  setNameForm((prev) => ({ ...prev, sources: e.target.value }))
                }
                placeholder="Реестр РФ, сайт производителя, каталог ЕАЭС..."
              />
            </div>
          </div>

          {/* Name Results */}
          {nameResults && (
            <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
              {/* Summary */}
              {nameResults.summary && (
                <div className="card">
                  <div className="card-header">
                    <h2 className="card-title">Сводка</h2>
                  </div>
                  <p style={{ color: 'var(--color-text-secondary)', lineHeight: 1.7 }}>
                    {nameResults.summary}
                  </p>
                </div>
              )}

              {/* Manufacturers */}
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">
                    <Factory size={20} style={{ marginRight: '0.5rem', verticalAlign: 'text-bottom' }} />
                    Производители
                  </h2>
                  <span className="badge badge-info">
                    {nameResults.manufacturers.length}
                  </span>
                  {nameResults.manufacturers.length > 0 && (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleExport(nameResults.manufacturers, nameForm.product_name)}
                      style={{ marginLeft: '0.5rem' }}
                    >
                      <Download size={14} /> Экспорт XLSX
                    </button>
                  )}
                </div>

                {nameResults.manufacturers.length === 0 ? (
                  <div className="search-empty">Производители не найдены.</div>
                ) : (
                  <div className="table-container">
                    <table>
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Производитель</th>
                          <th>Страна</th>
                          <th>Контакты</th>
                          <th>Сайт</th>
                          <th>Основной</th>
                        </tr>
                      </thead>
                      <tbody>
                        {nameResults.manufacturers.map((m, i) => (
                          <tr key={i}>
                            <td>{i + 1}</td>
                            <td style={{ fontWeight: 600 }}>{m.name}</td>
                            <td>{m.country || '—'}</td>
                            <td>
                              {m.contacts ? (
                                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                  <Phone size={12} /> {m.contacts}
                                </span>
                              ) : (
                                '—'
                              )}
                            </td>
                            <td>
                              {m.website ? (
                                <a
                                  href={m.website.startsWith('http') ? m.website : `https://${m.website}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                                >
                                  <Globe size={12} /> Сайт
                                </a>
                              ) : (
                                '—'
                              )}
                            </td>
                            <td>
                              {m.is_primary ? (
                                <span className="badge badge-success">Да</span>
                              ) : (
                                '—'
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Documentation */}
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">
                    <FileText size={20} style={{ marginRight: '0.5rem', verticalAlign: 'text-bottom' }} />
                    Документация
                  </h2>
                  <span className="badge badge-info">
                    {nameResults.documentation.length}
                  </span>
                </div>

                {nameResults.documentation.length === 0 ? (
                  <div className="search-empty">Документация не найдена.</div>
                ) : (
                  <div className="table-container">
                    <table>
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Документ</th>
                          <th>Тип</th>
                          <th>Описание</th>
                          <th>Источник</th>
                        </tr>
                      </thead>
                      <tbody>
                        {nameResults.documentation.map((d, i) => (
                          <tr key={i}>
                            <td>{i + 1}</td>
                            <td style={{ fontWeight: 600 }}>{d.title}</td>
                            <td>
                              {d.doc_type ? (
                                <span className="badge badge-warning">{d.doc_type}</span>
                              ) : (
                                '—'
                              )}
                            </td>
                            <td>{d.description || '—'}</td>
                            <td>
                              {d.source_url ? (
                                <a
                                  href={d.source_url.startsWith('http') ? d.source_url : `https://${d.source_url}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                                >
                                  <ExternalLink size={12} /> Ссылка
                                </a>
                              ) : (
                                '—'
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
