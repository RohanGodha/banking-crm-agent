import { useEffect, useState } from 'react';
import { SessionsSidebar } from '@/features/sessions/SessionsSidebar';
import { ChatPane } from '@/features/chat/ChatPane';
import { CandidatesPanel } from '@/features/candidates/CandidatesPanel';
import { CustomerDrawer } from '@/features/drawer/CustomerDrawer';
import { useUi } from '@/store/uiStore';
import { api } from '@/lib/api';
import { LogOut, Activity, Server, BookOpen } from 'lucide-react';
import { GuidePanel } from '@/features/guide/GuidePanel';
import { useAgentStream } from '@/hooks/useAgentStream';

export function Dashboard({ onLogout }: { onLogout: () => void }) {
  const selected = useUi((s) => s.selectedCustomerId);
  const sessionId = useUi((s) => s.sessionId);
  const [guideOpen, setGuideOpen] = useState(false);
  const { run } = useAgentStream();
  const [status, setStatus] = useState<{
    datasource_active: string;
    datasource_healthy: boolean;
    llm_providers: Record<string, boolean>;
  } | null>(null);

  useEffect(() => {
    api.status().then(setStatus).catch(() => null);
  }, []);

  const llmActive = status
    ? Object.entries(status.llm_providers)
        .filter(([k, v]) => v && k !== 'mock')
        .map(([k]) => k)
    : [];
  const llmLabel = llmActive.length ? llmActive.join(' + ') : 'mock';

  return (
    <div className="h-screen flex flex-col bg-bg text-text">
      {/* Top bar */}
      <header className="h-12 flex items-center justify-between px-4 border-b border-border bg-bg-soft/60 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="h-7 w-7 rounded-md bg-accent/15 border border-accent-soft/40 flex items-center justify-center">
            <Activity size={14} className="text-accent-glow" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-semibold">RM Copilot</span>
            <span className="text-[11px] text-text-dim">Banking CRM Agent · for Rohan</span>
          </div>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-text-muted">
          {status && (
            <>
              <span className="badge"><Server size={11} /> {status.datasource_active}</span>
              <span className={status.datasource_healthy ? 'badge-pos' : 'badge-neg'}>
                {status.datasource_healthy ? 'data ok' : 'data degraded'}
              </span>
              <span className="badge-accent">llm: {llmLabel}</span>
            </>
          )}
          <button onClick={() => setGuideOpen(true)} className="btn-ghost text-xs" title="What can RM Copilot do?">
            <BookOpen size={13} />
            Guide
          </button>
          <button onClick={onLogout} className="btn-ghost text-xs">
            <LogOut size={13} />
            Sign out
          </button>
        </div>
      </header>

      <main className="flex-1 grid grid-cols-[260px_1fr_440px] overflow-hidden">
        <aside className="border-r border-border overflow-hidden">
          <SessionsSidebar />
        </aside>
        <section className="overflow-hidden">
          <ChatPane />
        </section>
        <aside className="border-l border-border overflow-hidden">
          <CandidatesPanel />
        </aside>
      </main>

      {selected && <CustomerDrawer customerId={selected} />}
      {guideOpen && (
        <GuidePanel
          onClose={() => setGuideOpen(false)}
          onRunPrompt={(q) => run({ query: q, sessionId })}
        />
      )}
    </div>
  );
}
