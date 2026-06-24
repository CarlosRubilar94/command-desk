# Gateway Windows Recovery

## Symptoms

- Restart Gateway fails with `UnicodeDecodeError` on subprocess output.
- Restart logs show interrupted update/install recovery failures.
- Restart hangs waiting for `Install it now so the gateway starts on login? [Y/n]:`.
- `taskkill` errors appear even when the process is already gone.
- Dashboard reports that the gateway service is not installed.

## Safe recovery

1. Run **Repair Install** from the dashboard.
2. Run **Install Gateway Service**.
3. Run **Restart Gateway**.
4. If restart still fails, copy diagnostics from the recovery card and inspect logs.

## Repair Install

The dashboard `POST /api/system/repair-install` flow runs these non-interactive commands with the active Python runtime:

1. `python -m ensurepip --upgrade`
2. `python -m pip install --upgrade pip setuptools wheel`
3. `python -m pip install -e .`
4. `python -m pip install -e ".[all]"`

If step 4 fails, Hermes retries optional extras individually and returns
`degraded_optional_extras_failed` instead of blocking gateway restart.

## Install Gateway Service

Use dashboard action **Install Gateway Service** (API: `POST /api/gateway/install-service`).

This action is separate from restart to avoid interactive prompts during restart.

## Restart Gateway

Use dashboard action **Restart Gateway** (API: `POST /api/gateway/restart`).

If the service is missing, restart returns a structured response:

```json
{
  "status": "needs_service_install",
  "message": "Gateway service is not installed.",
  "action": "install_gateway_service"
}
```

## Manual commands

Use this exact Python 3.12 executable on Windows:

- `& "C:\Users\Vinicius\AppData\Local\Programs\Python\Python312\python.exe" -m ensurepip --upgrade`
- `& "C:\Users\Vinicius\AppData\Local\Programs\Python\Python312\python.exe" -m pip install --upgrade pip setuptools wheel`
- `& "C:\Users\Vinicius\AppData\Local\Programs\Python\Python312\python.exe" -m pip install -e .`
- `& "C:\Users\Vinicius\AppData\Local\Programs\Python\Python312\python.exe" -m pip install -e ".[all]"`

## Troubleshooting

- If repair returns `degraded_optional_extras_failed`, base runtime is usable; inspect failed extras and continue with service install/restart.
- If install service does not complete, re-run from an elevated shell.
- If restart still fails, collect diagnostics from the dashboard recovery card.
- If a PID kill fails but the PID no longer exists, treat it as an already-exited process and retry restart.
