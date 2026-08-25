# Health & Services

Monitoring the status of your `xcore` ecosystem is vital for maintaining a healthy production environment.

## Global Health Check

The `health` command performs an exhaustive check of all configured services and components.

```bash title="Check Everything"
xcli health
```

This command validates:
- **Connectivity**: Database and Redis connections.
- **Plugins**: Integrity and loading status.
- **Worker**: Celery/XWorker availability.
- **Environment**: Python version and required dependencies.

!!! danger "Service Failures"
    If any critical service is down, `xcli health` will return a non-zero exit code, making it suitable for CI/CD health gates.

## Service Status

For a more focused view of system services, use the `services` command.

```bash title="Service Overview"
xcli services
```

### Features:
- **Real-time Status**: Shows which services are `UP`, `DOWN`, or `DEGRADED`.
- **Resource Usage**: Brief overview of memory/CPU used by each service.
- **Rich Table**: Displays information in a beautiful, easy-to-read table format.

!!! tip "Service Management"
    Individual services can be managed via the `manager services` command group. See [Service Management](../manager/services.md) for more details.

## Troubleshooting

If `health` reports errors:
1. Check the logs: `make logs`
2. Check your marketplace credentials aren't the issue: `xcli config show`
   (there's no dedicated `integration.yaml` validator — it's checked
   automatically whenever `xcli manager start` reads it)
3. Restart services: `make restart`
