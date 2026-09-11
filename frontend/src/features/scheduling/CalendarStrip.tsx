import type { MachineSlot } from '../../shared/types';
import styles from './CalendarStrip.module.css';

function groupByDate(slots: MachineSlot[]): Map<string, MachineSlot[]> {
  const map = new Map<string, MachineSlot[]>();
  for (const slot of slots) {
    const arr = map.get(slot.slot_date) ?? [];
    arr.push(slot);
    map.set(slot.slot_date, arr);
  }
  return map;
}

function formatDayLabel(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', month: 'short' });
}

export function CalendarStrip({ slots }: { slots: MachineSlot[] }) {
  const byDate = groupByDate(slots);
  const dates = Array.from(byDate.keys()).sort();

  if (dates.length === 0) {
    return <p className={styles.empty}>Слоты ещё не сгенерированы для этого диапазона.</p>;
  }

  return (
    <div className={styles.strip}>
      {dates.map((date) => {
        const daySlots = byDate.get(date)!;
        const free = daySlots.filter((s) => s.status === 'free').length;
        const total = daySlots.length;
        const load = total > 0 ? (total - free) / total : 0;

        return (
          <div key={date} className={styles.day}>
            <div className={styles.dayLabel}>{formatDayLabel(date)}</div>
            <div className={styles.bar}>
              <div
                className={styles.barFill}
                style={{ width: `${load * 100}%` }}
                data-full={free === 0}
              />
            </div>
            <div className={styles.dayCount}>
              {free} свободно из {total}
            </div>
          </div>
        );
      })}
    </div>
  );
}
