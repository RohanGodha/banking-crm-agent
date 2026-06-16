import { useEffect, useMemo, useRef } from 'react';
import * as d3 from 'd3';
import { useUi } from '@/store/uiStore';
import type { TraceEvent } from '@/lib/types';

/**
 * Live D3 pipeline visualization. As TraceEvents stream in, each stage node
 * transitions from pending -> active (pulsing) -> done, and a particle flows
 * along the connecting edges. Gives the agent a tangible "thinking + streaming"
 * feel without re-rendering React on every event.
 */
const STAGES = [
  { key: 'intent', label: 'Intent' },
  { key: 'plan', label: 'Plan' },
  { key: 'tools', label: 'Retrieve' },
  { key: 'critic', label: 'Critic' },
  { key: 'synth', label: 'Synthesize' },
  { key: 'draft', label: 'Draft' },
] as const;

type StageKey = (typeof STAGES)[number]['key'];

function computeProgress(events: TraceEvent[]): { reached: Set<StageKey>; active: StageKey | null; toolCount: number } {
  const reached = new Set<StageKey>();
  let active: StageKey | null = null;
  let toolCount = 0;
  for (const e of events) {
    switch (e.event) {
      case 'info':
        if ((e.data as any)?.node === 'intent') { reached.add('intent'); active = 'intent'; }
        break;
      case 'plan': reached.add('intent'); reached.add('plan'); active = 'plan'; break;
      case 'tool_call': reached.add('plan'); active = 'tools'; break;
      case 'tool_result': reached.add('tools'); active = 'tools'; toolCount += 1; break;
      case 'critic': reached.add('tools'); active = 'critic'; break;
      case 'synth': reached.add('critic'); reached.add('synth'); active = 'synth'; break;
      case 'candidate': reached.add('synth'); active = 'synth'; break;
      case 'draft': reached.add('synth'); active = 'draft'; break;
      case 'final': STAGES.forEach((s) => reached.add(s.key)); active = null; break;
    }
  }
  return { reached, active, toolCount };
}

export function AgentFlowD3() {
  const events = useUi((s) => s.events);
  const isStreaming = useUi((s) => s.isStreaming);
  const ref = useRef<SVGSVGElement | null>(null);
  const timerRef = useRef<d3.Timer | null>(null);

  const { reached, active, toolCount } = useMemo(() => computeProgress(events), [events]);

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();

    const W = 560;
    const H = 96;
    const pad = 46;
    const y = 42;
    const n = STAGES.length;
    const step = (W - pad * 2) / (n - 1);
    const xs = STAGES.map((_, i) => pad + i * step);

    svg.attr('viewBox', `0 0 ${W} ${H}`).attr('preserveAspectRatio', 'xMidYMid meet');

    // edges
    const edges = svg.append('g');
    for (let i = 0; i < n - 1; i++) {
      edges.append('line')
        .attr('x1', xs[i]).attr('y1', y).attr('x2', xs[i + 1]).attr('y2', y)
        .attr('stroke', '#1f2733').attr('stroke-width', 2);
      edges.append('line').attr('class', `edge-fill-${i}`)
        .attr('x1', xs[i]).attr('y1', y).attr('x2', xs[i]).attr('y2', y)
        .attr('stroke', '#3b82f6').attr('stroke-width', 2);
    }

    // nodes
    const node = svg.append('g');
    STAGES.forEach((s, i) => {
      const done = reached.has(s.key) && active !== s.key;
      const isActive = active === s.key;
      const g = node.append('g').attr('transform', `translate(${xs[i]},${y})`);
      g.append('circle').attr('class', `halo-${i}`).attr('r', 14)
        .attr('fill', 'none').attr('stroke', '#3b82f6')
        .attr('stroke-width', 2).attr('opacity', isActive ? 0.6 : 0);
      g.append('circle').attr('class', `core-${i}`).attr('r', 9)
        .attr('fill', done ? '#10b981' : isActive ? '#3b82f6' : '#141923')
        .attr('stroke', done ? '#10b981' : isActive ? '#60a5fa' : '#2a3344')
        .attr('stroke-width', 2);
      if (done) {
        g.append('path').attr('d', 'M-3.5,0 L-1,2.5 L4,-3')
          .attr('fill', 'none').attr('stroke', '#0a0d12').attr('stroke-width', 1.6)
          .attr('stroke-linecap', 'round').attr('stroke-linejoin', 'round');
      }
      g.append('text').attr('y', 28).attr('text-anchor', 'middle')
        .attr('fill', isActive ? '#e5e7eb' : done ? '#9aa3af' : '#6b7280')
        .attr('font-size', 10).attr('font-weight', isActive ? 600 : 400)
        .text(s.key === 'tools' && toolCount > 0 ? `Retrieve ·${toolCount}` : s.label);
    });

    // fill reached edges
    for (let i = 0; i < n - 1; i++) {
      if (reached.has(STAGES[i + 1].key)) {
        svg.select(`.edge-fill-${i}`).attr('x2', xs[i + 1]);
      }
    }

    // animate active node halo + flowing particle on the active edge
    const activeIdx = active ? STAGES.findIndex((s) => s.key === active) : -1;
    if (isStreaming) {
      const particle = svg.append('circle').attr('r', 3).attr('fill', '#60a5fa').attr('opacity', 0);
      timerRef.current?.stop();
      timerRef.current = d3.timer((elapsed) => {
        const t = elapsed / 1000;
        if (activeIdx >= 0) {
          const pulse = 14 + 4 * Math.sin(t * 5);
          svg.select(`.halo-${activeIdx}`).attr('r', pulse).attr('opacity', 0.35 + 0.3 * (0.5 + 0.5 * Math.sin(t * 5)));
        }
        // particle flows into the active node along the incoming edge
        if (activeIdx > 0) {
          const frac = (t % 1);
          const x = xs[activeIdx - 1] + (xs[activeIdx] - xs[activeIdx - 1]) * frac;
          particle.attr('cx', x).attr('cy', y).attr('opacity', 1 - frac);
        }
      });
    }

    return () => { timerRef.current?.stop(); };
  }, [reached, active, toolCount, isStreaming]);

  return <svg ref={ref} className="w-full h-[96px]" />;
}
