Yes. For a Discord-like app, I’d avoid putting everything into one database model. A scalable design is usually:

* **PostgreSQL** for strongly relational/control-plane data: users, guilds, roles, permissions, channel definitions, memberships.
* **ScyllaDB/Cassandra** for the high-volume message timeline.
* **Redis** for ephemeral/cached state: sessions, presence, rate limits, hot permission caches.
* **Elasticsearch/OpenSearch** for full-text message search.
* Object storage for attachments.

Discord publicly documents a similar separation: its current persistence infrastructure includes ScyllaDB, Postgres, and Elasticsearch, while its message store partitions messages by **channel + time bucket** and orders them by Snowflake message ID. ([Discord][1])

Below is a schema I would actually use as the foundation.

## 1. PostgreSQL: users and identity

```sql
CREATE TABLE users (
    id              BIGINT PRIMARY KEY,          -- Snowflake / distributed ID
    username        VARCHAR(32) NOT NULL,
    global_name     VARCHAR(64),
    email           VARCHAR(320),
    password_hash   TEXT,
    avatar_key      TEXT,

    status          SMALLINT NOT NULL DEFAULT 1,
    flags           BIGINT NOT NULL DEFAULT 0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT users_username_check
        CHECK (length(username) >= 2)
);

CREATE UNIQUE INDEX users_email_unique
ON users (lower(email))
WHERE email IS NOT NULL;

CREATE INDEX users_username_idx
ON users (lower(username));
```

I would **not** use username as the primary identity.

Everything references:

```text
user_id = 928374982374982374
```

not:

```text
username = "alice"
```

because usernames change.

---

# 2. Guild/server table

```sql
CREATE TABLE guilds (
    id                  BIGINT PRIMARY KEY,
    owner_id            BIGINT NOT NULL REFERENCES users(id),

    name                VARCHAR(100) NOT NULL,
    description         TEXT,

    icon_key            TEXT,
    banner_key          TEXT,

    verification_level  SMALLINT NOT NULL DEFAULT 0,
    default_notifications SMALLINT NOT NULL DEFAULT 0,

    member_count        INTEGER NOT NULL DEFAULT 0,

    flags               BIGINT NOT NULL DEFAULT 0,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX guilds_owner_idx
ON guilds(owner_id);
```

Do **not** store:

```json
{
  "members": [...],
  "channels": [...],
  "roles": [...]
}
```

inside the guild row.

A guild could eventually have millions of members.

Keep those relations independently partitionable.

---

# 3. Guild memberships

This becomes one of your biggest relational tables.

```sql
CREATE TABLE guild_members (
    guild_id            BIGINT NOT NULL,
    user_id             BIGINT NOT NULL,

    nickname            VARCHAR(64),

    joined_at           TIMESTAMPTZ NOT NULL,
    premium_since       TIMESTAMPTZ,

    flags               BIGINT NOT NULL DEFAULT 0,

    timeout_until       TIMESTAMPTZ,

    PRIMARY KEY (guild_id, user_id)
);
```

Indexes:

```sql
CREATE INDEX guild_members_user_idx
ON guild_members(user_id, guild_id);

CREATE INDEX guild_members_joined_idx
ON guild_members(guild_id, joined_at DESC);
```

This gives you both important access patterns:

```text
Get members of guild X
```

and:

```text
Get guilds user X belongs to
```

At very high scale, however, I'd eventually split those into **two query-optimized representations** rather than relying on one gigantic secondary index:

```text
guild_members_by_guild
guild_members_by_user
```

That's a recurring theme in large distributed applications:

> Design around query patterns, not normalized elegance.

---

# 4. Channels

You need multiple channel types.

