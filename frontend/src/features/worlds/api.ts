import { z } from 'zod';

import { ApiError, apiGet, apiSend, ensureCsrf } from '@/api/client';

export const roleSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  invite_only: z.boolean(),
  max_slots: z.number().nullable().optional(),
  claimable: z.boolean(),
});

export const worldLandingSchema = z.object({
  id: z.string(),
  slug: z.string(),
  title: z.string(),
  premise: z.string(),
  status: z.string(),
  visibility: z.string(),
  content_rating: z.string(),
  world_time: z.string(),
  population: z.number(),
  roles: z.array(roleSchema),
});

export const characterSchema = z.object({
  id: z.string(),
  world_id: z.string(),
  display_name: z.string(),
  bio: z.string(),
  avatar: z.string(),
  status: z.string(),
  role_template_id: z.string(),
  role_name: z.string(),
  location_id: z.string().nullable(),
  public_profile: z.record(z.string(), z.unknown()),
  capability_codes: z.array(z.string()),
});

export type WorldLanding = z.infer<typeof worldLandingSchema>;
export type Character = z.infer<typeof characterSchema>;

export async function fetchWorldLanding(slug: string, signal?: AbortSignal) {
  const data = await apiGet<unknown>(`/worlds/${slug}/`, signal);
  return worldLandingSchema.parse(data);
}

export async function fetchMyCharacter(slug: string, signal?: AbortSignal) {
  try {
    const data = await apiGet<unknown>(`/worlds/${slug}/character/`, signal);
    return characterSchema.parse(data);
  } catch (err) {
    // 404 not_joined → show join form; other errors bubble to QueryState.
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export async function joinWorld(
  slug: string,
  input: { role_template_id: string; display_name: string; invite_ref?: string },
) {
  await ensureCsrf();
  const data = await apiSend<unknown>('post', `/worlds/${slug}/join/`, input, {
    idempotent: true,
  });
  return characterSchema.parse(data);
}
