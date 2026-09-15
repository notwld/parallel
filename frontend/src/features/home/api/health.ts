import { z } from 'zod';

import { apiGet } from '@/api/client';

export const healthSchema = z.object({
  status: z.string(),
  service: z.string().optional(),
});

export type Health = z.infer<typeof healthSchema>;

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const data = await apiGet<unknown>('/health/', signal);
  return healthSchema.parse(data);
}
