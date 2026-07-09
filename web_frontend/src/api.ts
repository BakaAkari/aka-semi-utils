import type { WatermarkConfig } from './watermarkConfig';
import { API_BASE } from './env';

export type ApiFile = { filename: string; download_url: string; download_filename?: string };
export type ProcessResponse = { ok: true; file: ApiFile };
export type ApiErrorResponse = {
  ok: false;
  error: { code: string; message: string; detail?: string };
};
export type ResourceUploadResponse = {
  ok: true;
  filename: string;
  kind: string;
  resource_id: string;
};
type UploadResponse = { ok: true; image_id: string; expires_in: number; original_filename: string };

export type VisitResponse = { ok: true; new: boolean };
export type StatsResponse = {
  ok: true;
  today: {
    unique_visitors: number;
    new_visitors: number;
    processed_images: number;
    api_calls: number;
  };
  lifetime: {
    total_visitors: number;
    total_processed_images: number;
    total_api_calls: number;
  };
  trend: {
    last_7_days: Array<{
      date: string;
      unique_visitors: number;
      new_visitors: number;
      processed_images: number;
      api_calls: number;
    }>;
    last_15_days: Array<{
      date: string;
      unique_visitors: number;
      new_visitors: number;
      processed_images: number;
      api_calls: number;
    }>;
    last_30_days: Array<{
      date: string;
      unique_visitors: number;
      new_visitors: number;
      processed_images: number;
      api_calls: number;
    }>;
  };
  latency: {
    p50_ms: number;
    p99_ms: number;
  };
  extra: {
    avg_batch_size: number;
    active_ratio: number;
  };
};

const uploadedImages = new WeakMap<File, Promise<{ image_id: string; original_filename: string }>>();
const originalNames = new WeakMap<File, string>();

async function ensureUploaded(file: File, signal?: AbortSignal): Promise<{ image_id: string; original_filename: string }> {
  const cached = uploadedImages.get(file);
  if (cached) return cached;

  const request = (async () => {
    const form = new FormData();
    form.append('file', file);
    const response = await fetch(`${API_BASE}/api/uploads`, { method: 'POST', body: form, signal });
    const payload = (await response.json()) as UploadResponse | ApiErrorResponse;
    if (!response.ok || !payload.ok) {
      throw new Error((payload as ApiErrorResponse).error?.message || `上传失败：${response.status}`);
    }
    originalNames.set(file, payload.original_filename);
    return { image_id: payload.image_id, original_filename: payload.original_filename };
  })();

  uploadedImages.set(file, request);
  try {
    return await request;
  } catch (error) {
    uploadedImages.delete(file);
    throw error;
  }
}

export async function processImage(
  endpoint: 'process' | 'preview',
  file: File,
  config: WatermarkConfig,
  signal?: AbortSignal
): Promise<ProcessResponse> {
  const { image_id, original_filename } = await ensureUploaded(file, signal);
  const form = new FormData();
  form.append('image_id', image_id);
  // Strip UI-only sides config — backend has no sides field yet
  const { sides: _, ...apiConfig } = config as WatermarkConfig & { sides?: unknown };
  form.append('config', JSON.stringify(apiConfig));
  form.append('original_filename', original_filename);

  const response = await fetch(`${API_BASE}/api/${endpoint}`, { method: 'POST', body: form, signal });
  const payload = (await response.json()) as ProcessResponse | ApiErrorResponse;
  if (!response.ok || !payload.ok) {
    throw new Error((payload as ApiErrorResponse).error?.message || `请求失败：${response.status}`);
  }
  return payload;
}

export async function uploadResource(file: File, kind: 'logo' | 'signature'): Promise<ResourceUploadResponse> {
  const form = new FormData();
  form.append('file', file);
  form.append('kind', kind);
  const response = await fetch(`${API_BASE}/api/upload-resource`, { method: 'POST', body: form });
  const payload = (await response.json()) as ResourceUploadResponse | ApiErrorResponse;
  if (!response.ok || !payload.ok) {
    throw new Error((payload as ApiErrorResponse).error?.message || `上传失败：${response.status}`);
  }
  return payload;
}

export function toDownloadUrl(file: ApiFile): string {
  return file.download_url;
}

export async function postVisit(visitorId: string): Promise<VisitResponse> {
  const response = await fetch(`${API_BASE}/api/_visit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ visitor_id: visitorId }),
  });
  const payload = (await response.json()) as VisitResponse | ApiErrorResponse;
  if (!response.ok || !payload.ok) {
    throw new Error((payload as ApiErrorResponse).error?.message || `请求失败：${response.status}`);
  }
  return payload as VisitResponse;
}

export async function getStats(password: string): Promise<StatsResponse> {
  const response = await fetch(`${API_BASE}/api/_stats`, {
    headers: { 'X-Dev-Password': password },
  });
  const payload = (await response.json()) as StatsResponse | ApiErrorResponse;
  if (!response.ok || !payload.ok) {
    throw new Error((payload as ApiErrorResponse).error?.message || `请求失败：${response.status}`);
  }
  return payload as StatsResponse;
}
