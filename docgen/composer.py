from summarizer import call_model


def compose_file_doc(path, filename, summary, cfg):
    """
    Génère la documentation Markdown pour un seul fichier source.
    """
    prompt = f"""
You are a senior software architect writing official developer documentation.

Write a clean, well-structured Markdown documentation page for the following source file.
This page will be published in the project's `docs/` directory.

--- STYLE GUIDELINES ---
- Write in clear, flowing prose. Use bullet lists only for discrete enumerable items (e.g. parameters, config keys).
- Use a confident, technical tone. The reader is a developer joining the project.
- Use Markdown headings (## and ###), backticks for code references (`ClassName`, `function_name()`), and short paragraphs.
- Do not pad sections. If a section has little to say, keep it brief.
- Never repeat the filename in the body — it will appear as the page title.

--- REQUIRED SECTIONS ---

## Overview
What this file does and why it exists. 2–3 sentences max.

## Responsibilities
The specific tasks this file handles within the system. Write in prose, not a bullet list.

## Key Components
For each important class or function, write a short paragraph: what it does, its signature (if relevant), and any notable behavior or edge cases.

## Dependencies
What this file imports and relies on — internal modules and external libraries. Briefly explain why each dependency is needed.

## How It Fits In
How this file connects to the rest of the codebase: who calls it, what it produces, and where its output goes.

--- FILE SUMMARY ---
File: {path}

{summary}
"""
    return call_model(prompt, cfg)


def compose_module_index(module_name, file_docs, child_modules, cfg):
    """
    Génère un README.md pour un module.
    Gère les deux cas :
      - module feuille   : a des fichiers directs, pas de sous-modules
      - module intermédiaire : a des sous-modules (et éventuellement des fichiers directs)

    module_name    : ex "linting" ou "core/utils"
    file_docs      : dict filename → { summary, doc_path }  (fichiers directs)
    child_modules  : dict child_module_path → description courte  (sous-modules directs)
    """
    # Section fichiers directs
    if file_docs:
        files_section = "### Files\n" + "\n".join(
            f"- [`{fname}.py`](./{fname}.md) — {data['summary'][:120].rstrip()}"
            for fname, data in file_docs.items()
        )
    else:
        files_section = ""

    # Section sous-modules directs
    # Le lien doit être relatif : depuis docs/core/README.md → ./utils/README.md
    if child_modules:
        # Extraire uniquement le dernier segment pour le lien relatif
        sub_section = "### Sub-modules\n" + "\n".join(
            f"- [`{child.split('/')[-1]}/`](./{child.split('/')[-1]}/README.md) — {desc}"
            for child, desc in child_modules.items()
        )
    else:
        sub_section = ""

    content_block = "\n\n".join(filter(None, [files_section, sub_section]))

    prompt = f"""You are writing the index page for a Python module's documentation.

Module: `{module_name}`

Write a concise README.md in Markdown for this module.
It will serve as the entry point when a developer opens the `docs/{module_name}/` folder.

--- STYLE GUIDELINES ---
- Start with 2–4 sentences of prose describing what this module is responsible for. Be specific.
- Then reproduce the "Files" and "Sub-modules" sections below exactly as provided — do not rewrite them,
  just insert them after your prose overview. They already contain the correct Markdown links.
- Use backticks for module and file names.
- Do not add extra sections.

--- CONTENT TO INSERT AFTER YOUR OVERVIEW ---
{content_block}
"""
    return call_model(prompt, cfg)


def compose_root_index(modules_summary, root_files, cfg):
    """
    Génère le README.md racine de docs/.
    modules_summary : dict module_name → description courte  (modules de premier niveau)
    root_files      : dict filename → { summary }  (fichiers à la racine du repo, hors module)
    """
    modules_list = "\n".join(
        f"- [`{mod}/`](./{mod}/README.md) — {desc}"
        for mod, desc in modules_summary.items()
    )

    root_files_list = (
        "\n".join(
            f"- [`{fname}.py`](./{fname}.md) — {data['summary'][:120].rstrip()}"
            for fname, data in root_files.items()
        )
        if root_files
        else ""
    )

    root_files_section = (
        f"### Root-level files\n{root_files_list}" if root_files_list else ""
    )

    prompt = f"""You are writing the top-level documentation index for a software project.

Write a root README.md for the `docs/` folder. This is the first page a developer reads.

--- STYLE GUIDELINES ---
- Start with a short, specific project overview (3–4 sentences). No filler.
- Then reproduce the modules list and root files section below exactly as provided — do not rewrite the links.
- Close with one short paragraph explaining how the documentation is organized and how to navigate it.

--- MODULES ---
{modules_list}

{root_files_section}
"""
    return call_model(prompt, cfg)
