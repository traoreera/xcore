# XCore Production-Ready Examples

This directory contains complete examples of how to build real-world applications using XCore.

## 🔑 Auth Example (`/examples/auth`)
A production-grade authentication plugin.
- JWT token generation and verification.
- Password hashing integration.
- Service usage: `db` for user storage.

## 📅 Task Manager (`/examples/tasks`)
Demonstrates the integration with the XCore Scheduler.
- Dynamic task scheduling (one-off and recurring).
- Service usage: `scheduler`.

## 🤖 Sandboxed Chatbot (`/examples/chatbot`)
Shows how to run untrusted code securely.
- Isolated process execution.
- Filesystem restrictions.
- IPC communication.

## 🚀 How to Run Examples

1. Copy the example plugin to your `plugins/` directory.
2. Ensure dependencies are installed (e.g., `python-jose` for Auth).
3. Start XCore using `xcore plugin load <name>`.
4. Test using the CLI:
   ```bash
   xcore plugin call auth login '{"username": "admin", "password": "password"}'
   ```
