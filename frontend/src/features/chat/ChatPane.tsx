import { useState, useRef, useEffect } from 'react';
import { useUi } from '@/store/uiStore';
import { useAgentStream } from '@/hooks/useAgentStream';
import { TracePanel } from '@/features/trace/TracePanel';
import { ArrowUp, Sparkles, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/cn';

const QUICK_PROMPTS = [
  'Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages.',
  'Now narrow it to Bangalore customers and make the messages warmer.',
  'Show me customers with salary-credit slowdown — what should we offer them?',
];

export function ChatPane() {
  const ui = useUi();
  const { run } = useAgentStream();
  const [input, setInput] = useState('');
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    taRef.current?.focus();
  }, []);

  function submit(q?: string) {
    const query = (q ?? input).trim();
    if (!query || ui.isStreaming) return;
    setInput('');
    void run({ query, sessionId: ui.sessionId });
  }

  return (
    <div className="h-full flex flex-col">
      {/* Conversation / trace area */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {/* Full conversation transcript */}
        {ui.transcript.map((turn, i) =>
          turn.role === 'user' ? (
            <div key={i} className="flex justify-end animate-fade-in">
              <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-accent/15 border border-accent-soft/40 px-4 py-2.5 text-sm text-text whitespace-pre-wrap">
                {turn.content}
              </div>
            </div>
          ) : (
            <AssistantBubble key={i} text={turn.content} />
          ),
        )}

        {/* Trace panel — the current run's reasoning (events cleared each run) */}
        {ui.events.length > 0 && <TracePanel />}

        {/* Live assistant preview while streaming (before the final turn is committed) */}
        {ui.isStreaming && ui.summary && <AssistantBubble text={ui.summary} />}

        {/* Thinking indicator while streaming with no summary yet */}
        {ui.isStreaming && !ui.summary && (
          <div className="flex items-center gap-2 text-xs text-text-muted animate-fade-in">
            <Sparkles size={12} className="text-accent-glow animate-pulse-dot" />
            <span>Working through it…</span>
          </div>
        )}

        {ui.error && (
          <div className="flex items-start gap-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            <AlertCircle size={14} className="mt-0.5" />
            <span>{ui.error}</span>
          </div>
        )}

        {/* Empty state */}
        {ui.transcript.length === 0 && !ui.isStreaming && (
          <EmptyState onPick={(q) => { setInput(q); submit(q); }} />
        )}
      </div>

      {/* Composer */}
      <div className="border-t border-border p-3">
        <div className="rounded-xl border border-border bg-bg-card focus-within:border-accent/60 transition-colors">
          <textarea
            ref={taRef}
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="Ask Copilot to find customers, score them, draft outreach…"
            className="w-full resize-none bg-transparent px-3 py-2.5 text-sm placeholder:text-text-dim focus:outline-none"
            disabled={ui.isStreaming}
          />
          <div className="flex items-center justify-between px-3 pb-2 pt-1">
            <div className="text-[11px] text-text-dim">
              Enter to send · Shift+Enter for newline
            </div>
            <button
              onClick={() => submit()}
              disabled={ui.isStreaming || input.trim() === ''}
              className={cn(
                'inline-flex items-center justify-center h-7 w-7 rounded-md transition-colors',
                ui.isStreaming || input.trim() === ''
                  ? 'bg-bg-soft text-text-dim cursor-not-allowed'
                  : 'bg-accent text-white hover:bg-accent-glow',
              )}
              aria-label="Send"
            >
              <ArrowUp size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AssistantBubble({ text }: { text: string }) {
  return (
    <div className="flex animate-fade-in">
      <div className="max-w-[88%] space-y-2">
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <Sparkles size={12} className="text-accent-glow" />
          <span>RM Copilot</span>
        </div>
        <div className="rounded-2xl rounded-tl-sm bg-bg-card border border-border px-4 py-3 text-sm leading-relaxed text-text whitespace-pre-wrap">
          {text}
        </div>
      </div>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="max-w-2xl mx-auto pt-6 animate-fade-in">
      <div className="text-center space-y-2">
        <div className="inline-flex items-center justify-center h-10 w-10 rounded-xl bg-accent/10 border border-accent-soft/30 text-accent-glow">
          <Sparkles size={18} />
        </div>
        <h2 className="text-lg font-semibold">Good morning, Rohan.</h2>
        <p className="text-sm text-text-muted">
          Ask in plain language. I’ll decompose, query the warehouse, score customers,
          and draft compliant WhatsApp outreach you can review and approve.
        </p>
      </div>
      <div className="mt-6 grid gap-2">
        {QUICK_PROMPTS.map((q, i) => (
          <button
            key={i}
            onClick={() => onPick(q)}
            className="text-left text-sm rounded-lg border border-border bg-bg-card hover:border-accent/40 hover:bg-bg-soft transition-colors px-4 py-3"
          >
            <span className="text-text">{q}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
