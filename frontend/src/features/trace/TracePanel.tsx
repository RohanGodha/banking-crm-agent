import { useState } from 'react';
import { useUi } from '@/store/uiStore';
import { ChevronDown, ChevronRight, Sparkles, Wrench, CheckCircle2, AlertTriangle, Zap, GitBranch, MessageSquare } from 'lucide-react';
import { cn } from '@/lib/cn';
import type { TraceEvent } from '@/lib/types';

const IconFor: Record<string, React.ReactNode> = {
  plan: <GitBranch size={12} />,
  tool_call: <Wrench size={12} />,
  tool_result: <CheckCircle2 size={12} />,
  critic: <AlertTriangle size={12} />,
  synth: <Sparkles size={12} />,
  candidate: <Zap size={12} />,
  draft: <MessageSquare size={12} />,
  final: <CheckCircle2 size={12} />,
};

export function TracePanel() {
  const events = useUi((s) => s.events);
  const isStreaming = useUi((s) => s.isStreaming);
  const [open, setOpen] = useState(true);

  // Filter out very low-signal events from the visible trace
  const visible = events.filter(
    (e) => !['token', 'candidate', 'draft', 'info'].includes(e.event),
  );

  return (
    <div className="rounded-2xl rounded-tl-sm bg-bg-card border border-border overflow-hidden animate-fade-in">
      <button
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-bg-soft transition-colors"
        onClick={() => setOpen((o) => !o)}
      >
        <div className="flex items-center gap-2 text-sm">
          <Sparkles size={13} className="text-accent-glow" />
          <span className="font-medium">Agent reasoning</span>
          {isStreaming && (
            <span className="badge-accent">
              <span className="animate-pulse-dot">●</span>&nbsp;running
            </span>
          )}
          <span className="text-[11px] text-text-dim">
            {visible.length} step{visible.length === 1 ? '' : 's'}
          </span>
        </div>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      {open && (
        <ul className="px-4 pb-3 pt-1 space-y-1.5">
          {visible.map((ev, i) => (
            <li key={i} className="animate-fade-in">
              <EventRow ev={ev} />
            </li>
          ))}
          {visible.length === 0 && (
            <li className="text-xs text-text-dim px-2 py-2">Waiting for plan…</li>
          )}
        </ul>
      )}
    </div>
  );
}

function EventRow({ ev }: { ev: TraceEvent }) {
  const d: any = ev.data || {};
  const icon = IconFor[ev.event] || <Wrench size={12} />;
  const route = ev.llm_route;

  let body: React.ReactNode = null;
  switch (ev.event) {
    case 'plan': {
      const plan = d.plan || d;
      body = (
        <div>
          <div className="text-text">
            Plan generated · target: <span className="text-accent-glow">{plan.target_product || d.target_product}</span>
            {plan.tone && <> · tone: <span className="text-text-muted">{plan.tone}</span></>}
          </div>
          <div className="text-text-dim text-[11px] mt-0.5">
            {(plan.steps || []).length} steps · intent: {plan.intent}
          </div>
        </div>
      );
      break;
    }
    case 'tool_call':
      body = (
        <div>
          <div className="text-text">
            <span className="font-mono text-[12px] text-accent-glow">{d.tool}</span>
            <span className="text-text-dim"> · step {d.step}</span>
          </div>
        </div>
      );
      break;
    case 'tool_result':
      body = (
        <div>
          <div className="text-text">
            <span className="font-mono text-[12px]">{d.tool}</span>
            <span className={cn('ml-2', d.ok ? 'text-positive' : 'text-danger')}>
              {d.ok ? 'ok' : 'fail'}
            </span>
            {d.rows != null && <span className="text-text-dim"> · {d.rows} rows</span>}
            {d.source && (
              <span className="ml-2 badge text-[10px]">source: {d.source}</span>
            )}
            {ev.latency_ms != null && (
              <span className="text-text-dim"> · {ev.latency_ms}ms</span>
            )}
          </div>
          {d.error && <div className="text-danger text-[11px] mt-0.5">{d.error}</div>}
        </div>
      );
      break;
    case 'critic':
      body = (
        <div>
          <div className="text-text">
            Critic: <span className={d.verdict === 'pass' ? 'text-positive' : 'text-warning'}>
              {d.verdict}
            </span>
            {d.replan && <span className="ml-1 text-warning">(replan)</span>}
          </div>
          <div className="text-text-dim text-[11px]">{d.notes}</div>
        </div>
      );
      break;
    case 'synth':
      body = (
        <div className="text-text">
          Synthesised {d.candidate_count} candidates
          {route && <span className="ml-2 badge-accent">{route}</span>}
        </div>
      );
      break;
    default:
      body = <div className="text-text-muted">{ev.event}</div>;
  }

  return (
    <div className="flex items-start gap-2 text-[12px]">
      <div className="mt-0.5 text-text-muted">{icon}</div>
      <div className="flex-1">{body}</div>
    </div>
  );
}
