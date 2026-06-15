/**
 * Thin REST client. The shared password token is read from localStorage and
 * forwarded as `X-Access-Token` on every request. For the SSE stream we have
 * a separate hook that uses `@microsoft/fetch-event-source`.
 */
import type { SessionRow } from './types';

const RAW_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const API_BASE = RAW_BASE.replace(/\/$/, '');

const TOKEN_KEY = 'bca.token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = getToken() ?? '';
  return { 'X-Access-Token': token, ...(extra || {}) };
}

async function jfetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${text || path}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  async verifyPassword(password: string) {
    const res = await fetch(`${API_BASE}/auth/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    if (!res.ok) throw new Error('Invalid password');
    return res.json() as Promise<{ ok: boolean; token: string }>;
  },
  status: () => jfetch<{
    datasource_active: string;
    datasource_healthy: boolean;
    llm_providers: Record<string, boolean>;
  }>('/status'),
  listSessions: () => jfetch<SessionRow[]>('/sessions'),
  createSession: (title?: string) =>
    jfetch<SessionRow>('/sessions', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
  getTrace: (sessionId: string) =>
    jfetch<{ events: any[]; messages: any[]; drafts: any[] }>(`/trace/${sessionId}`),
  getCustomer: (customerId: string) =>
    jfetch<{
      customer: any;
      source: string;
      transactions: any[];
      holdings: any[];
      interactions: any[];
    }>(`/customers/${customerId}`),
  listDrafts: (sessionId: string) =>
    jfetch<{ drafts: any[] }>(`/outreach/${sessionId}`),
  updateDraft: (draftId: string, message: string) =>
    jfetch<{ ok: boolean }>(`/outreach/${draftId}`, {
      method: 'PATCH',
      body: JSON.stringify({ message }),
    }),
  approve: (draftIds: string[]) =>
    jfetch<{ approved: number }>(`/outreach/approve`, {
      method: 'POST',
      body: JSON.stringify({ draft_ids: draftIds }),
    }),
  listTools: () => jfetch<{ tools: any[]; count: number }>('/tools'),
};
