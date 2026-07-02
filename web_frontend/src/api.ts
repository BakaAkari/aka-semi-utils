import type { WatermarkConfig } from './watermarkConfig';

export type ApiFile = { filename: string; download_url: string };
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
type UploadResponse = { ok: true; image_id: string; expires_in: number };

const uploadedImages = new WeakMap<File, Promise<string>>();

async function ensureUploaded(file: File, signal?: AbortSignal): Promise<string> {
  const cached = uploadedImages.get(file);
  if (cached) return cached;

  const request = (async () => {
    const form = new FormData();
    form.append('file', file);
    const response = await fetch('/api/uploads', { method: 'POST', body: form, signal });
    const payload = (await response.json()) as UploadResponse | ApiErrorResponse;
    if (!response.ok || !payload.ok) {
      throw new Error((payload as ApiErrorResponse).error?.message || `上传失败：${response.status}`);
    }
    return payload.image_id;
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
  endpoint: '/api/process' | '/api/preview',
  file: File,
  config: WatermarkConfig,
  signal?: AbortSignal
): Promise<ProcessResponse> {
  const imageId = await ensureUploaded(file, signal);
  const form = new FormData();
  form.append('image_id', imageId);
  form.append('config', JSON.stringify(config));

  const response = await fetch(endpoint, { method: 'POST', body: form, signal });
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
  const response = await fetch('/api/upload-resource', { method: 'POST', body: form });
  const payload = (await response.json()) as ResourceUploadResponse | ApiErrorResponse;
  if (!response.ok || !payload.ok) {
    throw new Error((payload as ApiErrorResponse).error?.message || `上传失败：${response.status}`);
  }
  return payload;
}

export function toDownloadUrl(file: ApiFile): string {
  return file.download_url;
}
