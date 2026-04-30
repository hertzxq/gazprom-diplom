import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import UploadPage from './UploadPage';

// Захватываем onDrop, чтобы вызывать его вручную из тестов.
let capturedOnDrop = null;
vi.mock('react-dropzone', () => ({
  useDropzone: ({ onDrop }) => {
    capturedOnDrop = onDrop;
    return {
      getRootProps: () => ({}),
      getInputProps: () => ({}),
      isDragActive: false,
    };
  },
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}));

const toastError = vi.fn();
const toastSuccess = vi.fn();
vi.mock('react-hot-toast', () => ({
  default: {
    error: (msg) => toastError(msg),
    success: (msg) => toastSuccess(msg),
  },
}));

const uploadMock = vi.fn();
vi.mock('../services/api', () => ({
  documentsApi: {
    upload: (...args) => uploadMock(...args),
  },
}));

const _fakeFile = (name, size = 1024, type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') => {
  const blob = new Blob(['x'.repeat(size)], { type });
  // File in jsdom — Blob with name
  return new File([blob], name, { type });
};

describe('UploadPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedOnDrop = null;
  });

  it('renders dropzone hint and supports the 6 file types in the select', async () => {
    render(<UploadPage />);
    expect(screen.getByText(/Перетащите файлы/i)).toBeInTheDocument();
    expect(screen.getByText(/XLS, XLSX, PDF/i)).toBeInTheDocument();

    // После добавления файла появляется select
    expect(capturedOnDrop).toBeInstanceOf(Function);
    await act(async () => {
      capturedOnDrop([_fakeFile('positions.xlsx')]);
    });

    await waitFor(() => {
      const select = screen.getByRole('combobox');
      const optionValues = Array.from(select.options).map((o) => o.value);
      expect(optionValues).toEqual([
        'positions',
        'upd',
        'act',
        'template',
        'payment_registry',
        'contract_registry',
      ]);
    });
  });

  it('uploads added file with the selected file_type', async () => {
    uploadMock.mockResolvedValue({ data: { id: 'doc-1' } });
    const user = userEvent.setup();
    render(<UploadPage />);

    await act(async () => {
      capturedOnDrop([_fakeFile('act.xlsx')]);
    });
    await waitFor(() => expect(screen.getByRole('combobox')).toBeInTheDocument());

    // Меняем file_type на act
    await user.selectOptions(screen.getByRole('combobox'), 'act');
    await user.click(screen.getByRole('button', { name: /Загрузить все/i }));

    await waitFor(() => {
      expect(uploadMock).toHaveBeenCalledTimes(1);
      const [file, fileType] = uploadMock.mock.calls[0];
      expect(file.name).toBe('act.xlsx');
      expect(fileType).toBe('act');
      expect(toastSuccess).toHaveBeenCalledWith(expect.stringContaining('Загружено'));
    });
  });

  it('shows error status when upload fails', async () => {
    uploadMock.mockRejectedValue({ response: { data: { detail: 'Сервер недоступен' } } });
    const user = userEvent.setup();
    render(<UploadPage />);

    await act(async () => {
      capturedOnDrop([_fakeFile('upd.xlsx')]);
    });
    await waitFor(() => expect(screen.getByRole('combobox')).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: /Загрузить все/i }));

    await waitFor(() => {
      expect(uploadMock).toHaveBeenCalled();
      // success toast не должен срабатывать
      expect(toastSuccess).not.toHaveBeenCalled();
    });
  });

  it('uploads multiple files in one click, each with its own type', async () => {
    uploadMock.mockResolvedValue({ data: { id: 'ok' } });
    const user = userEvent.setup();
    render(<UploadPage />);

    await act(async () => {
      capturedOnDrop([_fakeFile('a.xlsx'), _fakeFile('b.xlsx')]);
    });
    await waitFor(() => expect(screen.getAllByRole('combobox')).toHaveLength(2));

    const selects = screen.getAllByRole('combobox');
    await user.selectOptions(selects[0], 'positions');
    await user.selectOptions(selects[1], 'upd');

    await user.click(screen.getByRole('button', { name: /Загрузить все/i }));

    await waitFor(() => {
      expect(uploadMock).toHaveBeenCalledTimes(2);
      const types = uploadMock.mock.calls.map((c) => c[1]);
      expect(types).toEqual(['positions', 'upd']);
    });
  });
});
