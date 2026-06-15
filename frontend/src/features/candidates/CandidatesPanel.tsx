import { useUi } from '@/store/uiStore';
import { inr, pct, truncate } from '@/lib/format';
import { cn } from '@/lib/cn';
import { MapPin, ShoppingBag, Zap, Users } from 'lucide-react';

const SEGMENT_LABEL: Record<string, string> = {
  hnw: 'HNW',
  affluent: 'Affluent',
  mass_affluent: 'Mass Affluent',
  mass: 'Mass',
};

export function CandidatesPanel() {
  const candidates = useUi((s) => s.candidates);
  const setSelected = useUi((s) => s.setSelectedCustomerId);
  const isStreaming = useUi((s) => s.isStreaming);

  return (
    <div className="h-full flex flex-col bg-bg-soft/40">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users size={14} className="text-accent-glow" />
          <span className="text-sm font-semibold">Candidates</span>
          <span className="text-[11px] text-text-dim">
            ({candidates.length}{isStreaming ? ' so far' : ''})
          </span>
        </div>
        {candidates.length > 0 && (
          <span className="text-[10px] text-text-dim">sorted by composite score</span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {candidates.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center px-6">
            <div className="h-10 w-10 rounded-xl bg-bg-card border border-border flex items-center justify-center text-text-dim">
              <Users size={16} />
            </div>
            <p className="mt-3 text-sm text-text-muted">No candidates yet.</p>
            <p className="text-[11px] text-text-dim">
              {isStreaming
                ? 'Agent is shortlisting…'
                : 'Send a question to begin.'}
            </p>
          </div>
        )}

        {candidates.map((c) => (
          <button
            key={c.customer_id}
            onClick={() => setSelected(c.customer_id)}
            className="w-full text-left card p-3 hover:border-accent/50 transition-colors animate-fade-in"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="font-medium text-sm truncate">{c.name}</div>
                <div className="text-[11px] text-text-muted flex items-center gap-2 mt-0.5">
                  <span className="inline-flex items-center gap-1">
                    <MapPin size={10} />
                    {c.city || '—'}
                  </span>
                  <span className="badge text-[10px]">{SEGMENT_LABEL[c.segment] || c.segment}</span>
                </div>
              </div>
              <ScoreRing score={c.composite_score} />
            </div>

            <div className="mt-2 flex items-center gap-2 text-[11px]">
              <ShoppingBag size={11} className="text-accent-glow" />
              <span className="text-text">{c.recommended_product_name}</span>
            </div>

            {c.top_features?.[0] && (
              <div className="mt-2 text-[11px] text-text-muted flex items-start gap-1">
                <Zap size={10} className="mt-0.5 text-accent-glow" />
                <span>{truncate(c.top_features[0].rationale, 88)}</span>
              </div>
            )}

            <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
              <KV k="Income" v={inr(extractIncome(c), { compact: true })} />
              <KV k="Value" v={pct(c.value_score)} />
              <KV k="Propensity" v={pct(c.propensity_score)} />
              <KV k="Citations" v={c.citations?.length || 0} />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function KV({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between">
      <span className="text-text-dim">{k}</span>
      <span className="text-text">{v}</span>
    </div>
  );
}

function ScoreRing({ score }: { score: number }) {
  const pctNum = Math.round(score * 100);
  const tone =
    pctNum >= 75 ? 'text-positive' : pctNum >= 55 ? 'text-accent-glow' : 'text-warning';
  return (
    <div
      className={cn(
        'h-9 w-9 rounded-full border flex items-center justify-center text-[11px] font-semibold',
        tone,
        pctNum >= 75
          ? 'border-positive/40 bg-positive/10'
          : pctNum >= 55
          ? 'border-accent-soft/50 bg-accent/10'
          : 'border-warning/40 bg-warning/10',
      )}
    >
      {pctNum}
    </div>
  );
}

function extractIncome(c: any): number | null {
  // We don't get income on the candidate event; the drawer fetches it. Show '—' for now.
  return null;
}
