# XCore V3 — Native Distributed Runtime

**Status:** Specification
**Target:** XCore V3
**Architecture:** Python + Rust
**Primary objective:** Distributed, robust and high-performance XCore runtime

---

## 1. Vision

XCore V3 introduces a native runtime layer designed to extend XCore from a single-process plugin runtime into a distributed execution platform.

The objective is **not to rewrite XCore in Rust**.

Python remains the primary language for:

* plugins;
* SDK;
* application logic;
* API;
* configuration;
* orchestration;
* schemas;
* CLI;
* business logic;
* integrations.

Rust becomes the native execution layer for operations where predictable latency, concurrency, fault isolation and network performance are critical.

The resulting architecture is:

```text
                         XCore
                           │
             ┌─────────────┴─────────────┐
             │                           │
       Python Control Plane         Native Runtime
             │                           │
      ┌──────┼────────┐           ┌──────┼──────────┐
      │      │        │           │      │          │
   Plugins  API   Orchestration   IPC   Events    Routing
      │      │        │           │      │          │
      └──────┴────────┘           ├── Cluster
                                  ├── Failover
                                  ├── Circuit Breaker
                                  └── Transport
```

---

# 2. Architectural Principle

The fundamental rule of V3 is:

> **Python defines what XCore should execute. Rust determines how it is transported and executed across the runtime.**

Python must not become responsible for:

* cluster membership;
* node-to-node routing;
* low-level IPC transport;
* distributed event transport;
* connection lifecycle;
* retry storms;
* circuit state;
* failover;
* network serialization;
* low-level health monitoring.

These responsibilities belong to the native runtime.

---

# 3. Compatibility Principle

V3 MUST preserve compatibility with existing Python plugins whenever possible.

An existing plugin should continue to use APIs such as:

```python
await ctx.ipc.call(
    target="inventory",
    action="reserve",
    payload=data,
)
```

without knowing whether the target plugin is:

```text
same process
     ↓
local process
     ↓
sandbox
     ↓
same node
     ↓
remote node
     ↓
remote cluster
```

The location of the target is an implementation detail of the runtime.

---

# 4. Runtime Layers

XCore V3 consists of two major execution layers.

## 4.1 Python Control Plane

The Python layer contains:

### Kernel

* plugin loader;
* lifecycle;
* registry;
* permissions;
* tenancy;
* configuration;
* schemas;
* middleware;
* application orchestration.

### SDK

* plugin API;
* decorators;
* actions;
* routers;
* schemas;
* event APIs;
* lifecycle APIs.

### Application Layer

* business logic;
* domain services;
* application plugins;
* integrations.

### API Layer

* FastAPI;
* HTTP endpoints;
* WebSocket interfaces;
* external integrations.

Python remains the primary extension mechanism.

---

# 5. Native Runtime

The native runtime MUST be implemented in Rust.

Suggested package:

```text
xcore-runtime/
├── core/
├── ipc/
├── transport/
├── router/
├── federation/
├── cluster/
├── events/
├── resilience/
├── discovery/
├── serialization/
├── telemetry/
└── bindings/
```

The native runtime must be usable:

1. embedded inside the Python XCore process;
2. as a standalone runtime process;
3. as a node runtime in a distributed cluster.

---

# 6. Native Runtime Responsibilities

The Rust runtime is responsible for:

* local IPC;
* remote IPC;
* transport;
* request routing;
* node discovery;
* cluster membership;
* federation;
* distributed events;
* connection pooling;
* request timeout;
* retries;
* circuit breakers;
* failover;
* health checks;
* backpressure;
* serialization;
* connection lifecycle;
* distributed telemetry propagation.

---

# 7. IPC Architecture

XCore V3 introduces a unified IPC abstraction.

```text
Plugin A
   │
   ▼
XCore SDK
   │
   ▼
Native IPC Layer
   │
   ├── Local Process
   ├── Sandbox
   ├── Local Node
   └── Remote Node
```

