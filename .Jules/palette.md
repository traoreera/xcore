## 2025-05-14 - [Enhancing CLI with Rich]
**Learning:** Transitioning from plain text to `rich` components like Panels and Status spinners significantly improves the perceived responsiveness and readability of terminal interfaces without adding heavy overhead.
**Action:** Use `rich.console.Status` for network-bound CLI operations and `rich.panel.Panel` to group related metadata for better visual hierarchy.

## 2025-05-15 - [Structured CLI Data with Rich Tables]
**Learning:** For command outputs involving multiple entity attributes (like name, version, status), using structured tables with clear headers and semantic colors (e.g., green for OK, red for error) drastically reduces cognitive load compared to manual padding.
**Action:** Prefer `rich.table.Table` over custom string formatting for any CLI output that lists more than two related properties.
