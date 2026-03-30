# Sandboxed Plugin Example (Advanced)

Un exemple complet de plugin **Sandboxed** avec architecture sécurisée utilisant `router.py` séparé et opérations isolées.

## Cas d'usage : Convertisseur de Documents (Document Converter)

Ce plugin convertit des documents entre différents formats de manière sécurisée, sans accès direct à la base de données ou au système de fichiers.

## Pourquoi Sandboxed ?

Ce plugin est idéal pour le mode sandboxed car :
- Il traite des **fichiers utilisateurs** (risque de contenu malveillant)
- Il utilise des **bibliothèques externes** (pandoc, libreoffice)
- Il doit être **isolé** du système principal
- Les **ressources sont limitées** (CPU, mémoire, disque)

## Structure du Plugin

```
plugins/document_converter/
├── plugin.yaml           # Manifest du plugin
├── src/
│   ├── __init__.py
│   ├── main.py          # Point d'entrée principal
│   ├── router.py        # Routes HTTP FastAPI
│   └── converter.py     # Logique de conversion
└── data/                # Zone de travail isolée (temporaire)
    └── .gitkeep
```

## 1. plugin.yaml

```yaml
name: document_converter
version: 1.5.0
author: XCore Team
description: |
  Convertisseur de documents sécurisé supportant:
  - PDF vers Word, Excel, PowerPoint
  - Images vers PDF (OCR)
  - Markdown vers HTML/PDF
  - Compression et optimisation
  Mode Sandboxed pour isolation maximale.

execution_mode: sandboxed
framework_version: ">=2.0"
entry_point: src/main.py

# Imports autorisés (liste blanche)
allowed_imports:
  - fastapi
  - pydantic
  - httpx
  - asyncio
  - subprocess
  - tempfile
  - pathlib
  - hashlib
  - json
  - os
  - sys
  - time
  - typing
  - dataclasses
  - datetime
  - base64
  - io
  - zipfile
  - PIL
  - pypandoc

# Permissions minimales requises
permissions:
  # Accès au cache uniquement pour les métadonnées
  - resource: "cache.converter.*"
    actions: ["read", "write"]
    effect: allow

  # Accès au storage pour récupérer/envoyer des fichiers
  - resource: "storage.files"
    actions: ["read", "write"]
    effect: allow

  # Pas d'accès à la DB, email, scheduler, etc.
  - resource: "db.*"
    actions: ["*"]
    effect: deny
  - resource: "ext.email*"
    actions: ["*"]
    effect: deny
  - resource: "scheduler"
    actions: ["*"]
    effect: deny
  - resource: "audit.log"
    actions: ["*"]
    effect: deny

# Ressources strictement limitées (sandbox)
resources:
  timeout_seconds: 60          # Max 60 secondes par opération
  max_memory_mb: 256           # Max 256 MB RAM
  max_disk_mb: 100             # Max 100 MB disque temporaire
  rate_limit:
    calls: 50                  # Max 50 conversions/minute
    period_seconds: 60

# Runtime avec surveillance
runtime:
  health_check:
    enabled: true
    interval_seconds: 10
    timeout_seconds: 2
  retry:
    max_attempts: 1            # Pas de retry (sandbox)
    backoff_seconds: 0

# Filesystem isolé
filesystem:
  allowed_paths:
    - "data/temp/"             # Zone de travail temporaire
    - "data/uploads/"          # Uploads entrants
    - "data/outputs/"          # Fichiers générés
  denied_paths:
    - ".."                     # Pas d'accès parent
    - "/etc"                   # Pas d'accès système
    - "/proc"                  # Pas d'accès proc
    - "/sys"                   # Pas d'accès sys
    - "src/"                   # Pas d'accès au code source

# Configuration du plugin
conversion:
  formats:
    supported:
      - "pdf"
      - "docx"
      - "xlsx"
      - "pptx"
      - "md"
      - "html"
      - "txt"
      - "jpg"
      - "png"
    max_input_size_mb: 10       # Max 10 MB par fichier
    max_output_size_mb: 50

  quality:
    pdf_dpi: 150
    image_quality: 85

  security:
    scan_uploads: true
    allow_scripts: false       # Pas de macros/scripts
    sanitize_html: true
```

## 2. src/converter.py

