import { useEffect, useState } from 'react';
import { useUi } from '@/store/uiStore';
import { api } from '@/lib/api';
import { inr, maskPhone, pct, relTime, truncate } from '@/lib/format';
import { cn } from '@/lib/cn';
import { X, Phone, MapPin, Briefcase, ShieldCheck, ListChecks, Wallet, Calendar, AlertTriangle, CheckCircle2, Sparkles } from 'lucide-react';
import { WhatsAppPreview } from './WhatsAppPreview';
import { ScoreBreakdownChart } from './ScoreBreakdownChart';
import { D3Loader } from '@/features/trace/D3Loader';

export function CustomerDrawer({ customerId }: { customerId: string }) {
  const close = useUi((s) => () => s.setSelectedCustomerId(null));
  const candidate = useUi((s) =>
    s.candidates.find((c) => c.customer_id === customerId) || null,
  );
  const draft = useUi((s) =>
    s.drafts.find((d) => d.customer_id === customerId) || null,
  );

  const [data, setData] = useState<{
    customer: any;
    source: string;
    transactions: any[];
    holdings: any[];
    interactions: any[];
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setErr(null);
    api
      .getCustomer(customerId)
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [customerId]);

  return (
    <>
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm animate-fade-in z-40"
        onClick={close}
      />
      <aside className="fixed right-0 top-0 h-screen w-[680px] max-w-[100vw] bg-bg border-l border-border shadow-2xl z-50 animate-fade-in overflow-hidden flex flex-col">
        <header className="h-12 px-4 flex items-center justify-between border-b border-border bg-bg-soft">
          <div className="flex items-center gap-2">
            <Sparkles size={14} className="text-accent-glow" />
            <span className="text-sm font-semibold">Customer 360</span>
          </div>
          <button onClick={close} className="btn-ghost p-1.5">
            <X size={14} />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {loading && <Skeleton />}
          {err && (
            <div className="text-sm text-danger flex items-center gap-2">
              <AlertTriangle size={14} /> {err}
            </div>
          )}
          {data && (
            <>
              <ProfileBlock customer={data.customer} source={data.source} candidate={candidate} />
              {candidate && (
                <Section title="Score breakdown" subtitle="Top features contributing to ranking">
                  <ScoreBreakdownChart features={candidate.top_features} />
                  <div className="mt-3 text-xs text-text-muted leading-relaxed">
                    {candidate.rationale}
                  </div>
                </Section>
              )}
              {draft && (
                <Section
                  title="WhatsApp draft"
                  subtitle={draft.compliance.ok
                    ? 'All numbers grounded · ready to send'
                    : `${(draft.compliance.ungrounded || []).length} ungrounded number(s) stripped`}
                  badge={
                    draft.compliance.ok ? (
                      <span className="badge-pos">
                        <CheckCircle2 size={11} /> compliance ok
                      </span>
                    ) : (
                      <span className="badge-warn">
                        <AlertTriangle size={11} /> redacted
                      </span>
                    )
                  }
                >
                  <WhatsAppPreview customer={data.customer} draft={draft} />
                </Section>
              )}
              <Section title="Holdings" subtitle={`${data.holdings.length} active`}>
                <ul className="space-y-1.5 text-sm">
                  {data.holdings.map((h: any) => (
                    <li key={h.product_id} className="flex items-center justify-between rounded-md bg-bg-card border border-border px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Briefcase size={12} className="text-text-muted" />
                        <span>{h.name}</span>
                      </div>
                      <span className="badge text-[10px]">{h.category}</span>
                    </li>
                  ))}
                  {data.holdings.length === 0 && (
                    <li className="text-text-dim text-xs">No active holdings.</li>
                  )}
                </ul>
              </Section>
              <Section title="Recent transactions" subtitle={`last 6 months · ${data.transactions.length} txns`}>
                <ul className="space-y-1 text-[12px]">
                  {data.transactions.slice(0, 8).map((t: any) => (
                    <li key={t.id} className="flex items-center justify-between rounded-md bg-bg-soft/60 px-3 py-1.5">
                      <div className="flex items-center gap-2 min-w-0">
                        <Calendar size={10} className="text-text-dim" />
                        <span className="text-text-muted text-[11px]">{relTime(t.ts)}</span>
                        <span className="text-text truncate">{t.merchant || t.category}</span>
                        <span className="badge text-[10px]">{t.category}</span>
                      </div>
                      <span className={cn('font-mono', t.amount > 0 ? 'text-positive' : 'text-danger')}>
                        {t.amount > 0 ? '+' : ''}
                        {inr(t.amount, { compact: true })}
                      </span>
                    </li>
                  ))}
                </ul>
              </Section>
              <Section title="Past interactions" subtitle={`${data.interactions.length} note(s) on file`}>
                <ul className="space-y-2 text-sm">
                  {data.interactions.map((i: any) => (
                    <li key={i.id} className="rounded-md bg-bg-card border border-border p-3">
                      <div className="flex items-center gap-2 text-[11px] text-text-muted mb-1">
                        <span className="badge text-[10px]">{i.channel}</span>
                        <span>{relTime(i.ts)}</span>
                      </div>
                      <div className="text-text leading-relaxed">{i.summary}</div>
                    </li>
                  ))}
                  {data.interactions.length === 0 && (
                    <li className="text-text-dim text-xs">No interactions recorded.</li>
                  )}
                </ul>
              </Section>
            </>
          )}
        </div>
      </aside>
    </>
  );
}

