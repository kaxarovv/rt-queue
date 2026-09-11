export type DocumentStatus =
  | 'pending'
  | 'text_extracted'
  | 'llm_processed'
  | 'needs_review'
  | 'reviewed'
  | 'failed';

export interface ConflictInfo {
  reason: string;
  explanation?: string;
  requires_mandatory_doctor_decision: boolean;
}

export interface UrgencySignals {
  pain_or_bleeding_mentioned?: boolean;
  mass_effect_or_compression?: boolean;
  ecog_score?: number | null;
  symptom_acuity_note?: string;
}

export interface LlmExtraction {
  diagnosis_text: string;
  icd10_code: string | null;
  treatment_modality: string;
  clinical_pathway: string | null;
  urgency_signals: UrgencySignals;
  sessions_required: number | null;
  fractions_per_week: number | null;
  confidence: Record<string, number>;
}

export interface RegexExtraction {
  icd10_codes: string[];
  iin_candidates: { value: string; checksum_valid: boolean; position: number }[];
  dates_found_count: number;
}

export interface SourceDocument {
  id: string;
  original_filename: string;
  status: DocumentStatus;
  extracted_entities: {
    llm?: LlmExtraction;
    regex?: RegexExtraction;
  };
  confidence_scores: Record<string, number>;
  conflict_info: ConflictInfo | null;
  error_message: string | null;
  created_at: string;
  case_id: string | null;
}

export interface Patient {
  id: string;
  iin: string;
  full_name: string;
  birth_date: string | null;
  created_at: string;
}

export type PriorityCategory = 'immediate' | 'urgent_1_2w' | 'planned_1_2m' | 'low_3m';

export const PRIORITY_LABELS: Record<PriorityCategory, string> = {
  immediate: 'Сразу начать',
  urgent_1_2w: '1–2 недели',
  planned_1_2m: '1–2 месяца',
  low_3m: 'Через 3 месяца',
};

export interface TreatmentCase {
  id: string;
  patient_id: string;
  diagnosis_text: string;
  icd10_code: string | null;
  treatment_modality: string;
  clinical_pathway: string | null;
  urgency_signals: UrgencySignals;
  priority_category: PriorityCategory | null;
  priority_score: number | null;
  has_signal_conflict: boolean;
  sessions_required: number;
  sessions_completed: number;
  fractions_per_week: number | null;
  status: string;
  clinical_deadline_date: string | null;
  planned_start_date: string | null;
  confirmed_by_doctor: string | null;
  confirmed_at: string | null;
  created_at: string;
}

export interface SuggestedDate {
  date: string;
  month_occupied: number;
  month_capacity: number;
  within_clinical_deadline: boolean;
}

export interface QueueByPriority {
  category: PriorityCategory;
  count: number;
}

export interface CapacityByMonth {
  year: number;
  month: number;
  occupied: number;
  capacity: number;
}

export interface AvgWaitByPriority {
  category: PriorityCategory;
  avg_days: number | null;
  sample_size: number;
}

export interface DashboardStats {
  queue_by_priority: QueueByPriority[];
  capacity_by_month: CapacityByMonth[];
  avg_wait_by_priority: AvgWaitByPriority[];
}

export interface DisplacementCandidate {
  session_id: string;
  slot_id: string;
  treatment_case_id: string;
  patient_name: string;
  original_date: string;
  proposed_new_date: string | null;
  proposed_new_slot_id: string | null;
  damage_score: number;
  explanation: string;
}

export interface BookingResult {
  booked: boolean;
  treatment_case: TreatmentCase;
  booked_session_ids: string[];
  displacement_candidates: DisplacementCandidate[];
  message: string;
}

export interface MachineSlot {
  id: string;
  slot_date: string;
  time_start: string;
  time_end: string;
  status: 'free' | 'booked' | 'blocked_maintenance';
}
