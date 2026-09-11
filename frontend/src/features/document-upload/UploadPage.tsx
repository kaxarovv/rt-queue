import { useCallback, useMemo, useRef, useState } from 'react';
import type { SourceDocument } from '../../shared/types';
import styles from './UploadPage.module.css';

const STATUS_LABELS: Record<string, string> = {
  pending: 'В очереди',
  text_extracted: 'Текст извлечён',
  llm_processed: 'Обработано ИИ',
  needs_review: 'Требует проверки',
  reviewed: 'Проверено врачом',
  failed: 'Ошибка обработки',
};

const STATUS_CLASS: Record<string, string> = {
  pending: styles.statusPending,
  text_extracted: styles.statusPending,
  llm_processed: styles.statusOk,
  needs_review: styles.statusReview,
  reviewed: styles.statusOk,
  failed: styles.statusError,
};

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'needs_review', label: 'Требует проверки' },
  { value: 'pending', label: 'В обработке' },
  { value: 'reviewed', label: 'Проверено' },
  { value: 'failed', label: 'Ошибки' },
];

/**
 * backend помечает и техническую ошибку LLM-экстракции (LM Studio недоступен /
 * контекст переполнен), и обычный конфликт сигналов, требующий решения врача,
 * ОДНИМ статусом needs_review (см. documents/router.py) -- отличить их можно
 * только по наличию error_message. Без этого документ с реальной ошибкой
 * обработки визуально неотличим от нормального "требует проверки" случая и
 * не находится через фильтр "Ошибки".
 */
function displayStatus(doc: SourceDocument): { key: string; label: string; className: string } {
  if (doc.status === 'needs_review' && doc.error_message) {
    return { key: 'failed', label: 'Ошибка ИИ-анализа', className: styles.statusError };
  }
  return {
    key: doc.status,
    label: STATUS_LABELS[doc.status] || doc.status,
    className: STATUS_CLASS[doc.status] || '',
  };
}

function matchesStatusFilter(doc: SourceDocument, filter: string): boolean {
  if (filter === 'all') return true;
  const key = displayStatus(doc).key;
  if (filter === 'pending') return key === 'pending' || key === 'text_extracted' || key === 'llm_processed';
  return key === filter;
}

interface Props {
  documents: SourceDocument[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onUpload: (file: File) => Promise<void>;
  uploading: boolean;
}

export function DocumentListPanel({ documents, selectedId, onSelect, onUpload, uploading }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const inputRef = useRef<HTMLInputElement>(null);

  const filteredDocuments = useMemo(() => {
    const query = search.trim().toLowerCase();
    return documents.filter(
      (doc) =>
        matchesStatusFilter(doc, statusFilter) &&
        (query === '' || doc.original_filename.toLowerCase().includes(query))
    );
  }, [documents, search, statusFilter]);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const file = files?.[0];
      if (file && file.type === 'application/pdf') {
        onUpload(file);
      }
    },
    [onUpload]
  );

  return (
    <div className={styles.panel}>
      <div
        className={`${styles.dropzone} ${dragOver ? styles.dropzoneActive : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
        {uploading ? (
          <p className={styles.dropzoneText}>Загружаем и распознаём текст…</p>
        ) : (
          <>
            <p className={styles.dropzoneText}>
              Перетащите медицинскую карту (PDF) сюда
              <br />
              или нажмите, чтобы выбрать файл
            </p>
          </>
        )}
      </div>

      {documents.length > 0 && (
        <div className={styles.filters}>
          <input
            className={styles.searchInput}
            type="text"
            placeholder="Поиск по имени файла…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className={styles.statusPills}>
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                className={`${styles.statusPill} ${statusFilter === f.value ? styles.statusPillActive : ''}`}
                onClick={() => setStatusFilter(f.value)}
                type="button"
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className={styles.list}>
        {documents.length === 0 && (
          <p className={styles.empty}>Пока нет загруженных документов.</p>
        )}
        {documents.length > 0 && filteredDocuments.length === 0 && (
          <p className={styles.empty}>Ничего не найдено по этому фильтру.</p>
        )}
        {filteredDocuments.map((doc) => {
          const status = displayStatus(doc);
          return (
            <button
              key={doc.id}
              className={`${styles.docItem} ${doc.id === selectedId ? styles.docItemActive : ''}`}
              onClick={() => onSelect(doc.id)}
            >
              <span className={styles.docName}>{doc.original_filename}</span>
              <span className={styles.docTags}>
                <span className={`${styles.statusTag} ${status.className}`}>{status.label}</span>
                {doc.case_id && <span className={styles.caseTag}>case создан</span>}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
