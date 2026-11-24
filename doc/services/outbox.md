---
title: Outbox Service
description: Transactional outbox — external effects that happen after the commit, at least once.
icon: material/email-fast-outline
---

# Outbox Service

A hook that runs inside a transaction cannot undo an external effect: a mail handed to the SMTP server during a document submission is gone even if a later write fails — and re-submitting sends a second copy.

With the outbox you do not perform the effect; you deposit an **intention** in *your* transaction. It is committed or rolled back **with** your document, and a dispatcher runs it after the commit.

---

### Usage

```python linenums="1"
outbox = self.get_service("outbox")

async with self.db.session() as session:
    ...                                        # the document writes
    await outbox.defer(
        "mail", "send", {"to": "a@b.c", "invoice": 42},
        key="invoice:42:submitted",            # idempotent: two deposits, one send
        session=session,                       # the caller's transaction
    )
# commit   → the dispatcher will call plugin "mail", action "send"
# rollback → the intention never existed
```

| Argument | Meaning |
|:--- | :--- |
| `plugin`, `task` | The plugin action to call (through the supervisor), or a function registered with `outbox.register(plugin, task, fn)`. |
| `session` | SQLAlchemy session/connection of the running transaction (async or sync). Omitted: committed at once in its own transaction. |
| `key` | Idempotency key. A second deposit of the same key deposits nothing (`Receipt.deferred` is `False`). |
| `delay` | Seconds to wait after the commit before the first attempt. |

The session must be on the outbox database (`services.outbox.database`), otherwise there is no shared transaction.

---

### Delivery

```
pending ──ok──▶ sent
   └─ failure ─▶ pending (attempts+1, exponential backoff) ─ max_attempts ─▶ dead
```

- **At least once.** A process dying after the send but before recording `sent` makes the intention run again. The task receives `payload["_outbox"]` (`id`, `key`, `attempt`) to deduplicate.
- A task fails by raising, or — for a plugin action — by returning `{"status": "error"}`.
- Several processes may dispatch: each intention is claimed with a lease on the database clock; a dead dispatcher's lease expires and another takes over.
- The tenant of the deposit is restored when the task runs.
- `outbox.notify()` wakes the dispatcher right after your commit instead of waiting for the next poll.

**Operations**: `await outbox.stats()`, `await outbox.list("dead")`, `await outbox.retry(intent_id)`.

---

### YAML Configuration

```yaml linenums="1" title="integration.yaml"
services:
  outbox:
    enabled: true            # default: false — needs a SQL connection in services.databases
    database: ~              # null = default connection (db)
    dispatch: true           # false: this process deposits, another one dispatches
    poll_seconds: 1.0
    batch_size: 20
    max_attempts: 8          # then the dead letter queue
    backoff_seconds: 5.0     # 5, 10, 20… capped by max_backoff_seconds
    max_backoff_seconds: 3600
    lease_seconds: 300       # keep above the slowest task timeout
    retention_seconds: 604800  # sent intentions are purged after 7 days (0 = never)
```

The table (`xcore_outbox`) is created on first start. On PostgreSQL it is addressed with its schema, so it stays reachable from a tenant session.
