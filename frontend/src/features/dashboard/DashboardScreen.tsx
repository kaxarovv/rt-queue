import { useEffect, useState } from 'react';
import { api } from '../../shared/api/client';
import type { AvgWaitByPriority, CapacityByMonth, DashboardStats, QueueByPriority } from '../../shared/types';
import { PRIORITY_LABELS } from '../../shared/types';
import type { PriorityCategory } from '../../shared/types';
import styles from './DashboardScreen.module.css';

const PRIORITY_ORDER: PriorityCategory[] = ['immediate', 'urgent_1_2w', 'planned_1_2m', 'low_3m'];

const PRIORITY_BAR_CLASS: Record<PriorityCategory, string> = {
  immediate: styles.barImmediate,
  urgent_1_2w: styles.barUrgent,
  planned_1_2m: styles.barPlanned,
  low_3m: styles.barLow,
};

const MONTH_NAMES = [
  'янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек',
];

function QueueByPriorityChart({ data }: { data: QueueByPriority[] }) {
  const byCategory = new Map(data.map((d) => [d.category, d.count]));
  const max = Math.max(1, ...data.map((d) => d.count));

  return (
    <div className={styles.card}>
      <h3 className={styles.cardTitle}>Очередь по приоритету</h3>
      <p className={styles.cardSubtitle}>Случаи, ожидающие даты старта лечения</p>
      <div className={styles.hBarChart}>
        {PRIORITY_ORDER.map((cat) => {
          const count = byCategory.get(cat) ?? 0;
          const widthPct = (count / max) * 100;
          return (
            <div key={cat} className={styles.hBarRow}>
              <span className={styles.hBarLabel}>{PRIORITY_LABELS[cat]}</span>
              <div className={styles.hBarTrack}>
                <div
                  className={`${styles.hBarFill} ${PRIORITY_BAR_CLASS[cat]}`}
                  style={{ width: `${count === 0 ? 0 : Math.max(widthPct, 4)}%` }}
                />
              </div>
              <span className={styles.hBarValue}>{count}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CapacityByMonthChart({ data }: { data: CapacityByMonth[] }) {
  const max = Math.max(1, ...data.map((d) => Math.max(d.occupied, d.capacity)));

  function statusClass(occupied: number, capacity: number): string {
    const ratio = occupied / capacity;
    if (ratio >= 1) return styles.barCritical;
    if (ratio >= 0.7) return styles.barWarning;
    return styles.barGood;
  }

  return (
    <div className={styles.card}>
      <h3 className={styles.cardTitle}>Загрузка ёмкости по месяцам</h3>
      <p className={styles.cardSubtitle}>
        Подтверждённые старты лечения относительно лимита {data[0]?.capacity ?? 60} человек/месяц
      </p>
      <div className={styles.vBarChart}>
        {data.map((m) => {
          const heightPct = (m.occupied / max) * 100;
          const capacityLinePct = (m.capacity / max) * 100;
          return (
            <div key={`${m.year}-${m.month}`} className={styles.vBarColumn}>
              <div className={styles.vBarTrack}>
                <div className={styles.capacityLine} style={{ bottom: `${capacityLinePct}%` }} />
                <span
                  className={styles.vBarValue}
                  style={{ bottom: `calc(${m.occupied === 0 ? 0 : Math.max(heightPct, 3)}% + 6px)` }}
                >
                  {m.occupied}
                </span>
                <div
                  className={`${styles.vBarFill} ${statusClass(m.occupied, m.capacity)}`}
                  style={{ height: `${m.occupied === 0 ? 0 : Math.max(heightPct, 3)}%` }}
                />
              </div>
              <span className={styles.vBarLabel}>
                {MONTH_NAMES[m.month - 1]} {String(m.year).slice(2)}
              </span>
            </div>
          );
        })}
      </div>
      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <span className={`${styles.legendSwatch} ${styles.barGood}`} /> &lt;70%
        </span>
        <span className={styles.legendItem}>
          <span className={`${styles.legendSwatch} ${styles.barWarning}`} /> 70–99%
        </span>
        <span className={styles.legendItem}>
          <span className={`${styles.legendSwatch} ${styles.barCritical}`} /> заполнен
        </span>
        <span className={styles.legendItem}>
          <span className={styles.capacityLineSwatch} /> лимит
        </span>
      </div>
    </div>
  );
}

function AvgWaitChart({ data }: { data: AvgWaitByPriority[] }) {
  const byCategory = new Map(data.map((d) => [d.category, d]));
  const max = Math.max(1, ...data.map((d) => d.avg_days ?? 0));

  return (
    <div className={styles.card}>
      <h3 className={styles.cardTitle}>Среднее время ожидания</h3>
      <p className={styles.cardSubtitle}>
        От создания случая до подтверждённой даты старта лечения, по категориям
      </p>
      <div className={styles.hBarChart}>
        {PRIORITY_ORDER.map((cat) => {
          const entry = byCategory.get(cat);
          const avg = entry?.avg_days ?? null;
          const widthPct = avg === null ? 0 : (avg / max) * 100;
          return (
            <div key={cat} className={styles.hBarRow}>
              <span className={styles.hBarLabel}>{PRIORITY_LABELS[cat]}</span>
              <div className={styles.hBarTrack}>
                {avg !== null && (
                  <div
                    className={`${styles.hBarFill} ${PRIORITY_BAR_CLASS[cat]}`}
                    style={{ width: `${Math.max(widthPct, 4)}%` }}
                  />
                )}
              </div>
              <span className={styles.hBarValue}>
                {avg === null ? 'нет данных' : `${avg.toFixed(1)} дн.`}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function DashboardScreen() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .dashboardStats()
      .then(setStats)
      .catch((err) => setError(err instanceof Error ? err.message : 'Ошибка загрузки статистики'));
  }, []);

  if (error) return <div className={styles.error}>{error}</div>;
  if (!stats) return <p className={styles.empty}>Загрузка…</p>;

  return (
    <div className={styles.grid}>
      <QueueByPriorityChart data={stats.queue_by_priority} />
      <CapacityByMonthChart data={stats.capacity_by_month} />
      <AvgWaitChart data={stats.avg_wait_by_priority} />
    </div>
  );
}
