# Release checklist

- [ ] Bump version and tag (e.g., `v1.0.0`)
- [ ] Run local build and smoke test: `./packaging/build_exe.ps1` and run `dist\launcher.exe`
- [ ] Run `scripts/post_install_wizard.py` to set secrets locally
- [ ] Verify `/health` endpoint and sample UI flows
- [ ] Verify logs in `TRADEDESK_LOGS_DIR` and backups in `TRADEDESK_BACKUP_DIR`
- [ ] Update `CHANGELOG.md` and release notes
- [ ] Push tag and wait for GitHub Actions to build
- [ ] Download release assets and test installer on a clean Windows VM
- [ ] Share release link with tester(s)
