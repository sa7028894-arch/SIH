const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface HealthStatus {
  status: string;
  service: string;
  timestamp: string;
}

export interface RootMessage {
  message: string;
  docs: string;
  health: string;
}

export interface CheckDigitValidation {
  number?: boolean | null;
  date_of_birth?: boolean | null;
  expiration_date?: boolean | null;
  composite?: boolean | null;
  personal_number?: boolean | null;
}

export interface MRZData {
  name?: string | null;
  document_number?: string | null;
  nationality?: string | null;
  date_of_birth?: string | null;
  expiry_date?: string | null;
  sex?: string | null;
  mrz_valid: boolean;
  valid_score: number;
  mrz_type?: string | null;
  country?: string | null;
  raw_text?: string | null;
  extraction_method: string;
  check_digits: CheckDigitValidation;
}

export interface PassportValidationResponse {
  success: boolean;
  mrz_detected: boolean;
  message: string;
  filename: string;
  data?: MRZData | null;
}

export const api = {
  async getRoot(): Promise<RootMessage> {
    const res = await fetch(`${API_BASE_URL}/`);
    if (!res.ok) {
      throw new Error(`HTTP error ${res.status}: ${res.statusText}`);
    }
    return res.json();
  },

  async getHealth(): Promise<HealthStatus> {
    const res = await fetch(`${API_BASE_URL}/api/v1/health`);
    if (!res.ok) {
      throw new Error(`HTTP error ${res.status}: ${res.statusText}`);
    }
    return res.json();
  },

  async validatePassport(file: File): Promise<PassportValidationResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE_URL}/api/v1/passport-validation`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      let detailMsg = `Request failed (${res.status} ${res.statusText})`;
      try {
        const errorData = await res.json();
        if (errorData.detail) {
          detailMsg = errorData.detail;
        }
      } catch {
        // use fallback message
      }
      throw new Error(detailMsg);
    }

    return res.json();
  },
};
