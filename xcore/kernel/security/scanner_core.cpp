/*
 * scanner_core.cpp — Extension C++ pour le scan AST des plugins xcore.
 *
 * Architecture :
 *   - ImportClassifier  : construit les sets forbidden/allowed une seule fois,
 *                         expose scan_file() et scan_directory() (multithread).
 *   - extract_imports() : tokeniseur léger ligne-à-ligne, évite un parse AST
 *                         complet pour les imports (95 % du travail du scan).
 *   - Bindings pybind11 : GIL relâché pendant le scan → parallélisme réel.
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <atomic>
#include <filesystem>
#include <fstream>
#include <regex>
#include <string>
#include <thread>
#include <unordered_set>
#include <vector>

namespace py = pybind11;
namespace fs = std::filesystem;

// ─────────────────────────────────────────────────────────────
// Structures
// ─────────────────────────────────────────────────────────────

struct RawImport {
    std::string module;
    int         lineno;
    bool        is_from;
    bool        is_relative; // from . import X  ou  from .. import X
};

struct FileResult {
    std::string              filepath;
    std::vector<std::string> errors;
    std::vector<std::string> warnings;
    bool                     passed = true;

    void add_error(const std::string& msg) {
        errors.push_back(msg);
        passed = false;
    }
    void add_warning(const std::string& msg) { warnings.push_back(msg); }
};

// ─────────────────────────────────────────────────────────────
// Extraction des imports  (tokeniseur léger, sans AST complet)
// ─────────────────────────────────────────────────────────────
//
// Couvre :
//   import os
//   import os.path
//   from os import path, getcwd
//   from os.path import join
//   from . import utils          (relatif pur)
//   from ..utils import helper   (relatif avec module)
//
// Multi-line `from X import (\n  a,\n  b\n)` : seul le module source
// (la partie `from X`) nous intéresse — il est toujours sur la 1re ligne.
// ─────────────────────────────────────────────────────────────

// Regexes pré-compilées avec le flag optimize (NFA compilé une fois)
static const std::regex RE_IMPORT{
    R"(^\s*import\s+([\w.]+)(?:\s|,|$))",
    std::regex::optimize | std::regex::ECMAScript
};
static const std::regex RE_FROM_ABS{
    R"(^\s*from\s+([\w.]+)\s+import)",
    std::regex::optimize | std::regex::ECMAScript
};
static const std::regex RE_FROM_REL{
    R"(^\s*from\s+(\.+)([\w.]*)\s+import)",
    std::regex::optimize | std::regex::ECMAScript
};

std::vector<RawImport> extract_imports(const std::string& source) {
    std::vector<RawImport> out;
    out.reserve(32);

    size_t pos = 0;
    int    lineno = 0;
    const  size_t len = source.size();

    while (pos < len) {
        size_t eol = source.find('\n', pos);
        if (eol == std::string::npos) eol = len;
        ++lineno;

        // Pré-filtre rapide : seuls 'i' et 'f' commencent un import
        size_t s = pos;
        while (s < eol && (source[s] == ' ' || source[s] == '\t')) ++s;

        if (s < eol && (source[s] == 'i' || source[s] == 'f')) {
            std::string line = source.substr(pos, eol - pos);
            std::smatch m;

            if (std::regex_search(line, m, RE_FROM_REL)) {
                // Import relatif → toujours local
                out.push_back({m[2].str(), lineno, true, true});
            } else if (std::regex_search(line, m, RE_FROM_ABS)) {
                out.push_back({m[1].str(), lineno, true, false});
            } else if (std::regex_search(line, m, RE_IMPORT)) {
                out.push_back({m[1].str(), lineno, false, false});
            }
        }

        pos = eol + 1;
    }

    return out;
}

// ─────────────────────────────────────────────────────────────
// Helper : racine d'un module  ("os.path" → "os")
// ─────────────────────────────────────────────────────────────

static inline std::string root_of(const std::string& module) {
    auto dot = module.find('.');
    return (dot == std::string::npos) ? module : module.substr(0, dot);
}

// ─────────────────────────────────────────────────────────────
// ImportClassifier
// ─────────────────────────────────────────────────────────────

class ImportClassifier {
public:
    /**
     * @param forbidden        Racines de modules interdits (ex: "os", "sys")
     * @param allowed_exact    Modules/racines autorisés en exact (ex: "json")
     * @param allowed_prefixes Préfixes wildcard sans le ".*" (ex: "xcore", "sqlalchemy")
     */
    ImportClassifier(
        std::unordered_set<std::string> forbidden,
        std::unordered_set<std::string> allowed_exact,
        std::vector<std::string>        allowed_prefixes
    )
        : forbidden_(std::move(forbidden))
        , allowed_exact_(std::move(allowed_exact))
        , allowed_prefixes_(std::move(allowed_prefixes))
    {}

    // ── Lookup O(1) ammorti ──────────────────────────────────

    bool is_forbidden(const std::string& module) const {
        return forbidden_.count(root_of(module)) > 0;
    }

    bool is_allowed(const std::string& module) const {
        if (allowed_exact_.count(module))         return true;
        if (allowed_exact_.count(root_of(module))) return true;
        for (const auto& prefix : allowed_prefixes_) {
            if (module == prefix) return true;
            if (module.size() > prefix.size() &&
                module[prefix.size()] == '.' &&
                module.compare(0, prefix.size(), prefix) == 0)
                return true;
        }
        return false;
    }

    // ── Scan d'un fichier ────────────────────────────────────

    FileResult scan_file(
        const std::string& filepath,
        const std::unordered_set<std::string>& local_modules
    ) const {
        FileResult result;
        result.filepath = filepath;

        std::ifstream f(filepath, std::ios::binary);
        if (!f) {
            result.add_error(filepath + ": impossible d'ouvrir le fichier");
            return result;
        }

        std::string source(
            (std::istreambuf_iterator<char>(f)),
             std::istreambuf_iterator<char>()
        );

        for (const auto& imp : extract_imports(source)) {
            if (imp.is_relative || imp.module.empty()) continue;

            // Module local → skip
            if (local_modules.count(root_of(imp.module)) ||
                local_modules.count(imp.module))
                continue;

            const std::string loc =
                filepath + ":" + std::to_string(imp.lineno) + ": ";

            if (is_forbidden(imp.module)) {
                result.add_error(loc + "import interdit — '" + imp.module + "'");
            } else if (!is_allowed(imp.module)) {
                result.add_warning(loc + "import non whitelisté — '" + imp.module + "'");
            }
        }

        return result;
    }

    // ── Scan d'un répertoire (multithread) ──────────────────

    std::vector<FileResult> scan_directory(
        const std::string& src_dir_str,
        const std::unordered_set<std::string>& local_modules,
        unsigned int num_threads = 0
    ) const {
        // Collecte des fichiers .py
        std::vector<fs::path> py_files;
        for (auto& entry : fs::recursive_directory_iterator(src_dir_str)) {
            if (entry.is_regular_file() && entry.path().extension() == ".py")
                py_files.push_back(entry.path());
        }

        const size_t n = py_files.size();
        if (n == 0) return {};

        if (num_threads == 0)
            num_threads = std::max(1u, std::thread::hardware_concurrency());
        num_threads = std::min(num_threads, static_cast<unsigned>(n));

        std::vector<FileResult> results(n);
        std::atomic<size_t>    idx{0};

        auto worker = [&] {
            size_t i;
            while ((i = idx.fetch_add(1, std::memory_order_relaxed)) < n)
                results[i] = scan_file(py_files[i].string(), local_modules);
        };

        std::vector<std::thread> threads;
        threads.reserve(num_threads);
        for (unsigned t = 0; t < num_threads; ++t)
            threads.emplace_back(worker);
        for (auto& t : threads)
            t.join();

        return results;
    }

