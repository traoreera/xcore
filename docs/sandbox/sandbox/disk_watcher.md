Okay, here's a Markdown documentation page based on your provided summary of `disk_watcher.py`, adhering to the style guidelines you’ve outlined:

```markdown
# DiskQuotaExceeded

## Overview

The `disk_watcher.py` module provides a disk space monitoring system for sandboxed plugins within the XCore project. It prevents plugin writes from consuming excessive storage on the host machine, safeguarding against instability and data loss. This module operates proactively by checking disk usage before any write operations occur.

## Responsibilities

This file is responsible for tracking and limiting the amount of disk space used by individual plugins running within the XCore sandbox environment.  It ensures that no single plugin can monopolize storage resources, maintaining system stability and preventing potential crashes due to full disks.

## Key Components

*   **`DiskWatcher` Class:** This class forms the core of the monitoring system. It tracks the size of each plugin's data directory (`data/`) and provides methods for checking usage against configured limits.
    *   `__init__(self, data_dir: Path, max_disk_mb: int)`:  The constructor initializes the `DiskWatcher` with the path to the plugin’s data directory and the maximum allowed disk space in megabytes.
    *   `current_size_bytes(self) -> int`: Calculates the total size of all files within the data directory, returning the value in bytes. This is used to determine if a plugin's usage has exceeded its limit.
    *   `check(self, plugin_name: str)`:  This method checks whether the current disk usage for a given plugin exceeds its allocated quota. If it does, it raises the `DiskQuotaExceeded` exception, preventing further writes.
    *   `check_write(self, plugin_name: str, estimated_bytes: int = 0)`: This method is called before a write operation to determine if the additional data will exceed the quota. It returns True if the write can proceed and False otherwise.
    *   `stats(self) -> dict`: Returns a dictionary containing key statistics about disk usage for each plugin, including used space (in MB), maximum allowed space (in MB), percentage used, and a boolean indicating whether the quota is within limits.

*   **`DiskQuotaExceeded(Exception)`:** A custom exception class specifically designed to signal that a plugin has exceeded its allocated disk space limit. This allows for targeted error handling in the XCore system.


## Dependencies

*   **`logging`:**  This module provides logging functionality, enabling developers to track disk usage patterns and troubleshoot potential issues related to quota limits.
*   **`pathlib.Path`:** Utilized for representing file paths as objects, simplifying path manipulation operations within the `DiskWatcher`.



## How It Fits In

The `DiskWatcher` is invoked by the XCore system's plugin management component *before* any write operation occurs to a plugin’s data directory.  It periodically checks existing usage to ensure that limits are not being approached. The module does not directly call other modules, but it is designed to be integrated with the broader XCore system for handling plugin operations and monitoring.
```

**Key improvements and explanations:**

*   **Clearer Prose:** I've focused on writing in a more natural and flowing style, avoiding overly technical jargon where possible while maintaining a professional tone.
*   **Detailed Descriptions:**  I expanded the descriptions of each method to provide a better understanding of its purpose and how it interacts with other parts of the system.
*   **Explicit Type Hints:** I’ve retained the type hints you provided for clarity.
*   **Conciseness:** I've trimmed down some sections where possible, focusing on the most important information.  I avoided redundant statements.
*   **Formatting:** Used appropriate Markdown formatting (headings, lists, code blocks) to improve readability.

This documentation page should be ready to publish in your `docs/` directory and provide a clear overview of the `disk_watcher.py` module for developers joining the XCore project.  Let me know if you'd like any further refinements!