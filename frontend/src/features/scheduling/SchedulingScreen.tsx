import { useEffect, useState } from 'react';
import { api } from '../../shared/api/client';
import type { DisplacementCandidate, MachineSlot, Patient, TreatmentCase } from '../../shared/types';
import { PriorityBadge } from '../../shared/components/PriorityBadge';
import { CalendarStrip } from './CalendarStrip';
import { DisplacementModal } from './DisplacementModal';
import styles from './SchedulingScreen.module.css';

const STATUS_LABELS: Record<string, string> = {
  pending_review: 'Ожидает бронирования',
  scheduled: 'Запланирован',
  in_progress: 'В процессе',
  completed: 'Завершён',
  cancelled: 'Отменён',
};

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDaysIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function SchedulingScreen() {
  const [cases, setCases] = useState<TreatmentCase[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [slots, setSlots] = useState<MachineSlot[]>([]);
  const [bookingCaseId, setBookingCaseId] = useState<string | null>(null);
  const [pendingDisplacement, setPendingDisplacement] = useState<{
    urgentCase: TreatmentCase;
    candidates: DisplacementCandidate[];
  } | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [c, p, s] = await Promise.all([
      api.listCases(),
      api.listPatients(),
      api.listSlots(todayIso(), addDaysIso(21)),
    ]);
    setCases(c);
    setPatients(p);
    setSlots(s);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err instanceof Error ? err.message : 'Ошибка загрузки'));
  }, []);

  const patientNameById = new Map(patients.map((p) => [p.id, p.full_name]));

  async function handleBook(treatmentCase: TreatmentCase) {
    setBookingCaseId(treatmentCase.id);
    setError(null);
    setMessage(null);
    try {
      const result = await api.bookCase(treatmentCase.id);
      if (result.booked) {
        setMessage(result.message);
        await refresh();
      } else {
        setPendingDisplacement({ urgentCase: treatmentCase, candidates: result.displacement_candidates });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось забронировать случай');
    } finally {
      setBookingCaseId(null);
    }
  }

  async function handleConfirmDisplacement(candidate: DisplacementCandidate, doctorName: string) {
    if (!pendingDisplacement || !candidate.proposed_new_slot_id) return;
    const result = await api.confirmDisplacement({
      session_id_to_move: candidate.session_id,
      new_slot_id_for_moved_session: candidate.proposed_new_slot_id,
      urgent_case_id: pendingDisplacement.urgentCase.id,
      confirmed_by_doctor: doctorName,
    });
    setMessage(result.message);
    setPendingDisplacement(null);
    await refresh();
  }

  return (
    <div className={styles.layout}>
      <section className={styles.casesColumn}>
        <h2 className={styles.sectionTitle}>Очередь по приоритету</h2>
        {message && <div className={styles.success}>{message}</div>}
        {error && <div className={styles.error}>{error}</div>}

        {cases.length === 0 && <p className={styles.empty}>Пока нет созданных случаев лечения.</p>}

        <div className={styles.caseList}>
          {cases.map((c) => (
            <div key={c.id} className={styles.caseCard}>
              <div className={styles.caseHeader}>
                <PriorityBadge category={c.priority_category} />
                <span className={styles.caseStatus}>{STATUS_LABELS[c.status] || c.status}</span>
              </div>
              <p className={styles.patientName}>{patientNameById.get(c.patient_id) ?? '—'}</p>
              <p className={styles.diagnosis}>{c.diagnosis_text}</p>
              <div className={styles.caseMeta}>
                <span>{c.sessions_required} сеансов</span>
                {c.clinical_deadline_date && <span>до {c.clinical_deadline_date}</span>}
                <span className={styles.score}>score: {c.priority_score?.toFixed(0)}</span>
              </div>
              {c.status === 'pending_review' && (
                <button
                  className={styles.bookButton}
                  onClick={() => handleBook(c)}
                  disabled={bookingCaseId === c.id}
                >
                  {bookingCaseId === c.id ? 'Ищем слоты…' : 'Забронировать'}
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className={styles.calendarColumn}>
        <h2 className={styles.sectionTitle}>Загрузка аппарата (21 день)</h2>
        <CalendarStrip slots={slots} />
      </section>

      {pendingDisplacement && (
        <DisplacementModal
          urgentPatientName={patientNameById.get(pendingDisplacement.urgentCase.patient_id) ?? '—'}
          candidates={pendingDisplacement.candidates}
          onConfirm={handleConfirmDisplacement}
          onCancel={() => setPendingDisplacement(null)}
        />
      )}
    </div>
  );
}
