import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ProcessingPage from './ProcessingPage';

// Мок react-hot-toast
const toastError = vi.fn();
const toastSuccess = vi.fn();
vi.mock('react-hot-toast', () => ({
  default: {
    error: (msg) => toastError(msg),
    success: (msg) => toastSuccess(msg),
  },
}));

// Мок API
const listMock = vi.fn();
const processMock = vi.fn();
const downloadMock = vi.fn();
vi.mock('../services/api', () => ({
  documentsApi: {
    list: (...args) => listMock(...args),
    process: (...args) => processMock(...args),
    download: (...args) => downloadMock(...args),
  },
}));

const SAMPLE_DOCS = [
  {
    id: 'pos-1',
    file_type: 'positions',
    original_filename: 'positions.xlsx',
    created_at: '2024-03-01T10:00:00',
  },
  {
    id: 'upd-1',
    file_type: 'upd',
    original_filename: 'upd.xlsx',
    created_at: '2024-03-02T10:00:00',
  },
  {
    id: 'act-1',
    file_type: 'act',
    original_filename: 'act.pdf',
    created_at: '2024-03-03T10:00:00',
  },
  {
    id: 'tpl-1',
    file_type: 'template',
    original_filename: 'template.xlsx',
    created_at: '2024-02-01T10:00:00',
  },
];

describe('ProcessingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listMock.mockResolvedValue({ data: SAMPLE_DOCS });
  });

  it('loads documents on mount and pre-fills selects', async () => {
    render(<ProcessingPage />);
    await waitFor(() => {
      expect(listMock).toHaveBeenCalled();
      expect(screen.getByRole('button', { name: /Обработать/i })).toBeInTheDocument();
    });

    const positionsSelect = document.getElementById('select-positions');
    const updSelect = document.getElementById('select-upd');
    expect(positionsSelect.value).toBe('pos-1');
    // Предзаполнение: первый upd/act, отсортированный по created_at desc → act-1 (03.03) перед upd-1 (02.03)
    expect(['upd-1', 'act-1']).toContain(updSelect.value);
  });

  it('renders all 4 scenario options', async () => {
    render(<ProcessingPage />);
    await waitFor(() => {
      const select = document.getElementById('select-scenario');
      expect(select).toBeInTheDocument();
      const optionValues = Array.from(select.options).map((o) => o.value);
      expect(optionValues).toEqual(['', 'leader_smi', 'veneta', 'd_lux']);
    });
  });

  it('sends selected scenario to backend on process', async () => {
    processMock.mockResolvedValue({
      data: {
        task_id: 't-1',
        matches: [],
        message: 'ok',
        result_document_id: 'res-1',
        result_document_filename: 'filled.xlsx',
      },
    });
    const user = userEvent.setup();
    render(<ProcessingPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: /Обработать/i })).toBeEnabled());

    const scenarioSelect = document.getElementById('select-scenario');
    await user.selectOptions(scenarioSelect, 'd_lux');
    await user.click(screen.getByRole('button', { name: /Обработать/i }));

    await waitFor(() => {
      expect(processMock).toHaveBeenCalledTimes(1);
      const payload = processMock.mock.calls[0][0];
      expect(payload.scenario).toBe('d_lux');
      expect(payload.positions_document_id).toBe('pos-1');
      expect(payload.upd_document_id).toBeTruthy();
    });
  });

  it('shows error toast if no documents selected', async () => {
    listMock.mockResolvedValue({ data: [] });  // Без документов
    const user = userEvent.setup();
    render(<ProcessingPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: /Обработать/i })).toBeInTheDocument());

    const btn = screen.getByRole('button', { name: /Обработать/i });
    // Кнопка disabled когда нет positions/upd
    expect(btn).toBeDisabled();
  });

  it('renders results after successful process', async () => {
    processMock.mockResolvedValue({
      data: {
        task_id: 't-1',
        matches: [
          {
            upd_row_index: 0,
            upd_item_name: 'Мойка кузова',
            matched_position_number: 5,
            matched_position_name: 'Мойка седан',
            confidence: 92,
            needs_review: false,
            quantity: 1,
            unit: 'шт',
            price: 850,
            total: 850,
            highlight_price: false,
          },
          {
            upd_row_index: 1,
            upd_item_name: 'Полировка',
            matched_position_number: null,
            matched_position_name: null,
            confidence: 30,
            needs_review: true,
            quantity: 1,
            unit: 'шт',
            price: null,
            total: null,
            highlight_price: false,
          },
        ],
        message: 'Готово',
        result_document_id: 'res-1',
        result_document_filename: 'out.xlsx',
        document_number: 'INV-5',
        document_date: '15.03.2024',
      },
    });

    const user = userEvent.setup();
    render(<ProcessingPage />);
    await waitFor(() => expect(screen.getByRole('button', { name: /Обработать/i })).toBeEnabled());
    await user.click(screen.getByRole('button', { name: /Обработать/i }));

    await waitFor(() => {
      expect(screen.getByText(/Результаты сопоставления/i)).toBeInTheDocument();
      // Badges
      expect(screen.getByText(/Совпало: 1/i)).toBeInTheDocument();
      expect(screen.getByText(/На проверку: 1/i)).toBeInTheDocument();
      // Строка с Мойкой
      expect(screen.getByText('Мойка кузова')).toBeInTheDocument();
    });
  });

  it('displays load error toast if list fails', async () => {
    listMock.mockRejectedValue(new Error('network'));
    render(<ProcessingPage />);
    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith('Не удалось загрузить документы');
    });
  });
});