The caller MUST NOT need to select the transport manually.

Example:

```python
result = await ctx.ipc.call(
    target="stock",
    action="reserve",
    payload={
        "product_id": product_id,
        "quantity": quantity,
    },
)
```

The runtime resolves the destination.

---

# 8. IPC Routing

Every IPC request contains a logical destination.

```text
Request
├── request_id
├── caller
├── tenant_id
├── target
├── action
├── payload
├── timeout
├── trace_context
└── metadata
```

The router determines:

```text
target
  ↓
plugin registry
  ↓
service location
  ↓
node
  ↓
transport
  ↓
plugin
```

Routing MUST be deterministic and tenant-aware.

---

# 9. Tenant Isolation

Tenant isolation is mandatory.

Every distributed request MUST carry a tenant context when tenancy is enabled.

```text
tenant_id
    │
    ├── IPC
    ├── routing
    ├── events
    ├── cache
    ├── database
    ├── scheduler
    └── telemetry
```

A request MUST NOT be routed to another tenant context accidentally.

The native runtime MUST treat tenant identity as security metadata, not merely application payload.

The existing XCore multi-tenancy model remains the source of truth for Python services. V3 extends this isolation across distributed boundaries. The current roadmap already identifies comprehensive multi-tenancy as implemented at the local runtime level.

---

# 10. Node Model

Each XCore node represents one runtime instance.

```text
Cluster
│
├── Node A
│   ├── Python Runtime
│   └── Native Runtime
│
├── Node B
│   ├── Python Runtime
│   └── Native Runtime
│
└── Node C
    ├── Python Runtime
    └── Native Runtime
```

A node exposes:

```text
NodeIdentity
├── node_id
├── cluster_id
├── runtime_version
├── capabilities
├── address
├── status
├── load
└── health
```

---

# 11. Cluster Membership

The native runtime MUST maintain cluster membership.

The membership subsystem is responsible for:

* node registration;
* node discovery;
* node health;
* heartbeat;
* node expiration;
* node removal;
* capability discovery.

A node MUST transition through explicit states:

```text
JOINING
   ↓
READY
   ↓
DEGRADED
   ↓
UNAVAILABLE
   ↓
REMOVED
```

Cluster state MUST NOT depend on Python application code.

---

# 12. Static Federation

V3 initially supports static federation.

Example:

```yaml
cluster:
  id: production

nodes:
  - id: node-01
    address: 10.0.0.10:9000

  - id: node-02
    address: 10.0.0.11:9000

  - id: node-03
    address: 10.0.0.12:9000
```

Static federation is the first implementation stage.

Dynamic discovery may be introduced later without changing the public IPC abstraction.

---

# 13. FederatedHandler

`FederatedHandler` provides a logical handler abstraction independent of physical location.

```text
FederatedHandler
       │
       ├── local handler
       ├── local process
       ├── remote node
       └── fallback node
```

The handler MUST expose a consistent interface regardless of location.

---

# 14. Inter-node Transport

The transport layer MUST be implemented in Rust.

Requirements:

* asynchronous I/O;
* connection reuse;
* bounded buffers;
* configurable timeout;
* connection pooling;
* backpressure;
* cancellation;
* graceful shutdown;
* efficient binary serialization.

The transport MUST avoid spawning a Python coroutine for every low-level network operation.

---

# 15. Serialization

V3 should introduce a versioned native wire protocol.

```text
XCore Message
├── protocol_version
├── message_type
├── request_id
├── tenant_id
├── source
├── destination
├── trace_context
├── flags
└── payload
```

The protocol MUST support:

* version negotiation;
* backward compatibility;
* request/response;
* events;
* errors;
* cancellation;
* metadata.

The serialization format should prioritize:

1. low latency;
2. low allocation;
3. compact payloads;
4. schema evolution.

---

# 16. Distributed Event Bus

