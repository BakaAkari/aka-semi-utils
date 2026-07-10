import type { WatermarkConfigV3 } from './v3Types';
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

export async function processImageV3(
  endpoint: 'process' | 'preview',
  file: File,
  config: WatermarkConfigV3,
  signal?: AbortSignal
): Promise<ProcessResponse> {
  const { image_id, original_filename } = await ensureUploaded(file, signal);
  const form = new FormData();
  form.append('image_id', image_id);
  form.append('config', JSON.stringify(config));
  form.append('original_filename', original_filename);

  const response = await fetch(`${API_BASE}/api/${endpoint}`, { method: 'POST', body: form, signal });
  const payload = (await response.json()) as ProcessResponse | ApiErrorResponse;
  if (!response.ok || !payload.ok) {
    throw new Error((payload as ApiErrorResponse).error?.message || `请求失败：${response.status}`);
  }
  return payload;
}

export async function uploadResourceV3(
  file: File,
  kind: 'logo' | 'signature',
): Promise<ResourceUploadResponse> {
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