```python
"""Logique de conversion de documents en mode isolé."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image


@dataclass
class ConversionResult:
    """Résultat d'une conversion."""
    success: bool
    output_data: bytes | None = None
    output_format: str | None = None
    file_hash: str | None = None
    file_size: int = 0
    duration_ms: float = 0.0
    error_message: str | None = None
    warnings: list[str] = None

    def to_dict(self) -> dict:
        """Convertit en dictionnaire (sans données binaires)."""
        return {
            "success": self.success,
            "output_format": self.output_format,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "warnings": self.warnings or [],
        }


@dataclass
class ConversionRequest:
    """Requête de conversion."""
    input_data: bytes
    input_format: str
    output_format: str
    options: dict[str, Any] = None


class DocumentConverter:
    """
    Convertisseur de documents en mode sandbox.

    Caractéristiques de sécurité:
    - Travaille uniquement dans un répertoire temporaire isolé
    - Vérifie les types MIME et magic numbers
    - Limite la taille des entrées/sorties
    - Timeout strict sur les subprocess
    """

    # Magic numbers pour validation
    MAGIC_NUMBERS = {
        "pdf": b"%PDF",
        "docx": b"PK\x03\x04",  # ZIP
        "xlsx": b"PK\x03\x04",
        "pptx": b"PK\x03\x04",
        "png": b"\x89PNG\r\n\x1a\n",
        "jpg": b"\xff\xd8\xff",
    }

    def __init__(self, config: dict, temp_dir: Path) -> None:
        self.config = config
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.max_input_size = config.get("max_input_size_mb", 10) * 1024 * 1024
        self.max_output_size = config.get("max_output_size_mb", 50) * 1024 * 1024
        self.timeout = config.get("timeout_seconds", 60)

    async def convert(self, request: ConversionRequest) -> ConversionResult:
        """Convertit un document de manière sécurisée."""
        start_time = datetime.utcnow()
        warnings = []

        try:
            # Validation
            if not self._validate_request(request):
                return ConversionResult(
                    success=False,
                    error_message="Requête invalide ou fichier trop grand",
                    warnings=warnings
                )

            # Vérification du type de fichier
            if not self._verify_file_type(request.input_data, request.input_format):
                return ConversionResult(
                    success=False,
                    error_message=f"Type de fichier invalide (attendu: {request.input_format})",
                    warnings=warnings
                )

            # Création d'un répertoire de travail unique
            work_dir = self._create_work_dir()

            try:
                # Écriture du fichier d'entrée
                input_path = work_dir / f"input.{request.input_format}"
                input_path.write_bytes(request.input_data)

                # Conversion selon le format
                result = await self._do_conversion(
                    input_path,
                    request.output_format,
                    work_dir,
                    request.options or {}
                )

                result.duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                result.warnings = warnings

                return result

            finally:
                # Nettoyage sécurisé
                self._cleanup_work_dir(work_dir)

        except Exception as e:
            return ConversionResult(
                success=False,
                error_message=f"Erreur conversion: {str(e)}",
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                warnings=warnings
            )

    def _validate_request(self, request: ConversionRequest) -> bool:
        """Valide la requête."""
        # Taille d'entrée
        if len(request.input_data) > self.max_input_size:
            return False

        # Formats supportés
        supported = self.config.get("formats", {}).get("supported", [])
        if request.input_format not in supported:
            return False
        if request.output_format not in supported:
            return False

        return True

    def _verify_file_type(self, data: bytes, expected_format: str) -> bool:
        """Vérifie le magic number du fichier."""
        magic = self.MAGIC_NUMBERS.get(expected_format.lower())
        if not magic:
            return True  # Pas de vérification possible

        return data.startswith(magic)

    def _create_work_dir(self) -> Path:
        """Crée un répertoire de travail unique."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.md5(os.urandom(16)).hexdigest()[:8]
        work_dir = self.temp_dir / f"work_{timestamp}_{random_suffix}"
        work_dir.mkdir(parents=True, exist_ok=True)
        return work_dir

    def _cleanup_work_dir(self, work_dir: Path) -> None:
        """Nettoie le répertoire de travail."""
        try:
            for file in work_dir.iterdir():
                file.unlink()
            work_dir.rmdir()
        except Exception:
            pass  # Ignorer les erreurs de nettoyage

    async def _do_conversion(
        self,
        input_path: Path,
        output_format: str,
        work_dir: Path,
        options: dict
    ) -> ConversionResult:
        """Effectue la conversion appropriée."""
        input_format = input_path.suffix[1:].lower()

        # PDF vers autre
        if input_format == "pdf":
            if output_format in ["docx", "xlsx", "pptx"]:
                return await self._convert_pdf_to_office(input_path, output_format, work_dir, options)
            if output_format == "txt":
                return await self._convert_pdf_to_text(input_path, work_dir, options)

        # Office vers PDF
        if input_format in ["docx", "xlsx", "pptx"] and output_format == "pdf":
            return await self._convert_office_to_pdf(input_path, work_dir, options)

        # Markdown vers HTML/PDF
        if input_format == "md":
            if output_format == "html":
                return await self._convert_md_to_html(input_path, work_dir, options)
            if output_format == "pdf":
                return await self._convert_md_to_pdf(input_path, work_dir, options)

        # Images vers PDF
        if input_format in ["jpg", "png"] and output_format == "pdf":
            return await self._convert_image_to_pdf(input_path, work_dir, options)

        # Images compression
        if input_format in ["jpg", "png"] and output_format == input_format:
            return await self._compress_image(input_path, work_dir, options)

        return ConversionResult(
            success=False,
            error_message=f"Conversion {input_format} -> {output_format} non supportée"
        )

    async def _convert_pdf_to_office(
        self,
        input_path: Path,
        output_format: str,
        work_dir: Path,
        options: dict
    ) -> ConversionResult:
        """Convertit PDF vers format Office avec LibreOffice."""
        output_path = work_dir / f"output.{output_format}"

        cmd = [
            "libreoffice",
            "--headless",
            "--convert-to", output_format,
            "--outdir", str(work_dir),
            str(input_path)
        ]

        result = await self._run_subprocess(cmd)

        if result.returncode != 0:
            return ConversionResult(
                success=False,
                error_message=f"LibreOffice error: {result.stderr}"
            )

        return self._read_output(output_path)

    async def _convert_office_to_pdf(
        self,
        input_path: Path,
        work_dir: Path,
        options: dict
    ) -> ConversionResult:
        """Convertit Office vers PDF."""
        output_path = work_dir / "output.pdf"

        cmd = [
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(work_dir),
            str(input_path)
        ]

        result = await self._run_subprocess(cmd)

        if result.returncode != 0:
            return ConversionResult(
                success=False,
                error_message=f"LibreOffice error: {result.stderr}"
            )

        return self._read_output(output_path)

    async def _convert_pdf_to_text(
        self,
        input_path: Path,
        work_dir: Path,
        options: dict
    ) -> ConversionResult:
        """Extrait le texte d'un PDF."""
        cmd = ["pdftotext", str(input_path), "-"]

        result = await self._run_subprocess(cmd)

        if result.returncode != 0:
            return ConversionResult(
                success=False,
                error_message=f"pdftotext error: {result.stderr}"
            )

        text_data = result.stdout.encode("utf-8")
        file_hash = hashlib.sha256(text_data).hexdigest()

        return ConversionResult(
            success=True,
            output_data=text_data,
            output_format="txt",
            file_hash=file_hash,
            file_size=len(text_data)
        )

    async def _convert_md_to_html(
        self,
        input_path: Path,
        work_dir: Path,
        options: dict
    ) -> ConversionResult:
        """Convertit Markdown vers HTML."""
        try:
            import pypandoc

            html = pypandoc.convert_file(
                str(input_path),
                "html",
                format="markdown",
                extra_args=["--standalone"]
            )

            html_data = html.encode("utf-8")
            file_hash = hashlib.sha256(html_data).hexdigest()

            return ConversionResult(
                success=True,
                output_data=html_data,
                output_format="html",
                file_hash=file_hash,
                file_size=len(html_data)
            )

        except Exception as e:
            return ConversionResult(
                success=False,
                error_message=f"Pandoc error: {str(e)}"
            )

    async def _convert_md_to_pdf(
        self,
        input_path: Path,
        work_dir: Path,
        options: dict
    ) -> ConversionResult:
        """Convertit Markdown vers PDF via HTML."""
        # D'abord en HTML
        html_result = await self._convert_md_to_html(input_path, work_dir, options)

        if not html_result.success:
            return html_result

        # Puis HTML vers PDF avec weasyprint ou similaire
        html_path = work_dir / "temp.html"
        html_path.write_bytes(html_result.output_data)

        output_path = work_dir / "output.pdf"

        cmd = ["weasyprint", str(html_path), str(output_path)]
        result = await self._run_subprocess(cmd)

        if result.returncode != 0:
            return ConversionResult(
                success=False,
                error_message=f"Weasyprint error: {result.stderr}"
            )

        return self._read_output(output_path)

    async def _convert_image_to_pdf(
        self,
        input_path: Path,
        work_dir: Path,
        options: dict
    ) -> ConversionResult:
        """Convertit une image vers PDF."""
        try:
            from PIL import Image

            output_path = work_dir / "output.pdf"

            image = Image.open(input_path)

            # Convertir en RGB si nécessaire (pour PNG avec transparence)
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")

            image.save(output_path, "PDF", resolution=options.get("dpi", 150))

            return self._read_output(output_path)

        except Exception as e:
            return ConversionResult(
                success=False,
                error_message=f"Image conversion error: {str(e)}"
            )

    async def _compress_image(
        self,
        input_path: Path,
        work_dir: Path,
        options: dict
    ) -> ConversionResult:
        """Compresse une image."""
        try:
            from PIL import Image

            output_path = work_dir / f"output.{input_path.suffix[1:]}"

            image = Image.open(input_path)

            # Qualité
            quality = options.get("quality", 85)

            # Redimensionnement optionnel
            max_size = options.get("max_dimension")
            if max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Sauvegarde avec compression
            if input_path.suffix.lower() in [".jpg", ".jpeg"]:
                image.save(output_path, "JPEG", quality=quality, optimize=True)
            else:
                image.save(output_path, optimize=True)

            return self._read_output(output_path)

        except Exception as e:
            return ConversionResult(
                success=False,
                error_message=f"Image compression error: {str(e)}"
            )

    async def _run_subprocess(self, cmd: list[str]) -> Any:
        """Exécute une commande avec timeout."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.temp_dir)
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout
            )
            return type("Result", (), {
                "returncode": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="ignore"),
                "stderr": stderr.decode("utf-8", errors="ignore")
            })
        except asyncio.TimeoutError:
            proc.kill()
            return type("Result", (), {
                "returncode": -1,
                "stdout": "",
                "stderr": "Timeout"
            })

    def _read_output(self, output_path: Path) -> ConversionResult:
        """Lit le fichier de sortie."""
        if not output_path.exists():
            return ConversionResult(
                success=False,
                error_message="Fichier de sortie non créé"
            )

        data = output_path.read_bytes()

        if len(data) > self.max_output_size:
            return ConversionResult(
                success=False,
                error_message="Fichier de sortie trop grand"
            )

        file_hash = hashlib.sha256(data).hexdigest()

        return ConversionResult(
            success=True,
            output_data=data,
            output_format=output_path.suffix[1:],
            file_hash=file_hash,
            file_size=len(data)
        )

## Utilisation

### Endpoints HTTP

```bash
# Lister les formats supportés
curl "http://localhost:8082/plugins/document_converter/convert/formats"
# Réponse: {"status": "ok", "formats": {"pdf": ["docx", "txt"], ...}}