The existing XBus remains the application-level event abstraction.

V3 extends it to distributed nodes.

```text
             XBus
              │
       ┌──────┴──────┐
       │             │
    Local Bus    Distributed Bus
       │             │
    Process        Cluster
```

A plugin continues to publish:

```python
await ctx.events.emit(
    "stock.updated",
    payload,
)
```

The runtime determines whether the event is:

```text
local
```

or:

```text
distributed
```

---

# 17. Event Routing

Distributed events MUST support:

* topic;
* tenant scope;
* source node;
* event ID;
* timestamp;
* trace context;
* delivery metadata.

Example:

```text
Event
├── event_id
├── topic
├── tenant_id
├── source
├── timestamp
├── trace_context
└── payload
```

Events MUST NOT accidentally cross tenant boundaries.

---

# 18. Delivery Semantics

V3 MUST explicitly define event delivery semantics.

Initial implementation:

```text
At-least-once delivery
```

Consumers MUST therefore be designed to tolerate duplicate delivery.

The runtime should expose event identifiers allowing consumers to implement idempotency.

Exactly-once semantics MUST NOT be assumed.

---

# 19. Circuit Breaker

Every remote communication path MUST support circuit breaking.

State machine:

```text
CLOSED
   │
   │ failures
   ▼
OPEN
   │
   │ timeout
   ▼
HALF_OPEN
   │
   ├── success → CLOSED
   │
   └── failure → OPEN
```

Circuit breaker parameters:

```yaml
circuit_breaker:
  failure_threshold: 5
  recovery_timeout: 10s
  half_open_requests: 1
```

The implementation belongs to the native runtime.

---

# 20. Failover

When a node becomes unavailable:

```text
Node A
  │
  X
  │
Router
  │
  ├── Node B
  └── Node C
```

The router MUST:

1. detect failure;
2. stop sending traffic to the failed node;
3. open the circuit;
4. select an eligible node;
5. retry when safe;
6. restore the original route when the node recovers.

Failover MUST respect:

* tenant;
* service capability;
* routing policy;
* request idempotency;
* timeout;
* circuit state.

---

# 21. Retry Policy

Retries MUST NOT be unconditional.

The runtime must distinguish:

```text
retryable
non-retryable
```

Examples of potentially retryable failures:

* connection reset;
* temporary node unavailable;
* timeout before request acceptance.

Examples of non-retryable failures:

* validation error;
* authorization failure;
* business error;
* malformed request.

Retry configuration:

```yaml
retry:
  enabled: true
  max_attempts: 3
  backoff: exponential
  max_delay: 2s
```

The runtime MUST prevent retry amplification.

---

# 22. Backpressure

The native runtime MUST support bounded queues.

```text
Producer
   │
   ▼
Bounded Queue
   │
   ▼
Transport
```

When the queue reaches capacity, the runtime must apply an explicit policy:

```text
reject
block
drop
shed
```

The policy must never be implicit.

---

# 23. Health Monitoring

Native health monitoring operates independently of Python plugin code.

Health checks include:

* node availability;
* transport availability;
* connection state;
* event bus state;
* queue pressure;
* latency;
* error rate;
* resource pressure.

Python-level plugin health checks remain supported.

---

# 24. Observability

V3 MUST preserve the existing OpenTelemetry model.

The current XCore V2 implementation already supports real OpenTelemetry and W3C trace propagation across HTTP and sandbox IPC.

V3 extends the same trace context across:

```text
HTTP
 ↓
Python
 ↓
Native IPC
 ↓
Node A
 ↓
Node B
 ↓
Plugin
```

A single distributed operation MUST retain its trace identity.

Required telemetry:

* trace ID;
* span ID;
* node;
* plugin;
* tenant;
* action;
* latency;
* status;
* transport;
* retry count;
* circuit state.

---

# 25. Security

Native communication MUST be authenticated.

The runtime MUST support:

