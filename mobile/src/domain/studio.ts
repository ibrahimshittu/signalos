export type BrokerEnvironment = 'mainnet' | 'testnet';
export type ConnectionStatus =
  'pending' | 'verifying' | 'syncing' | 'healthy' | 'degraded' | 'failed' | 'revoked';
export type CredentialPurpose = 'broker_access';

export type InvestmentGoal = 'capital_growth' | 'income' | 'capital_preservation' | 'learning';
export type TimeHorizon = 'intraday' | 'swing' | 'medium_term' | 'long_term';
export type LiquidityNeed = 'low' | 'moderate' | 'high';
export type ExperienceLevel = 'none' | 'beginner' | 'intermediate' | 'advanced';
export type TradedProduct =
  'stocks_etfs' | 'crypto_spot' | 'options' | 'futures' | 'forex' | 'managed_portfolios';
export type DecisionFrequency = 'first_time' | 'few_per_year' | 'monthly' | 'weekly' | 'daily';
export type DrawdownResponse = 'exit' | 'reduce' | 'hold' | 'add' | 'unsure';
export type HoldingPeriod = 'intraday' | 'multi_day' | 'multi_week' | 'long_term';
export type ExplanationDetail = 'concise' | 'standard' | 'detailed';
export type NotificationFrequency = 'critical_only' | 'opportunities_only' | 'daily_digest';

/** Decimal values are strings because the backend serializes Pydantic Decimal fields losslessly. */
export interface InvestmentProfileInput {
  goals: InvestmentGoal[];
  /** Deprecated compatibility field. Sizing uses synchronized broker equity. */
  intended_capital?: string | null;
  time_horizon: TimeHorizon;
  liquidity_need: LiquidityNeed;
  investing_experience: ExperienceLevel;
  trading_experience: ExperienceLevel;
  products_traded: TradedProduct[];
  decision_frequency: DecisionFrequency;
  drawdown_response: DrawdownResponse;
  holding_periods: HoldingPeriod[];
  explanation_detail: ExplanationDetail;
  notification_frequency: NotificationFrequency;
  disclosures_accepted: boolean;
}

export interface InvestmentProfile extends InvestmentProfileInput {
  user_id: string;
  disclosures_accepted_at: string | null;
  created_at: string;
  updated_at: string;
  adaptive_mandate: AdaptiveRiskMandate;
}

export interface AdaptiveRiskMandate {
  risk_posture: 'capital_protective' | 'measured' | 'selective_growth';
  max_loss_per_trade_pct: string;
  max_portfolio_drawdown_pct: string;
  max_leverage: string;
  derivatives_eligible: boolean;
  reasons: string[];
  policy_version: string;
}

export interface OnboardingState {
  investment_profile_completed: boolean;
  disclosures_accepted: boolean;
  broker_account_read_connected: boolean;
  initial_account_sync_completed: boolean;
  studio_unlocked: boolean;
  missing_requirements: string[];
  investment_profile: InvestmentProfile | null;
  broker_connection: BrokerConnection | null;
}

export interface PersonalizedPreferences {
  investor_summary: string;
  priority_objectives: string[];
  preferred_markets: MarketCategory[];
  preferred_strategy_families: (
    | 'trend'
    | 'momentum'
    | 'mean_reversion'
    | 'breakout'
    | 'session'
    | 'volatility'
    | 'funding_carry'
    | 'microstructure'
  )[];
  preferred_sessions: ('tokyo' | 'london' | 'new_york' | 'utc_rollover' | 'funding')[];
  holding_periods: HoldingPeriod[];
  explanation_detail: ExplanationDetail;
  notification_frequency: NotificationFrequency;
  avoid_conditions: string[];
  rationale: string[];
}
export type PersonalizedPreferencesUpdate = Partial<
  Omit<PersonalizedPreferences, 'investor_summary' | 'priority_objectives' | 'rationale'>
>;
export interface PersonalizedPolicy {
  preferences: PersonalizedPreferences;
  safety_mandate: AdaptiveRiskMandate;
  source: string;
  updated_at: string;
}

export interface BrokerProvider {
  id: 'bybit';
  display_name: string;
  status: 'enabled' | 'coming_soon';
  default_environment: BrokerEnvironment;
  supported_environments: BrokerEnvironment[];
  supports_account_read: boolean;
  supports_trading: boolean;
}

