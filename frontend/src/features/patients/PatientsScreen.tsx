import { useEffect, useMemo, useState } from 'react';
import { api } from '../../shared/api/client';
import type { Patient, TreatmentCase } from '../../shared/types';
import { PriorityBadge } from '../../shared/components/PriorityBadge';
import styles from './PatientsScreen.module.css';

const CASE_STATUS_LABELS: Record<string, string> = {
  pending_review: 'Ожидает даты старта',
  scheduled: 'Запланировано',
  in_progress: 'В процессе лечения',
  completed: 'Завершено',
  cancelled: 'Отменено',
};

const CASE_STATUS_CLASS: Record<string, string> = {
  pending_review: styles.statusPending,
  scheduled: styles.statusOk,
  in_progress: styles.statusOk,
  completed: styles.statusOk,
  cancelled: styles.statusCancelled,
};

export function PatientsScreen() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [cases, setCases] = useState<TreatmentCase[]>([]);
  const [search, setSearch] = useState('');
  const [loadingCases, setLoadingCases] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listPatients().then(setPatients).catch((err) => setError(err instanceof Error ? err.message : 'Ошибка загрузки'));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setCases([]);
      return;
    }
    setLoadingCases(true);
    api
      .patientCases(selectedId)
      .then(setCases)
      .catch((err) => setError(err instanceof Error ? err.message : 'Не удалось загрузить историю'))
      .finally(() => setLoadingCases(false));
  }, [selectedId]);

  const filteredPatients = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (query === '') return patients;
    return patients.filter(
      (p) => p.full_name.toLowerCase().includes(query) || p.iin.includes(query)
    );
  }, [patients, search]);

  const selectedPatient = patients.find((p) => p.id === selectedId) ?? null;

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <input
          className={styles.searchInput}
          type="text"
          placeholder="Поиск по ФИО или ИИН…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className={styles.list}>
          {filteredPatients.length === 0 && <p className={styles.empty}>Пациенты не найдены.</p>}
          {filteredPatients.map((p) => (
            <button
              key={p.id}
              className={`${styles.patientItem} ${p.id === selectedId ? styles.patientItemActive : ''}`}
              onClick={() => setSelectedId(p.id)}
            >
              <span className={styles.patientItemName}>{p.full_name}</span>
              <span className={styles.patientItemIin}>ИИН {p.iin}</span>
            </button>
          ))}
        </div>
      </aside>

      <section className={styles.content}>
        {error && <div className={styles.error}>{error}</div>}

        {!selectedPatient && (
          <div className={styles.placeholder}>
            <p>Выберите пациента слева, чтобы увидеть карточку и историю обращений.</p>
          </div>
        )}

        {selectedPatient && (
          <>
            <div className={styles.profileCard}>
              <h2 className={styles.profileName}>{selectedPatient.full_name}</h2>
              <div className={styles.profileMeta}>
                <span>ИИН: {selectedPatient.iin}</span>
                {selectedPatient.birth_date && <span>Дата рождения: {selectedPatient.birth_date}</span>}
                <span>В системе с {new Date(selectedPatient.created_at).toLocaleDateString('ru-RU')}</span>
              </div>
            </div>

            <h3 className={styles.historyTitle}>История обращений</h3>
            {loadingCases && <p className={styles.empty}>Загрузка…</p>}
            {!loadingCases && cases.length === 0 && (
              <p className={styles.empty}>У пациента пока нет случаев лечения.</p>
            )}
            <div className={styles.caseList}>
              {cases.map((c) => (
                <div key={c.id} className={styles.caseCard}>
                  <div className={styles.caseHeader}>
                    <PriorityBadge category={c.priority_category} />
                    <span className={`${styles.statusTag} ${CASE_STATUS_CLASS[c.status] || ''}`}>
                      {CASE_STATUS_LABELS[c.status] || c.status}
                    </span>
                  </div>
                  <p className={styles.diagnosis}>{c.diagnosis_text}</p>
                  <div className={styles.caseMeta}>
                    <span>{c.sessions_required} сеансов</span>
                    <span>создан {new Date(c.created_at).toLocaleDateString('ru-RU')}</span>
                    {c.planned_start_date && <span>старт: {c.planned_start_date}</span>}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
