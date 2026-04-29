import os
from collections import defaultdict

from aggregator import aggregate_file_summaries, summarize_by_file
from composer import compose_file_doc, compose_module_index, compose_root_index
from scanner import scan_repo
from summarizer import load_config


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[WRITTEN] {path}")


def get_all_ancestor_modules(module):
    """
    Retourne tous les niveaux intermédiaires d'un module.
    Exemple : "core/utils/parsers" → ["core", "core/utils", "core/utils/parsers"]
    """
    parts = module.split("/")
    return ["/".join(parts[: i + 1]) for i in range(len(parts))]


def main():
    cfg = load_config()
    docs_root = cfg["project"]["docs_dir"]  # ex: "docs"

    # 1. Scanner le repo
    chunks = scan_repo(cfg)
    if not chunks:
        print(
            "No files found to process. Check repo_path and include_extensions in config."
        )
        return

    # 2. Résumer chaque fichier (avec cache)
    file_map = summarize_by_file(chunks, cfg)
    file_summaries = aggregate_file_summaries(file_map, cfg)

    # 3. Générer une doc .md par fichier source
    #    Structure : docs/<module/sous_module>/<fichier>.md
    #
    # On construit aussi deux index :
    #   - modules_files  : module_path → { filename → { summary, doc_path } }
    #   - modules_children : module_path → set de sous-modules directs
    #     (pour les README des niveaux intermédiaires)

    modules_files = defaultdict(dict)  # module -> fichiers directs
    modules_children = defaultdict(set)  # module -> sous-modules directs
    root_files = {}  # fichiers à la racine du repo

    for path, data in file_summaries.items():
        module = data["module"]  # ex: "core/utils" | None
        filename = data["filename"]  # ex: "scanner"
        summary = data["summary"]

        # Calcul du chemin de sortie
        if module:
            doc_path = os.path.join(docs_root, module, f"{filename}.md")
        else:
            doc_path = os.path.join(docs_root, f"{filename}.md")

        # Génération de la doc du fichier
        print(f"[COMPOSING] {doc_path}")
        doc_content = compose_file_doc(path, filename, summary, cfg)
        write_file(doc_path, doc_content)

        if module:
            # Enregistrer le fichier dans son module direct
            modules_files[module][filename] = {
                "summary": summary,
                "doc_path": doc_path,
            }
            # Enregistrer tous les liens parent → enfant pour les niveaux intermédiaires
            # ex: "core/utils" → enregistre core→core/utils et core/utils (feuille)
            ancestors = get_all_ancestor_modules(module)
            for i in range(len(ancestors) - 1):
                parent = ancestors[i]
                child = ancestors[i + 1]
                modules_children[parent].add(child)
        else:
            root_files[filename] = {
                "summary": summary,
                "doc_path": doc_path,
            }

    # 4. Générer un README.md pour chaque module (tous niveaux confondus)
    #    On traite du plus profond au plus haut pour que les descriptions
    #    des sous-modules soient disponibles quand on génère les parents.
    #
    #    all_modules = union de tous les modules qui ont des fichiers directs
    #                  + tous les modules intermédiaires (qui n'ont que des enfants)
    all_modules = set(modules_files.keys()) | set(modules_children.keys())

    # Trier du plus profond (plus de "/" dans le chemin) au plus haut
    sorted_modules = sorted(all_modules, key=lambda m: m.count("/"), reverse=True)

    # Stocker une description courte par module (pour les index parents)
    module_descriptions = {}

    for module in sorted_modules:
        index_path = os.path.join(docs_root, module, "README.md")
        print(f"[MODULE INDEX] {index_path}")

        # Fichiers directs dans ce module
        direct_files = modules_files.get(module, {})

        # Sous-modules directs (enfants immédiats seulement)
        direct_children = sorted(modules_children.get(module, set()))
        child_descriptions = {
            child: module_descriptions.get(child, "") for child in direct_children
        }

        index_content = compose_module_index(
            module_name=module,
            file_docs=direct_files,
            child_modules=child_descriptions,
            cfg=cfg,
        )
        write_file(index_path, index_content)

        # Résumé court pour le niveau parent
        if direct_files:
            first_summary = next(iter(direct_files.values()))["summary"]
        elif child_descriptions:
            first_summary = next(iter(child_descriptions.values()))
        else:
            first_summary = ""
        module_descriptions[module] = first_summary[:120].rstrip() + "..."

    # 5. Générer le README.md racine de docs/
    #    Liste uniquement les modules de premier niveau (sans "/" dans le chemin)
    top_level_modules = {
        mod: module_descriptions[mod] for mod in sorted(all_modules) if "/" not in mod
    }

    root_index_path = os.path.join(docs_root, "README.md")
    print(f"[ROOT INDEX] {root_index_path}")
    root_index = compose_root_index(
        modules_summary=top_level_modules,
        root_files=root_files,
        cfg=cfg,
    )
    write_file(root_index_path, root_index)

    print("\nDocumentation generated successfully.")
    print(f"Output: {docs_root}/")


if __name__ == "__main__":
    main()