function ProfileBlock({
  customer,
  source,
  candidate,
}: {
  customer: any;
  source: string;
  candidate: any | null;
}) {
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-base font-semibold">{customer.name}</div>
          <div className="text-xs text-text-muted mt-0.5 flex items-center gap-3">
            <span className="inline-flex items-center gap-1">
              <MapPin size={11} /> {customer.city}
            </span>
            <span className="inline-flex items-center gap-1">
              <Phone size={11} /> {maskPhone(customer.phone)}
            </span>
            <span className="badge text-[10px]">{customer.segment}</span>
            <span className="badge text-[10px]">data: {source}</span>
            {candidate?.escalate && (
              <span className="badge-warn text-[10px]">
                {candidate.churn_risk ? 'churn risk' : 'escalate'}
              </span>
            )}
            {candidate?.sentiment && candidate.sentiment !== 'neutral' && (
              <span className={candidate.sentiment === 'negative' ? 'badge-neg text-[10px]' : 'badge-pos text-[10px]'}>
                {candidate.sentiment}
              </span>
            )}
          </div>
        </div>
        {candidate && (
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wider text-text-dim">Composite</div>
            <div className="text-xl font-semibold text-accent-glow">
              {Math.round(candidate.composite_score * 100)}
            </div>
            <div className="text-[10px] text-text-dim">
              v {pct(candidate.value_score)} · p {pct(candidate.propensity_score)}
            </div>
          </div>
        )}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
        <Stat label="Monthly income" value={inr(customer.monthly_income, { compact: true })} />
        <Stat label="Avg balance (6m)" value={inr(customer.avg_balance_6m, { compact: true })} />
        <Stat label="Tenure" value={truncate(customer.account_open_date, 10)} />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-md bg-bg-soft px-3 py-2 border border-border">
      <div className="text-[10px] uppercase tracking-wider text-text-dim">{label}</div>
      <div className="text-sm font-medium text-text mt-0.5">{value}</div>
    </div>
  );
}

function Section({
  title,
  subtitle,
  badge,
  children,
}: {
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-baseline gap-2">
          <h3 className="text-sm font-semibold">{title}</h3>
          {subtitle && <span className="text-[11px] text-text-dim">{subtitle}</span>}
        </div>
        {badge}
      </div>
      {children}
    </section>
  );
}

function Skeleton() {
  return (
    <div className="space-y-4">
      <div className="flex justify-center py-4">
        <D3Loader size={32} label="Loading customer 360…" />
      </div>
      <div className="h-24 rounded-lg bg-bg-soft animate-pulse" />
      <div className="h-32 rounded-lg bg-bg-soft animate-pulse" />
      <div className="h-40 rounded-lg bg-bg-soft animate-pulse" />
    </div>
  );
}
