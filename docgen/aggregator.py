from collections import defaultdict
from summarizer import summarize_chunk, call_model

def summarize_by_file(chunks, cfg):
    """
    Groupe les chunks par fichier (path) et génère un résumé par chunk.
    Retourne un dict : path -> liste de résumés partiels + métadonnées du fichier.
    """
    file_map = defaultdict(lambda: {"summaries": [], "module": None, "filename": None})

    for chunk in chunks:
        path     = chunk["path"]
        summary  = summarize_chunk(path, chunk["content"], cfg)
        file_map[path]["summaries"].append(summary)
        file_map[path]["module"]   = chunk["module"]
        file_map[path]["filename"] = chunk["filename"]

    return file_map

def aggregate_file_summaries(file_map, cfg):
    """
    Fusionne les résumés partiels de chaque fichier en un résumé unique.
    Retourne un dict : path -> { summary, module, filename }
    """
    if not file_map:
        raise ValueError("No file summaries to aggregate.")

    aggregated = {}

    for path, data in file_map.items():
        summaries = data["summaries"]
        combined  = "\n".join(summaries)

        if len(summaries) == 1:
            # Pas besoin de fusion si un seul chunk
            final_summary = summaries[0]
        else:
            final_prompt = f"""You are writing technical documentation for a software project.

The following are partial summaries of different chunks of the same source file: `{path}`.
Merge them into a single, unified technical summary as if the file had been read in full.

Rules:
- Write in plain, direct prose. No bullet lists.
- Eliminate any redundancy between the partial summaries.
- Keep only information that is accurate and relevant to understanding this file's role.
- Maximum length: 150 words.
- Do not mention that this is a merge of multiple summaries.

--- PARTIAL SUMMARIES ---

{combined}
"""
            final_summary = call_model(final_prompt, cfg)

        aggregated[path] = {
            "summary":  final_summary,
            "module":   data["module"],
            "filename": data["filename"],
        }

    return aggregated