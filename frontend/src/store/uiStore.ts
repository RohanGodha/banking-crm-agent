import { create } from 'zustand';
import type { CandidateRecord, DraftRecord, TraceEvent } from '@/lib/types';

export interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
}

interface UiState {
  sessionId: string | null;
  rmQuery: string;
  isStreaming: boolean;
  transcript: ChatTurn[];
  events: TraceEvent[];
  candidates: CandidateRecord[];
  drafts: DraftRecord[];
  summary: string;
  selectedCustomerId: string | null;
  error: string | null;

  setSessionId(id: string | null): void;
  setRmQuery(q: string): void;
  addTurn(role: 'user' | 'assistant', content: string): void;
  startStream(): void;
  pushEvent(ev: TraceEvent): void;
  pushCandidate(c: CandidateRecord): void;
  pushDraft(d: DraftRecord): void;
  setSummary(s: string): void;
  setSelectedCustomerId(id: string | null): void;
  setError(e: string | null): void;
  finishStream(): void;
  resetForNewQuery(): void;
}

export const useUi = create<UiState>((set) => ({
  sessionId: null,
  rmQuery: '',
  isStreaming: false,
  transcript: [],
  events: [],
  candidates: [],
  drafts: [],
  summary: '',
  selectedCustomerId: null,
  error: null,

  setSessionId: (id) => set({ sessionId: id }),
  setRmQuery: (q) => set({ rmQuery: q }),
  addTurn: (role, content) => set((s) => ({ transcript: [...s.transcript, { role, content }] })),
  startStream: () =>
    set({
      isStreaming: true,
      events: [],
      candidates: [],
      drafts: [],
      summary: '',
      error: null,
    }),
  pushEvent: (ev) => set((s) => ({ events: [...s.events, ev] })),
  pushCandidate: (c) =>
    set((s) => {
      const idx = s.candidates.findIndex((x) => x.customer_id === c.customer_id);
      const next = [...s.candidates];
      if (idx >= 0) next[idx] = c;
      else next.push(c);
      next.sort((a, b) => b.composite_score - a.composite_score);
      return { candidates: next };
    }),
  pushDraft: (d) =>
    set((s) => {
      const idx = s.drafts.findIndex((x) => x.customer_id === d.customer_id);
      const next = [...s.drafts];
      if (idx >= 0) next[idx] = d;
      else next.push(d);
      return { drafts: next };
    }),
  setSummary: (text) => set({ summary: text }),
  setSelectedCustomerId: (id) => set({ selectedCustomerId: id }),
  setError: (e) => set({ error: e }),
  finishStream: () => set({ isStreaming: false }),
  resetForNewQuery: () =>
    set({
      transcript: [],
      events: [],
      candidates: [],
      drafts: [],
      summary: '',
      error: null,
      isStreaming: false,
    }),
}));
