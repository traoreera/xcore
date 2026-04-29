# SECURITY FIX TASKS

## Priority 1: High - Continued Monitoring
- **Task:** Monitor for new sandbox escape techniques using Python internals.
- **Task:** Implement automated security regression tests for identified bypasses.

## Priority 2: Medium - Hardening
- **Task:** Consider using a more robust IPC protocol that strictly separates stdout/stderr from the JSON communication channel.
- **Task:** Review all plugins for "event sniffing" practices and enforce secret masking.
