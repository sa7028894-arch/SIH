const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

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
  first_name?: string | null;
  last_name?: string | null;
  date_of_issue?: string | null;
  place_of_issue?: string | null;
  country_code?: string | null;
  passport_number?: string | null;
  dob?: string | null;
  mrz?: string | null;
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

export interface EVisaData {
  name?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  dob?: string | null;
  place_of_birth?: string | null;
  sex?: string | null;
  nationality?: string | null;
  passport_number?: string | null;
  passport_issuing_country?: string | null;
  passport_issue_date?: string | null;
  passport_expiration_date?: string | null;
  visa_number?: string | null;
  visa_type?: string | null;
  stay_duration?: string | null;
  entry_validation?: string | null;
  visa_valid: boolean;
  valid_score: number;
  extraction_method: string;
}

export interface EVisaValidationResponse {
  success: boolean;
  visa_detected: boolean;
  message: string;
  filename: string;
  data?: EVisaData | null;
}

export interface AadhaarData {
  name?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  dob?: string | null;
  sex?: string | null;
  aadhaar_no?: string | null;
  formatted_aadhaar_no?: string | null;
  checksum_valid?: boolean | null;
  aadhaar_valid: boolean;
  valid_score: number;
  extraction_method: string;
}

export interface AadhaarValidationResponse {
  success: boolean;
  aadhaar_detected: boolean;
  message: string;
  filename: string;
  data?: AadhaarData | null;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ExtractedFace {
  face_detected: boolean;
  image_base64?: string | null;
  bbox?: BoundingBox | null;
  confidence: number;
}

export interface FaceExtractionResponse {
  success: boolean;
  face_detected: boolean;
  message: string;
  filename: string;
  face?: ExtractedFace | null;
}

export interface FaceCompareResponse {
  success: boolean;
  is_match: boolean;
  similarity_score: number;
  distance: number;
  threshold: number;
  message: string;
  doc_face?: ExtractedFace | null;
  live_face?: ExtractedFace | null;
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

  async validateEVisa(file: File): Promise<EVisaValidationResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE_URL}/api/v1/evisa-validation`, {
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

  async validateAadhaar(file: File): Promise<AadhaarValidationResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE_URL}/api/v1/aadhaar-validation`, {
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

  async extractFace(file: File): Promise<FaceExtractionResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE_URL}/api/v1/extract-face`, {
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

  async compareFaces(documentFile: File, liveFile: File, threshold?: number): Promise<FaceCompareResponse> {
    const formData = new FormData();
    formData.append('document_file', documentFile);
    formData.append('live_file', liveFile);
    if (threshold !== undefined) {
      formData.append('threshold', threshold.toString());
    }

    const res = await fetch(`${API_BASE_URL}/api/v1/face-compare`, {
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

