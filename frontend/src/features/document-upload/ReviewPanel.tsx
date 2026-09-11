import { useState } from 'react';
import { api } from '../../shared/api/client';
import type { PriorityCategory, SourceDocument } from '../../shared/types';
import { PRIORITY_LABELS } from '../../shared/types';
import { PriorityBadge } from '../../shared/components/PriorityBadge';
import styles from './ReviewPanel.module.css';

const PATHWAY_LABELS: Record<string, string> = {
  acute_symptomatic: 'Острая симптоматика (боль/кровотечение)',
  awaiting_lab_results: 'Ожидание результатов анализов',
  post_surgery_planned: 'Плановое продолжение после операции',
  post_chemo_hormone: 'После химио/гормонотерапии',
};

const PATHWAY_TO_PRIORITY: Record<string, PriorityCategory> = {
  acute_symptomatic: 'immediate',
  awaiting_lab_results: 'urgent_1_2w',
  post_surgery_planned: 'planned_1_2m',
  post_chemo_hormone: 'low_3m',
};

function confidencePercent(v: number | undefined): string {
  if (v === undefined) return '—';
  return v <= 1 ? `${Math.round(v * 100)}%` : `${Math.round(v)}%`;
}

interface Props {
  document: SourceDocument;
  onExtract: (id: string) => Promise<void>;
  onCaseCreated: () => void;
  extracting: boolean;
}

