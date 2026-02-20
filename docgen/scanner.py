import os
import yaml

def load_config():
    with open("docgen/config.yaml") as f:
        return yaml.safe_load(f)

def split_content(content, max_chars):
    return [
        content[i:i+max_chars]
        for i in range(0, len(content), max_chars)
    ]

def is_excluded(root, exclude_dirs):
    parts = root.replace("\\", "/").split("/")
    return any(part in exclude_dirs for part in parts)

def get_module_name(path, repo_root):
    """
    Retourne le chemin relatif du dossier contenant le fichier, depuis la racine du repo.
    Si le fichier est directement à la racine, retourne None.
    Exemples :
      /repo/linting/scanner.py    -> "linting"
      /repo/core/utils/helpers.py -> "core/utils"
      /repo/pipeline.py           -> None
    """
    rel = os.path.relpath(path, repo_root)
    parts = rel.replace("\\", "/").split("/")
    if len(parts) == 1:
        return None
    return "/".join(parts[:-1])

def scan_repo(cfg=None):
    if cfg is None:
        from summarizer import load_config
        cfg = load_config()

    repo      = cfg["project"]["repo_path"]
    max_chars = cfg["generation"]["max_file_chunk_chars"]
    exts      = tuple(cfg["generation"]["include_extensions"])
    exclude   = set(cfg["generation"]["exclude_dirs"])

    # Fichiers a ignorer completement (configurable, defaut : __init__.py)
    ignore_files = set(cfg["generation"].get("exclude_files", ["__init__.py"]))

    chunks = []

    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in exclude]

        if is_excluded(root, exclude):
            continue

        for file in files:
            if file in ignore_files:
                print(f"[SKIP] {os.path.join(root, file)} (excluded file)")
                continue

            if file.endswith(exts):
                path   = os.path.join(root, file)
                module = get_module_name(path, repo)

                try:
                    with open(path, "r", errors="ignore") as f:
                        content = f.read()
                except OSError as e:
                    print(f"[SKIP] Cannot read {path}: {e}")
                    continue

                for part in split_content(content, max_chars):
                    chunks.append({
                        "path":     path,
                        "module":   module,
                        "filename": os.path.splitext(file)[0],
                        "content":  part,
                    })

    return chunks