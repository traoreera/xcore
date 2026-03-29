# Sandboxed Plugin Example: Document Converter

This advanced example demonstrates a **Sandboxed** plugin designed for secure file processing with strict resource isolation.

## Why Sandboxed?
-   **Untrusted Files**: Handles user-uploaded files which could contain exploits.
-   **External Tools**: Uses subprocesses to call system tools (e.g., LibreOffice, Pandoc).
-   **Isolation**: Ensures heavy processing or crashes do not impact the main XCore kernel.

## 1. Plugin Structure

```text
plugins/doc_converter/
├── plugin.yaml
└── src/
    ├── main.py          # Entry point and IPC handlers
    ├── router.py        # HTTP routing for file uploads
    └── converter.py     # Isolated conversion logic
```

## 2. Manifest (`plugin.yaml`)

```yaml
name: doc_converter
version: 1.5.0
author: XCore Team
description: Secure document converter with process isolation.

execution_mode: sandboxed
framework_version: ">=2.0"
entry_point: src/main.py

# Strict whitelisting of allowed Python modules
allowed_imports:
  - fastapi
  - pydantic
  - httpx
  - asyncio
  - subprocess
  - tempfile
  - pathlib
  - PIL

# Minimal permissions
permissions:
  - resource: "cache.converter.*"
    actions: ["read", "write"]
    effect: allow

# Strict resource limits for the sandbox
resources:
  timeout_seconds: 60      # Max time per conversion
  max_memory_mb: 512       # RAM limit
  max_disk_mb: 100         # Temp disk limit
  rate_limit:
    calls: 20              # Max conversions per minute
    period_seconds: 60

# Filesystem isolation
filesystem:
  allowed_paths:
    - "data/temp/"         # Temporary working area
  denied_paths:
    - "src/"               # Cannot read its own source code
```

## 3. Key Implementation Details

### Subprocess Security
In `sandboxed` mode, you should always use timeouts when executing external commands.

```python
async def _run_tool(self, cmd: list[str]):
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=30.0  # Force kill if taking too long
        )
        return stdout
    except asyncio.TimeoutError:
        proc.kill()
        raise
```

### File Handling
Always use unique temporary directories within the allowed `data/` path and ensure they are cleaned up.

```python
async def convert(self, file_data: bytes):
    with tempfile.TemporaryDirectory(dir="data/temp") as tmp_dir:
        input_path = Path(tmp_dir) / "input.docx"
        input_path.write_bytes(file_data)
        # ... perform conversion ...
        # Directory is automatically deleted after the block
```

## 4. Usage

### Uploading a file for conversion
```bash
curl -X POST "http://localhost:8082/plugins/doc_converter/convert/pdf" \
  -F "file=@my_doc.docx" \
  -o output.pdf
```

### Checking Sandbox Status via CLI
```bash
# View resource consumption and limits
xcore sandbox limits doc_converter

# Audit network access (should be blocked for this plugin)
xcore sandbox network doc_converter
```
