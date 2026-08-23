// Hand-written mirrors of backend/models/containment.py — keep in sync in the same edit.

export const DIMENSIONS = 14;

export interface Dimension {
  index: number;
  label: string;
  unit: string;
  min: number;
  max: number;
}

export interface Constraint {
  id: string;
  label: string;
  coeffs: number[];
  b: number;
}

export interface Profile {
  id: string;
  name: string;
  description: string;
  dimensions: Dimension[];
  constraints: Constraint[];
  center: number[];
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProfileUpdate {
  name?: string;
  description?: string;
  dimensions?: Dimension[];
  constraints?: Constraint[];
  center?: number[];
}

export interface MarginRow {
  constraint_id: string;
  label: string;
  slack: number;
  normalized: number;
  binding: boolean;
  violated: boolean;
}

export interface MarginReport {
  profile_id: string;
  profile_name: string;
  center: number[];
  feasible: boolean;
  min_margin: number;
  tightest: string | null;
  rows: MarginRow[];
}

export interface ContainRequest {
  vector: number[];
  source?: string;
  label?: string;
}

export interface ContainEvent {
  id: string;
  profile_id: string;
  profile_name: string;
  client_id: string | null;
  client_name: string | null;
  label: string;
  source: string;
  vector: number[];
  residuals: number[];
  max_residual: number;
  status: "permitted" | "corrected" | "revised" | "withheld";
  mode: string | null;
  attempts: number;
  projected_vector: number[] | null;
  correction_magnitude: number;
  violated_constraints: string[];
  latency_ms: number;
  iterations: number;
  created_at: string;
}

export interface SimulateResult {
  generated: number;
  corrected: number;
  events: ContainEvent[];
}

export interface HistogramBucket {
  label: string;
  count: number;
}

export interface TrendPoint {
  bucket: string;
  total: number;
  corrected: number;
}

export interface ConstraintHit {
  label: string;
  count: number;
}

export interface ClientSplit {
  client_name: string;
  permitted: number;
  corrected: number;
}

export interface Client {
  id: string;
  name: string;
  description: string;
  key_prefix: string;
  profile_id: string | null;
  profile_name: string | null;
  rate_limit_per_min: number | null;
  active: boolean;
  enforcement_mode: string | null;
  created_at: string;
  rotated_at: string | null;
  last_seen_at: string | null;
}

export interface ClientCreate {
  name: string;
  description?: string;
  profile_id?: string | null;
  rate_limit_per_min?: number | null;
}

export interface ClientPatch {
  rate_limit_per_min?: number | null;
  inherit_rate_limit?: boolean;
  profile_id?: string | null;
  clear_profile_pin?: boolean;
  enforcement_mode?: string | null;
  inherit_enforcement_mode?: boolean;
}

export interface ClientCreated {
  client: Client;
  api_key: string;
}

export interface ClientStat {
  client_id: string;
  client_name: string;
  key_prefix: string;
  active: boolean;
  profile_name: string | null;
  calls: number;
  corrected: number;
  violation_rate: number;
  mean_correction: number;
  p99_latency_ms: number;
  last_seen_at: string | null;
  rate_limit_per_min: number | null;
  effective_limit: number | null;
  enforcement_mode: string | null;
  effective_mode: string;
  usage_last_min: number;
  throttled: boolean;
}

export interface ClientStatsResponse {
  stats: ClientStat[];
  unattributed_calls: number;
}

export interface EngineSettings {
  id: string;
  enforce_api_keys: boolean;
  rate_limit_enabled: boolean;
  rate_limit_default_per_min: number;
  enforcement_mode: string;
  max_reflections: number;
  updated_at: string;
}

export interface EngineSettingsUpdate {
  enforce_api_keys?: boolean;
  rate_limit_enabled?: boolean;
  rate_limit_default_per_min?: number;
  enforcement_mode?: string;
  max_reflections?: number;
}

export interface GateRequest {
  text: string;
  context?: string;
  label?: string;
  mode?: string | null;
  max_reflections?: number | null;
}

export interface ReflectionStep {
  attempt: number;
  text: string;
  vector: number[];
  max_residual: number;
  violated_constraints: string[];
  feasible: boolean;
  correction_magnitude: number;
  note: string;
}

export interface WisdomReport {
  applied: boolean;
  overconfidence_detected: boolean;
  humility_added: boolean;
  validation_suggested: boolean;
  adjustments: string[];
}

export interface GateResponse {
  decision: "permitted" | "corrected" | "revised" | "withheld";
  mode: string;
  mode_source: string;
  profile_id: string;
  profile_name: string;
  client_name: string | null;
  dimension_names: string[];
  encoded_vector: number[];
  final_vector: number[] | null;
  final_text: string | null;
  max_residual: number;
  correction_magnitude: number;
  alignment_score: number;
  violated_constraints: string[];
  attempts: number;
  iterations: number;
  steps: ReflectionStep[];
  wisdom: WisdomReport;
  latency_ms: number;
  event_id: string;
  withheld_reason: string | null;
}

export interface EncodeResponse {
  vector: number[];
  dimension_names: string[];
}

// Mirrors backend/models/chat.py
export interface ChatSession {
  id: string;
  title: string;
  client_id: string | null;
  client_name: string | null;
  profile_id: string;
  profile_name: string;
  mode: string | null;
  model: string;
  turns: number;
  withheld: number;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionCreate {
  title?: string;
  mode?: string | null;
}

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: "admin" | "operator";
  active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

export interface UserCreate {
  email: string;
  name?: string;
  password: string;
  role: string;
}

export interface PasswordChange {
  current_password: string;
  new_password: string;
}

export interface ChatExport {
  session_id: string;
  filename: string;
  content: string;
  turns: number;
}

export interface ChatTurn {
  id: string;
  session_id: string;
  user_text: string;
  draft_text: string;
  released_text: string | null;
  decision: "permitted" | "corrected" | "revised" | "withheld";
  mode: string;
  encoded_vector: number[];
  final_vector: number[] | null;
  dimension_names: string[];
  violated_constraints: string[];
  why: string[];
  suggested_rewrite: string | null;
  max_residual: number;
  correction_magnitude: number;
  alignment_score: number;
  attempts: number;
  steps: ReflectionStep[];
  wisdom: string[];
  withheld_reason: string | null;
  latency_ms: number;
  event_id: string;
  created_at: string;
}

export interface TelemetrySummary {
  active_profile: string | null;
  active_profile_id: string | null;
  engine_status: string;
  dimensions: number;
  constraint_count: number;
  total_events: number;
  permitted: number;
  corrected: number;
  withheld: number;
  revised: number;
  enforcement_mode: string;
  violation_rate: number;
  mean_correction: number;
  max_correction: number;
  mean_latency_ms: number;
  p50_latency_ms: number;
  p99_latency_ms: number;
  throughput_per_min: number;
  latency_histogram: HistogramBucket[];
  violation_trend: TrendPoint[];
  top_constraints: ConstraintHit[];
  by_client: ClientSplit[];
  enforce_api_keys: boolean;
  client_count: number;
}

export interface AuditEntry {
  id: string;
  action: string;
  detail: string;
  actor: string;
  created_at: string;
}
