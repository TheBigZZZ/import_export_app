from tradedesk.backend import config
from tradedesk.backend.backup import backup_db, restore_db


def test_backup_and_restore(tmp_path):
    # Arrange: point settings.data_dir to tmp_path
    config.settings.data_dir = tmp_path
    db_path = config.settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # create a fake db file
    db_path.write_text("original-db-content")

    # Act: create backup
    backup_dir = tmp_path / "backups"
    backup_path = backup_db(destination_dir=backup_dir)
    assert backup_path.exists()

    # Modify original db
    db_path.write_text("modified-content")

    # Restore from backup
    restored = restore_db(backup_path)
    assert restored.exists()
    assert restored.read_text() == "original-db-content"
