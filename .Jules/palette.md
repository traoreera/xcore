## 2025-05-14 - [Enhancing CLI with Rich]
**Learning:** Transitioning from plain text to `rich` components like Panels and Status spinners significantly improves the perceived responsiveness and readability of terminal interfaces without adding heavy overhead.
**Action:** Use `rich.console.Status` for network-bound CLI operations and `rich.panel.Panel` to group related metadata for better visual hierarchy.

## 2025-05-15 - [Structured CLI Data with Rich Tables]
**Learning:** For command outputs involving multiple entity attributes (like name, version, status), using structured tables with clear headers and semantic colors (e.g., green for OK, red for error) drastically reduces cognitive load compared to manual padding.
**Action:** Prefer `rich.table.Table` over custom string formatting for any CLI output that lists more than two related properties.

## 2025-05-16 - [Safe Destructive Prompts in CLI]
**Learning:** When using `rich.prompt.Confirm.ask()` for destructive actions like plugin removal, the default behavior is `True` (Yes). To prevent accidental data loss, explicitly set `default=False` to require an intentional confirmation.
**Action:** Always use `Confirm.ask(..., default=False)` for deletions or other irreversible operations.

## 2025-05-17 - [Defensive Metadata Display in CLI]
**Learning:** Metadata in plugin manifests (like `requires`) may be parsed into complex objects (e.g., `PluginDependency`) rather than simple strings. Directly using `", ".join()` on these lists causes a `TypeError`.
**Action:** Always use a generator or `map` with defensive attribute access (e.g., `d.name if hasattr(d, "name") else str(d)`) when joining metadata lists for display.

## 2025-05-18 - [Visual Hierarchy with Rich Panels]
**Learning:** Grouping related metadata into a `rich.panel.Panel` using `rich.console.Group` creates a clear visual boundary and hierarchy, making dense information (like plugin specs and permissions) much easier to scan than plain text with manual separators.
**Action:** Use `Panel(Group(...))` for entity-detail commands to provide a "card-like" experience in the terminal.

## 2025-05-19 - [Escaping Markup in Rich]
**Learning:** Dynamic content or error messages containing square brackets can be misinterpreted as `rich` markup, leading to broken layouts or missing text.
**Action:** Always wrap dynamic or user-provided strings in `rich.markup.escape()` before passing them to `rich` renderables.

## 2025-05-20 - [Backward Compatibility in CLI UX]
**Learning:** Replacing raw JSON or plain-text CLI output with structured `rich` components (like Tables or Panels) improves human readability but breaks automation/scripts (e.g., `jq` pipes).
**Action:** When adding visual enhancements to CLI commands that return structured data, always provide a `--json` flag to maintain machine-readability.

## 2025-05-21 - [Perceived Responsiveness with Status Spinners]
**Learning:** Using `rich.console.Status` context managers to wrap long-running operations (like sandbox startup or network calls) provides immediate visual feedback, making the application feel faster and more responsive even if the actual execution time remains the same.
**Action:** Wrap any operation expected to take >500ms in a `console.status` spinner with a descriptive message.

## 2025-05-22 - [Batch Operation Summaries]
**Learning:** Adding a summary line after a table in batch CLI operations (like a health check) provides an immediate "TL;DR" for the user, especially when dealing with many items, improving scanability.
**Action:** Provide a concise summary (e.g., success/failure counts) after rendering tables for batch operations.

## 2025-05-23 - [Language Consistency in CLI]
**Learning:** Mixing languages (e.g., French and English) in CLI outputs creates a fragmented and confusing user experience.
**Action:** Maintain strict language consistency across all user-facing strings, adhering to the primary language of the codebase (English).
