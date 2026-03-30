# Architecture Overview

Understanding XCore's architecture and design principles.

## Design Philosophy

XCore follows these principles:

1. **Plugin-First**: Everything is a plugin. Core functionality is minimal.
2. **Security by Default**: Sandboxed execution with resource limits.
3. **Service-Oriented**: Shared services for common needs.
4. **Event-Driven**: Loose coupling via events.
5. **Production Ready**: Observability, metrics, and logging built-in.

## System Architecture

```mermaid
flowchart TB
    subgraph XCore["XCore Framework"]
        direction TB

        subgraph Core["Core"]
            X[Xcore]
            Config[Configuration]
            Registry[Plugin Registry]
        end

        subgraph Runtime["Runtime"]
            PS[PluginSupervisor]
            PL[PluginLoader]
            LM[LifecycleManager]
            SM[StateMachine]
        end

        subgraph Sandbox["Sandbox"]
            PM[ProcessManager]
            IPC[IPC]
            Limits[RateLimiter]
        end

        subgraph Events["Events"]
            EB[EventBus]
            HM[HookManager]
            ED[EventDispatcher]
        end

        subgraph Services["Services"]
            SC[ServiceContainer]
            DB[(Database)]
            Cache[(Cache)]
            Sched[Scheduler]
            Ext[Extensions]
        end

        subgraph Security["Security"]
            Sig[Signature]
            Val[Validation]
            Hash[Hashing]
        end

        subgraph API["API Layer"]
            Router[Router Builder]
            Context[PluginContext]
        end
    end

    subgraph External["External"]
        FastAPI[FastAPI App]
        Plugins[Plugin Directory]
    end

    X --> Config
    X --> PS
    X --> EB
    X --> SC

    PS --> PL
    PS --> LM
    PL --> Sandbox
    LM --> SM

    EB --> HM
    EB --> ED

    SC --> DB
    SC --> Cache
    SC --> Sched
    SC --> Ext

    PL --> Security

    PS --> API
    API --> FastAPI
    PL --> Plugins
```

## Component Details

### Core Components

#### Xcore (Orchestrator)

**Location**: `xcore/__init__.py`

The main orchestrator that:
- Loads configuration
- Initializes services
- Boots the plugin system
- Attaches FastAPI routers

```mermaid
sequenceDiagram
    participant App as Application
    participant X as Xcore
    participant SC as ServiceContainer
    participant PS as PluginSupervisor
    participant FA as FastAPI

    App->>+X: __init__(config_path)
    X->>X: load_config()
    X-->>-App: instance

    App->>+X: boot(app)
    X->>+SC: init()
    SC->>SC: init_databases()
    SC->>SC: init_cache()
    SC->>SC: init_scheduler()
    SC-->>-X: services ready

    X->>X: init_events()
    X->>X: init_hooks()
    X->>X: init_registry()

    X->>+PS: boot()
    PS->>PS: load_all_plugins()
    PS-->>-X: plugins ready

    X->>FA: attach_router()
    X-->>-App: ready
```

#### Configuration

**Location**: `xcore/configurations/`

Configuration system:
- YAML parsing
- Environment variable substitution
- Validation
- Runtime access

```mermaid
flowchart LR
    A[Config File] --> B[ConfigLoader]
    B --> C[Environment]
    B --> D[Validation]
    D --> E[Config Objects]
    E --> F[Xcore]
```

### Runtime Components

#### PluginSupervisor

**Location**: `xcore/kernel/runtime/supervisor.py`

High-level plugin management:
- Plugin lifecycle
- Action routing
- Rate limiting
- Retry logic

```mermaid
sequenceDiagram
    participant Client
    participant PS as PluginSupervisor
    participant RL as RateLimiter
    participant PL as PluginLoader
    participant P as Plugin

    Client->>+PS: call(plugin, action, payload)
    PS->>+RL: check(plugin)
    RL-->>-PS: allowed

    PS->>+PL: get(plugin)
    PL-->>-PS: handler

    PS->>+P: call(action, payload)
    P-->>-PS: result
    PS-->>-Client: result
```

#### PluginLoader

**Location**: `xcore/kernel/runtime/loader.py`

Plugin loading logic:
- Directory scanning
- Manifest parsing
- Dependency resolution
- Topological sorting
- Mode-specific loading

```mermaid
flowchart TD
    A[Scan plugins/] --> B[Parse Manifests]
    B --> C[Validate]
    C --> D[Resolve Dependencies]
    D --> E[Topological Sort]
    E --> F[Load Trusted]
    E --> G[Load Sandboxed]
    E --> H[Load Legacy]
    F --> I[Inject Services]
    G --> J[Start Process]
    H --> I
    I --> K[Call on_load]
    J --> K
```

