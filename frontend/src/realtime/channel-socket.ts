/**
 * Production channel WebSocket manager (outside React lifecycle).
 * Patterns: exponential backoff + jitter, app ping/pong, bounded outbound queue,
 * REST catch-up signal on reconnect (FE066 / WebSocket.org guidance).
 */

export type SocketStatus = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'failed' | 'closed';

export type ChannelSocketEvent =
  | { type: 'message.create'; message: unknown }
  | { type: 'typing.start'; typing: unknown }
  | { type: 'pong' }
  | { type: 'error'; code?: string }
  | { type: string; [key: string]: unknown };

type Listener = () => void;
type EventHandler = (event: ChannelSocketEvent) => void;

const MAX_ATTEMPTS = 12;
const MAX_QUEUE = 50;
const PING_MS = 25_000;
const PONG_TIMEOUT_MS = 10_000;

function backoffMs(attempt: number) {
  const base = Math.min(500 * 2 ** attempt, 30_000);
  return base * (0.5 + Math.random() * 0.5);
}

function wsUrl(channelId: string | number): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws/chat/channels/${channelId}/`;
}

export class ChannelSocket {
  readonly channelId: string;
  private ws: WebSocket | null = null;
  private status: SocketStatus = 'idle';
  private attempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private pongTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalClose = false;
  private outbound: string[] = [];
  private readonly listeners = new Set<Listener>();
  private readonly eventHandlers = new Set<EventHandler>();
  private lastOpenAt = 0;

  constructor(channelId: string | number) {
    this.channelId = String(channelId);
  }

  getStatus(): SocketStatus {
    return this.status;
  }

  /** True after a successful reconnect so callers can REST catch-up. */
  consumeNeedsCatchUp(): boolean {
    if (this.lastOpenAt && this.attempt > 0) {
      this.attempt = 0;
      return true;
    }
    return false;
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  onEvent(handler: EventHandler): () => void {
    this.eventHandlers.add(handler);
    return () => this.eventHandlers.delete(handler);
  }

  connect() {
    this.intentionalClose = false;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    this.clearReconnect();
    this.setStatus(this.attempt > 0 ? 'reconnecting' : 'connecting');
    const socket = new WebSocket(wsUrl(this.channelId));
    this.ws = socket;

    socket.onopen = () => {
      this.lastOpenAt = Date.now();
      const needsCatchUp = this.attempt > 0;
      this.attempt = 0;
      this.setStatus('open');
      this.flushOutbound();
      this.startHeartbeat();
      if (needsCatchUp) {
        this.emit({ type: 'socket.reconnected' });
      }
    };

    socket.onmessage = (ev) => {
      this.armPongWatch();
      try {
        const data = JSON.parse(String(ev.data)) as ChannelSocketEvent;
        if (data.type === 'pong') return;
        this.emit(data);
      } catch {
        /* ignore malformed */
      }
    };

    socket.onerror = () => {
      /* onclose handles retry */
    };

    socket.onclose = () => {
      this.stopHeartbeat();
      this.ws = null;
      if (this.intentionalClose) {
        this.setStatus('closed');
        return;
      }
      this.scheduleReconnect();
    };
  }

  close() {
    this.intentionalClose = true;
    this.clearReconnect();
    this.stopHeartbeat();
    this.ws?.close();
    this.ws = null;
    this.setStatus('closed');
  }

  /** Queue if not open; drop oldest when full. */
  send(payload: Record<string, unknown>) {
    const raw = JSON.stringify(payload);
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(raw);
      return;
    }
    if (this.outbound.length >= MAX_QUEUE) this.outbound.shift();
    this.outbound.push(raw);
  }

  sendTyping() {
    this.send({ type: 'typing.start' });
  }

  retryNow() {
    this.attempt = 0;
    this.clearReconnect();
    this.connect();
  }

  private scheduleReconnect() {
    if (this.attempt >= MAX_ATTEMPTS) {
      this.setStatus('failed');
      this.emit({ type: 'socket.failed' });
      return;
    }
    this.setStatus('reconnecting');
    const delay = backoffMs(this.attempt);
    this.attempt += 1;
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  private flushOutbound() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    while (this.outbound.length) {
      const next = this.outbound.shift();
      if (next) this.ws.send(next);
    }
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
        this.armPongWatch();
      }
    }, PING_MS);
  }

  private armPongWatch() {
    if (this.pongTimer) clearTimeout(this.pongTimer);
    this.pongTimer = setTimeout(() => {
      // Dead connection — force close to trigger reconnect.
      this.ws?.close();
    }, PONG_TIMEOUT_MS);
  }

  private stopHeartbeat() {
    if (this.pingTimer) clearInterval(this.pingTimer);
    if (this.pongTimer) clearTimeout(this.pongTimer);
    this.pingTimer = null;
    this.pongTimer = null;
  }

  private clearReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
  }

  private setStatus(status: SocketStatus) {
    if (this.status === status) return;
    this.status = status;
    this.listeners.forEach((l) => l());
  }

  private emit(event: ChannelSocketEvent) {
    this.eventHandlers.forEach((h) => h(event));
  }
}

const sockets = new Map<string, ChannelSocket>();

export function getChannelSocket(channelId: string | number): ChannelSocket {
  const key = String(channelId);
  let sock = sockets.get(key);
  if (!sock) {
    sock = new ChannelSocket(key);
    sockets.set(key, sock);
  }
  return sock;
}

export function releaseChannelSocket(channelId: string | number) {
  const key = String(channelId);
  const sock = sockets.get(key);
  if (sock) {
    sock.close();
    sockets.delete(key);
  }
}
