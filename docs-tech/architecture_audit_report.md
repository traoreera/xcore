# XCore Architectural Audit Report

## 1. Executive Summary
XCore is a modular framework for managing plugins with isolation and dependency injection. This audit identifies several areas for improvement to enhance scalability, maintainability, and extensibility. Key findings include hardcoded service providers, imperative plugin orchestration, and limited middleware introspection.

## 2. Layer Analysis

### Core Kernel (`xcore.kernel`)
- **PluginSupervisor:** Acts as a central orchestrator but suffers from "God Object" tendencies. It manually manages permissions, rate limits, and plugin loading in its `boot()` method, making it difficult to extend without modification.
- **Middleware System:** Robust but lacks introspection. It's difficult to know which middlewares are active at runtime.

### Plugins & Registry (`xcore.registry`)
- **PluginRegistry:** Centralizes plugin metadata and exported services. While it supports basic scoping (public/private), it lacks a "protected" scope for core services, making them vulnerable to accidental overwrites by plugins.

### Services Layer (`xcore.services`)
- **ServiceContainer:** Uses a hardcoded `DEFAULT_PROVIDERS` list. This violates the Open/Closed Principle as adding a new core service requires modifying the framework itself.

### Sandbox (`xcore.kernel.sandbox`)
- Strong isolation via `FilesystemGuard` and AST scanning. The IPC mechanism for sandboxed services is a potential area for further unification.

## 3. Coupling Points & Friction
- **Manual Orchestration:** The `PluginSupervisor.boot()` method's imperative nature couples plugin loading with security and rate-limiting configuration.
- **Hardcoded Providers:** The dependency on `DEFAULT_PROVIDERS` in `ServiceContainer` prevents external packages from contributing core-level services easily.

## 4. Technical Debt Risks
- **Extensibility Ceiling:** As the number of cross-cutting concerns (logging, metrics, etc.) grows, `PluginSupervisor` will become increasingly complex.
- **Service Collision:** Without a protected scope, a malicious or buggy plugin could attempt to override critical core services like `db` or `cache`.

## 5. Proposed Design Improvements

### A. Dynamic Service Providers
Refactor `ServiceContainer` to support a registry of providers instead of a hardcoded list.

### B. Protected Service Scope
Introduce a `protected` scope in `PluginRegistry` to safeguard core services.

### C. Event-Driven Lifecycle
Transition `PluginSupervisor` to reactively configure plugins by listening to `plugin.loaded` events, decoupling loading from configuration.

### D. Middleware Introspection
Add methods to inspect the active middleware pipeline for better observability.