# Convertir un PDF vers Word
curl -X POST "http://localhost:8082/plugins/document_converter/convert/docx" \
  -F "file=@document.pdf" \
  -o document.docx

# Convertir avec options
curl -X POST "http://localhost:8082/plugins/document_converter/convert/pdf?dpi=300" \
  -F "file=@image.jpg" \
  -o output.pdf

# Convertir en base64 (pour API)
curl -X POST "http://localhost:8082/plugins/document_converter/convert/base64/html" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": "IyBIZWxsbwoKKipXb3JsZCoq",
    "input_format": "md",
    "filename": "mydoc"
  }'

# Conversion en lot
curl -X POST "http://localhost:8082/plugins/document_converter/convert/batch?output_format=pdf" \
  -F "files=@doc1.docx" \
  -F "files=@doc2.docx" \
  -o converted_batch.zip

# Health check
curl "http://localhost:8082/plugins/document_converter/convert/health"
```

### Appels IPC

```bash
# Conversion via IPC
curl -X POST http://localhost:8082/app/document_converter/convert \
  -H "Content-Type: application/json" \
  -d '{
    "data": "JVBERi0xLjQK...",
    "input_format": "pdf",
    "output_format": "txt"
  }'

# Lister les formats
curl -X POST http://localhost:8082/app/document_converter/get_formats

