import { useEffect, useState } from 'react';
import { api } from '../../shared/api/client';
import type { Patient, PriorityCategory, SuggestedDate, TreatmentCase } from '../../shared/types';
import { PRIORITY_LABELS } from '../../shared/types';
import { PriorityBadge } from '../../shared/components/PriorityBadge';
import { SuggestedDatesModal } from './SuggestedDatesModal';
import styles from './QueueScreen.module.css';

export function QueueScreen() {
  const [cases, setCases] = useState<TreatmentCase[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loadingCaseId, setLoadingCaseId] = useState<string | null>(null);
  const [busyCaseId, setBusyCaseId] = useState<string | null>(null);
  const [pending, setPending] = useState<{ treatmentCase: TreatmentCase; dates: SuggestedDate[] } | null>(
    null
  );
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [c, p] = await Promise.all([api.listCases(), api.listPatients()]);
    setCases(c);
    setPatients(p);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err instanceof Error ? err.message : 'Ошибка загрузки'));
  }, []);

  const patientNameById = new Map(patients.map((p) => [p.id, p.full_name]));
  const queued = cases.filter((c) => c.status === 'pending_review');

  async function handleSuggest(treatmentCase: TreatmentCase) {
    setLoadingCaseId(treatmentCase.id);
    setError(null);
    setMessage(null);
    try {
      const dates = await api.suggestedDates(treatmentCase.id);
      setPending({ treatmentCase, dates });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось получить предложения дат');
    } finally {
      setLoadingCaseId(null);
    }
  }

  async function handleConfirm(chosen: SuggestedDate) {
    if (!pending) return;
    const updated = await api.confirmStartDate(pending.treatmentCase.id, chosen.date);
    setMessage(`Дата старта лечения ${updated.planned_start_date} подтверждена.`);
    setPending(null);
    await refresh();
  }

  async function handlePriorityChange(treatmentCase: TreatmentCase, category: PriorityCategory) {
    setBusyCaseId(treatmentCase.id);
    setError(null);
    setMessage(null);
    try {
      const updated = await api.updatePriority(treatmentCase.id, category);
      setMessage(
        `Приоритет случая изменён на «${PRIORITY_LABELS[category]}», новый дедлайн: ${updated.clinical_deadline_date}.`
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось изменить приоритет');
    } finally {
      setBusyCaseId(null);
    }
  }

  async function handleCancel(treatmentCase: TreatmentCase) {
    if (!window.confirm('Отменить этот случай? Действие необратимо.')) return;
    setBusyCaseId(treatmentCase.id);
    setError(null);
    setMessage(null);
    try {
      await api.cancelCase(treatmentCase.id);
      setMessage('Случай отменён.');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось отменить случай');
    } finally {
      setBusyCaseId(null);
    }
  }

  return (
    <div className={styles.layout}>
      <h2 className={styles.sectionTitle}>Очередь МДГ по приоритету</h2>
      {message && <div className={styles.success}>{message}</div>}
      {error && <div className={styles.error}>{error}</div>}

      {queued.length === 0 && (
        <p className={styles.empty}>Пока нет случаев, ожидающих даты старта лечения.</p>
      )}

      <div className={styles.caseList}>
        {queued.map((c, index) => (
          <div key={c.id} className={styles.caseCard}>
            <div className={styles.caseHeader}>
              <span className={styles.rank}>#{index + 1}</span>
              <PriorityBadge category={c.priority_category} />
              <select
                className={styles.prioritySelect}
                value={c.priority_category ?? ''}
                disabled={busyCaseId === c.id}
                onChange={(e) => handlePriorityChange(c, e.target.value as PriorityCategory)}
                aria-label="Изменить категорию приоритета"
              >
                {(Object.keys(PRIORITY_LABELS) as PriorityCategory[]).map((cat) => (
                  <option key={cat} value={cat}>
                    {PRIORITY_LABELS[cat]}
                  </option>
                ))}
              </select>
            </div>
            <p className={styles.patientName}>{patientNameById.get(c.patient_id) ?? '—'}</p>
            <p className={styles.diagnosis}>{c.diagnosis_text}</p>
            <div className={styles.caseMeta}>
              <span>{c.sessions_required} сеансов</span>
              {c.clinical_deadline_date && <span>дедлайн до {c.clinical_deadline_date}</span>}
              {c.planned_start_date && (
                <span className={styles.plannedDate}>старт: {c.planned_start_date}</span>
              )}
            </div>
            <div className={styles.actions}>
              <button
                className={styles.suggestButton}
                onClick={() => handleSuggest(c)}
                disabled={loadingCaseId === c.id || busyCaseId === c.id}
              >
                {loadingCaseId === c.id
                  ? 'Подбираем даты…'
                  : c.planned_start_date
                    ? 'Изменить дату'
                    : 'Предложить даты'}
              </button>
              <button
                className={styles.cancelButton}
                onClick={() => handleCancel(c)}
                disabled={busyCaseId === c.id}
              >
                Отменить
              </button>
            </div>
          </div>
        ))}
      </div>

      {pending && (
        <SuggestedDatesModal
          patientName={patientNameById.get(pending.treatmentCase.patient_id) ?? '—'}
          dates={pending.dates}
          onConfirm={handleConfirm}
          onCancel={() => setPending(null)}
        />
      )}
    </div>
  );
}
