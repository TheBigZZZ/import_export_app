# Deployment & GitHub publishing

This document explains how to publish a release of TradeDesk and what repository secrets are needed.

1) Pre-release checks (local)
   - Run `./packaging/build_exe.ps1` locally and verify `dist\launcher.exe` runs.
   - Run `scripts/post_install_wizard.py` to set SMTP/Twilio secrets locally.
   - Verify `http://127.0.0.1:8742/health` returns 200.

2) Tag and push
   - Create a tag: `git tag -a v1.0.0 -m "Release v1.0.0"`
   - Push: `git push origin --tags`

3) GitHub Actions
   - The workflow `.github/workflows/publish-windows.yml` will build the EXE and create a Release.
   - The workflow will also run a smoke test and build an NSIS installer.

4) Repository secrets (optional)
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` — if CI needs to send email in integration tests.
   - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` — for SMS integration tests.
   - `PERSONAL_ACCESS_TOKEN` — only if you need extra GitHub scopes beyond `GITHUB_TOKEN`.
   - `CODESIGN_CERT`, `CODESIGN_PASSWORD` — base64 certificate and password to code-sign the EXE in CI if desired.

5) Post-release
   - Download the release assets and verify on a clean Windows VM before sharing with others.