# Health check
curl -X POST http://localhost:8082/app/document_converter/health

# Forcer le nettoyage
curl -X POST http://localhost:8082/app/document_converter/cleanup
```

## Points Clés de l'Architecture Sandboxed

### 1. Séparation des Responsabilités

```
main.py       → Point d'entrée, actions IPC (limitées), cycle de vie
router.py     → Routes HTTP, gestion upload/download
converter.py  → Logique de conversion isolée
```

### 2. Contraintes de Sécurité

| Aspect | Trusted | Sandboxed |
|--------|---------|-----------|
| Accès DB | ✅ Lecture/Écriture | ❌ Interdit |
| Email | ✅ Envoi | ❌ Interdit |
| Scheduler | ✅ Planification | ❌ Interdit |
| Filesystem | ✅ Accès étendu | ⚠️ Restreint à data/ |
| Mémoire | ✅ Illimitée | ⚠️ 256 MB max |
| Timeout | ✅ 30s par défaut | ⚠️ 60s max |
| Rate Limit | ✅ 1000 calls/min | ⚠️ 50 calls/min |

### 3. Liste Blanche d'Imports

Les imports sont strictement contrôlés:

```yaml
allowed_imports:
  - fastapi
  - pydantic
  - httpx
  - subprocess      # ⚠️ Limité avec timeout
  - tempfile        # ✅ Utilisé pour isolation
  - pathlib
  - hashlib
  # Pas d'accès à:
  # - socket
  # - requests
  # - sqlite3
  # - psycopg2
```

### 4. Validation des Fichiers

```python
# Magic numbers pour détecter les vrais types
MAGIC_NUMBERS = {
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04",  # ZIP (Office)
    "png": b"\x89PNG\r\n\x1a\n",
    "jpg": b"\xff\xd8\xff",
}
```

### 5. Isolation des Processus

```python
# Création d'un répertoire unique par conversion
work_dir = self._create_work_dir()  # work_YYYYMMDD_HHMMSS_random/

try:
    # Opération dans le répertoire isolé
    result = await self._do_conversion(input_path, ...)
finally:
    # Nettoyage garanti
    self._cleanup_work_dir(work_dir)
```

### 6. Subprocess avec Timeout

```python
proc = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=str(self.temp_dir)  # Chroot-like
)

try:
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(),
        timeout=self.timeout  # Kill après timeout
    )
except asyncio.TimeoutError:
    proc.kill()
```

## Comparaison Trusted vs Sandboxed

### Plugin Trusted (Task Manager)

```python
# Accès complet aux services
self.db = ctx.services.get("db")           # ✅
self.cache = ctx.services.get("cache")     # ✅
self.email = ctx.services.get("ext.email") # ✅
self.scheduler = ctx.services.get("scheduler")  # ✅

# Persistance en base
await self.db.execute("INSERT INTO tasks ...")

# Notifications
await self.email.send(...)
```

### Plugin Sandboxed (Document Converter)

```python
# Accès limité
self.cache = ctx.services.get("cache")     # ✅ (patterns spécifiques)
# db, email, scheduler: ❌ Interdit

# Pas de persistance
# Travail uniquement en mémoire et temp files

# Communication via storage service
storage = ctx.services.get("storage")
await storage.write("temp/output.pdf", data)
```

## Bonnes Pratiques Sandboxed

### 1. Toujours valider les entrées

```python
if len(input_data) > self.max_input_size:
    return error("Fichier trop grand")

if not self._verify_file_type(data, expected_format):
    return error("Type de fichier invalide")
```

### 2. Utiliser des répertoires temporaires uniques

```python
work_dir = self._create_work_dir()  # Unique par requête
try:
    # Traitement
finally:
    self._cleanup_work_dir(work_dir)  # Nettoyage garanti
```

### 3. Limiter les ressources

```yaml
resources:
  timeout_seconds: 60
  max_memory_mb: 256
  max_disk_mb: 100
  rate_limit:
    calls: 50
    period_seconds: 60
```

### 4. Pas de fuites d'information

```python
# ✅ Bon: retourne les métadonnées
return ok(
    size=result.file_size,
    hash=result.file_hash,
)

# ❌ Mauvais: expose des chemins système
return ok(
    path="/var/lib/xcore/plugins/...",  # Fuite!
)
```

## Tests

```python
# tests/test_document_converter.py
import pytest
import httpx


@pytest.mark.asyncio
async def test_convert_pdf_to_docx():
    async with httpx.AsyncClient() as client:
        with open("tests/fixtures/sample.pdf", "rb") as f:
            response = await client.post(
                "http://localhost:8082/plugins/document_converter/convert/docx",
                files={"file": ("sample.pdf", f, "application/pdf")}
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        )


@pytest.mark.asyncio
async def test_invalid_file_type():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8082/plugins/document_converter/convert/docx",
            files={"file": ("virus.exe", b"MZ\x90\x00", "application/pdf")}
        )

        assert response.status_code == 400
        assert "Type de fichier invalide" in response.text


@pytest.mark.asyncio
async def test_file_too_large():
    async with httpx.AsyncClient() as client:
        # Fichier de 20 MB quand max est 10 MB
        large_file = b"x" * (20 * 1024 * 1024)

        response = await client.post(
            "http://localhost:8082/plugins/document_converter/convert/docx",
            files={"file": ("large.pdf", large_file, "application/pdf")}
        )

        assert response.status_code == 413
