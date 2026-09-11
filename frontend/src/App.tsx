import { useState } from 'react';
import { DashboardScreen } from './features/dashboard/DashboardScreen';
import { DocumentsScreen } from './features/document-upload/DocumentsScreen';
import { PatientsScreen } from './features/patients/PatientsScreen';
import { QueueScreen } from './features/queue/QueueScreen';
import { SchedulingScreen } from './features/scheduling/SchedulingScreen';
import styles from './app/AppShell.module.css';

type Screen = 'documents' | 'patients' | 'queue' | 'scheduling' | 'dashboard';

export function App() {
  const [screen, setScreen] = useState<Screen>('documents');

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>RT Queue</span>
          <span className={styles.brandSub}>Алматинский онкологический центр</span>
        </div>
        <nav className={styles.nav}>
          <button
            className={screen === 'documents' ? styles.navButtonActive : styles.navButton}
            onClick={() => setScreen('documents')}
          >
            Документы
          </button>
          <button
            className={screen === 'patients' ? styles.navButtonActive : styles.navButton}
            onClick={() => setScreen('patients')}
          >
            Пациенты
          </button>
          <button
            className={screen === 'queue' ? styles.navButtonActive : styles.navButton}
            onClick={() => setScreen('queue')}
          >
            Очередь
          </button>
          <button
            className={screen === 'scheduling' ? styles.navButtonActive : styles.navButton}
            onClick={() => setScreen('scheduling')}
          >
            Расписание
          </button>
          <button
            className={screen === 'dashboard' ? styles.navButtonActive : styles.navButton}
            onClick={() => setScreen('dashboard')}
          >
            Дэшборд
          </button>
        </nav>
      </header>
      <main className={styles.main}>
        {screen === 'documents' && <DocumentsScreen />}
        {screen === 'patients' && <PatientsScreen />}
        {screen === 'queue' && <QueueScreen />}
        {screen === 'scheduling' && <SchedulingScreen />}
        {screen === 'dashboard' && <DashboardScreen />}
      </main>
    </div>
  );
}
