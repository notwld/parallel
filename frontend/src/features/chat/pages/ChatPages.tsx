import { Link, useNavigate, useParams } from '@tanstack/react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo, useState, type FormEvent } from 'react';
import { toast } from 'sonner';

import { ApiError } from '@/api/client';
import { mutationScopes, queryKeys } from '@/api/query-client';
import { AppShell, AuthGate } from '@/components/layout/AppShell';
import { ConnectionBanner } from '@/components/loading/ConnectionBanner';
import { QueryState } from '@/components/loading/QueryState';
import { ListSkeleton, MessagePaneSkeleton } from '@/components/loading/skeletons';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  createChannel,
  createServer,
  fetchChannels,
  fetchMessages,
  fetchServers,
  joinInvite,
  sendMessage,
  type ChatMessage,
} from '@/features/chat/api';
import { useChannelSocket } from '@/realtime/useChannelSocket';
import type { ChannelSocketEvent } from '@/realtime/channel-socket';

export function ChatIndexPage() {
  return (
    <AppShell title="Chat">
      <AuthGate>
        <ServerList />
      </AuthGate>
    </AppShell>
  );
}

function ServerList() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const servers = useQuery({
    queryKey: queryKeys.chatServers,
    queryFn: ({ signal }) => fetchServers(signal),
  });
  const [name, setName] = useState('');
  const [invite, setInvite] = useState('');

  const create = useMutation({
    mutationFn: () => createServer(name),
    onSuccess: (server) => {
      void client.invalidateQueries({ queryKey: queryKeys.chatServers });
      toast.success('Server created');
      void navigate({ to: '/chat/servers/$serverId', params: { serverId: String(server.id) } });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : 'Create failed'),
  });

  const join = useMutation({
    mutationFn: () => joinInvite(invite),
    onSuccess: (server) => {
      void client.invalidateQueries({ queryKey: queryKeys.chatServers });
      toast.success(`Joined ${server.name}`);
      void navigate({ to: '/chat/servers/$serverId', params: { serverId: String(server.id) } });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : 'Join failed'),
  });

  return (
    <div className="space-y-8">
      <QueryState
        isPending={servers.isPending}
        isError={servers.isError}
        onRetry={() => void servers.refetch()}
        skeleton={<ListSkeleton rows={4} />}
        loadingLabel="Loading servers"
        isEmpty={!servers.data?.length}
        emptyTitle="No servers yet"
        emptyDescription="Create a server or join with an invite code."
      >
        <ul className="divide-y divide-border">
          {servers.data?.map((s) => (
            <li key={String(s.id)} className="py-3">
              <Link
                to="/chat/servers/$serverId"
                params={{ serverId: String(s.id) }}
                className="font-medium text-foreground no-underline hover:underline"
              >
                {s.name}
              </Link>
              {s.description ? (
                <p className="text-sm text-muted-foreground">{s.description}</p>
              ) : null}
            </li>
          ))}
        </ul>
      </QueryState>

      <form
        className="flex max-w-md flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <Input
          placeholder="New server name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <Button type="submit" disabled={create.isPending}>
          Create
        </Button>
      </form>

      <form
        className="flex max-w-md flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          join.mutate();
        }}
      >
        <Input
          placeholder="Invite code"
          value={invite}
          onChange={(e) => setInvite(e.target.value)}
          required
        />
        <Button type="submit" variant="outline" disabled={join.isPending}>
          Join invite
        </Button>
      </form>
    </div>
  );
}

export function ChatServerPage() {
  const { serverId } = useParams({ from: '/chat/servers/$serverId' });
  return (
    <AppShell title="Server">
      <AuthGate>
        <ServerWorkspace serverId={serverId} />
      </AuthGate>
    </AppShell>
  );
}