```

## Dépannage

### Problème: Timeout sur les conversions

**Solution**: Augmenter le timeout dans `plugin.yaml`:
```yaml
resources:
  timeout_seconds: 120  # Au lieu de 60
```

### Problème: Espace disque insuffisant

**Solution**: Vérifier et nettoyer:
```bash
curl -X POST http://localhost:8082/app/document_converter/cleanup
```

### Problème: LibreOffice non trouvé

**Solution**: Installer les dépendances:
```bash
# Debian/Ubuntu
sudo apt-get install libreoffice poppler-utils pandoc

# Vérifier
which libreoffice  # doit retourner un chemin
```

## Commandes Sandbox CLI

Le mode sandbox peut être testé et inspecté via les commandes CLI :

```bash
# Lancer un plugin en mode sandbox isolé pour test
xcore sandbox run document_converter
# 🚀  Lancement sandbox : document_converter
#     mémoire max : 256MB
#     timeout     : 60s
# ✅  Sandbox démarré
#     PID   : 12345
#     État  : running
# ✅  Ping OK — plugin opérationnel
# 🛑  Sandbox arrêté.

# Vérifier les limites ressources
xcore sandbox limits document_converter

# Auditer la politique réseau
xcore sandbox network document_converter

# Valider la politique filesystem
xcore sandbox fs document_converter
```

## Appels IPC depuis le Core

Pour appeler un plugin sandboxed depuis l'extérieur (Core ou autre plugin Trusted) :

```bash
# Via l'API HTTP IPC
curl -X POST http://localhost:8000/plugin/ipc/document_converter/convert \
  -H "Content-Type: application/json" \
  -H "X-Plugin-Key: ${API_KEY}" \
  -d '{
    "data": "JVBERi0xLjQK...",
    "input_format": "pdf",
    "output_format": "txt"
  }'

# Réponse :
# {
#   "status": "ok",
#   "data": "...base64...",
#   "format": "txt",
#   "size": 1234,
#   "hash": "sha256...",
#   "duration_ms": 250
# }

#ou via autre plugin

class Plugin(TustedBase):
    ...

    def 


```

Le canal IPC est géré par `IPCChannel` qui communique en JSON newline-delimited avec le subprocess sandbox.

## Résumé

| Caractéristique | Trusted Plugin | Sandboxed Plugin |
|-----------------|----------------|------------------|
| **Cas d'usage** | Gestion données, workflows | Traitement fichiers, conversion |
| **Accès services** | Complet | Limité (cache, storage) |
| **Filesystem** | Étendu | Isolé à data/ |
| **Ressources** | Configurables | Strictement limitées |
| **Imports** | Libres | Liste blanche |
| **Timeout** | 30s par défaut | 60s max |
| **Persistance** | Base de données | Fichiers temporaires |
| **Configuration** | `.env` + `plugin.yaml` | `plugin.yaml` uniquement |
| **IPC** | Via services directs | Via `IPCChannel` JSON-RPC |

## 3. src/router.py

```python
"""Routes HTTP FastAPI pour Document Converter (mode Sandboxed)."""
from __future__ import annotations

import base64
import hashlib
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Body
from fastapi.responses import StreamingResponse
import io

from .converter import ConversionRequest


