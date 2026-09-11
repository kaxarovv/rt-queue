import type { PriorityCategory } from '../types';
import { PRIORITY_LABELS } from '../types';
import styles from './PriorityBadge.module.css';

const CLASS_BY_CATEGORY: Record<PriorityCategory, string> = {
  immediate: styles.immediate,
  urgent_1_2w: styles.urgent,
  planned_1_2m: styles.planned,
  low_3m: styles.low,
};

export function PriorityBadge({ category }: { category: PriorityCategory | null }) {
  if (!category) {
    return <span className={`${styles.badge} ${styles.unknown}`}>Не определён</span>;
  }
  return (
    <span className={`${styles.badge} ${CLASS_BY_CATEGORY[category]}`}>
      {PRIORITY_LABELS[category]}
    </span>
  );
}
