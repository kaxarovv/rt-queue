import { useState } from 'react';
import type { SuggestedDate } from '../../shared/types';
import styles from './SuggestedDatesModal.module.css';

interface Props {
  patientName: string;
  dates: SuggestedDate[];
  onConfirm: (chosen: SuggestedDate) => Promise<void>;
  onCancel: () => void;
}

export function SuggestedDatesModal({ patientName, dates, onConfirm, onCancel }: Props) {
  const [selected, setSelected] = useState<SuggestedDate | null>(dates[0] ?? null);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    if (!selected) return;
    setConfirming(true);
    setError(null);
    try {
      await onConfirm(selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось подтвердить дату');
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true">
      <div className={styles.modal}>
        <h3 className={styles.title}>Предложенные даты старта лечения</h3>
        <p className={styles.subtitle}>
          Для пациента <strong>{patientName}</strong> — варианты с учётом месячной ёмкости очереди.
          Система ничего не бронирует автоматически — выберите дату и подтвердите.
        </p>

        {dates.length === 0 && (
          <p className={styles.empty}>
            Свободных мест не найдено в ближайшие месяцы. Требуется решение врача вручную.
          </p>
        )}

        <div className={styles.candidates}>
          {dates.map((d) => (
            <label
              key={d.date}
              className={`${styles.candidate} ${
                selected?.date === d.date ? styles.candidateActive : ''
              }`}
            >
              <input
                type="radio"
                name="suggested-date"
                checked={selected?.date === d.date}
                onChange={() => setSelected(d)}
                className={styles.radio}
              />
              <div className={styles.candidateBody}>
                <div className={styles.candidateHeader}>
                  <span className={styles.candidateDate}>{d.date}</span>
                  <span className={styles.occupancy}>
                    занято {d.month_occupied}/{d.month_capacity}
                  </span>
                </div>
                {!d.within_clinical_deadline && (
                  <p className={styles.deadlineWarning}>
                    ⚠ Дата выходит за клинический дедлайн случая — берите с осторожностью
                  </p>
                )}
              </div>
            </label>
          ))}
        </div>

        {error && <div className={styles.error}>{error}</div>}

        <div className={styles.actions}>
          <button className={styles.cancelButton} onClick={onCancel} disabled={confirming}>
            Отменить
          </button>
          <button
            className={styles.confirmButton}
            onClick={handleConfirm}
            disabled={!selected || confirming}
          >
            {confirming ? 'Подтверждаем…' : 'Подтвердить дату'}
          </button>
        </div>
      </div>
    </div>
  );
}