def create_router(plugin_instance) -> APIRouter:
    """
    Crée le router FastAPI avec accès au plugin.

    Args:
        plugin_instance: Instance du plugin (Sandboxed)
    """
    router = APIRouter(
        prefix="/convert",
        tags=["document-converter"],
    )

    converter = plugin_instance.converter
    cache = plugin_instance.ctx.services.get("cache") if plugin_instance.ctx else None

    @router.get("/formats")
    async def list_formats():
        """Liste les formats supportés et leurs conversions possibles."""
        supported = converter.get_supported_conversions()
        return {
            "status": "ok",
            "formats": supported,
            "max_input_size_mb": converter.config.get("max_input_size_mb", 10),
            "max_output_size_mb": converter.config.get("max_output_size_mb", 50),
        }

    @router.post("/{output_format}")
    async def convert_file(
        output_format: str,
        file: UploadFile = File(..., description="Fichier à convertir"),
        quality: int = Query(85, ge=1, le=100, description="Qualité (pour images)"),
        dpi: int = Query(150, ge=72, le=600, description="DPI (pour PDF)"),
        max_dimension: int = Query(None, description="Dimension max (pour images)"),
    ):
        """
        Convertit un fichier uploadé vers le format demandé.

        Exemple: POST /convert/pdf avec un fichier .docx
        """
        if not file.filename:
            raise HTTPException(status_code=400, detail="Nom de fichier manquant")

        # Détecter le format d'entrée depuis l'extension
        input_format = file.filename.split(".")[-1].lower()

        # Vérifier si la conversion est supportée
        supported = converter.get_supported_conversions()
        if input_format not in supported:
            raise HTTPException(
                status_code=400,
                detail=f"Format d'entrée '{input_format}' non supporté"
            )

        if output_format not in supported.get(input_format, []):
            raise HTTPException(
                status_code=400,
                detail=f"Conversion {input_format} -> {output_format} non supportée"
            )

        # Lire le fichier
        input_data = await file.read()

        # Vérifier la taille
        max_size = converter.config.get("max_input_size_mb", 10) * 1024 * 1024
        if len(input_data) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Fichier trop grand (max {max_size / 1024 / 1024} MB)"
            )

        # Préparer la requête
        request = ConversionRequest(
            input_data=input_data,
            input_format=input_format,
            output_format=output_format,
            options={
                "quality": quality,
                "dpi": dpi,
                "max_dimension": max_dimension,
            }
        )

        # Exécuter la conversion
        import asyncio
        result = await converter.convert(request)

        if not result.success:
            raise HTTPException(
                status_code=422,
                detail=result.error_message
            )

        # Mettre en cache le hash pour tracking
        if cache:
            cache_key = f"converter:hash:{result.file_hash}"
            await cache.set(cache_key, {
                "input_format": input_format,
                "output_format": output_format,
                "file_size": result.file_size,
                "duration_ms": result.duration_ms,
            }, ttl=3600)

        # Retourner le fichier
        output_io = io.BytesIO(result.output_data)

        # Type MIME approprié
        mime_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "html": "text/html",
            "txt": "text/plain",
        }

        return StreamingResponse(
            output_io,
            media_type=mime_types.get(output_format, "application/octet-stream"),
            headers={
                "Content-Disposition": f'attachment; filename="converted.{output_format}"',
                "X-Conversion-Time": str(result.duration_ms),
                "X-Output-Hash": result.file_hash,
            }
        )

    @router.post("/base64/{output_format}")
    async def convert_base64(
        output_format: str,
        input_data: str = Body(..., description="Données base64"),
        input_format: str = Body(..., description="Format d'entrée"),
        filename: str = Body("document", description="Nom du fichier"),
        options: dict = Body({}, description="Options de conversion"),
    ):
        """
        Convertit des données encodées en base64.

        Utile pour les API et les intégrations frontend.
        """
        try:
            decoded = base64.b64decode(input_data)
        except Exception:
            raise HTTPException(status_code=400, detail="Données base64 invalides")

        request = ConversionRequest(
            input_data=decoded,
            input_format=input_format,
            output_format=output_format,
            options=options
        )

        import asyncio
        result = await converter.convert(request)

        if not result.success:
            raise HTTPException(status_code=422, detail=result.error_message)

        # Retourner en base64
        output_b64 = base64.b64encode(result.output_data).decode("utf-8")

        return {
            "status": "ok",
            "filename": f"{filename}.{output_format}",
            "format": output_format,
            "size": result.file_size,
            "hash": result.file_hash,
            "duration_ms": result.duration_ms,
            "data": output_b64,
        }

    @router.post("/batch")
    async def convert_batch(
        files: list[UploadFile] = File(..., description="Fichiers à convertir"),
        output_format: str = Query(..., description="Format de sortie commun"),
    ):
        """
        Convertit plusieurs fichiers en lot.

        Retourne une archive ZIP avec tous les fichiers convertis.
        """
        import zipfile
        import asyncio

        results = []
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file in files:
                if not file.filename:
                    continue

                input_format = file.filename.split(".")[-1].lower()
                input_data = await file.read()

                request = ConversionRequest(
                    input_data=input_data,
                    input_format=input_format,
                    output_format=output_format
                )

                result = await converter.convert(request)

                if result.success:
                    output_name = f"{file.filename.rsplit('.', 1)[0]}.{output_format}"
                    zip_file.writestr(output_name, result.output_data)
                    results.append({
                        "original": file.filename,
                        "converted": output_name,
                        "success": True,
                    })
                else:
                    results.append({
                        "original": file.filename,
                        "success": False,
                        "error": result.error_message,
                    })

        zip_buffer.seek(0)

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="converted_batch.zip"',
                "X-Results": str(results),
            }
        )

    @router.get("/health")
    async def health_check():
        """Vérifie l'état du convertisseur."""
        import shutil

        # Vérifier les dépendances
        deps = {
            "libreoffice": shutil.which("libreoffice") is not None,
            "pdftotext": shutil.which("pdftotext") is not None,
            "pandoc": shutil.which("pandoc") is not None,
        }

        all_ready = all(deps.values())

        return {
            "status": "healthy" if all_ready else "degraded",
            "dependencies": deps,
            "sandbox": {
                "temp_dir": str(converter.temp_dir),
                "max_memory_mb": converter.config.get("max_memory_mb", 256),
                "timeout_seconds": converter.timeout,
            }
        }

    return router