#### LifecycleManager

**Location**: `xcore/kernel/runtime/lifecycle.py`

Plugin lifecycle management:
- Context injection
- Hook execution
- State transitions

### Sandbox Components

#### ProcessManager

**Location**: `xcore/kernel/sandbox/process_manager.py`

Isolated execution:
- Process spawning
- IPC communication
- Resource monitoring
- Timeout handling

```mermaid
flowchart LR
    subgraph Main["Main Process"]
        PM[ProcessManager]
        IPC[IPC Handler]
    end

    subgraph Worker["Worker Process"]
        W[Worker]
        P[Plugin Instance]
    end

    PM --> IPC
    IPC -->|pipe/socket| IPC
    IPC --> W
    W --> P
```

### Event System

#### EventBus

**Location**: `xcore/kernel/events/bus.py`

Event handling:
- Subscription management
- Priority-based execution
- Synchronous/asynchronous emission
- Error handling

```mermaid
flowchart TB
    A[Event Source] -->|emit| B[EventBus]
    B --> C[Priority Queue]
    C -->|High Priority| D[Handler 1]
    C -->|Medium| E[Handler 2]
    C -->|Low| F[Handler 3]
    D --> G[Results]
    E --> G
    F --> G
```

### Service Container

**Location**: `xcore/services/container.py`

Service management:
- Initialization order
- Dependency injection
- Health monitoring
- Graceful shutdown

```mermaid
flowchart TD
    subgraph Init["Initialization"]
        A[Database] --> B[Cache]
        B --> C[Scheduler]
        C --> D[Extensions]
    end

    subgraph Shutdown["Shutdown"]
        D2[Extensions] --> C2[Scheduler]
        C2 --> B2[Cache]
        B2 --> A2[Database]
    end
```

## Data Flow

### Plugin Action Flow

```mermaid
sequenceDiagram
    participant HTTP as HTTP Client
    participant FA as FastAPI
    participant R as Router
    participant PS as PluginSupervisor
    participant PL as PluginLoader
    participant Handler as Plugin Handler

    HTTP->>FA: POST /app/plugin/action
    FA->>R: Route Request
    R->>PS: call(plugin, action, payload)

    PS->>PL: Get Plugin
    PL-->>PS: Handler

    PS->>PS: Check Rate Limit
    PS->>PS: Apply Retry Logic

    alt Trusted Plugin
        PS->>Handler: Direct Call
        Handler-->>PS: Result
    else Sandboxed Plugin
        PS->>Handler: IPC Call
        Handler-->>PS: Result
    end

    PS-->>R: Result
    R-->>FA: JSON Response
    FA-->>HTTP: Response
```

### HTTP Route Flow

```mermaid
sequenceDiagram
    participant HTTP as Client
    participant FA as FastAPI
    participant PR as Plugin Router
    participant P as Plugin Code
    participant S as Services

    HTTP->>FA: GET /plugins/name/endpoint
    FA->>PR: Route to Plugin
    PR->>P: Handler Function

    P->>S: get_service("db")
    S-->>P: Database Connection

    P->>S: Query Data
    S-->>P: Results

    P-->>PR: Response
    PR-->>FA: JSON
    FA-->>HTTP: Response
```

### Event Flow

```mermaid
sequenceDiagram
    participant P1 as Plugin A
    participant EB as EventBus
    participant P2 as Plugin B
    participant P3 as Plugin C

    P1->>EB: emit("user.created", data)

    EB->>P2: Handler (Priority 100)
    P2-->>EB: Ack

    EB->>P3: Handler (Priority 50)
    P3->>P3: Process Event
    P3->>EB: emit("notification.sent")
    P3-->>EB: Ack

    EB-->>P1: Results
```

## Security Architecture

### Sandboxing

```mermaid
flowchart TB
    subgraph Trusted["Trusted Plugin"]
        T[Runs in Main Process]
        T1[Full Access]
    end

    subgraph Sandboxed["Sandboxed Plugin"]
        S[Runs in Subprocess]
        subgraph Restrictions
            AST[AST Validation]
            IMP[Import Whitelist]
            MEM[Memory Limits]
            CPU[CPU Limits]
            DISK[Disk Quota]
        end
        S --> Restrictions
    end

    subgraph Communication["IPC"]
        P[Pipe/Socket]
        SER[Serialization]
    end

    Sandboxed --> Communication
```

### Signature Verification

```mermaid
flowchart LR
    A[Plugin Files] -->|Hash| B[HMAC-SHA256]
    K[Secret Key] --> B
    B --> C[Signature]
    C --> D[plugin.sig]

    A2[Plugin] --> E[Verification]
    D2[plugin.sig] --> E
    K2[Secret Key] --> E
    E -->|Match| F[Load]
    E -->|No Match| G[Reject]
```

