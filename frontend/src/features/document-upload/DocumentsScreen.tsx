import { useEffect, useState } from 'react';
import { api } from '../../shared/api/client';
import type { SourceDocument } from '../../shared/types';
import { DocumentListPanel } from './UploadPage';
import { ReviewPanel } from './ReviewPanel';
import styles from './DocumentsScreen.module.css';

export function DocumentsScreen() {
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  async function refresh() {
    try {
      const docs = await api.listDocuments();
      setDocuments(docs);
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Не удалось загрузить список документов');
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleUpload(file: File) {
    setUploading(true);
    try {
      const doc = await api.uploadDocument(file);
      await refresh();
      setSelectedId(doc.id);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Не удалось загрузить файл');
    } finally {
      setUploading(false);
    }
  }

  async function handleExtract(id: string) {
    setExtracting(true);
    try {
      await api.extractDocument(id);
      await refresh();
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Не удалось выполнить ИИ-анализ');
    } finally {
      setExtracting(false);
    }
  }

  const selected = documents.find((d) => d.id === selectedId) ?? null;

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <DocumentListPanel
          documents={documents}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onUpload={handleUpload}
          uploading={uploading}
        />
      </aside>
      <section className={styles.content}>
        {loadError && <div className={styles.error}>{loadError}</div>}
        {selected ? (
          <ReviewPanel
            document={selected}
            onExtract={handleExtract}
            onCaseCreated={refresh}
            extracting={extracting}
          />
        ) : (
          <div className={styles.placeholder}>
            <p>Выберите документ слева или загрузите новую медицинскую карту.</p>
          </div>
        )}
      </section>
    </div>
  );
}