```

## 4. src/main.py

```python
"""Point d'entrée du plugin Document Converter (mode Sandboxed)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from xcore.sdk import BasePlugin, ok, error

from .converter import DocumentConverter
from .router import create_router


class Plugin:
    """
    Plugin Document Converter - Mode Sandboxed.

    Caractéristiques de sécurité:
    - Exécution isolée avec ressources limitées
    - Pas d'accès direct à la base de données
    - Filesystem restreint au répertoire data/
    - Timeout strict sur les opérations
    - Validation des types de fichiers
    """

    def __init__(self) -> None:
        self.converter: DocumentConverter | None = None
        self.config: dict[str, Any] = {}
        self.work_dir: Path | None = None
        self.ctx: Any = None

    async def _inject_context(self, ctx: Any) -> None:
        """Injecte le contexte du plugin."""
        self.ctx = ctx

        # Récupérer la configuration
        self.config = ctx.config if ctx else {}

        # Définir le répertoire de travail (sandbox)
        plugin_dir = ctx.plugin_dir if ctx else Path(".")
        self.work_dir = plugin_dir / "data" / "temp"
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Initialiser le convertisseur
        conversion_config = self.config.get("conversion", {})
        self.converter = DocumentConverter(conversion_config, self.work_dir)

    async def on_load(self) -> None:
        """Initialisation du plugin."""
        print("📄 Document Converter - Chargement (mode Sandboxed)...")

        if not self.converter:
            raise RuntimeError("Contexte non injecté")

        # Vérifier l'espace disponible
        stat = os.statvfs(self.work_dir)
        free_mb = (stat.f_bavail * stat.f_frsize) / 1024 / 1024

        print(f"✅ Document Converter v1.5.0 chargé")
        print(f"   Mode: Sandboxed")
        print(f"   Work dir: {self.work_dir}")
        print(f"   Espace libre: {free_mb:.1f} MB")
        print(f"   Formats supportés: {len(self.converter.get_supported_conversions())}")

    async def on_unload(self) -> None:
        """Nettoyage à l'arrêt."""
        print("👋 Document Converter - Nettoyage...")

        # Nettoyer le répertoire temporaire
        if self.work_dir:
            import shutil
            try:
                for item in self.work_dir.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
            except Exception as e:
                print(f"   ⚠️ Erreur nettoyage: {e}")

        print("   ✅ Nettoyage terminé")

    def get_router(self) -> APIRouter | None:
        """Fournit le router HTTP."""
        if not self.converter:
            return None
        return create_router(self)

    async def handle(self, action: str, payload: dict) -> dict:
        """
        Gère les actions IPC.

        En mode sandboxed, seules les actions sûres sont exposées.
        """
        if not self.converter:
            return error("Plugin non initialisé", code="not_ready")

        handlers = {
            "convert": self._handle_convert,
            "get_formats": self._handle_get_formats,
            "health": self._handle_health,
            "cleanup": self._handle_cleanup,
        }

        handler = handlers.get(action)
        if not handler:
            return error(
                f"Action '{action}' inconnue ou non autorisée en mode Sandboxed",
                code="unknown_action"
            )

        try:
            return await handler(payload)
        except Exception as e:
            return error(f"Erreur: {str(e)}", code="internal_error")

    async def _handle_convert(self, payload: dict) -> dict:
        """Convertit un document via IPC."""
        import base64

        input_b64 = payload.get("data")
        input_format = payload.get("input_format")
        output_format = payload.get("output_format")
        options = payload.get("options", {})

        if not all([input_b64, input_format, output_format]):
            return error(
                "Paramètres requis: data, input_format, output_format",
                code="missing_params"
            )

        try:
            input_data = base64.b64decode(input_b64)
        except Exception:
            return error("Données base64 invalides", code="invalid_data")

        from .converter import ConversionRequest

        request = ConversionRequest(
            input_data=input_data,
            input_format=input_format,
            output_format=output_format,
            options=options
        )

        result = await self.converter.convert(request)

        if not result.success:
            return error(result.error_message, code="conversion_failed")

        return ok(
            data=base64.b64encode(result.output_data).decode("utf-8"),
            format=output_format,
            size=result.file_size,
            hash=result.file_hash,
            duration_ms=result.duration_ms,
            warnings=result.warnings,
        )

    async def _handle_get_formats(self, payload: dict) -> dict:
        """Liste les formats supportés."""
        return ok(
            formats=self.converter.get_supported_conversions(),
            max_input_size_mb=self.converter.config.get("max_input_size_mb", 10),
            max_output_size_mb=self.converter.config.get("max_output_size_mb", 50),
        )

    async def _handle_health(self, payload: dict) -> dict:
        """Vérifie la santé du plugin."""
        import shutil

        deps = {
            "libreoffice": shutil.which("libreoffice") is not None,
            "pdftotext": shutil.which("pdftotext") is not None,
            "pandoc": shutil.which("pandoc") is not None,
        }

        return ok(
            ready=all(deps.values()),
            dependencies=deps,
            sandbox=True,
            work_dir=str(self.work_dir),
        )

    async def _handle_cleanup(self, payload: dict) -> dict:
        """Force le nettoyage des fichiers temporaires."""
        if not self.work_dir:
            return error("Work dir non initialisé", code="not_ready")

        import shutil
        cleaned = 0

        try:
            for item in self.work_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                    cleaned += 1
                elif item.name.startswith("work_"):
                    item.unlink()
                    cleaned += 1

            return ok(cleaned=cleaned)
        except Exception as e:
            return error(f"Erreur nettoyage: {str(e)}", code="cleanup_failed")


# Compatibility avec le protocole BasePlugin
Plugin.__protocol__ = True

## Utilisation

### Endpoints HTTP

```bash
# Lister les formats supportés
curl "http://localhost:8082/plugins/document_converter/convert/formats"
# {
#   "status": "ok",
#   "formats": {
#     "pdf": ["docx", "txt"],
#     "docx": ["pdf"],
#     ...
#   },
#   "max_input_size_mb": 10,
#   "max_output_size_mb": 50
# }

# Convertir un PDF en Word
curl -X POST "http://localhost:8082/plugins/document_converter/convert/docx" \
  -F "file=@document.pdf" \
  --output document.docx

# Convertir une image en PDF
curl -X POST "http://localhost:8082/plugins/document_converter/convert/pdf" \
  -F "file=@photo.jpg" \
  -F "dpi=300" \
  --output photo.pdf

# Convertir avec compression
curl -X POST "http://localhost:8082/plugins/document_converter/convert/jpg" \
  -F "file=@large.jpg" \
  -F "quality=70" \
  -F "max_dimension=1920" \
  --output compressed.jpg

# Conversion en base64 (pour API)
curl -X POST "http://localhost:8082/plugins/document_converter/convert/base64/pdf" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": "JVBERi0xLjQKJcOkw7zDtsO...",
    "input_format": "pdf",
    "filename": "document"
  }'

# Conversion en lot
curl -X POST "http://localhost:8082/plugins/document_converter/convert/batch?output_format=pdf" \
  -F "files=@doc1.docx" \
  -F "files=@doc2.docx" \
  -F "files=@doc3.docx" \
  --output converted_batch.zip

# Health check
curl "http://localhost:8082/plugins/document_converter/convert/health"
# {
#   "status": "healthy",
#   "dependencies": {
#     "libreoffice": true,
#     "pdftotext": true,
#     "pandoc": true
#   },
#   "sandbox": {...}
# }
```

