const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options?.body && !(options.body instanceof FormData)
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ? JSON.stringify(body.detail) : detail;
    } catch {
      /* тело не JSON -- оставляем statusText */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  // documents
  uploadDocument: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<import('../types').SourceDocument>('/api/documents/upload', {
      method: 'POST',
      body: form,
    });
  },
  listDocuments: () => request<import('../types').SourceDocument[]>('/api/documents'),
  getDocument: (id: string) => request<import('../types').SourceDocument>(`/api/documents/${id}`),
  extractDocument: (id: string) =>
    request<import('../types').SourceDocument>(`/api/documents/${id}/extract`, { method: 'POST' }),
  documentFileUrl: (id: string) => `${BASE_URL}/api/documents/${id}/file`,

  // patients
  createPatient: (payload: { iin: string; full_name: string; birth_date?: string | null }) =>
    request<import('../types').Patient>('/api/patients', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listPatients: () => request<import('../types').Patient[]>('/api/patients'),
  patientCases: (patientId: string) =>
    request<import('../types').TreatmentCase[]>(`/api/patients/${patientId}/cases`),

  // cases
  createCase: (payload: Record<string, unknown>) =>
    request<import('../types').TreatmentCase>('/api/cases', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listCases: () => request<import('../types').TreatmentCase[]>('/api/cases'),
  suggestedDates: (caseId: string) =>
    request<import('../types').SuggestedDate[]>(`/api/cases/${caseId}/suggested-dates`),
  confirmStartDate: (caseId: string, plannedStartDate: string) =>
    request<import('../types').TreatmentCase>(`/api/cases/${caseId}/confirm-date`, {
      method: 'POST',
      body: JSON.stringify({ planned_start_date: plannedStartDate }),
    }),
  dashboardStats: () => request<import('../types').DashboardStats>('/api/cases/stats/dashboard'),
  cancelCase: (caseId: string) =>
    request<import('../types').TreatmentCase>(`/api/cases/${caseId}/cancel`, { method: 'POST' }),
  updatePriority: (caseId: string, priorityCategory: import('../types').PriorityCategory) =>
    request<import('../types').TreatmentCase>(`/api/cases/${caseId}/priority`, {
      method: 'PATCH',
      body: JSON.stringify({ priority_category: priorityCategory }),
    }),

  // scheduling
  listSlots: (startDate: string, endDate: string) =>
    request<import('../types').MachineSlot[]>(
      `/api/schedule/slots?start_date=${startDate}&end_date=${endDate}`
    ),
  bookCase: (caseId: string) =>
    request<import('../types').BookingResult>(`/api/schedule/cases/${caseId}/book`, {
      method: 'POST',
    }),
  confirmDisplacement: (payload: {
    session_id_to_move: string;
    new_slot_id_for_moved_session: string;
    urgent_case_id: string;
    confirmed_by_doctor: string;
  }) =>
    request<import('../types').BookingResult>('/api/schedule/confirm-displacement', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

export { ApiError };
