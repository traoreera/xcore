Okay, here’s a Markdown documentation page based on your provided information and style guidelines. I've aimed for clarity, conciseness, and a technical tone suitable for a developer joining the XCore project.

```markdown
# Integrations.Events - Asynchronous Event Bus

## Overview

`Integrations.Events` is an asynchronous event bus system designed to facilitate decoupled communication within the XCore project. It allows components to react to events without direct dependencies, providing a flexible and robust mechanism for building reactive systems. The core functionality revolves around emitting and handling events with prioritization and filtering capabilities.

## Responsibilities

This file provides the infrastructure for managing and distributing asynchronous events throughout the XCore codebase. Specifically, it handles:

*   Event registration (subscribing handlers to specific events).
*   Event emission (triggering handlers based on events).
*   Prioritized event handling (executing handlers in order of priority).
*   Filtering of event handlers based on their type and scope.

## Key Components

*   **`Event`:** A data structure representing a single event instance. It contains the event name, associated data payload, the source component triggering the event, and a flag to control propagation of handlers.  (Signature: `event_name`, `data`, `source`, `propagate`)
*   **`HandlerEntry`:** Represents a handler function registered for an event. Includes priority, whether it's a one-shot handler, and its name (used for logging). (Signature: `priority`, `is_one_shot`, `name`)
*   **`EventBus`:** The core class managing event subscriptions and emissions. It maintains a dictionary (`_handlers`) mapping event names to lists of `HandlerEntry` objects.  (Signature: `emit(event_name, data)`, `on(event_name, handler)`, `once(event_name, handler)`, `unsubscribe(handler)`)

## Dependencies

*   **`asyncio`:** Provides the asynchronous programming primitives necessary for handling events concurrently and efficiently.
*   **`logging`:** Used for logging debug information related to event handler registrations, errors, and performance metrics.
*   **`dataclasses`:** Utilized for defining the `Event` and `HandlerEntry` classes, providing a concise way to structure data.

## How It Fits In

The `Integrations.Events` bus is instantiated as a singleton (`get_event_bus()`).  Components register handlers using the `on()` and `once()` decorators. When an event occurs, the `emit()` method triggers these registered handlers asynchronously (or synchronously if `gather=False`), passing event data. Handlers can be unsubscribed using the `unsubscribe` method. The bus internally sorts handlers by priority before emitting events, ensuring that higher-priority handlers are executed first. Error handling is implemented within the handler execution process to prevent failures from disrupting other handlers.

**Example:**

```python
from integrations_events import EventBus

bus = get_event_bus()

@bus.on("user_created", lambda event: print(f"User created: {event.data['username']}"))
def user_created_handler(event):
    pass

bus.emit("user_created", {"username": "Alice"})
```

---

**Note:** This documentation is intended to provide a high-level overview of the `Integrations.Events` system.  Refer to the source code for detailed implementation details and advanced usage scenarios.
```

**Explanation of Choices & Style Adherence:**

*   **Conciseness:** I've trimmed unnecessary words and phrases to keep it focused on essential information.
*   **Technical Tone:** The language is direct, using terms like "asynchronous," "prioritized," and "decoupled."
*   **Clear Headings & Subheadings:**  The structure follows your guidelines for readability.
*   **Code Snippet:** I've included a simple example to illustrate how the bus is used.
*   **Short Paragraphs:** Each section is broken down into digestible paragraphs.
*   **Markdown Formatting:** Used headings, lists, and code blocks appropriately.

To further improve this documentation, you could add:

*   More detailed explanations of specific methods within the `EventBus` class.
*   Examples of error handling scenarios.
*   Information about performance considerations (e.g., how to optimize handler registration).
*   Links to relevant code files or issues in your repository.