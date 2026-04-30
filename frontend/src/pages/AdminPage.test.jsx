import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminPage from './AdminPage';

const toastError = vi.fn();
const toastSuccess = vi.fn();
vi.mock('react-hot-toast', () => ({
  default: {
    error: (msg) => toastError(msg),
    success: (msg) => toastSuccess(msg),
  },
}));

const listUsersMock = vi.fn();
const updateUserMock = vi.fn();
const deleteUserMock = vi.fn();
const registerMock = vi.fn();
const listRulesMock = vi.fn();
const updateRulesMock = vi.fn();
vi.mock('../services/api', () => ({
  adminApi: {
    listUsers: (...args) => listUsersMock(...args),
    updateUser: (...args) => updateUserMock(...args),
    deleteUser: (...args) => deleteUserMock(...args),
  },
  authApi: {
    register: (...args) => registerMock(...args),
  },
  task2Api: {
    listExclusionRules: (...args) => listRulesMock(...args),
    updateExclusionRules: (...args) => updateRulesMock(...args),
  },
}));

const CURRENT_ADMIN = { id: 'me-1', username: 'admin', role: 'admin' };
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: CURRENT_ADMIN }),
}));

const SAMPLE_USERS = [
  {
    id: 'me-1',
    username: 'admin',
    email: 'a@x.com',
    full_name: 'Admin',
    role: 'admin',
    is_active: true,
    created_at: '2024-01-10T10:00:00',
  },
  {
    id: 'u-2',
    username: 'user2',
    email: 'u2@x.com',
    full_name: 'User Two',
    role: 'user',
    is_active: true,
    created_at: '2024-02-15T10:00:00',
  },
  {
    id: 'u-3',
    username: 'blocked',
    email: 'b@x.com',
    full_name: null,
    role: 'user',
    is_active: false,
    created_at: '2024-03-01T10:00:00',
  },
];

describe('AdminPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listUsersMock.mockResolvedValue({ data: SAMPLE_USERS });
    listRulesMock.mockResolvedValue({ data: [] });
  });

  it('loads and renders user list', async () => {
    render(<AdminPage />);
    await waitFor(() => {
      expect(screen.getByText('User Two')).toBeInTheDocument();
      expect(screen.getByText('a@x.com')).toBeInTheDocument();
    });
  });

  it('disables role and status buttons for current admin', async () => {
    render(<AdminPage />);
    await waitFor(() => expect(screen.getByText('Admin')).toBeInTheDocument());

    const rows = screen.getAllByRole('row');
    // Первая строка — заголовок. Находим строку с собственным логином
    const selfRow = rows.find((r) => r.textContent.includes('admin') && r.textContent.includes('a@x.com'));
    expect(selfRow).toBeDefined();
    const selfSelect = selfRow.querySelector('select');
    expect(selfSelect).toBeDisabled();
  });

  it('promotes user to admin on role change', async () => {
    updateUserMock.mockResolvedValue({ data: {} });
    const user = userEvent.setup();
    render(<AdminPage />);

    await waitFor(() => expect(screen.getByText('User Two')).toBeInTheDocument());

    const rows = screen.getAllByRole('row');
    const u2Row = rows.find((r) => r.textContent.includes('u2@x.com'));
    const roleSelect = u2Row.querySelector('select');
    await user.selectOptions(roleSelect, 'admin');

    await waitFor(() => {
      expect(updateUserMock).toHaveBeenCalledWith('u-2', { role: 'admin' });
      expect(toastSuccess).toHaveBeenCalledWith('Роль обновлена');
    });
  });

  it('toggles user active state', async () => {
    updateUserMock.mockResolvedValue({ data: {} });
    const user = userEvent.setup();
    render(<AdminPage />);
    await waitFor(() => expect(screen.getByText('User Two')).toBeInTheDocument());

    const rows = screen.getAllByRole('row');
    const u2Row = rows.find((r) => r.textContent.includes('u2@x.com'));
    const toggleBtn = u2Row.querySelector('button[title*="Заблокировать"]');
    await user.click(toggleBtn);

    await waitFor(() => {
      expect(updateUserMock).toHaveBeenCalledWith('u-2', { is_active: false });
    });
  });

  it('shows create form on "Добавить" click and submits', async () => {
    registerMock.mockResolvedValue({ data: {} });
    const user = userEvent.setup();
    render(<AdminPage />);

    await waitFor(() => expect(screen.getByText('User Two')).toBeInTheDocument());

    // На странице две кнопки «Добавить» (пользователи и правила СМСП).
    // Кнопка пользователей помечена id="add-user-btn".
    await user.click(document.getElementById('add-user-btn'));

    await user.type(screen.getByPlaceholderText('username'), 'new_user');
    await user.type(screen.getByPlaceholderText('user@example.com'), 'new@test.com');
    await user.type(screen.getByPlaceholderText('••••••'), 'pass123');

    await user.click(screen.getByRole('button', { name: /Создать/i }));

    await waitFor(() => {
      expect(registerMock).toHaveBeenCalledWith(expect.objectContaining({
        username: 'new_user',
        email: 'new@test.com',
        password: 'pass123',
      }));
      expect(toastSuccess).toHaveBeenCalledWith('Пользователь создан');
    });
  });

  it('shows error toast if list fails', async () => {
    listUsersMock.mockRejectedValue(new Error('boom'));
    render(<AdminPage />);
    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith('Не удалось загрузить пользователей');
    });
  });
});
