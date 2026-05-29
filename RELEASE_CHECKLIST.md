# Release checklist

- [ ] Bump version and tag (e.g., `v1.0.0`)
- [ ] Run local build and smoke test: `./scripts/build_windows.ps1` and `./scripts/smoke_test.ps1 -ExePath .\dist\TradeDeskERP\TradeDeskERP.exe -Timeout 180`
- [ ] Run `scripts/post_install_wizard.py` to set secrets locally
- [ ] Verify `/health` endpoint and sample UI flows
- [ ] Verify logs in `TRADEDESK_LOGS_DIR` and backups in `TRADEDESK_BACKUP_DIR`
- [ ] Run `scripts/check_secrets.py` to validate environment before release
- [ ] Create and verify a backup: `python scripts/backup_verify.py --backup-dir ./test_backups`
- [ ] Prepare release locally: `python scripts/release_helper.py --tag vX.Y.Z` (build + smoke)
- [ ] Update `CHANGELOG.md` and release notes
- [ ] Push tag and wait for GitHub Actions to build and verify assets
- [ ] Download release assets and test the unsigned installer and exe on a clean Windows VM if you choose to do manual verification later
- [ ] Share release link with tester(s)