export function ReviewPanel({ document, onExtract, onCaseCreated, extracting }: Props) {
  const llm = document.extracted_entities.llm;
  const regex = document.extracted_entities.regex;

  const [iin, setIin] = useState('');
  const [fullName, setFullName] = useState('');
  const [diagnosis, setDiagnosis] = useState(llm?.diagnosis_text ?? '');
  const [icd10, setIcd10] = useState(llm?.icd10_code ?? regex?.icd10_codes[0] ?? '');
  const [modality, setModality] = useState(llm?.treatment_modality ?? 'unknown');
  const [pathway, setPathway] = useState(llm?.clinical_pathway ?? '');
  const [priorityCategory, setPriorityCategory] = useState<PriorityCategory | ''>(
    llm?.clinical_pathway && !document.conflict_info
      ? PATHWAY_TO_PRIORITY[llm.clinical_pathway]
      : ''
  );
  const [sessionsRequired, setSessionsRequired] = useState(llm?.sessions_required ?? 1);
  const [fractionsPerWeek, setFractionsPerWeek] = useState(llm?.fractions_per_week ?? undefined);
  const [doctorName, setDoctorName] = useState('');
  const [reasonNote, setReasonNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedCase, setSavedCase] = useState(false);

  const hasConflict = !!document.conflict_info;
  const canSubmit =
    iin.trim().length > 0 &&
    fullName.trim().length > 0 &&
    diagnosis.trim().length > 0 &&
    priorityCategory !== '' &&
    doctorName.trim().length > 0 &&
    (!hasConflict || reasonNote.trim().length > 0);

  async function handleCreateCase() {
    setSaving(true);
    setSaveError(null);
    try {
      const patient = await api.createPatient({ iin: iin.trim(), full_name: fullName.trim() });
      await api.createCase({
        patient_id: patient.id,
        source_document_id: document.id,
        diagnosis_text: diagnosis,
        icd10_code: icd10 || null,
        treatment_modality: modality,
        clinical_pathway: pathway || null,
        urgency_signals: llm?.urgency_signals ?? {},
        priority_category: priorityCategory,
        has_signal_conflict: hasConflict,
        sessions_required: sessionsRequired,
        fractions_per_week: fractionsPerWeek ?? null,
        confirmed_by_doctor: doctorName.trim(),
      });
      setSavedCase(true);
      onCaseCreated();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Не удалось создать случай');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.split}>
      <div className={styles.pdfColumn}>
        <iframe
          key={document.id}
          title="Медицинская карта"
          src={api.documentFileUrl(document.id)}
          className={styles.pdfFrame}
        />
      </div>

      <div className={styles.fieldsColumn}>
        <h2 className={styles.title}>{document.original_filename}</h2>

        {document.status === 'text_extracted' && (
          <div className={styles.callToAction}>
            <p>Текст извлечён. Запустите ИИ-анализ, чтобы получить диагноз и приоритет.</p>
            <button
              className={styles.primaryButton}
              onClick={() => onExtract(document.id)}
              disabled={extracting}
            >
              {extracting ? 'Анализируем…' : 'Извлечь данные через ИИ'}
            </button>
          </div>
        )}

        {document.error_message && (
          <div className={styles.errorBanner}>
            <strong>Проблема при обработке:</strong> {document.error_message}
          </div>
        )}

        {hasConflict && (
          <div className={styles.conflictBanner}>
            <div className={styles.conflictHeader}>
              <span className={styles.conflictIcon} aria-hidden>
                ⚠
              </span>
              <strong>Требуется решение врача</strong>
            </div>
            <p className={styles.conflictText}>{document.conflict_info!.explanation}</p>
          </div>
        )}

        {llm && (
          <div className={styles.fieldsGrid}>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>
                Диагноз{' '}
                <span className={styles.confidence}>
                  {confidencePercent(llm.confidence?.diagnosis_text)}
                </span>
              </span>
              <textarea
                className={styles.textarea}
                value={diagnosis}
                onChange={(e) => setDiagnosis(e.target.value)}
                rows={2}
              />
            </label>

            <label className={styles.field}>
              <span className={styles.fieldLabel}>Код МКБ-10</span>
              <input
                className={styles.input}
                value={icd10}
                onChange={(e) => setIcd10(e.target.value)}
              />
            </label>

            <div className={styles.fieldRow}>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>Метод лечения</span>
                <select
                  className={styles.select}
                  value={modality}
                  onChange={(e) => setModality(e.target.value)}
                >
                  {['SRT', 'SRS', 'EBRT', 'IMRT', 'IGRT', 'unknown'].map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>

              <label className={styles.field}>
                <span className={styles.fieldLabel}>Клинический путь</span>
                <select
                  className={styles.select}
                  value={pathway}
                  onChange={(e) => {
                    setPathway(e.target.value);
                    if (!hasConflict) {
                      setPriorityCategory(PATHWAY_TO_PRIORITY[e.target.value] ?? '');
                    }
                  }}
                >
                  <option value="">— не указано —</option>
                  {Object.entries(PATHWAY_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className={styles.fieldRow}>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>
                  Кол-во сеансов{' '}
                  <span className={styles.confidence}>
                    {confidencePercent(llm.confidence?.sessions_required)}
                  </span>
                </span>
                <input
                  type="number"
                  min={1}
                  className={styles.input}
                  value={sessionsRequired}
                  onChange={(e) => setSessionsRequired(Number(e.target.value))}
                />
              </label>

              <label className={styles.field}>
                <span className={styles.fieldLabel}>Фракций в неделю</span>
                <input
                  type="number"
                  min={1}
                  className={styles.input}
                  value={fractionsPerWeek ?? ''}
                  onChange={(e) =>
                    setFractionsPerWeek(e.target.value ? Number(e.target.value) : undefined)
                  }
                />
              </label>
            </div>

            {llm.urgency_signals?.symptom_acuity_note && (
              <div className={styles.noteBox}>
                <span className={styles.fieldLabel}>Заметка об остроте симптомов (ИИ)</span>
                <p>{llm.urgency_signals.symptom_acuity_note}</p>
              </div>
            )}

            <label className={styles.field}>
              <span className={styles.fieldLabel}>
                Итоговая категория приоритета
                {hasConflict && <span className={styles.requiredMark}> — выбор врача обязателен</span>}
              </span>
              <div className={styles.priorityChoices}>
                {(Object.keys(PRIORITY_LABELS) as PriorityCategory[]).map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    className={`${styles.priorityChoice} ${
                      priorityCategory === cat ? styles.priorityChoiceActive : ''
                    }`}
                    onClick={() => setPriorityCategory(cat)}
                  >
                    <PriorityBadge category={cat} />
                  </button>
                ))}
              </div>
            </label>

            {hasConflict && (
              <label className={styles.field}>
                <span className={styles.fieldLabel}>Комментарий врача (обязательно при конфликте)</span>
                <textarea
                  className={styles.textarea}
                  rows={2}
                  value={reasonNote}
                  onChange={(e) => setReasonNote(e.target.value)}
                  placeholder="Почему выбрана именно эта категория приоритета?"
                />
              </label>
            )}

            <div className={styles.fieldRow}>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>ИИН пациента</span>
                <input
                  className={styles.input}
                  value={iin}
                  onChange={(e) => setIin(e.target.value)}
                  maxLength={12}
                />
              </label>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>ФИО пациента</span>
                <input
                  className={styles.input}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </label>
            </div>

            <label className={styles.field}>
              <span className={styles.fieldLabel}>Подтверждающий врач</span>
              <input
                className={styles.input}
                value={doctorName}
                onChange={(e) => setDoctorName(e.target.value)}
                placeholder="Ф.И.О. врача"
              />
            </label>

            {saveError && <div className={styles.errorBanner}>{saveError}</div>}

            {savedCase ? (
              <div className={styles.successBanner}>Случай создан и передан в расписание.</div>
            ) : (
              <button
                className={styles.primaryButton}
                disabled={!canSubmit || saving}
                onClick={handleCreateCase}
              >
                {saving ? 'Сохраняем…' : 'Подтвердить и создать случай'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
