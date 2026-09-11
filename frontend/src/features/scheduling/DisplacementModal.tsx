import { useState } from 'react';
import type { DisplacementCandidate } from '../../shared/types';
import styles from './DisplacementModal.module.css';

interface Props {
  urgentPatientName: string;
  candidates: DisplacementCandidate[];
  onConfirm: (candidate: DisplacementCandidate, doctorName: string) => Promise<void>;
  onCancel: () => void;
}

export function DisplacementModal({ urgentPatientName, candidates, onConfirm, onCancel }: Props) {
  const [selected, setSelected] = useState<DisplacementCandidate | null>(candidates[0] ?? null);
  const [doctorName, setDoctorName] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    if (!selected) return;
    setConfirming(true);
    setError(null);
    try {
      await onConfirm(selected, doctorName.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось подтвердить перенос');
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true">
      <div className={styles.modal}>
        <h3 className={styles.title}>Слотов не хватает — предложено вытеснение</h3>
        <p className={styles.subtitle}>
          Для пациента <strong>{urgentPatientName}</strong> нет свободных слотов в клиническом
          окне. Ниже — кандидаты на перенос, отсортированные от наименьшего ущерба к наибольшему.
          Ничего не изменится в расписании, пока вы явно не подтвердите перенос.
        </p>

        <div className={styles.candidates}>
          {candidates.map((c) => (
            <label
              key={c.session_id}
              className={`${styles.candidate} ${
                selected?.session_id === c.session_id ? styles.candidateActive : ''
              }`}
            >
              <input
                type="radio"
                name="candidate"
                checked={selected?.session_id === c.session_id}
                onChange={() => setSelected(c)}
                className={styles.radio}
              />
              <div className={styles.candidateBody}>
                <div className={styles.candidateHeader}>
                  <span className={styles.candidateName}>{c.patient_name}</span>
                  <span className={styles.damageScore}>ущерб: {c.damage_score.toFixed(0)}</span>
                </div>
                <p className={styles.candidateDates}>
                  {c.original_date}
                  {c.proposed_new_date ? ` → ${c.proposed_new_date}` : ' → нет альтернативы'}
                </p>
                <p className={styles.candidateExplanation}>{c.explanation}</p>
              </div>
            </label>
          ))}
        </div>

        <label className={styles.doctorField}>
          <span>Ваше Ф.И.О. (подтверждение)</span>
          <input
            className={styles.doctorInput}
            value={doctorName}
            onChange={(e) => setDoctorName(e.target.value)}
            placeholder="Ф.И.О. врача"
          />
        </label>

        {error && <div className={styles.error}>{error}</div>}

        <div className={styles.actions}>
          <button className={styles.cancelButton} onClick={onCancel} disabled={confirming}>
            Отменить
          </button>
          <button
            className={styles.confirmButton}
            onClick={handleConfirm}
            disabled={!selected || !selected.proposed_new_slot_id || !doctorName.trim() || confirming}
          >
            {confirming ? 'Применяем…' : 'Подтвердить перенос'}
          </button>
        </div>
      </div>
    </div>
  );
}