function ServerWorkspace({ serverId }: { serverId: string }) {
  const client = useQueryClient();
  const [channelId, setChannelId] = useState<string | null>(null);
  const [channelName, setChannelName] = useState('');
  const [draft, setDraft] = useState('');
  const [liveMessages, setLiveMessages] = useState<ChatMessage[]>([]);

  const channels = useQuery({
    queryKey: queryKeys.chatChannels(serverId),
    queryFn: ({ signal }) => fetchChannels(serverId, signal),
  });

  const activeChannel = channelId || (channels.data?.[0] ? String(channels.data[0].id) : null);

  const messages = useQuery({
    queryKey: queryKeys.chatMessages(activeChannel || 'none'),
    queryFn: ({ signal }) => fetchMessages(activeChannel!, signal),
    enabled: Boolean(activeChannel),
  });

  const onSocketEvent = useCallback(
    (event: ChannelSocketEvent) => {
      if (event.type === 'message.create' && event.message) {
        const parsed = event.message as ChatMessage;
        setLiveMessages((prev) => [...prev, parsed]);
      }
      if (event.type === 'socket.reconnected' && activeChannel) {
        void client.invalidateQueries({ queryKey: queryKeys.chatMessages(activeChannel) });
        setLiveMessages([]);
      }
    },
    [activeChannel, client],
  );

  const { status, sendTyping, retry } = useChannelSocket(activeChannel, onSocketEvent);

  const timeline = useMemo(() => {
    const base = messages.data || [];
    const byId = new Map(base.map((m) => [String(m.id), m]));
    for (const m of liveMessages) byId.set(String(m.id), m);
    return [...byId.values()].sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
  }, [messages.data, liveMessages]);

  const createCh = useMutation({
    mutationFn: () => createChannel(serverId, channelName),
    onSuccess: (ch) => {
      void client.invalidateQueries({ queryKey: queryKeys.chatChannels(serverId) });
      setChannelId(String(ch.id));
      setChannelName('');
      toast.success('Channel created');
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : 'Failed'),
  });

  const send = useMutation({
    scope: activeChannel ? mutationScopes.chatSend(activeChannel) : undefined,
    mutationFn: () => sendMessage(activeChannel!, draft),
    onSuccess: (msg) => {
      setDraft('');
      setLiveMessages((prev) => [...prev, msg]);
      void client.invalidateQueries({ queryKey: queryKeys.chatMessages(activeChannel!) });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : 'Send failed'),
  });

  function onSend(e: FormEvent) {
    e.preventDefault();
    if (!activeChannel || !draft.trim()) return;
    send.mutate();
  }

  return (
    <div className="space-y-4">
      <ConnectionBanner status={status} onRetry={retry} />
      <div className="grid gap-6 md:grid-cols-[14rem_1fr]">
        <aside className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">Channels</h2>
          <QueryState
            isPending={channels.isPending}
            isError={channels.isError}
            onRetry={() => void channels.refetch()}
            skeleton={<ListSkeleton rows={4} />}
            loadingLabel="Loading channels"
            isEmpty={!channels.data?.length}
            emptyTitle="No channels"
          >
            <ul className="space-y-1">
              {channels.data?.map((ch) => {
                const id = String(ch.id);
                const active = id === activeChannel;
                return (
                  <li key={id}>
                    <button
                      type="button"
                      className={`w-full rounded-md px-2 py-1.5 text-left text-sm ${
                        active ? 'bg-muted font-medium' : 'hover:bg-muted/50'
                      }`}
                      onClick={() => {
                        setChannelId(id);
                        setLiveMessages([]);
                      }}
                    >
                      # {ch.name}
                    </button>
                  </li>
                );
              })}
            </ul>
          </QueryState>
          <form
            className="flex gap-1"
            onSubmit={(e) => {
              e.preventDefault();
              createCh.mutate();
            }}
          >
            <Input
              placeholder="new-channel"
              value={channelName}
              onChange={(e) => setChannelName(e.target.value)}
              required
            />
            <Button type="submit" size="sm" variant="outline" disabled={createCh.isPending}>
              Add
            </Button>
          </form>
        </aside>

        <section>
          {!activeChannel ? (
            <p className="text-sm text-muted-foreground">Select or create a channel.</p>
          ) : (
            <QueryState
              isPending={messages.isPending}
              isError={messages.isError}
              onRetry={() => void messages.refetch()}
              skeleton={<MessagePaneSkeleton />}
              loadingLabel="Loading messages"
            >
              <div className="flex h-[min(70vh,32rem)] flex-col rounded-lg border border-border">
                <ScrollArea className="flex-1 p-4">
                  <ul className="space-y-3">
                    {timeline.map((m) => (
                      <li key={String(m.id)} className="text-sm">
                        <p className="text-xs text-muted-foreground">
                          {(m.author_id || '?').slice(0, 8)} ·{' '}
                          {new Date(m.created_at).toLocaleTimeString()}
                        </p>
                        <p>{m.deleted ? <em className="text-muted-foreground">deleted</em> : m.content}</p>
                      </li>
                    ))}
                  </ul>
                </ScrollArea>
                <form onSubmit={onSend} className="flex gap-2 border-t border-border p-3">
                  <Input
                    value={draft}
                    onChange={(e) => {
                      setDraft(e.target.value);
                      sendTyping();
                    }}
                    placeholder="Message"
                    disabled={send.isPending || status === 'failed'}
                  />
                  <Button type="submit" disabled={send.isPending || !draft.trim()}>
                    Send
                  </Button>
                </form>
              </div>
            </QueryState>
          )}
        </section>
      </div>
      <Button asChild variant="ghost" size="sm">
        <Link to="/chat">All servers</Link>
      </Button>
    </div>
  );
}
