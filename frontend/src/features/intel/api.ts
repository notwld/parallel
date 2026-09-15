import { z } from 'zod';

import { apiGet } from '@/api/client';

export const claimSchema = z.object({
  id: z.string(),
  proposition: z.string(),
  my_state: z.object({
    stance: z.string(),
    confidence: z.number(),
    verification: z.string(),
    shareability: z.string(),
    acquired_at: z.string(),
  }),
  sources: z.array(
    z.object({
      type: z.string(),
      display: z.string(),
      ref: z.string().optional(),
    }),
  ),
  evidence: z.array(z.string()),
  allowed_actions: z.array(z.string()),
});

export const evidenceSchema = z.object({
  id: z.string(),
  media_type: z.string(),
  metadata: z.record(z.string(), z.unknown()),
  visibility: z.string(),
  created_at: z.string(),
});

export type Claim = z.infer<typeof claimSchema>;

export async function fetchIntelClaims(slug: string, q = '', signal?: AbortSignal) {
  const qs = q ? `?q=${encodeURIComponent(q)}` : '';
  const data = await apiGet<{ results: unknown }>(
    `/knowledge/worlds/${slug}/intel/claims/${qs}`,
    signal,
  );
  return z.object({ results: z.array(claimSchema) }).parse(data).results;
}

export async function fetchIntelClaim(slug: string, claimId: string, signal?: AbortSignal) {
  const data = await apiGet<unknown>(`/knowledge/worlds/${slug}/intel/claims/${claimId}/`, signal);
  return claimSchema.parse(data);
}

export async function fetchEvidence(slug: string, evidenceId: string, signal?: AbortSignal) {
  const data = await apiGet<unknown>(
    `/knowledge/worlds/${slug}/intel/evidence/${evidenceId}/`,
    signal,
  );
  return evidenceSchema.parse(data);
}