export interface BrokerConnection {
  id: string;
  provider_id: 'bybit';
  environment: BrokerEnvironment;
  status: ConnectionStatus;
  external_uid: string | null;
  spot_trading_enabled: boolean;
  derivatives_trading_enabled: boolean;
  credential_purposes: CredentialPurpose[];
  last_verified_at: string | null;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BrokerCredentialsInput {
  api_key: string;
  api_secret: string;
}

export interface CreateBrokerConnectionInput extends BrokerCredentialsInput {
  provider_id: 'bybit';
  environment: BrokerEnvironment;
}

export interface BrokerContext {
  user_id: string;
  environment: BrokerEnvironment;
  connection_id: string;
  switched_at: string;
  invalidated_proposals: number;
}

export interface AccountBalance {
  coin: string;
  wallet_balance: string;
  equity: string;
  available_to_withdraw: string;
}

export interface PortfolioSummary {
  connection_id: string;
  provider_id: 'bybit';
  environment: BrokerEnvironment;
  account_type: string;
  total_equity: string;
  available_balance: string;
  invested_value: string;
  balances: AccountBalance[];
  captured_at: string;
}

export interface BrokerPosition {
  id: string;
  connection_id: string;
  environment: BrokerEnvironment;
  state: 'open' | 'closed';
  category: MarketCategory;
  symbol: string;
  position_index: number;
  side: 'buy' | 'sell';
  size: string;
  average_price: string;
  position_value: string;
  leverage: string | null;
  mark_price: string;
  liquidation_price: string | null;
  take_profit: string | null;
  stop_loss: string | null;
  unrealised_pnl: string;
  cumulative_realised_pnl: string;
  broker_updated_at: string;
  opened_at: string;
  closed_at: string | null;
  last_reconciled_at: string;
}

export type MarketCategory = 'spot' | 'linear';

export interface MarketCandidate {
  category: MarketCategory;
  symbol: string;
  activity_score: string;
  turnover_24h: string;
  price_change_24h: string;
  spread_bps: string;
  observed_at: string;
}

export interface MarketScan {
  id: string;
  environment: BrokerEnvironment;
  source_count: number;
  observed_at: string;
  created_at: string;
  result: {
    hot_universe: MarketCandidate[];
    agent_shortlist: MarketCandidate[];
  };
}

export type MarketReviewStatus =
  | 'model_unavailable'
  | 'market_data_unavailable'
  | 'no_approved_strategy'
  | 'no_strategy_match'
  | 'evidence_gate_rejected'
  | 'no_valid_signal'
  | 'ai_no_trade'
  | 'passed_market_checks';

export interface MarketReviewCandidate {
  portfolio_review?: { code: string; reason: string; evaluated_at: string } | null;
  category: MarketCategory;
  symbol: string;
  rank: number;
  status: MarketReviewStatus;
  reason: string;
  strategy_id: string | null;
}

export interface MarketReview {
  scan_id: string;
  environment: BrokerEnvironment;
  analyzed_at: string;
  approved_strategies: number;
  candidates_considered: number;
  strategy_matches: number;
  signals_found: number;
  analysis_completed: number;
  no_trade_decisions: number;
  proposals_created: number;
  duplicates_skipped: number;
  gate_rejections: number;
  model_available: boolean;
  candidates: MarketReviewCandidate[];
}

export type MarketAnalysisRequestStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface MarketAnalysisRequest {
  id: string;
  environment: BrokerEnvironment;
  status: MarketAnalysisRequestStatus;
  requested_at: string;
  started_at: string | null;
  completed_at: string | null;
  scan_id: string | null;
  error_code: string | null;
}

export type ProposalStatus =
  'available' | 'submitted' | 'rejected' | 'expired' | 'invalidated' | 'archived';

export interface TradeProposal {
  id: string;
  user_id: string;
  connection_id: string;
  environment: BrokerEnvironment;
  strategy_id: string;
  strategy_version: string;
  strategy_family: string;
  category: MarketCategory;
  symbol: string;
  side: 'buy' | 'sell';
  order_type: 'market' | 'limit';
  quantity: string;
  limit_price: string | null;
  stop_loss: string;
  take_profit: string;
  leverage: string;
  estimated_fees: string;
  estimated_funding: string;
  estimated_slippage: string;
  estimated_max_loss: string;
  market_price: string;
  market_observed_at: string;
  expires_at: string;
  thesis: string;
  opposing_case: string;
  why_it_fits: string;
  why_reject: string;
  gate_report: { passed: boolean; failures: string[] };
  status: ProposalStatus;
  proposal_hash: string;
  created_at: string;
  updated_at: string;
}

export interface OrderTicket {
  proposal_id: string;
  proposal_hash: string;
  provider_id: string;
  environment: BrokerEnvironment;
  category: MarketCategory;
  symbol: string;
  side: TradeProposal['side'];
  order_type: TradeProposal['order_type'];
  quantity: string;
  limit_price: string | null;
  stop_loss: string;
  take_profit: string;
  leverage: string;
  estimated_max_loss: string;
  proposal_expires_at: string;
}

export interface OrderReview {
  id: string;
  user_id: string;
  ticket: OrderTicket;
  expires_at: string;
  created_at: string;
}

export interface SubmitOrderInput {
  review_id: string;
  proposal_hash: string;
  idempotency_key: string;
}

export type BrokerOrderState =
  | 'submitting'
  | 'acknowledged'
  | 'partially_filled'
  | 'filled'
  | 'cancelling'
  | 'cancelled'
  | 'rejected'
  | 'submission_unknown'
  | 'reconciliation_required';

export interface BrokerOrder {
  id: string;
  user_id: string;
  proposal_id: string;
  connection_id: string;
  environment: BrokerEnvironment;
  state: BrokerOrderState;
  idempotency_key: string;
  broker_order_link_id: string;
  broker_order_id: string | null;
  error_code: string | null;
  created_at: string;
  updated_at: string;
  category: MarketCategory | null;
  symbol: string | null;
  side: TradeProposal['side'] | null;
  order_type: TradeProposal['order_type'] | null;
  quantity: string;
  cumulative_executed_quantity: string;
  leaves_quantity: string;
  average_price: string | null;
  broker_status: string | null;
  last_reconciled_at: string | null;
}

export interface ProposalFeedbackInput {
  reason: string;
  comment?: string;
}

export type ExecutionActionType = 'cancel_order' | 'close_position' | 'update_protection';
export interface ExecutionActionReview {
  id: string;
  action_hash: string;
  expires_at: string;
  terms: {
    action_type: ExecutionActionType;
    target_id: string;
    connection_id: string;
    environment: BrokerEnvironment;
    category: MarketCategory;
    symbol: string;
    quantity: string | null;
    side: 'buy' | 'sell' | null;
    mark_price: string | null;
    stop_loss: string | null;
    take_profit: string | null;
  };
}
export interface ConfirmExecutionActionInput {
  review_id: string;
  action_hash: string;
  idempotency_key: string;
}
export interface ExecutionAction {
  id: string;
  target_id: string;
  state: 'submitting' | 'acknowledged' | 'completed' | 'rejected' | 'reconciliation_required';
  error_code: string | null;
  updated_at: string;
}
export interface UpdateProtectionInput {
  stop_loss?: string;
  take_profit?: string;
}

export interface UserMemory {
  id: string;
  user_id: string;
  kind: 'account' | 'episodic' | 'learned_preference';
  key: string;
  value: Record<string, unknown>;
  source: 'account_sync' | 'explicit_feedback' | 'behavior_inference';
  confidence: string;
  evidence_count: number;
  created_at: string;
  updated_at: string;
  expires_at: string | null;
}

export interface InvestmentStudioApi {
  registerNotificationDevice(
    installationId: string,
    input: { platform: 'ios' | 'android'; expo_push_token: string; expo_project_id: string },
  ): Promise<void>;
  removeNotificationDevice(installationId: string): Promise<void>;
  getOnboardingState(): Promise<OnboardingState>;
  getInvestmentProfile(): Promise<InvestmentProfile | null>;
  saveInvestmentProfile(input: InvestmentProfileInput): Promise<InvestmentProfile>;
  getPersonalization(): Promise<PersonalizedPolicy | null>;
  updatePersonalization(input: PersonalizedPreferencesUpdate): Promise<PersonalizedPolicy>;
  generatePersonalization(): Promise<PersonalizedPolicy>;
  listBrokerProviders(): Promise<BrokerProvider[]>;
  createBrokerConnection(input: CreateBrokerConnectionInput): Promise<BrokerConnection>;
  getBrokerConnection(connectionId: string): Promise<BrokerConnection>;
  deleteBrokerConnection(connectionId: string): Promise<void>;
  verifyBrokerConnection(connectionId: string): Promise<BrokerConnection>;
  syncBrokerConnection(connectionId: string): Promise<BrokerConnection>;
  switchBrokerContext(connectionId: string, environment: BrokerEnvironment): Promise<BrokerContext>;
  getPortfolioSummary(): Promise<PortfolioSummary | null>;
  listOpenPositions(connectionId?: string): Promise<BrokerPosition[]>;
  getPosition(positionId: string): Promise<BrokerPosition>;
  createExecutionReview(
    type: ExecutionActionType,
    targetId: string,
    protection?: UpdateProtectionInput,
  ): Promise<ExecutionActionReview>;
  confirmExecutionAction(
    type: ExecutionActionType,
    targetId: string,
    input: ConfirmExecutionActionInput,
  ): Promise<ExecutionAction>;
  getExecutionAction(actionId: string): Promise<ExecutionAction>;
  getLatestMarketScan(environment: BrokerEnvironment): Promise<MarketScan | null>;
  runMarketScan(environment: BrokerEnvironment): Promise<MarketScan>;
  getLatestMarketReview(environment: BrokerEnvironment): Promise<MarketReview | null>;
  requestMarketAnalysis(environment: BrokerEnvironment): Promise<MarketAnalysisRequest>;
  getMarketAnalysisRequest(requestId: string): Promise<MarketAnalysisRequest>;
  listTradeProposals(connectionId?: string): Promise<TradeProposal[]>;
  getTradeProposal(proposalId: string): Promise<TradeProposal | null>;
  rejectTradeProposal(proposalId: string): Promise<TradeProposal>;
  addTradeProposalFeedback(proposalId: string, input: ProposalFeedbackInput): Promise<void>;
  createOrderReview(proposalId: string): Promise<OrderReview>;
  submitTradeOrder(proposalId: string, input: SubmitOrderInput): Promise<BrokerOrder>;
  listBrokerOrders(proposalId: string): Promise<BrokerOrder[]>;
  listMemory(): Promise<UserMemory[]>;
  deleteMemory(memoryId: string): Promise<void>;
  resetLearnedPreferences(): Promise<void>;
}
