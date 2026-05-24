---
title: XWorker Service
description: Distributed background tasks for Xcore using Celery.
icon: material/worker
---

# XWorker Service

The `XWorker` service provides a robust integration with [Celery](https://docs.celeryq.dev/) for executing heavy or long-running tasks asynchronously in a distributed environment. It allows you to offload work from the main FastAPI process to separate worker nodes.

---

### Prerequisites

- [x] [Service Container](./services.md) overview understood
- [x] `celery` installed (`pip install celery[redis]`)
- [x] A message broker running (Redis or RabbitMQ)

---

### Key Concepts

#### Distributed Task Execution
Unlike the [Scheduler](./scheduler.md), which runs tasks in the main process, `XWorker` dispatches tasks to a message broker. Independent worker processes then pick up these tasks and execute them, possibly on different physical machines.

#### Automatic Registration
Xcore simplifies Celery configuration by automatically registering tasks defined in your plugins and application modules. You don't need to manually create a `celery.py` entry point.

---

### Practical Guide

#### 1. Defining a Task
Use the `@task` decorator provided by the `xcore.services.xworker` module.

```python linenums="1"
from xcore.services.xworker import task

@task(name="image_processing.resize")
def resize_image(image_path, width, height):
    # Long running CPU-intensive work here
    print(f"Resizing {image_path} to {width}x{height}")
    return {"status": "success"}
```

#### 2. Dispatching a Task from a Plugin
You can trigger background work from within any Trusted plugin.

```python linenums="1"
class Plugin(TrustedBase):
    async def handle(self, action, payload):
        worker = self.get_service("worker")

        if action == "generate_report":
            # Fire-and-forget: returns immediately
            task_id = worker.send(
                "image_processing.resize",
                "/tmp/img.png", 640, 480
            )
            return ok(task_id=task_id)
```

#### 3. Starting the Worker Process
In production, you must run the Celery worker as a separate process.

```bash
# Using the Xcore CLI
xcore worker start --queues default,high --concurrency 4

# Or using Celery directly
celery -A xcore.services.xworker.xworker worker --loglevel=info
```

---

### API Reference

#### `WorkerService` Methods
| Method | Return Type | Description |
|--------|-------------|-------------|
| `send(task_name, *args, **kwargs)` | `str` | Dispatches a task to the broker. Returns the `task_id`. |
| `get_result(task_id)` | `AsyncResult`| Retrieve the status or result of a previously dispatched task. |

---

### YAML Configuration

```yaml linenums="1" title="xcore.yaml"
services:
  xworker:
    enabled: true            # bool — Enable/disable the service. Default: false
    broker_url: "redis://localhost:6379/0" # str — Message broker URL.
    result_backend: "redis://localhost:6379/0" # str — Where to store results.
    queues: ["default", "high"] # list — List of queues to listen to.
    concurrency: 4           # int — Number of worker child processes.
    modules: ["plugins.my_plugin.tasks"] # list — Modules containing @task decorators.
```

---

### Common Errors & Pitfalls

!!! danger "Task Not Registered"
    If the worker logs "Received unregistered task of type...", it means the module containing your `@task` was not imported by the worker.
    **Fix**: Add the module path to the `modules:` list in `xcore.yaml`.

!!! warning "Serialization Overhead"
    Arguments passed to `send()` must be JSON serializable. Avoid passing complex objects or database instances.
    **Fix**: Pass IDs (e.g., `user_id`) and fetch the object inside the task logic.

!!! failure "Broker Unreachable"
    If Xcore cannot connect to Redis/RabbitMQ at startup, the `XWorker` service will enter a `DEGRADED` state and `send()` calls will raise exceptions.

---

### Best Practices

!!! success "Use Dedicated Queues"
    Separate your tasks into queues based on priority or type (e.g., `default`, `email`, `heavy`). This allows you to scale workers independently for different types of work.

!!! tip "Idempotency"
    Design your tasks to be idempotent. In a distributed system, a task might be executed more than once due to network issues or worker crashes.
