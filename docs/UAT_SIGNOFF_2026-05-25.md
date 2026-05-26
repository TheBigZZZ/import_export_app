# UAT Checklist and Sign-off Report

Date: 2026-05-25
Project: TradeDesk ERP
Environment: Windows (local workspace)

## Scope

This report covers:

- Integration test implementation and execution
- Production config hardening and startup safety checks
- Packaging and installer verification

## Verification Checklist

1. Integration tests for operational flows

- Status: PASS
- Evidence: `pytest -q tests/test_integration_api.py`
- Result: `3 passed`

1. Full automated test suite

- Status: PASS
- Evidence: `pytest -q`
- Result: `13 passed, 2 warnings`

1. Startup hardening checks implemented

- Status: PASS
- Evidence:
  - Static production checks added for debug mode, JWT secret, and bcrypt rounds
  - Schema readiness check added for required tables at startup
  - Unit tests added in `tests/test_services.py`

1. PyInstaller packaging build

- Status: PASS
- Evidence: `powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1`
- Result: Build complete, output in `dist/TradeDeskERP`

1. Packaged executable smoke launch

- Status: NEEDS MANUAL CONFIRMATION
- Evidence: `dist\TradeDeskERP\TradeDeskERP.exe` executed and returned to prompt immediately
- Note: No CLI error was emitted; GUI behavior must be confirmed interactively on the target machine.

1. Installer compiler availability (Inno Setup)

- Status: FAIL
- Evidence: `Get-Command iscc`
- Result: `CommandNotFoundException` because Inno Setup compiler is not installed in this environment

1. Installer package build (`TradeDeskERP-Setup.exe`)

- Status: BLOCKED
- Blocker: `iscc` is unavailable in this environment

## Sign-off Decision

Decision: CONDITIONAL - NOT FULLY SIGNED OFF

Reason:

- Core code and tests are in good shape.
- Packaging build passes.
- Installer verification is blocked by a missing Inno Setup compiler.
- Packaged executable runtime UX requires manual GUI confirmation on the target machine.

## Required Actions Before Final Production Sign-off

1. Install Inno Setup and run the installer build using `packaging/TradeDeskERP.iss`.
2. Perform clean-machine install, uninstall, and upgrade tests.
3. Execute manual GUI smoke/UAT from the installed package and capture evidence.
4. Re-issue the final sign-off report with installer test results included.
