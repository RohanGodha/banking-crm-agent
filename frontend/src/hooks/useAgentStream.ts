/**
 * Streams the agent's events from the backend SSE endpoint.
 * Uses `@microsoft/fetch-event-source` so we can send the auth header.
 */
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { useCallback } from 'react';
import { API_BASE, getToken } from '@/lib/api';
import type {
  CandidateRecord,
  DraftRecord,
  TraceEvent,
  TraceEventName,
} from '@/lib/types';
import { useUi } from '@/store/uiStore';

interface RunArgs {
  query: string;
  sessionId?: string | null;
  rmName?: string;
}

export function useAgentStream() {
  const ui = useUi();

  const run = useCallback(
    async (args: RunArgs) => {
      const token = getToken();
      if (!token) {
        ui.setError('Not authenticated. Please log in again.');
        return;
      }
      ui.setRmQuery(args.query);
      ui.addTurn('user', args.query);
      ui.startStream();

      const ctrl = new AbortController();
      try {
        await fetchEventSource(`${API_BASE}/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Access-Token': token,
            Accept: 'text/event-stream',
          },
          body: JSON.stringify({
            session_id: args.sessionId ?? null,
            rm_query: args.query,
            rm_name: args.rmName ?? 'Rohan',
          }),
          signal: ctrl.signal,
          openWhenHidden: true,
          onmessage(msg) {
            const eventName = (msg.event || 'token') as TraceEventName;
            let payload: any = {};
            try {
              payload = msg.data ? JSON.parse(msg.data) : {};
            } catch {
              payload = { data: msg.data };
            }
            const evt: TraceEvent = {
              event: eventName,
              ts: payload.ts || new Date().toISOString(),
              data: payload.data || payload,
              llm_route: payload.llm_route,
              latency_ms: payload.latency_ms,
            };
            ui.pushEvent(evt);

            const d: any = evt.data || {};
            if (eventName === 'info' && d.session_id) {
              ui.setSessionId(d.session_id);
            }
            if (eventName === 'candidate' && d.customer_id) {
              ui.pushCandidate(d as CandidateRecord);
            }
            if (eventName === 'draft' && d.customer_id) {
              ui.pushDraft({
                customer_id: d.customer_id,
                product_id: d.product_id,
                message: d.message,
                compliance: d.compliance || {},
              } as DraftRecord);
            }
            if (eventName === 'synth' && d.summary) {
              ui.setSummary(d.summary);
            }
            if (eventName === 'final') {
              if (d.summary) ui.setSummary(d.summary);
              if (Array.isArray(d.candidates)) {
                d.candidates.forEach((c: CandidateRecord) => ui.pushCandidate(c));
              }
              if (Array.isArray(d.drafts)) {
                d.drafts.forEach((dr: DraftRecord) => ui.pushDraft(dr));
              }
              if (d.summary) ui.addTurn('assistant', d.summary);
              ui.finishStream();
            }
            if (eventName === 'error') {
              ui.setError(d.error || 'Unknown error');
              ui.finishStream();
            }
          },
          onerror(err) {
            ui.setError(`Connection error: ${err?.message || err}`);
            ui.finishStream();
            throw err;
          },
        });
      } catch (e: any) {
        if (!ctrl.signal.aborted) {
          ui.setError(e?.message || String(e));
        }
        ui.finishStream();
      }

      return () => ctrl.abort();
    },
    [ui],
  );

  return { run };
}
