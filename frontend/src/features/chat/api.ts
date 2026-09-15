import { z } from 'zod';

import { apiGet, apiSend, ensureCsrf } from '@/api/client';
import { newIdempotencyKey } from '@/api/idempotency';

export const serverSchema = z.object({
  id: z.union([z.string(), z.number()]),
  name: z.string(),
  description: z.string().optional().default(''),
  owner_id: z.string().optional(),
  member_count: z.number().optional(),
  created_at: z.string().optional(),
});

export const channelSchema = z.object({
  id: z.union([z.string(), z.number()]),
  server_id: z.union([z.string(), z.number()]).nullable().optional(),
  type: z.number().optional(),
  name: z.string(),
  topic: z.string().optional().default(''),
  position: z.number().optional(),
});

export const messageSchema = z.object({
  id: z.union([z.string(), z.number()]),
  channel_id: z.union([z.string(), z.number()]),
  author_id: z.string().nullable(),
  content: z.string(),
  reply_to_id: z.union([z.string(), z.number()]).nullable().optional(),
  edited_at: z.string().nullable().optional(),
  deleted: z.boolean().optional().default(false),
  created_at: z.string(),
});

export type ChatServer = z.infer<typeof serverSchema>;
export type ChatChannel = z.infer<typeof channelSchema>;
export type ChatMessage = z.infer<typeof messageSchema>;

export async function fetchServers(signal?: AbortSignal) {
  const data = await apiGet<{ servers: unknown }>('/chat/servers/', signal);
  return z.object({ servers: z.array(serverSchema) }).parse(data).servers;
}

export async function createServer(name: string, description = '') {
  await ensureCsrf();
  const data = await apiSend<unknown>('post', '/chat/servers/', { name, description });
  return serverSchema.parse(data);
}

export async function fetchChannels(serverId: string | number, signal?: AbortSignal) {
  const data = await apiGet<{ channels: unknown }>(`/chat/servers/${serverId}/channels/`, signal);
  return z.object({ channels: z.array(channelSchema) }).parse(data).channels;
}

export async function createChannel(serverId: string | number, name: string) {
  await ensureCsrf();
  const data = await apiSend<unknown>('post', `/chat/servers/${serverId}/channels/`, { name });
  return channelSchema.parse(data);
}

export async function fetchMessages(channelId: string | number, signal?: AbortSignal) {
  const data = await apiGet<{ messages: unknown }>(
    `/chat/channels/${channelId}/messages/`,
    signal,
  );
  return z.object({ messages: z.array(messageSchema) }).parse(data).messages;
}

export async function sendMessage(channelId: string | number, content: string) {
  await ensureCsrf();
  const data = await apiSend<unknown>(
    'post',
    `/chat/channels/${channelId}/messages/`,
    { content },
    { idempotent: true, idempotencyKey: newIdempotencyKey() },
  );
  return messageSchema.parse(data);
}

export async function joinInvite(code: string) {
  await ensureCsrf();
  const data = await apiSend<unknown>('post', '/chat/invites/join/', { code });
  return serverSchema.parse(data);
}
