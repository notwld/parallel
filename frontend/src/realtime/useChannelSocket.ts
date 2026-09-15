import { useCallback, useEffect, useRef, useSyncExternalStore } from 'react';

import {
  getChannelSocket,
  releaseChannelSocket,
  type ChannelSocketEvent,
  type SocketStatus,
} from '@/realtime/channel-socket';

export function useChannelSocket(
  channelId: string | number | null | undefined,
  onEvent?: (event: ChannelSocketEvent) => void,
) {
  const id = channelId == null ? null : String(channelId);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!id) return;
    const sock = getChannelSocket(id);
    sock.connect();
    const off = sock.onEvent((event) => onEventRef.current?.(event));
    return () => {
      off();
      releaseChannelSocket(id);
    };
  }, [id]);

  const status = useSyncExternalStore(
    useCallback(
      (onStoreChange) => {
        if (!id) return () => {};
        return getChannelSocket(id).subscribe(onStoreChange);
      },
      [id],
    ),
    () => (id ? getChannelSocket(id).getStatus() : ('idle' as SocketStatus)),
    () => 'idle' as SocketStatus,
  );

  const sendTyping = useCallback(() => {
    if (!id) return;
    getChannelSocket(id).sendTyping();
  }, [id]);

  const retry = useCallback(() => {
    if (!id) return;
    getChannelSocket(id).retryNow();
  }, [id]);

  return { status, sendTyping, retry };
}