private:
    std::unordered_set<std::string> forbidden_;
    std::unordered_set<std::string> allowed_exact_;
    std::vector<std::string>        allowed_prefixes_;
};

// ─────────────────────────────────────────────────────────────
// Bindings pybind11
// ─────────────────────────────────────────────────────────────

PYBIND11_MODULE(scanner_core, m) {
    m.doc() = "Scanner C++ pour plugins xcore — import classification multithread";

    py::class_<FileResult>(m, "FileResult")
        .def_readonly("filepath", &FileResult::filepath)
        .def_readonly("errors",   &FileResult::errors)
        .def_readonly("warnings", &FileResult::warnings)
        .def_readonly("passed",   &FileResult::passed)
        .def("__repr__", [](const FileResult& r) {
            return "<FileResult passed=" + std::string(r.passed ? "True" : "False") +
                   " errors=" + std::to_string(r.errors.size()) +
                   " warnings=" + std::to_string(r.warnings.size()) + ">";
        });

    py::class_<ImportClassifier>(m, "ImportClassifier")
        .def(py::init<
                std::unordered_set<std::string>,
                std::unordered_set<std::string>,
                std::vector<std::string>
             >(),
             py::arg("forbidden"),
             py::arg("allowed_exact"),
             py::arg("allowed_prefixes"),
             R"doc(
Construit le classificateur.

Parameters
----------
forbidden        : set de racines de modules interdits ("os", "sys", …)
allowed_exact    : set de modules/racines autorisés en exact ("json", "re", …)
allowed_prefixes : liste de préfixes sans ".*" ("xcore", "sqlalchemy", …)
             )doc"
        )
        .def("is_allowed",   &ImportClassifier::is_allowed,   py::arg("module"))
        .def("is_forbidden", &ImportClassifier::is_forbidden, py::arg("module"))
        .def("scan_file",
             &ImportClassifier::scan_file,
             py::arg("filepath"),
             py::arg("local_modules"),
             py::call_guard<py::gil_scoped_release>(),  // GIL relâché → I/O parallèle
             "Scanne un fichier .py et retourne un FileResult."
        )
        .def("scan_directory",
             &ImportClassifier::scan_directory,
             py::arg("src_dir"),
             py::arg("local_modules"),
             py::arg("num_threads") = 0u,
             py::call_guard<py::gil_scoped_release>(),  // GIL relâché → threads réels
             R"doc(
Scanne récursivement tous les .py d'un répertoire en parallèle.

num_threads=0 → hardware_concurrency() (auto).
             )doc"
        );
}
