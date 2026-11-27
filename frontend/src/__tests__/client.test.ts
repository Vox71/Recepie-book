import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, apiRequest } from '../api/client';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('api client', () => {
  it('turns a hanging request into a readable timeout error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => {
            reject(new DOMException('Aborted', 'AbortError'));
          });
        });
      }),
    );

    const request = apiRequest('/slow', { timeoutMs: 5 });

    await expect(request).rejects.toEqual(new ApiError(408, 'Request timed out'));
  });
});
