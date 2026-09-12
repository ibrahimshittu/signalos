export type IntelligenceMode = 'fast' | 'deep';
export type IntelligenceRunStatus =
  | 'queued'
  | 'researching'
  | 'verifying'
  | 'published'
  | 'quarantined'
  | 'rejected';

export interface IntelligenceQuestion {
  question: string;
  accountId?: string;
  contextEntityIds?: string[];
  mode?: IntelligenceMode;
}

export interface IntelligenceRun {
  id: string;
  request: {
    question: string;
    account_id?: string;
    context_entity_ids: string[];
    mode: IntelligenceMode;
  };
  status: IntelligenceRunStatus;
  report_id?: string;
  created_at: string;
  updated_at: string;
}

export interface IntelligenceEvent {
  id: string;
  run_id: string;
  sequence: number;
  kind: 'queued' | 'routing' | 'research' | 'calculation' | 'verification' | 'published' | 'failed';
  message: string;
  created_at: string;
}

export interface IntelligenceCitation {
  claim_id: string;
  source_id: string;
  label: string;
}

export interface IntelligenceReport {
  id: string;
  question_id?: string;
  title: string;
  executive_view: string;
  what_changed: string[];
  verified_facts: string[];
  quantitative_snapshot: { metrics: Record<string, string | number>; calculation_ids: string[] };
  strategy_interpretations: string[];
  bull_scenario: string;
  base_scenario: string;
  bear_scenario: string;
  portfolio_relevance: string;
  drivers: string[];
  risks_and_thesis_breakers: string[];
  monitoring_questions: string[];
  evidence_quality: string;
  source_coverage: string;
  citations: IntelligenceCitation[];
  data_as_of: string;
  limitations: string[];
  disputed_claims: string[];
}

