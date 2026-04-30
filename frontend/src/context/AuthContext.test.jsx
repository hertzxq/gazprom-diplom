import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { AuthProvider, useAuth } from './AuthContext';

vi.mock('../services/api', () => ({
  authApi: {
    login: vi.fn(),
    me: vi.fn(),
    register: vi.fn(),
  },
}));

import { authApi } from '../services/api';

function Probe() {
  const { user, login, logout } = useAuth();
  return (
    <div>
      <div data-testid="username">{user?.username ?? 'anonymous'}</div>
      <div data-testid="role">{user?.role ?? 'none'}</div>
      <button onClick={() => login('admin', 'secret')}>do-login</button>
      <button onClick={logout}>do-logout</button>
    </div>
  );
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('shows anonymous when no token in storage', async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => {
      expect(screen.getByTestId('username')).toHaveTextContent('anonymous');
    });
    expect(authApi.me).not.toHaveBeenCalled();
  });

  it('auto-loads user when token present and /me succeeds', async () => {
    localStorage.setItem('token', 'stored-token');
    authApi.me.mockResolvedValue({ data: { username: 'admin', role: 'admin' } });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('username')).toHaveTextContent('admin');
      expect(screen.getByTestId('role')).toHaveTextContent('admin');
    });
  });

  it('clears token when /me fails on mount', async () => {
    localStorage.setItem('token', 'bad-token');
    authApi.me.mockRejectedValue(new Error('401'));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('username')).toHaveTextContent('anonymous');
    });
    expect(localStorage.getItem('token')).toBe(null);
  });

  it('login stores token and fetches user', async () => {
    authApi.login.mockResolvedValue({ data: { access_token: 'new-token' } });
    authApi.me.mockResolvedValue({ data: { username: 'admin', role: 'admin' } });

    const { getByText } = render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('username')).toHaveTextContent('anonymous');
    });

    await act(async () => {
      getByText('do-login').click();
    });

    await waitFor(() => {
      expect(localStorage.getItem('token')).toBe('new-token');
      expect(screen.getByTestId('username')).toHaveTextContent('admin');
    });
  });

  it('logout clears token and user', async () => {
    localStorage.setItem('token', 'stored');
    authApi.me.mockResolvedValue({ data: { username: 'admin', role: 'admin' } });

    const { getByText } = render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('username')).toHaveTextContent('admin'));

    act(() => {
      getByText('do-logout').click();
    });

    expect(localStorage.getItem('token')).toBe(null);
    expect(screen.getByTestId('username')).toHaveTextContent('anonymous');
  });
});
