import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from './LoginPage';

// Мок react-hot-toast чтобы подсматривать вызовы
const toastError = vi.fn();
const toastSuccess = vi.fn();
vi.mock('react-hot-toast', () => ({
  default: {
    error: (msg) => toastError(msg),
    success: (msg) => toastSuccess(msg),
  },
}));

// Мок AuthContext.useAuth
const mockLogin = vi.fn();
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ login: mockLogin }),
}));

// Мок useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  );
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders form with username and password fields', () => {
    renderLogin();
    expect(screen.getByLabelText(/Логин/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Пароль/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Войти/i })).toBeInTheDocument();
  });

  it('shows error when fields are empty on submit', async () => {
    const user = userEvent.setup();
    renderLogin();
    await user.click(screen.getByRole('button', { name: /Войти/i }));
    expect(toastError).toHaveBeenCalledWith('Введите логин и пароль');
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('calls login with entered credentials on submit', async () => {
    mockLogin.mockResolvedValue({ username: 'admin' });
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText(/Логин/i), 'admin');
    await user.type(screen.getByLabelText(/Пароль/i), 'secret');
    await user.click(screen.getByRole('button', { name: /Войти/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('admin', 'secret');
      expect(toastSuccess).toHaveBeenCalledWith('Добро пожаловать!');
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  it('shows error toast on login failure', async () => {
    mockLogin.mockRejectedValue({
      response: { data: { detail: 'Неверный логин или пароль' } },
    });
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText(/Логин/i), 'admin');
    await user.type(screen.getByLabelText(/Пароль/i), 'wrong');
    await user.click(screen.getByRole('button', { name: /Войти/i }));

    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith('Неверный логин или пароль');
      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  it('shows generic error message if response detail missing', async () => {
    mockLogin.mockRejectedValue(new Error('network'));
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText(/Логин/i), 'admin');
    await user.type(screen.getByLabelText(/Пароль/i), 'pass');
    await user.click(screen.getByRole('button', { name: /Войти/i }));

    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith('Ошибка авторизации');
    });
  });
});
