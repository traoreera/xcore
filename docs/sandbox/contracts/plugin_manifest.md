# Plugin Manifest Parser and Validator

## Overview

This file, `plugin_manifest.py`, is responsible for parsing and validating XCore plugin manifests defined in YAML or JSON format. It generates a `PluginManifest` dataclass that represents a plugin’s configuration, which is essential for initializing plugins within the system's execution environments – Trusted, Sandboxed, or Legacy.

## Responsibilities

The primary responsibility of this file is to ensure that all XCore plugin manifests are correctly formatted and contain valid configurations. It handles parsing both YAML and JSON formats, performs necessary validation steps (like environment variable resolution), and ultimately constructs the `PluginManifest` dataclass for use by the XCore system. This ensures consistent and reliable plugin initialization across different environments.

## Key Components

*   **`load_manifest(manifest_path)`:**  This is the core function responsible for parsing the manifest file (YAML or JSON). It uses `pyyaml` and `json` libraries to handle the parsing process. Critically, it resolves environment variables referenced within the manifest using regular expressions, ensuring that plugin configurations are dynamically adaptable.
*   **`PluginManifest` Dataclass:** This dataclass is the central representation of a plugin's configuration. It encapsulates all relevant information, including execution mode (defined via an `ExecutionMode` enum), resource limits, filesystem access controls, and rate limiting settings. The dataclass provides a structured way to manage and access these parameters.
*   **`ExecutionMode` Enum:** This enum defines the different execution modes for plugins – Trusted, Sandboxed, or Legacy.  This allows the system to tailor the plugin's environment based on its intended use case and security requirements.

## Dependencies

*   **`pyyaml`:** Used for parsing YAML manifest files. The `pyyaml` library provides a robust and efficient way to handle YAML data structures within Python.
*   **`json`:**  Used for parsing JSON manifest files. This dependency ensures that the system can support both popular configuration formats.
*   **`dotenv` (Optional):** Used for loading environment variables from `.env` files, allowing plugins to dynamically adapt their configurations based on external settings.

## How It Fits In

The `plugin_manifest.py` file is called during the plugin initialization process. Specifically, the `load_manifest()` function is invoked with the path to the plugin's manifest file. The resulting `PluginManifest` dataclass is then used by the XCore system to configure the plugin’s execution environment – setting up resource limits, filesystem access controls, and rate limiting configurations based on the manifest data. This ensures that plugins are initialized correctly and securely within their designated environments.

---

**Notes & Considerations:**

*   I've aimed for a concise and technical tone suitable for a developer joining the project.
*   The sections are structured to provide a clear understanding of the file’s purpose, functionality, and relationships within the XCore system.
*   I've used backticks for code references (e.g., `pyyaml`) and enums (`ExecutionMode`).
*   I've kept paragraphs short and focused on specific points.

To help me refine this docume
```

---
ntation further, could you tell me:

*   What is the overall architecture of XCore?  (A brief overview would be helpful.)
*   Are there any specific security considerations related to plugin manifests that I should highlight?
*   Is there a preferred style for documenting enums (e.g., using a more descriptive name)?