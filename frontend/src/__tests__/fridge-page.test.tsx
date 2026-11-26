import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { FridgeItem } from '../api/fridge';
import App from '../App';
import { TOKEN_STORAGE_KEY } from '../auth/AuthContext';

function isoDate(offsetDays: number): string {
  const date = new Date();
  date.setHours(12, 0, 0, 0);
  date.setDate(date.getDate() + offsetDays);
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

function item(id: number, name: string, offsetDays: number, quantity = 1): FridgeItem {
  return {
    id,
    user_id: 1,
    product_name: name,
    expiration_date: isoDate(offsetDays),
    quantity,
    last_added: '2026-11-25T10:00:00+00:00',
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

function renderFridge() {
  return render(
    <MemoryRouter initialEntries={['/fridge']}>
      <App />
    </MemoryRouter>,
  );
}

const ITEMS = [item(1, 'Молоко', 2, 1), item(2, 'Хлеб', 30, 2), item(3, 'Сыр', -2, 1)];

function mockFetch(initial: FridgeItem[] = ITEMS) {
  let items = [...initial];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    if (method === 'POST' && url.endsWith('/profile/fridge')) {
      const body = JSON.parse(String(init?.body)) as {
        product_name: string;
        expiration_date: string;
        quantity: number;
      };
      const created: FridgeItem = {
        id: 99,
        user_id: 1,
        last_added: '2026-11-25T10:00:00+00:00',
        ...body,
      };
      items = [...items, created];
      return jsonResponse(created, 201);
    }
    if (method === 'DELETE' && url.includes('/profile/fridge/expired')) {
      items = items.filter(
        (row) => new Date(`${row.expiration_date}T00:00:00`) >= new Date(`${isoDate(0)}T00:00:00`),
      );
      return jsonResponse({ message: 'Deleted 1 expired product(s)' });
    }
    if (method === 'DELETE') {
      const id = Number(url.split('/').pop());
      items = items.filter((row) => row.id !== id);
      return jsonResponse({ message: `Fridge item ${id} deleted` });
    }
    return jsonResponse(items);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

beforeEach(() => {
  window.localStorage.setItem(TOKEN_STORAGE_KEY, 'test-token');
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('fridge page', () => {
  it('shows the title, the summary and the products of the signed-in user', async () => {
    mockFetch();
    renderFridge();

    expect(await screen.findByRole('heading', { name: 'Мой холодильник' })).toBeInTheDocument();
    const summary = screen.getByRole('region', { name: 'Сводка по холодильнику' });
    expect(within(summary).getByText('Всего продуктов')).toBeInTheDocument();
    expect(within(summary).getByText('3')).toBeInTheDocument();
    expect(within(summary).getByText('Скоро истекают')).toBeInTheDocument();
    expect(within(summary).getByText('Просрочено')).toBeInTheDocument();

    const products = screen.getByRole('region', { name: 'Продукты' });
    expect(within(products).getAllByRole('listitem')).toHaveLength(3);
    expect(within(products).getByRole('heading', { name: 'Молоко' })).toBeInTheDocument();
    expect(within(products).getAllByText('1 шт.')).toHaveLength(2);
    expect(within(products).getByText('Скоро истекает')).toBeInTheDocument();
    expect(within(products).getByText('Просрочен')).toBeInTheDocument();
  });

  it('filters the products by their status', async () => {
    const user = userEvent.setup();
    mockFetch();
    renderFridge();

    await screen.findByRole('heading', { name: 'Молоко' });
    const products = screen.getByRole('region', { name: 'Продукты' });
    expect(within(products).getAllByRole('listitem')).toHaveLength(3);

    await user.click(screen.getByRole('button', { name: 'Скоро истекают' }));

    expect(within(products).getAllByRole('listitem')).toHaveLength(1);
    expect(within(products).getByRole('heading', { name: 'Молоко' })).toBeInTheDocument();
    expect(within(products).queryByRole('heading', { name: 'Хлеб' })).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Просроченные' }));
    expect(within(products).getByRole('heading', { name: 'Сыр' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Все' }));
    expect(within(products).getAllByRole('listitem')).toHaveLength(3);
  });

  it('shows an empty state when the filter has no matches', async () => {
    const user = userEvent.setup();
    mockFetch([item(1, 'Хлеб', 30)]);
    renderFridge();

    await screen.findByRole('heading', { name: 'Хлеб' });
    await user.click(screen.getByRole('button', { name: 'Просроченные' }));

    expect(screen.getByText('По этому фильтру продуктов нет.')).toBeInTheDocument();
  });

  it('adds a product through the protected endpoint', async () => {
    const user = userEvent.setup();
    mockFetch();
    renderFridge();

    await screen.findByRole('heading', { name: 'Молоко' });
    await user.click(screen.getByRole('button', { name: 'Добавить продукт' }));
    await user.type(screen.getByLabelText('Название продукта'), 'Кефир');
    const quantity = screen.getByLabelText('Количество');
    await user.clear(quantity);
    await user.type(quantity, '3');
    await user.click(screen.getByRole('button', { name: 'Добавить' }));

    expect(await screen.findByRole('heading', { name: 'Кефир' })).toBeInTheDocument();
    expect(screen.getByText('3 шт.')).toBeInTheDocument();
  });

  it('deletes one product', async () => {
    const user = userEvent.setup();
    mockFetch();
    renderFridge();

    await screen.findByRole('heading', { name: 'Молоко' });
    await user.click(screen.getByRole('button', { name: 'Удалить Молоко' }));

    expect(screen.queryByRole('heading', { name: 'Молоко' })).toBeNull();
  });

  it('removes only expired products', async () => {
    const user = userEvent.setup();
    mockFetch();
    renderFridge();

    await screen.findByRole('heading', { name: 'Сыр' });
    await user.click(screen.getByRole('button', { name: 'Удалить просроченные' }));

    expect(await screen.findByRole('heading', { name: 'Молоко' })).toBeInTheDocument();
    expect(screen.queryByText('Сыр')).toBeNull();
  });

  it('returns to the login screen when the token is rejected', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ error: 'Authorization token is invalid' }, 401)),
    );
    renderFridge();

    expect(await screen.findByRole('heading', { name: 'С возвращением!' })).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
  });

  it('shows a load error and retries', async () => {
    const user = userEvent.setup();
    let calls = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        calls += 1;
        return calls === 1 ? jsonResponse({ error: 'Server is down' }, 500) : jsonResponse(ITEMS);
      }),
    );
    renderFridge();

    expect(await screen.findByRole('alert')).toHaveTextContent('Server is down');
    await user.click(screen.getByRole('button', { name: 'Повторить' }));

    expect(await screen.findByRole('heading', { name: 'Молоко' })).toBeInTheDocument();
  });

  it('shows an empty fridge', async () => {
    mockFetch([]);
    renderFridge();

    expect(
      await screen.findByText('В холодильнике пока пусто. Добавьте первый продукт.'),
    ).toBeInTheDocument();
  });

  it('shows a hint when nothing is expiring soon', async () => {
    mockFetch([item(1, 'Хлеб', 30)]);
    renderFridge();

    expect(await screen.findByText('Скоро истекающих продуктов нет.')).toBeInTheDocument();
  });

  it('shows the API error of the add form and closes it on cancel', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) =>
        init?.method === 'POST'
          ? jsonResponse({ error: 'Invalid item' }, 400)
          : jsonResponse(ITEMS),
      ),
    );
    renderFridge();

    await screen.findByRole('heading', { name: 'Молоко' });
    await user.click(screen.getByRole('button', { name: 'Добавить продукт' }));
    await user.type(screen.getByLabelText('Название продукта'), 'Кефир');
    await user.click(screen.getByRole('button', { name: 'Добавить' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid item');

    await user.click(screen.getByRole('button', { name: 'Отмена' }));
    expect(screen.queryByLabelText('Название продукта')).toBeNull();
  });

  it('shows an error when a product cannot be deleted', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) =>
        init?.method === 'DELETE'
          ? jsonResponse({ error: 'Cannot delete' }, 400)
          : jsonResponse(ITEMS),
      ),
    );
    renderFridge();

    await screen.findByRole('heading', { name: 'Молоко' });
    await user.click(screen.getByRole('button', { name: 'Удалить Молоко' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot delete');
  });
});