* node identity;
* authenticated connections;
* authorization;
* tenant validation;
* message integrity;
* protocol version validation.

Cluster communication MUST NOT trust a node solely because it is reachable on the network.

---

# 26. Plugin Location Transparency

The plugin developer must not need to know where a plugin is running.

```python
await ctx.ipc.call(
    target="payment",
    action="charge",
    payload=data,
)
```

is the only abstraction required.

The runtime may internally execute:

```text
Plugin A
   ↓
Local IPC
```

or:

```text
Plugin A
   ↓
Node Router
   ↓
Network
   ↓
Node B
   ↓
Plugin B
```

The public plugin API remains identical.

---

# 27. Python ↔ Rust Boundary

The boundary MUST be deliberately small.

Python should communicate with Rust through a stable native API.

Conceptually:

```python
runtime = XCoreNativeRuntime()

await runtime.ipc.call(...)
await runtime.events.publish(...)
await runtime.router.resolve(...)
```

The Rust implementation remains hidden behind this abstraction.

Possible Python binding technology:

```text
PyO3
maturin
```

The binding layer MUST NOT expose internal Rust structures directly.

---

# 28. Standalone Runtime Mode

The native runtime should also support standalone operation.

```text
Python XCore
     │
     │ IPC
     ▼
XCore Native Runtime
     │
     ├── cluster
     ├── transport
     ├── routing
     └── events
```

This allows XCore to evolve from an embedded architecture toward a dedicated runtime without breaking plugins.

---

# 29. Performance Requirements

V3 is a performance-oriented release.

The native runtime SHOULD target:

* low and predictable IPC latency;
* high concurrent connection counts;
* bounded memory usage;
* zero unbounded queues;
* connection reuse;
* minimal serialization overhead;
* minimal Python ↔ Rust transitions;
* no blocking operations on async runtime threads.

Performance MUST be measured through benchmarks rather than assumptions.

Required benchmark categories:

```text
local IPC
remote IPC
event publishing
event consumption
serialization
routing
failover
circuit breaker
10 / 100 / 1k / 10k concurrent requests
```

---

# 30. Memory Safety

The native runtime MUST NOT introduce manual memory management into the core architecture.

Rust ownership and borrowing rules are preferred over:

* raw pointers;
* manual allocation;
* unsafe shared state.

`unsafe` code MUST be isolated, documented and justified.

---

# 31. Failure Model

V3 assumes that failures are normal.

The runtime MUST tolerate:

* plugin crash;
* sandbox crash;
* Python process crash;
* node crash;
* network interruption;
* connection reset;
* timeout;
* event consumer failure;
* temporary overload.

A failure in one node MUST NOT automatically terminate the entire cluster.

---

# 32. Graceful Shutdown

Shutdown sequence:

```text
STOP ACCEPTING
      ↓
DRAIN REQUESTS
      ↓
DRAIN EVENTS
      ↓
CLOSE CONNECTIONS
      ↓
LEAVE CLUSTER
      ↓
STOP NATIVE RUNTIME
      ↓
STOP PYTHON RUNTIME
```

The native runtime must provide deterministic shutdown.

---

# 33. Version Compatibility

Cluster nodes MUST negotiate protocol compatibility.

```text
Node A
protocol: 3.x
       │
       ▼
Node B
protocol: 3.x
```

Incompatible nodes MUST be rejected explicitly.

The application/plugin version and transport protocol version MUST remain separate.

---

# 34. Proposed Repository Structure

```text
xcore/
├── kernel/
├── services/
├── sdk/
└── ...

native/
└── xcore-runtime/
    ├── Cargo.toml
    ├── src/
    │   ├── core/
    │   ├── ipc/
    │   ├── transport/
    │   ├── router/
    │   ├── federation/
    │   ├── cluster/
    │   ├── events/
    │   ├── resilience/
    │   ├── discovery/
    │   ├── serialization/
    │   ├── telemetry/
    │   └── bindings/
    └── tests/
```

