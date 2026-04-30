/**
 * Тесты для axios-клиента и интерсепторов.
 *
 * Стратегия: мокаем axios.create так, что он возвращает экземпляр с захватом
 * добавленных интерсепторов. Затем дёргаем интерсепторы напрямую и проверяем
 * их поведение (Authorization header / удаление токена при 401).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Захват интерсепторов и базовой конфигурации
const requestInterceptors = [];
const responseInterceptors = [];

vi.mock('axios', () => {
  const mockInstance = {
    interceptors: {
      request: {
        use: (fulfilled, rejected) => {
          requestInterceptors.push({ fulfilled, rejected });
          return requestInterceptors.length - 1;
        },
      },
      response: {
        use: (fulfilled, rejected) => {
          responseInterceptors.push({ fulfilled, rejected });
          return responseInterceptors.length - 1;
        },
      },
    },
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  };
  return {
    default: {
      create: vi.fn(() => mockInstance),
    },
  };
});

beforeEach(async () => {
  // Сбрасываем модули, чтобы импорт api.js повторно прогнал axios.create
  requestInterceptors.length = 0;
  responseInterceptors.length = 0;
  localStorage.clear();
  vi.resetModules();
  // Принудительно импортируем api после сброса — чтобы захватить интерсепторы
  await import('./api.js');
});

describe('api request interceptor', () => {
  it('adds Authorization header when token is in localStorage', () => {
    localStorage.setItem('token', 'jwt-abc');
    const { fulfilled } = requestInterceptors[0];
    const config = { headers: {} };
    const result = fulfilled(config);
    expect(result.headers.Authorization).toBe('Bearer jwt-abc');
  });

  it('does not add Authorization header when token is missing', () => {
    const { fulfilled } = requestInterceptors[0];
    const config = { headers: {} };
    const result = fulfilled(config);
    expect(result.headers.Authorization).toBeUndefined();
  });
});

describe('api response interceptor', () => {
  it('passes through successful responses unchanged', () => {
    const { fulfilled } = responseInterceptors[0];
    const response = { status: 200, data: { ok: true } };
    expect(fulfilled(response)).toBe(response);
  });

  it('removes token and redirects on 401', async () => {
    localStorage.setItem('token', 'jwt-abc');

    // window.location.href в jsdom можно безопасно перезаписать через delete + assign
    const originalLocation = window.location;
    delete window.location;
    window.location = { href: '' };

    const { rejected } = responseInterceptors[0];
    const error = { response: { status: 401 } };

    await expect(rejected(error)).rejects.toBe(error);
    expect(localStorage.getItem('token')).toBeNull();
    expect(window.location.href).toBe('/login');

    window.location = originalLocation;
  });

  it('does not remove token on non-401 errors', async () => {
    localStorage.setItem('token', 'jwt-abc');
    const { rejected } = responseInterceptors[0];
    const error = { response: { status: 500 } };
    await expect(rejected(error)).rejects.toBe(error);
    expect(localStorage.getItem('token')).toBe('jwt-abc');
  });
});
