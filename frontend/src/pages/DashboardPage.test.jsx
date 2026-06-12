import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import DashboardPage from './DashboardPage';

const listMock = vi.fn();
const getSummaryMock = vi.fn();

vi.mock('../services/api', () => ({
  documentsApi: {
    list: (...args) => listMock(...args),
  },
  analyticsApi: {
    getSummary: (...args) => getSummaryMock(...args),
  },
}));

// Recharts использует ResizeObserver и SVG; jsdom без этого глохнет, мокаем минимально.
beforeEach(() => {
  vi.clearAllMocks();
  global.ResizeObserver = global.ResizeObserver || class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

describe('DashboardPage', () => {
  it('shows KPI values from API (success_rate, error_rate)', async () => {
    listMock.mockResolvedValue({ data: [] });
    getSummaryMock.mockResolvedValue({
      data: {
        total: 100,
        processed: 75,
        pending: 20,
        errors: 5,
        success_rate: 75,
        error_rate: 5,
        by_status: { uploaded: 15, processing: 5, processed: 75, error: 5 },
        by_type: { positions: 50, upd: 30, act: 20 },
        monthly: [{ name: 'Янв 2026', value: 10 }],
        yearly: [{ name: '2026', 'Всего': 100, 'Обработано': 75 }],
        volume_trend: [{ name: '01.04', value: 3 }],
        top_items: [{ name: 'Заполнение ЕИС', value: 12 }],
        region_status: [],
      },
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(getSummaryMock).toHaveBeenCalled();
      // KPI 1 — success_rate
      expect(screen.getByText('75%')).toBeInTheDocument();
      // KPI 3 — error_rate
      expect(screen.getByText('5%')).toBeInTheDocument();
      // KPI 2 — pending count
      expect(screen.getByText('20')).toBeInTheDocument();
    });
  });

  it('shows empty placeholders when API returns empty arrays', async () => {
    listMock.mockResolvedValue({ data: [] });
    getSummaryMock.mockResolvedValue({
      data: {
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
      },
    });

    render(<DashboardPage />);

    await waitFor(() => {
      // На пустых данных не должно быть хардкода 39.32% / 1063 / 418
      expect(screen.queryByText('39.32%')).toBeNull();
      expect(screen.queryByText('1063')).toBeNull();
      expect(screen.queryByText('418')).toBeNull();
      // Placeholders для пустых графиков
      expect(screen.getAllByText(/Нет данных/i).length).toBeGreaterThan(0);
    });
  });

  it('shows error banner when summary fetch fails', async () => {
    listMock.mockResolvedValue({ data: [] });
    getSummaryMock.mockRejectedValue(new Error('boom'));
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText(/Не удалось загрузить статистику/i)).toBeInTheDocument();
    });
  });

  it('renders by_type pie data, not the old hardcoded categories', async () => {
    listMock.mockResolvedValue({ data: [] });
    getSummaryMock.mockResolvedValue({
      data: {
        total: 5, processed: 5, pending: 0, errors: 0,
        success_rate: 100, error_rate: 0,
        by_status: {}, by_type: { positions: 5 },
        monthly: [], yearly: [], volume_trend: [], top_items: [], region_status: [],
      },
    });
    render(<DashboardPage />);
    await waitFor(() => {
      // Старая «Услуги: 58269» не должна появляться
      expect(screen.queryByText(/58269/)).toBeNull();
      expect(screen.queryByText(/30630/)).toBeNull();
    });
  });
});
