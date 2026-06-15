/** Mirrors backend Pydantic models in TypeScript. */

export interface Customer {
  id: string;
  name: string;
  age: number;
  city: string;
  segment: 'mass' | 'mass_affluent' | 'affluent' | 'hnw';
  employment: string;
  monthly_income: number;
  account_open_date: string;
  kyc_status: string;
  phone: string;
  email?: string | null;
  risk_appetite: string;
  balance?: number | null;
  avg_balance_6m?: number | null;
}

export interface Transaction {
  id: string;
  customer_id: string;
  ts: string;
  amount: number;
  category: string;
  channel: string;
  merchant?: string | null;
}

export interface Holding {
  product_id: string;
  name: string;
  category: string;
  status: string;
  opened_at: string;
}

export interface Interaction {
  id: string;
  customer_id: string;
  ts: string;
  channel: string;
  summary: string;
}

export interface ScoreBreakdown {
  feature: string;
  value: number;
  contribution: number;
  direction: 'positive' | 'negative' | 'neutral';
  rationale: string;
  kind?: 'value' | 'propensity';
}

export interface CandidateRecord {
  customer_id: string;
  name: string;
  city: string;
  segment: string;
  value_score: number;
  propensity_score: number;
  composite_score: number;
  recommended_product_id: string;
  recommended_product_name: string;
  top_features: ScoreBreakdown[];
  rationale: string;
  citations: string[];
}

export interface DraftRecord {
  customer_id: string;
  product_id: string;
  message: string;
  compliance: {
    ok: boolean;
    numbers_in_draft?: string[];
    ungrounded?: string[];
    redacted_draft?: string;
  };
}

export type TraceEventName =
  | 'plan'
  | 'router'
  | 'tool_call'
  | 'tool_result'
  | 'critic'
  | 'synth'
  | 'candidate'
  | 'draft'
  | 'token'
  | 'final'
  | 'error'
  | 'info';

export interface TraceEvent {
  event: TraceEventName;
  ts: string;
  data: Record<string, unknown>;
  llm_route?: string | null;
  latency_ms?: number | null;
}

export interface SessionRow {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}