```sql
CREATE TABLE channels (
    id                  BIGINT PRIMARY KEY,

    guild_id            BIGINT REFERENCES guilds(id),
    parent_id           BIGINT REFERENCES channels(id),

    channel_type        SMALLINT NOT NULL,

    name                VARCHAR(100),
    topic               TEXT,

    position            INTEGER NOT NULL DEFAULT 0,

    bitrate             INTEGER,
    user_limit          INTEGER,

    nsfw                BOOLEAN NOT NULL DEFAULT FALSE,

    rate_limit_seconds  INTEGER NOT NULL DEFAULT 0,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Example channel types:

```text
0 = text
1 = DM
2 = voice
3 = group DM
4 = category
5 = announcement
10 = thread
11 = public thread
12 = private thread
13 = stage
14 = forum
```

Index:

```sql
CREATE INDEX channels_guild_idx
ON channels(guild_id, position, id);
```

Getting all channels in one server is then cheap:

```sql
SELECT *
FROM channels
WHERE guild_id = $1
ORDER BY position, id;
```

---

# 5. Direct-message conversations

Don't model DMs as arbitrary special cases everywhere.

Treat them as conversations/channels.

```sql
CREATE TABLE dm_channels (
    channel_id      BIGINT PRIMARY KEY REFERENCES channels(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE dm_participants (
    channel_id      BIGINT NOT NULL REFERENCES dm_channels(channel_id),
    user_id         BIGINT NOT NULL REFERENCES users(id),

    joined_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY(channel_id, user_id)
);

CREATE INDEX dm_participants_user_idx
ON dm_participants(user_id, channel_id);
```

Then messages work almost identically for:

```text
server channels
group DMs
1:1 DMs
threads
```

because they all ultimately have a:

```text
channel_id
```

That simplification pays off enormously.

---

# 6. Roles

```sql
CREATE TABLE roles (
    id              BIGINT PRIMARY KEY,
    guild_id        BIGINT NOT NULL REFERENCES guilds(id),

    name            VARCHAR(100) NOT NULL,

    permissions     BIGINT NOT NULL DEFAULT 0,

    position        INTEGER NOT NULL DEFAULT 0,

    color           INTEGER,
    hoist           BOOLEAN NOT NULL DEFAULT FALSE,
    mentionable     BOOLEAN NOT NULL DEFAULT FALSE,

    managed         BOOLEAN NOT NULL DEFAULT FALSE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX roles_guild_idx
ON roles(guild_id, position DESC);
```

The important piece:

```text
permissions BIGINT
```

Don't create:

```text
can_send_messages BOOLEAN
can_ban_members BOOLEAN
can_manage_channels BOOLEAN
can_create_threads BOOLEAN
...
```

Use a bitfield.

For example:

```text
VIEW_CHANNEL        = 1 << 0
SEND_MESSAGES       = 1 << 1
MANAGE_MESSAGES     = 1 << 2
MANAGE_CHANNELS     = 1 << 3
MANAGE_GUILD        = 1 << 4
BAN_MEMBERS         = 1 << 5
KICK_MEMBERS        = 1 << 6
ADMINISTRATOR       = 1 << 7
CONNECT_VOICE       = 1 << 8
...
```

Then:

```python
if permissions & SEND_MESSAGES:
    ...
```

is extremely cheap.

---

# 7. Member roles

```sql
CREATE TABLE member_roles (
    guild_id        BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,
    role_id         BIGINT NOT NULL,

    PRIMARY KEY(guild_id, user_id, role_id)
);

CREATE INDEX member_roles_role_idx
ON member_roles(guild_id, role_id, user_id);
```

Your permission calculation becomes approximately:

```text
Guild everyone role
        ↓
OR together
        ↓
member-specific roles
        ↓
channel permission overrides
        ↓
final permissions
```

Do not query the database repeatedly during every WebSocket event.

Cache the resolved information.

---

# 8. Channel permission overrides

```sql
CREATE TABLE channel_permission_overwrites (
    channel_id          BIGINT NOT NULL,
    target_id           BIGINT NOT NULL,

    target_type         SMALLINT NOT NULL,
    -- 0 = role
    -- 1 = member

    allow_permissions   BIGINT NOT NULL DEFAULT 0,
    deny_permissions    BIGINT NOT NULL DEFAULT 0,

    PRIMARY KEY(channel_id, target_type, target_id)
);
```

This gives:

```text
channel
   │
   ├── @everyone DENY SEND
   ├── moderator ALLOW SEND
   └── user Alice DENY VIEW
```

without duplicating complete permissions for every user.

---

# 9. The critical part: messages

Don't put trillions of messages in your PostgreSQL `messages` table if you're designing for Discord-scale.

For an MVP? PostgreSQL is perfectly fine.

For extreme scale, separate the message store.

Discord publicly documented this simplified message schema for its Cassandra/Scylla-style storage:

```sql
CREATE TABLE messages (
    channel_id bigint,
    bucket int,
    message_id bigint,
    author_id bigint,
    content text,

    PRIMARY KEY ((channel_id, bucket), message_id)
)
WITH CLUSTERING ORDER BY (message_id DESC);
```

The partition key is:

```text
(channel_id, bucket)
```

rather than simply:

```text
channel_id
```

so a ten-year-old extremely active channel doesn't create one gigantic partition. ([Discord][2])

I would extend that concept substantially.

---

# 10. Production ScyllaDB messages schema

Something like:

```sql
CREATE TABLE messages_by_channel_bucket (
    channel_id          bigint,
    bucket              int,
    message_id          bigint,

    author_id           bigint,

    message_type        tinyint,

    content             text,

    created_at          timestamp,
    edited_at           timestamp,

    reply_message_id    bigint,

    flags               bigint,

    nonce               text,

    PRIMARY KEY (
        (channel_id, bucket),
        message_id
    )
)
WITH CLUSTERING ORDER BY (message_id DESC);
```

Query:

```sql
SELECT *
FROM messages_by_channel_bucket
WHERE channel_id = ?
AND bucket = ?
LIMIT 50;
```

This is basically the ideal Discord query:

> Give me the latest 50 messages in this channel.

---

# 11. What is the bucket?

For example:

```text
bucket = YYYYMM
```

So:

```text
August 2026 → 202608
September 2026 → 202609
```

Then:

```text
(channel_123, 202608)
```

is one partition.

But fixed monthly buckets aren't always optimal.

A massive channel could generate tens of millions of messages in a month.

You might instead use:

```text
day bucket
```

or calculate buckets from the Snowflake:

```python
bucket = message_timestamp // BUCKET_DURATION
```

For normal channels:

```text
7-day bucket
```

For gigantic channels:

```text
1-day bucket
```

But I'd initially keep it predictable.

---

# 12. Attachments

Never store images/video/files inside your main DB.

Store:

```text
metadata → DB
binary → S3/R2/GCS
```

Schema:

```sql
CREATE TABLE message_attachments (
    message_id          BIGINT NOT NULL,
    attachment_id       BIGINT NOT NULL,

    object_key          TEXT NOT NULL,

    filename            TEXT NOT NULL,
    content_type        VARCHAR(128),

    size_bytes          BIGINT NOT NULL,

    width               INTEGER,
    height              INTEGER,

    duration_ms         INTEGER,

    PRIMARY KEY(message_id, attachment_id)
);
```

Object storage:

```text
attachments/
    ab/
      cd/
        983749837498374.jpg
```

Deliver through CDN:

```text
client
  ↓
CDN
  ↓ cache miss
object storage
```

Your API servers should not normally proxy large media files.

---

# 13. Message embeds

```sql
CREATE TABLE message_embeds (
    message_id      BIGINT NOT NULL,
    embed_index     SMALLINT NOT NULL,

    embed_type      SMALLINT,

    url             TEXT,
    title           TEXT,
    description     TEXT,

    metadata        JSONB,

    PRIMARY KEY(message_id, embed_index)
);
```

JSON is appropriate here because embeds are relatively flexible structures.

Don't use JSON for everything.

Use it where the schema is legitimately dynamic.

---

# 14. Message reactions

This gets interesting.

Naïve:

```sql
CREATE TABLE reactions (
   message_id BIGINT,
   user_id BIGINT,
   emoji TEXT
);
```

At scale, optimize for:

```text
Which emojis are on this message?
How many reactions?
Did the current user react?
Who reacted with 👍?
```

I'd use:

```sql
CREATE TABLE message_reaction_counts (
    message_id      BIGINT NOT NULL,
    emoji_key       VARCHAR(128) NOT NULL,

    reaction_count  INTEGER NOT NULL,

    PRIMARY KEY(message_id, emoji_key)
);
```

and:

```sql
CREATE TABLE message_reactions (
    message_id      BIGINT NOT NULL,
    emoji_key       VARCHAR(128) NOT NULL,
    user_id         BIGINT NOT NULL,

    created_at      TIMESTAMPTZ NOT NULL,

    PRIMARY KEY(message_id, emoji_key, user_id)
);
```

At huge scale these could migrate from Postgres into Scylla.

---

# 15. Custom emoji

```sql
CREATE TABLE guild_emojis (
    id              BIGINT PRIMARY KEY,
    guild_id        BIGINT NOT NULL,

    creator_id      BIGINT,

    name            VARCHAR(64) NOT NULL,

    image_key       TEXT NOT NULL,

    animated        BOOLEAN NOT NULL DEFAULT FALSE,
    available       BOOLEAN NOT NULL DEFAULT TRUE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX guild_emojis_guild_idx
ON guild_emojis(guild_id);
```

---

# 16. Threads

I'd model threads as channels.

That's important.

Don't create an entirely separate messaging architecture.

```text
channel
    type=text

channel
    type=thread

channel
    type=forum_post
```

Then add thread-specific metadata:

```sql
CREATE TABLE channel_threads (
    channel_id          BIGINT PRIMARY KEY REFERENCES channels(id),

    owner_id            BIGINT NOT NULL,

    archived            BOOLEAN NOT NULL DEFAULT FALSE,
    locked              BOOLEAN NOT NULL DEFAULT FALSE,

    auto_archive_minutes INTEGER,

    archived_at         TIMESTAMPTZ
);
```

Messages still query:

```text
messages_by_channel_bucket(thread_channel_id, bucket)
```

Beautifully simple.

---

# 17. Thread membership

```sql
CREATE TABLE thread_members (
    thread_id       BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,

    joined_at       TIMESTAMPTZ NOT NULL,

    flags           BIGINT NOT NULL DEFAULT 0,

    PRIMARY KEY(thread_id, user_id)
);

CREATE INDEX thread_members_user_idx
ON thread_members(user_id, thread_id);
```

---

# 18. Read state

This is critical.

Don't create:

```text
message_read_receipts
```

containing:

```text
user A read message 1
user A read message 2
user A read message 3
...
```

That explodes.

Instead:

```sql
CREATE TABLE channel_read_states (
    user_id                 BIGINT NOT NULL,
    channel_id              BIGINT NOT NULL,

    last_read_message_id    BIGINT,
    mention_count           INTEGER NOT NULL DEFAULT 0,

    updated_at              TIMESTAMPTZ NOT NULL,

    PRIMARY KEY(user_id, channel_id)
);
```

Suppose channel latest message is:

```text
9000
```

user last read:

```text
8500
```

Then UI knows there are unread messages after message `8500`.

This reduces potentially:

```text
billions/trillions of read rows
```

to:

```text
one row per user/channel relationship
```

---

# 19. Mentions

For notification queries:

```sql
CREATE TABLE user_mentions (
    user_id         BIGINT NOT NULL,
    message_id      BIGINT NOT NULL,

    guild_id        BIGINT,
    channel_id      BIGINT NOT NULL,

    created_at      TIMESTAMPTZ NOT NULL,

    PRIMARY KEY(user_id, message_id)
);
```

At bigger scale:

```text
mentions_by_user_bucket
```

could move to Scylla:

```sql
PRIMARY KEY ((user_id, bucket), message_id)
```

ordered descending.

---

# 20. Notifications

Notifications should be separate from messages.

```sql
CREATE TABLE notifications (
    id              BIGINT PRIMARY KEY,
    user_id         BIGINT NOT NULL,

    type            SMALLINT NOT NULL,

    guild_id        BIGINT,
    channel_id      BIGINT,
    message_id      BIGINT,
    actor_id        BIGINT,

    payload         JSONB,

    read_at         TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX notifications_user_idx
ON notifications(user_id, created_at DESC);
```

At massive scale:

```text
notifications_by_user_bucket
```

belongs in Scylla too.

---

# 21. Friends / relationships

```sql
CREATE TABLE user_relationships (
    user_id         BIGINT NOT NULL,
    target_user_id  BIGINT NOT NULL,

    relationship_type SMALLINT NOT NULL,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY(user_id, target_user_id)
);
```

Types:

```text
1 = friend
2 = blocked
3 = incoming request
4 = outgoing request
```

Represent both directions explicitly when useful.

Again:

> A little duplication can dramatically simplify distributed reads.

---

# 22. Invitations

```sql
CREATE TABLE guild_invites (
    code                VARCHAR(32) PRIMARY KEY,

    guild_id            BIGINT NOT NULL,
    channel_id          BIGINT,

    inviter_id          BIGINT,

    max_uses            INTEGER,
    uses                INTEGER NOT NULL DEFAULT 0,

    max_age_seconds     INTEGER,

    temporary           BOOLEAN NOT NULL DEFAULT FALSE,

    expires_at          TIMESTAMPTZ,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX guild_invites_guild_idx
ON guild_invites(guild_id);
```

You'd commonly cache invite lookups:

```text
invite:abcXYZ → invite metadata
```

in Redis.

---

# 23. Bans

```sql
CREATE TABLE guild_bans (
    guild_id        BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,

    moderator_id    BIGINT,

    reason          TEXT,

    created_at      TIMESTAMPTZ NOT NULL,

    PRIMARY KEY(guild_id, user_id)
);
```

---

# 24. Moderation audit log

This should be append-only.

```sql
CREATE TABLE audit_log_entries (
    id              BIGINT PRIMARY KEY,

    guild_id        BIGINT NOT NULL,

    actor_id        BIGINT,
    target_id       BIGINT,

    action_type     SMALLINT NOT NULL,

    reason          TEXT,

    changes         JSONB,

    created_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX audit_log_guild_idx
ON audit_log_entries(guild_id, id DESC);
```

Snowflake IDs make:

```text
ORDER BY id DESC
```

naturally useful because Snowflake-style IDs are time sortable. Discord likewise documents its IDs as chronologically sortable Snowflakes. ([Discord][2])

---

# 25. Voice state

Don't persist constantly changing voice state into Postgres.

This:

```text
Alice joined General
Alice muted
Alice unmuted
Alice started streaming
Alice left
```

belongs primarily in:

```text
memory / distributed realtime state
```

or Redis if needed.

Example:

```text
voice:guild:123
```

```json
{
  "alice": {
    "channel_id": 456,
    "muted": false,
    "deafened": false
  }
}
```

You can persist historical call information separately if the product needs it.

---

# 26. Presence

Likewise:

```text
online
idle
do-not-disturb
offline
current activities
```

should not continuously hammer PostgreSQL.

Redis/in-memory:

```text
presence:user:123
```

```json
{
  "status": "online",
  "last_seen": 1786442000,
  "sessions": [...]
}
```

TTL it.

If Redis loses this data?

That's acceptable.

Users reconnect and reconstruct presence.

That's the distinction between:

```text
durable state
```

and:

```text
ephemeral state
```

---

# 27. Sessions

```sql
CREATE TABLE user_sessions (
    id                  UUID PRIMARY KEY,

    user_id             BIGINT NOT NULL,

    token_hash          BYTEA NOT NULL,

    device_type         SMALLINT,
    user_agent          TEXT,

    ip_hash             BYTEA,

    created_at          TIMESTAMPTZ NOT NULL,
    last_used_at        TIMESTAMPTZ NOT NULL,

    expires_at          TIMESTAMPTZ NOT NULL,
    revoked_at          TIMESTAMPTZ
);

CREATE INDEX sessions_user_idx
ON user_sessions(user_id);
```

Never store raw session tokens.

Store:

```text
hash(token)
```

so a DB leak doesn't immediately hand out active sessions.

---

# 28. Bots/applications

```sql
CREATE TABLE applications (
    id              BIGINT PRIMARY KEY,
    owner_id        BIGINT NOT NULL,

    name            VARCHAR(100) NOT NULL,

    description     TEXT,

    public          BOOLEAN NOT NULL DEFAULT TRUE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

```sql
CREATE TABLE bots (
    application_id  BIGINT PRIMARY KEY,
    bot_user_id     BIGINT UNIQUE NOT NULL,

    token_hash      BYTEA NOT NULL
);
```

---

# 29. Webhooks

```sql
CREATE TABLE webhooks (
    id              BIGINT PRIMARY KEY,

    guild_id        BIGINT,
    channel_id      BIGINT NOT NULL,

    creator_id      BIGINT,

    name            VARCHAR(80),

    token_hash      BYTEA,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX webhooks_channel_idx
ON webhooks(channel_id);
```

---

# 30. Message search

Do not try:

```sql
SELECT *
FROM messages
WHERE content ILIKE '%hello%';
```

against billions/trillions of rows.

Send searchable message metadata asynchronously into Elasticsearch/OpenSearch.

Conceptually:

```json
{
  "message_id": 921873981273,
  "guild_id": 100,
  "channel_id": 200,
  "author_id": 300,
  "content": "hello world",
  "created_at": "2026-08-11T09:00:00Z",
  "has_attachment": false
}
```

Pipeline:

```text
Message created
       │
       ├─────────► ScyllaDB
       │
       └─────────► event queue
                       │
                       ▼
                 index workers
                       │
                       ▼
                  OpenSearch
```

So persistence isn't blocked by search indexing.

Discord similarly separates message persistence from search infrastructure. Its current search architecture places guild and DM messages into separate Elasticsearch “cells,” and particularly huge guilds can use multiple primary shards because individual guild histories can reach billions of messages. ([Discord][3])

---

# 31. Message deletion

There's an important distributed-systems issue here.

A message can exist in:

```text
ScyllaDB
Redis cache
OpenSearch
notification references
client caches
```

So don't make your API perform five synchronous deletes.

Publish an event:

```json
{
  "type": "MESSAGE_DELETED",
  "message_id": 123,
  "channel_id": 456
}
```

Consumers handle:

```text
Scylla delete
search index delete
cache invalidation
WebSocket fan-out
moderation bookkeeping
```

This is **eventual consistency**.

You need to embrace that in a system this large.

---

# 32. Recommended event table / outbox

If Postgres produces important asynchronous work, use an outbox pattern.

```sql
CREATE TABLE outbox_events (
    id              BIGSERIAL PRIMARY KEY,

    aggregate_type  VARCHAR(64) NOT NULL,
    aggregate_id    BIGINT NOT NULL,

    event_type      VARCHAR(128) NOT NULL,

    payload         JSONB NOT NULL,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    published_at    TIMESTAMPTZ
);

CREATE INDEX outbox_unpublished_idx
ON outbox_events(id)
WHERE published_at IS NULL;
```

Your transaction can do:

```text
BEGIN

create channel

insert CHANNEL_CREATED event

COMMIT
```

Then an async publisher puts that event into Kafka/NATS/etc.

This avoids:

```text
DB write succeeded
Kafka publish failed
→ inconsistent state
```

---

# 33. Snowflake ID design

For distributed creation of:

```text
messages
guilds
channels
roles
attachments
```

use a 64-bit distributed ID.

Something conceptually like:

```text
┌──────────── timestamp ───────────┐
│                                 │
63                               ...
             worker       sequence
               │              │
               ▼              ▼
       ┌──────────────┬───────────┐
       │ timestamp    │ worker │seq│
       └──────────────┴───────────┘
```

Example allocation:

```text
41 bits timestamp
10 bits worker
12 bits sequence
```

Exact allocation depends on your requirements.

Benefits:

```text
no central auto-increment DB
rough chronological ordering
high write throughput
generation from many services
```

---

# 34. PostgreSQL shard strategy

Once one Postgres cluster becomes insufficient, don't randomly shard every table.

Shard by natural ownership.

For guild-oriented data:

```text
hash(guild_id) % N
```

For example:

```text
guild 100 → shard 3
guild 101 → shard 9
guild 102 → shard 1
```

Keep:

```text
guild
channels
roles
member roles
permission overwrites
bans
audit logs
```

near the guild whenever possible.

But user-centric tables:

```text
sessions
relationships
DM membership
account settings
```

can be sharded by:

```text
user_id
```

You therefore eventually have different storage domains.

---

# 35. Don't use cross-shard SQL joins

Once sharded:

```text
SELECT *
FROM users
JOIN guild_members
JOIN guilds
JOIN channels...
```

becomes painful.

Services instead make bounded lookups:

```text
Guild Service
      │
      ├── guild metadata
      ├── role metadata
      └── membership lookup
```

and aggressively cache reusable information.

---

# 36. Redis key schema

I'd structure Redis intentionally.

Example:

```text
user:123:profile
guild:456
guild:456:roles
guild:456:channels

member:456:123
permissions:456:789:123

presence:123

ratelimit:user:123
ratelimit:ip:abc

session:abcdef

typing:channel:456
```

But don't blindly cache everything.

Cache things with:

```text
high read frequency
low/moderate mutation frequency
expensive recomputation
```

Permissions are a great example.

---

# 37. Permission cache

Permission calculation may require:

```text
guild owner?
+
everyone role
+
member roles
+
channel role overrides
+
member overrides
+
administrator flag
```

If every message does several DB queries, you're finished.

Instead:

```text
permissions:{guild}:{channel}:{user}
```

→ resolved bitset.

Invalidate when:

```text
role updated
member role changed
channel overwrite changed
guild ownership changed
```

---

# 38. Rate-limit storage

API rate limits:

```text
rl:user:{user_id}:{route}
rl:ip:{ip}:{route}
rl:guild:{guild_id}:{action}
```

with counters and short expiration.

Redis is appropriate.

Postgres isn't.

---

# 39. Typing indicators

Never persist:

```text
Alice is typing...
```

in your durable DB.

It should be an event:

```text
TYPING_START
channel=456
user=123
expires=10s
```

Possibly tracked in:

```text
gateway memory
```

or ephemeral Redis if necessary.

---

# 40. Online/member counters

Don't constantly execute:

```sql
SELECT COUNT(*)
FROM guild_members
WHERE guild_id = 123;
```

for every render.

Maintain counters:

```text
guild.member_count
```

and potentially:

```text
guild:123:online_count
```

in your realtime layer.

Counters can occasionally drift.

Reconcile them asynchronously.

---

# 41. Database responsibility map

This is the architecture I'd aim toward:

```text
                         CLIENTS
                            │
                    HTTP / WebSocket
                            │
               ┌────────────┴────────────┐
               │                         │
               ▼                         ▼
          API services             Gateway services
               │                         │
       ┌───────┼────────┐            ephemeral
       │       │        │               state
       ▼       ▼        ▼                 │
 PostgreSQL  Redis    Kafka/NATS           ▼
       │       │        │                Redis
       │       │        │
       │       │        ├─────────────┐
       │       │        │             │
       │       │        ▼             ▼
       │       │    Search workers   Push workers
       │       │        │
       │       │        ▼
       │       │    OpenSearch
       │       │
       │       ▼
       │   Cache / presence
       │
       └────────────────┐
                        │
                message service
                        │
                        ▼
                    ScyllaDB
                        │
                        ▼
               message timelines

attachments
    │
    ▼
Object Storage
    │
    ▼
   CDN
```

---

# 42. Full data-domain breakdown

I'd end up with something approximately like this:

```text
POSTGRESQL
──────────────────────────
users
user_settings
user_sessions
user_relationships

guilds
guild_members
roles
member_roles

channels
channel_permission_overwrites

dm_channels
dm_participants

thread_metadata
thread_members

guild_emojis
guild_invites
guild_bans

applications
bots
webhooks

audit_log_entries


SCYLLADB
──────────────────────────
messages_by_channel_bucket

mentions_by_user_bucket
notifications_by_user_bucket

possibly:
reactions_by_message
message_reactions_by_user

event history / selected timelines


REDIS
──────────────────────────
presence
typing
gateway sessions
rate limits

hot guild metadata
permissions cache
membership cache
channel cache

distributed locks
short-lived coordination


OPENSEARCH / ELASTICSEARCH
──────────────────────────
message search


OBJECT STORAGE
──────────────────────────
avatars
attachments
videos
voice recordings (if supported)
guild icons
stickers
emoji
```

---

# 43. The most important Scylla tables

Don't think relationally here.

You might intentionally maintain multiple versions of the same logical information.

### Channel timeline

```sql
CREATE TABLE messages_by_channel_bucket (
    channel_id bigint,
    bucket int,
    message_id bigint,
    author_id bigint,
    content text,
    created_at timestamp,
    edited_at timestamp,
    flags bigint,

    PRIMARY KEY ((channel_id, bucket), message_id)
)
WITH CLUSTERING ORDER BY (message_id DESC);
```

### User mentions

```sql
CREATE TABLE mentions_by_user_bucket (
    user_id bigint,
    bucket int,
    message_id bigint,

    guild_id bigint,
    channel_id bigint,

    created_at timestamp,

    PRIMARY KEY ((user_id, bucket), message_id)
)
WITH CLUSTERING ORDER BY (message_id DESC);
```

### Notifications

```sql
CREATE TABLE notifications_by_user_bucket (
    user_id bigint,
    bucket int,
    notification_id bigint,

    type tinyint,
    guild_id bigint,
    channel_id bigint,
    message_id bigint,
    actor_id bigint,

    payload text,

    created_at timestamp,

    PRIMARY KEY ((user_id, bucket), notification_id)
)
WITH CLUSTERING ORDER BY (notification_id DESC);
```

Notice the duplication.

That's normal.

In Scylla/Cassandra, you generally model:

```text
table = query
```

rather than:

```text
normalized entity graph
```

---

# 44. Query patterns should define your schema

Before creating a database table, write its important queries.

For messages:

```text
Q1: latest 50 messages in channel
Q2: 50 messages before message X
Q3: 50 messages after message X
Q4: fetch one message
Q5: search messages
```

Then choose storage:

```text
Q1/Q2/Q3 → Scylla timeline

Q4 → timeline lookup / optional direct lookup table

Q5 → OpenSearch
```

Don't force one table to satisfy all five.

---

# 45. Optional message lookup table

If you frequently need:

```text
GET /channels/123/messages/987654321
```

but don't know its bucket, either derive bucket from the Snowflake timestamp or create:

```sql
CREATE TABLE message_locations (
    message_id      bigint PRIMARY KEY,
    channel_id      bigint,
    bucket          int
);
```

I'd prefer deriving it from the Snowflake when possible.

That eliminates another write.

---

# 46. What I would actually build at the beginning

Here's something important.

If you're starting with:

```text
0 users
```

don't deploy:

```text
Scylla
Kafka
Redis Cluster
OpenSearch
8 PostgreSQL shards
Kubernetes
37 microservices
```

You'll spend your life operating infrastructure.

Start:

```text
              Backend
                 │
         ┌───────┴───────┐
         ▼               ▼
     PostgreSQL         Redis
         │
         ▼
   Object Storage
```

Put messages initially in Postgres:

```sql
CREATE TABLE messages (
    id              BIGINT PRIMARY KEY,

    channel_id      BIGINT NOT NULL,
    author_id       BIGINT NOT NULL,

    content         TEXT,

    reply_to_id     BIGINT,

    flags           BIGINT NOT NULL DEFAULT 0,

    created_at      TIMESTAMPTZ NOT NULL,
    edited_at       TIMESTAMPTZ
);

CREATE INDEX messages_channel_timeline_idx
ON messages(channel_id, id DESC);
```

That's an extremely strong starting point.

Partition it later:

```sql
PARTITION BY HASH(channel_id)
```

or use application-level sharding when necessary.

Then migrate only the timeline to Scylla once message volume demands it.

---

# 47. Evolution path I'd recommend

```text
STAGE 1
< 100k users

PostgreSQL
Redis
S3
WebSockets

             ↓

STAGE 2
100k–1M users

PostgreSQL replicas
partitioned messages
Redis cluster
background queue
OpenSearch
CDN

             ↓

STAGE 3
1M–10M+

Postgres domain shards
Scylla message store
Kafka
dedicated gateway
distributed cache
OpenSearch clusters

             ↓

STAGE 4
huge scale

Scylla cells/clusters
user/guild database shards
consistent-hash routing
request coalescing
regional gateways
partitioned event consumers
dedicated large-guild treatment
multi-region infrastructure
```

The exact user counts aren't hard thresholds; traffic shape matters much more.

A 100k-user crypto trading community can create more load than several million mostly inactive accounts.

---

# 48. One particularly important thing not to copy blindly

Discord's current architecture operates at a scale where ScyllaDB itself spans **dozens of clusters and hundreds of database nodes** and stores messages, channels, servers, and much of user data. ([Discord][1])

That architecture is a destination, not a sensible MVP starting point.

Your first scalable design should therefore optimize for a **clean migration path**:

```text
                    TODAY

                  PostgreSQL
                /     |      \
           users   guilds   messages

                         │
                         │ traffic grows
                         ▼

                    LATER

           ┌────────────┼─────────────┐
           ▼            ▼             ▼
       Postgres       Scylla      OpenSearch
        control      messages       search
        plane
```

The key is keeping your IDs, service boundaries, APIs, and query patterns clean enough that moving `messages` out of Postgres later doesn't require rewriting the entire application.

For a new Discord-like product, **that is the schema architecture I would use**: Snowflake IDs everywhere, `channel_id` as the universal conversation abstraction, PostgreSQL for relationships and permissions, channel+time-bucket Scylla partitions for timelines, Redis only for disposable/hot state, async search indexing, and object storage for binaries.

[1]: https://discord.com/blog/how-discord-automates-scylladb-clusters-at-scale?utm_source=chatgpt.com "How Discord Automates ScyllaDB Clusters at Scale"
[2]: https://discord.com/blog/how-discord-stores-trillions-of-messages?utm_source=chatgpt.com "How Discord Stores Trillions of Messages"
[3]: https://discord.com/blog/how-discord-indexes-trillions-of-messages?utm_source=chatgpt.com "How Discord Indexes Trillions of Messages"