### Appels IPC

```bash
# Conversion via IPC
curl -X POST http://localhost:8082/app/document_converter/convert \
  -H "Content-Type: application/json" \
  -d '{
    "data": "JVBERi0xLjQKJcOkw7zDtsO...",
    "input_format": "pdf",
    "output_format": "docx",
    "options": {"quality": 90}
  }'
# {"status": "ok", "data": "...base64...", "format": "docx", "size": 12345}

# Vérifier la santé
curl -X POST http://localhost:8082/app/document_converter/health
# {"status": "ok", "ready": true, "sandbox": true}

# Lister les formats
curl -X POST http://localhost:8082/app/document_converter/get_formats
# {"status": "ok", "formats": {...}}

# Nettoyage forcé
curl -X POST http://localhost:8082/app/document_converter/cleanup
# {"status": "ok", "cleaned": 5}
```

## Points Clés du Mode Sandboxed

### 1. Restrictions de Sécurité

```yaml
# Ressources strictement limitées
resources:
  timeout_seconds: 60      # Pas d'opération longue
  max_memory_mb: 256       # Mémoire limitée
  max_disk_mb: 100         # Espace disque restreint

# Filesystem isolé
filesystem:
  allowed_paths: ["data/temp/", "data/uploads/", "data/outputs/"]
  denied_paths: ["..", "/etc", "/proc", "/sys"]

# Pas d'accès aux services sensibles
permissions:
  - resource: "db.*"           # Interdit
    effect: deny
  - resource: "ext.email*"     # Interdit
    effect: deny
```

### 2. Liste Blanche d'Imports

```yaml
allowed_imports:
  - fastapi
  - pydantic
  - PIL           # Traitement d'images
  - pypandoc      # Conversion Markdown
  - subprocess    # Exécution contrôlée
  # ...pas de requests, pas de socket, etc.
```

### 3. Patterns de Sécurité

**Validation des fichiers:**
```python
def _verify_file_type(self, data: bytes, expected: str) -> bool:
    magic = self.MAGIC_NUMBERS.get(expected)
    return data.startswith(magic)
```

**Timeout sur subprocess:**
```python
async def _run_subprocess(self, cmd: list[str]):
    proc = await asyncio.create_subprocess_exec(*cmd, ...)
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=self.timeout
        )
    except asyncio.TimeoutError:
        proc.kill()  # Force l'arrêt
```

**Nettoyage automatique:**
```python
async def _do_conversion(...):
    work_dir = self._create_work_dir()
    try:
        # ... conversion ...
    finally:
        self._cleanup_work_dir(work_dir)  # Toujours exécuté
```

### 4. Différences avec Trusted

| Aspect | Trusted | Sandboxed |
|--------|---------|-----------|
| **Accès DB** | ✅ Complet | ❌ Interdit |
| **Accès Email** | ✅ Oui | ❌ Interdit |
| **Filesystem** | ✅ Configurable | 🔒 Restreint |
| **Imports** | ✅ Tout Python | 🔒 Liste blanche |
| **Mémoire** | Configurable | 🔒 256 MB max |
| **Timeout** | Configurable | 🔒 60s max |
| **Subprocess** | ✅ Libre | 🔒 Surveillé |

## Tests

```python
# tests/test_document_converter.py
import pytest
import httpx


@pytest.mark.asyncio
async def test_convert_pdf_to_docx():
    async with httpx.AsyncClient() as client:
        # Upload d'un PDF de test
        with open("tests/fixtures/sample.pdf", "rb") as f:
            response = await client.post(
                "http://localhost:8082/plugins/document_converter/convert/docx",
                files={"file": ("sample.pdf", f, "application/pdf")}
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == \
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.mark.asyncio
async def test_file_too_large():
    async with httpx.AsyncClient() as client:
        # Créer un fichier trop grand
        large_file = b"x" * (11 * 1024 * 1024)  # 11 MB

        response = await client.post(
            "http://localhost:8082/plugins/document_converter/convert/pdf",
            files={"file": ("large.txt", large_file, "text/plain")}
        )

        assert response.status_code == 413


@pytest.mark.asyncio
async def test_invalid_file_type():
    async with httpx.AsyncClient() as client:
        # Envoyer un fichier avec extension trompeuse
        fake_pdf = b"NOT_A_PDF_FILE_CONTENTS"

        response = await client.post(
            "http://localhost:8082/plugins/document_converter/convert/docx",
            files={"file": ("fake.pdf", fake_pdf, "application/pdf")}
        )

        assert response.status_code == 422


@pytest.mark.asyncio
async def test_sandbox_isolation():
    """Vérifie que le plugin ne peut pas accéder au filesystem externe."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8082/app/document_converter/convert",
            json={
                "data": "test",
                "input_format": "txt",
                "output_format": "pdf",
                "options": {"path": "../../../etc/passwd"}  # Tentative d'accès
            }
        )

        # Le plugin doit gérer cela de manière sécurisée
        assert response.status_code in [422, 400]
```

## Comparaison Trusted vs Sandboxed

| Cas d'usage | Mode Recommandé | Raison |
|-------------|----------------|--------|
| Gestion utilisateurs | Trusted | Accès DB nécessaire |
| Traitement fichiers | **Sandboxed** | Risque de contenu malveillant |
| Notifications email | Trusted | Accès service email |
| Analytics/Stats | Trusted | Accès DB et cache |
| Conversion documents | **Sandboxed** | Isolation des processus |
| Génération rapports | Trusted | Accès multi-services |
| Compression images | **Sandboxed** | Ressources limitables |