Python remains the main XCore repository layer.

Rust is introduced as a native subsystem rather than replacing the Python package.

---

# 35. Migration Strategy

V3 MUST be incremental.

### Phase 1 — Native Core

Implement:

* Rust runtime;
* Python bindings;
* native IPC abstraction;
* serialization;
* benchmark infrastructure.

### Phase 2 — Local IPC

Move local high-frequency IPC paths to Rust.

Existing Python IPC remains available as compatibility fallback.

### Phase 3 — Transport

Implement:

* connection manager;
* node identity;
* transport;
* remote calls.

### Phase 4 — Federation

Implement:

* node registry;
* static federation;
* routing;
* FederatedHandler.

### Phase 5 — Distributed Events

Move XBus transport to the native layer while preserving the Python event API.

### Phase 6 — Resilience

Implement:

* circuit breaker;
* retry;
* failover;
* backpressure;
* health monitoring.

### Phase 7 — Production Hardening

Add:

* security;
* benchmarks;
* chaos testing;
* observability;
* protocol compatibility tests;
* load testing.

---

# 36. Compatibility Fallback

V3 MUST maintain a fallback path.

```text
Native Runtime available?
       │
   ┌───┴───┐
   │       │
  YES      NO
   │       │
 Rust    Python
 Runtime  fallback
```

This is important during migration.

The Python implementation remains the reference compatibility implementation until the native implementation reaches production maturity.

---

# 37. Testing Strategy

V3 requires several test layers.

## Unit Tests

Rust:

* router;
* transport;
* serialization;
* circuit breaker;
* retry;
* membership;
* queues.

Python:

* bindings;
* API compatibility;
* plugin behavior.

## Integration Tests

```text
Python ↔ Rust
Python ↔ Node A
Node A ↔ Node B
Node A ↔ Node B ↔ Node C
```

## Failure Tests

Simulate:

* node crash;
* network partition;
* timeout;
* connection reset;
* plugin crash;
* event consumer crash;
* overloaded queue.

## Chaos Tests

The cluster must be tested under controlled failures before V3 is considered production-ready.

---

# 38. Definition of Done

V3 is considered complete when:

* [ ] Rust Native Runtime exists.
* [ ] Python bindings are stable.
* [ ] Local IPC can use the native runtime.
* [ ] Remote IPC works.
* [ ] Static federation works.
* [ ] Inter-node routing works.
* [ ] Cluster IPC works.
* [ ] Distributed XBus works.
* [ ] Tenant context propagates across nodes.
* [ ] Circuit breaker works.
* [ ] Failover works.
* [ ] Backpressure works.
* [ ] Distributed tracing works.
* [ ] Node authentication works.
* [ ] Failure scenarios are covered by integration tests.
* [ ] Performance benchmarks are established.
* [ ] Existing Python plugins remain compatible.

---

# 39. Architectural Target

The final V3 architecture is:

```text
                         XCORE V3
                            │
             ┌──────────────┴──────────────┐
             │                             │
       PYTHON CONTROL PLANE          RUST NATIVE PLANE
             │                             │
     ┌───────┼────────┐          ┌─────────┼─────────┐
     │       │        │          │         │         │
 Plugins    API    Services     IPC      Events    Router
     │       │        │          │         │         │
     └───────┴────────┘          │         │         │
             │                   └─────────┼─────────┘
             │                             │
             └─────────────┬───────────────┘
                           │
                      XCore Node
                           │
            ┌──────────────┼──────────────┐
            │              │              │
          Node A         Node B         Node C
            │              │              │
            └──────────────┼──────────────┘
                           │
                        Cluster
```

The key architectural invariant is:

> **Python remains the programmable surface of XCore. Rust becomes the execution fabric of XCore.**

This allows XCore to retain the flexibility of Python while gaining a native distributed runtime capable of handling the performance, concurrency and resilience requirements introduced by V3.