## Plugin Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Discovered: Scan Directory
    Discovered --> Validated: Parse Manifest
    Validated --> Resolved: Check Dependencies
    Resolved --> Loading: Begin Load
    Loading --> Loaded: on_load()
    Loading --> Failed: Error
    Loaded --> Active: Ready
    Active --> Reloading: Reload Request
    Reloading --> Loading: on_reload()
    Reloading --> Failed: Error
    Active --> Unloading: Unload Request
    Unloading --> Unloaded: on_unload()
    Unloaded --> [*]
    Failed --> [*]
```

## Threading Model

```mermaid
flowchart TB
    subgraph Main["Main Thread"]
        X[Xcore]
        EB[EventBus]
        SC[ServiceContainer]
        PS[PluginSupervisor]
    end

    subgraph Async["Async Event Loop"]
        FA[FastAPI]
        R[Router]
        Handler[Trusted Plugins]
    end

    subgraph Workers["Worker Processes"]
        W1[Sandboxed Plugin 1]
        W2[Sandboxed Plugin 2]
    end

    X --> SC
    X --> EB
    X --> PS
    FA --> R
    R --> Handler
    PS -->|IPC| Workers
```

## Directory Structure

```
xcore/
├── __init__.py                 # Main orchestrator
├── __version__.py              # Version info
│
├── kernel/                     # Core framework
│   ├── api/                    # API layer
│   │   ├── contract.py         # Plugin contracts
│   │   ├── context.py          # Plugin context
│   │   ├── router.py           # FastAPI router builder
│   │   └── versioning.py       # API versioning
│   │
│   ├── runtime/                # Plugin runtime
│   │   ├── loader.py           # Plugin loader
│   │   ├── supervisor.py         # High-level management
│   │   ├── lifecycle.py        # Lifecycle management
│   │   └── state_machine.py    # State management
│   │
│   ├── sandbox/                # Sandboxed execution
│   │   ├── process_manager.py  # Process management
│   │   ├── worker.py             # Worker process
│   │   ├── ipc.py              # Inter-process communication
│   │   ├── limits.py             # Rate limiting
│   │   └── isolation.py        # Resource isolation
│   │
│   ├── events/                   # Event system
│   │   ├── bus.py                # EventBus
│   │   ├── dispatcher.py         # Event dispatcher
│   │   └── hooks.py            # Hook manager
│   │
│   ├── security/               # Security
│   │   ├── signature.py        # Plugin signing
│   │   ├── validation.py       # AST validation
│   │   └── hashing.py          # Hash utilities
│   │
│   └── observability/          # Observability
│       ├── logging.py          # Structured logging
│       ├── metrics.py          # Metrics collection
│       ├── tracing.py          # Distributed tracing
│       └── health.py           # Health checks
│
├── configurations/             # Configuration
│   ├── loader.py               # Config loader
│   └── sections.py             # Config dataclasses
│
├── services/                   # Built-in services
│   ├── container.py            # Service container
│   ├── base.py                 # Base service class
│   ├── cache/                  # Cache service
│   ├── database/               # Database service
│   ├── scheduler/              # Scheduler service
│   └── extensions/             # Extension loader
│
├── registry/                   # Plugin registry
│   ├── index.py                # Registry index
│   ├── resolver.py             # Dependency resolver
│   └── versioning.py           # Version management
│
├── sdk/                        # Plugin SDK
│   ├── __init__.py
│   ├── plugin_base.py          # Plugin manifest
│   └── decorators.py           # SDK decorators
│
└── cli/                        # Command line
    ├── main.py                 # CLI entry point
    ├── plugin_cmd.py           # Plugin commands
    └── validate_cmd.py         # Validation commands
```

## Performance Considerations

### Trusted Plugins
- Run in main process (fastest)
- Direct service access
- No serialization overhead
- Shared memory

### Sandboxed Plugins
- Process isolation
- IPC overhead (~1-5ms)
- Serialization cost
- Memory copying

### Scaling Strategies

```mermaid
flowchart TB
    subgraph Single["Single Instance"]
        A[Process] --> B[Plugins]
    end

    subgraph Multi["Multi-Process"]
        C[Load Balancer] --> D[Instance 1]
        C --> E[Instance 2]
        C --> F[Instance N]
    end

    subgraph Distributed["Distributed"]
        G[API Gateway] --> H[Plugin Service A]
        G --> I[Plugin Service B]
        G --> J[Plugin Service C]
    end
```

## Next Steps

- [Plugin Development](../guides/creating-plugins.md)
- [Service Integration](../guides/services.md)
- [Configuration Reference](../reference/configuration.md)
