from __future__ import annotations

import asyncio

from PySide6.QtWidgets import QCheckBox, QFormLayout, QGroupBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ..error_messages import friendly_exception_message, friendly_http_error
from ..widgets.data_table import DataTable
from .base import BaseModuleWidget


class SettingsModule(BaseModuleWidget):
    module_title = "Settings"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        self.backups_table = DataTable()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(12)
        scroll.setWidget(content)

        layout = self.layout()
        layout.setSpacing(8)
        layout.addWidget(scroll)

        company_box = QGroupBox("Company Settings")
        form = QFormLayout(company_box)
        form.setVerticalSpacing(10)
        self.company_name = QLineEdit()
        self.company_address = QLineEdit()
        self.company_phone = QLineEdit()
        self.company_email = QLineEdit()
        self.allow_negative_stock = QCheckBox("Allow negative stock")

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        load_btn = QPushButton("Load Settings")
        load_btn.clicked.connect(self.load_settings)
        row_actions = QHBoxLayout()
        row_actions.addWidget(load_btn)
        row_actions.addWidget(save_btn)

        form.addRow("Company Name", self.company_name)
        form.addRow("Address", self.company_address)
        form.addRow("Phone", self.company_phone)
        form.addRow("Email", self.company_email)
        form.addRow("", self.allow_negative_stock)
        form.addRow("", row_actions)
        self.configure_form_layout(form, label_width=180)

        # SMTP / Email settings
        email_box = QGroupBox("Email / SMTP")
        email_form = QFormLayout(email_box)
        self.smtp_host = QLineEdit()
        self.smtp_port = QLineEdit()
        self.smtp_user = QLineEdit()
        self.smtp_password = QLineEdit()
        self.smtp_password.setPlaceholderText("Stored securely in app settings file")
        self.notify_from = QLineEdit()
        self.notify_to = QLineEdit()
        test_email_btn = QPushButton("Send Test Email")
        test_email_btn.clicked.connect(self.send_test_email)
        email_form.addRow("SMTP Host", self.smtp_host)
        email_form.addRow("SMTP Port", self.smtp_port)
        email_form.addRow("SMTP User", self.smtp_user)
        email_form.addRow("SMTP Password", self.smtp_password)
        email_form.addRow("From Address", self.notify_from)
        email_form.addRow("To Address (for test)", self.notify_to)
        email_form.addRow("", test_email_btn)
        self.configure_form_layout(email_form, label_width=180)

        backup_box = QGroupBox("Backups")
        backup_layout = QFormLayout(backup_box)
        self.restore_file_name = QLineEdit()
        self.restore_file_name.setPlaceholderText("Paste backup file name from table")
        create_backup_btn = QPushButton("Create Backup")
        create_backup_btn.clicked.connect(self.create_backup)
        restore_backup_btn = QPushButton("Restore Backup")
        restore_backup_btn.clicked.connect(self.restore_backup)
        refresh_backups_btn = QPushButton("Reload Backup List")
        refresh_backups_btn.clicked.connect(self.load_backups)
        backup_actions = QHBoxLayout()
        backup_actions.addWidget(create_backup_btn)
        backup_actions.addWidget(restore_backup_btn)
        backup_actions.addWidget(refresh_backups_btn)
        backup_layout.addRow("Restore File", self.restore_file_name)
        backup_layout.addRow("", backup_actions)
        self.configure_form_layout(backup_layout, label_width=150)

        # Exchange rates section
        rates_box = QGroupBox("Exchange Rates")
        rates_layout = QFormLayout(rates_box)
        rates_layout.setVerticalSpacing(10)
        self.rate_from = QLineEdit()
        self.rate_to = QLineEdit()
        self.rate_value = QLineEdit()
        self.rate_effective = QLineEdit()
        self.sync_interval_input = QLineEdit()
        self.sync_interval_input.setPlaceholderText('Minutes')
        self.auto_sync_checkbox = QCheckBox("Enable auto-sync exchange rates")
        create_rate_btn = QPushButton("Create Rate")
        create_rate_btn.clicked.connect(self.create_rate)
        load_rates_btn = QPushButton("Load Rates")
        load_rates_btn.clicked.connect(self.load_rates)
        rates_layout.addRow("From (USD)", self.rate_from)
        rates_layout.addRow("To (BDT)", self.rate_to)
        rates_layout.addRow("", self.auto_sync_checkbox)
        rates_layout.addRow("Rate", self.rate_value)
        rates_layout.addRow("Effective (YYYY-MM-DD)", self.rate_effective)
        rates_layout.addRow("Sync Interval (min)", self.sync_interval_input)
        rowh = QHBoxLayout()
        rowh.addWidget(load_rates_btn)
        rowh.addWidget(create_rate_btn)
        rates_layout.addRow("", rowh)
        self.configure_form_layout(rates_layout, label_width=190)

        self.rates_table = DataTable()

        # SMS test
        sms_box = QGroupBox("SMS / Notifications")
        sms_form = QFormLayout(sms_box)
        self.sms_to = QLineEdit()
        self.sms_message = QLineEdit()
        self.sms_message.setText("Test SMS from TradeDesk")
        sms_test_btn = QPushButton("Send Test SMS")
        sms_test_btn.clicked.connect(self.send_test_sms)
        sms_form.addRow("To Number", self.sms_to)
        sms_form.addRow("Message", self.sms_message)
        sms_form.addRow("", sms_test_btn)
        self.configure_form_layout(sms_form, label_width=130)
        content_layout.addWidget(sms_box)

        top_grid = QGridLayout()
        top_grid.setHorizontalSpacing(12)
        top_grid.setVerticalSpacing(12)
        top_grid.addWidget(company_box, 0, 0)
        top_grid.addWidget(email_box, 0, 1)
        top_grid.addWidget(backup_box, 1, 0)
        top_grid.addWidget(rates_box, 1, 1)
        top_grid.addWidget(QLabel("Available Backups"), 2, 0, 1, 2)
        top_grid.addWidget(self.backups_table, 3, 0, 1, 2)

        content_layout.insertLayout(0, top_grid)
        content_layout.addWidget(self.rates_table)

    def refresh(self) -> None:
        self.load_settings()
        self.load_backups()

    def load_settings(self) -> None:
        try:
            response = asyncio.run(self.api_client.get("/api/settings"))
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Settings", friendly_exception_message(exc, "Load settings"))
            return

        self.company_name.setText(data.get("company_name") or "")
        self.company_address.setText(data.get("company_address") or "")
        self.company_phone.setText(data.get("company_phone") or "")
        self.company_email.setText(data.get("company_email") or "")
        self.allow_negative_stock.setChecked(bool(data.get("allow_negative_stock")))
        # SMTP fields
        self.smtp_host.setText(data.get("diagnostics_smtp_host") or "")
        self.smtp_port.setText(str(data.get("diagnostics_smtp_port") or ""))
        self.smtp_user.setText(data.get("diagnostics_smtp_user") or "")
        # Do not expose the SMTP password; show whether it's configured
        if data.get("diagnostics_smtp_password_set"):
            self.smtp_password.setText("")
            self.smtp_password.setPlaceholderText("Configured (leave blank to keep existing)")
        else:
            self.smtp_password.setText("")
            self.smtp_password.setPlaceholderText("Enter SMTP password")
        self.notify_from.setText(data.get("diagnostics_notify_email_from") or "")
        self.notify_to.setText(data.get("diagnostics_notify_email_to") or "")
        # exchange-rate auto-sync
        self.auto_sync_checkbox.setChecked(bool(data.get('exchange_rate_auto_sync', False)))
        self.sync_interval_input.setText(str(data.get('exchange_rate_sync_interval_minutes') or ''))

    def save_settings(self) -> None:
        payload = {
            "company_name": self.company_name.text().strip(),
            "company_address": self.company_address.text().strip() or None,
            "company_phone": self.company_phone.text().strip() or None,
            "company_email": self.company_email.text().strip() or None,
            "allow_negative_stock": self.allow_negative_stock.isChecked(),
            # SMTP
            "diagnostics_smtp_host": self.smtp_host.text().strip() or None,
            "diagnostics_smtp_port": int(self.smtp_port.text().strip()) if self.smtp_port.text().strip() else None,
            "diagnostics_smtp_user": self.smtp_user.text().strip() or None,
            "diagnostics_smtp_password": self.smtp_password.text() or None,
            "diagnostics_notify_email_from": self.notify_from.text().strip() or None,
            "diagnostics_notify_email_to": self.notify_to.text().strip() or None,
            "exchange_rate_auto_sync": bool(self.auto_sync_checkbox.isChecked()),
            "exchange_rate_sync_interval_minutes": int(self.sync_interval_input.text().strip()) if self.sync_interval_input.text().strip().isdigit() else None,
        }
        try:
            response = asyncio.run(self.api_client.put("/api/settings", json=payload))
            response.raise_for_status()
        except Exception as exc:
            QMessageBox.warning(self, "Settings", friendly_exception_message(exc, "Save settings"))
            return
        QMessageBox.information(self, "Settings", "Settings saved")

    def send_test_email(self) -> None:
        to = self.notify_to.text().strip()
        if not to:
            QMessageBox.warning(self, "Test Email", "Enter a recipient email in 'To Address'")
            return
        payload = {"to": to, "subject": "Test Email from TradeDesk", "body": "This is a test email from your TradeDesk instance."}
        try:
            response = asyncio.run(self.api_client.post("/api/settings/email/test", json=payload))
            if response.status_code == 200:
                QMessageBox.information(self, "Test Email", "Test email sent (or queued)")
            else:
                QMessageBox.warning(self, "Test Email", friendly_http_error(response, "Send test email"))
        except Exception as exc:
            QMessageBox.warning(self, "Test Email", friendly_exception_message(exc, "Send test email"))

    def load_backups(self) -> None:
        try:
            response = asyncio.run(self.api_client.get("/api/settings/backups"))
            response.raise_for_status()
            rows = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Backups", friendly_exception_message(exc, "Load backups"))
            return

        table_rows = [
            [item["file_name"], item["created_at"], str(item["size_bytes"]), item["file_path"]]
            for item in rows
        ]
        self.backups_table.set_rows(["File", "Created", "Size", "Path"], table_rows, stretch_columns={3})

    def load_rates(self) -> None:
        try:
            response = asyncio.run(self.api_client.get('/api/exchange-rates'))
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, 'Exchange Rates', friendly_exception_message(exc, 'Load exchange rates'))
            return

        rows = [[str(item.get('id') or ''), item.get('currency_from'), item.get('currency_to'), str(item.get('rate')), item.get('effective_date')] for item in data]
        self.rates_table.set_rows(["ID", "From", "To", "Rate", "Effective"], rows, stretch_columns={4})

    def create_rate(self) -> None:
        frm = self.rate_from.text().strip()
        to = self.rate_to.text().strip()
        rate = self.rate_value.text().strip()
        eff = self.rate_effective.text().strip() or None
        if not frm or not to or not rate:
            QMessageBox.warning(self, 'Create Rate', 'Enter currency from/to and rate')
            return
        try:
            payload = {'currency_from': frm, 'currency_to': to, 'rate': float(rate)}
            if eff:
                payload['effective_date'] = eff
            response = asyncio.run(self.api_client.post('/api/exchange-rates', json=payload))
            if response.status_code in (200, 201):
                QMessageBox.information(self, 'Exchange Rates', 'Rate created')
                self.load_rates()
            else:
                QMessageBox.warning(self, 'Exchange Rates', friendly_http_error(response, 'Create exchange rate'))
        except Exception as exc:
            QMessageBox.warning(self, 'Exchange Rates', friendly_exception_message(exc, 'Create exchange rate'))

    def create_backup(self) -> None:
        try:
            response = asyncio.run(self.api_client.post("/api/settings/backups", json={}))
            response.raise_for_status()
        except Exception as exc:
            QMessageBox.warning(self, "Backups", friendly_exception_message(exc, "Create backup"))
            return
        QMessageBox.information(self, "Backups", "Backup created")
        self.load_backups()

    def send_test_sms(self) -> None:
        to = self.sms_to.text().strip()
        msg = self.sms_message.text().strip()
        if not to:
            QMessageBox.warning(self, 'Test SMS', 'Enter a destination number')
            return
        try:
            response = asyncio.run(self.api_client.post('/api/settings/sms/test', json={'to': to, 'message': msg}))
            if response.status_code == 200 and response.json().get('ok'):
                QMessageBox.information(self, 'Test SMS', 'SMS sent (or logged)')
            else:
                QMessageBox.warning(self, 'Test SMS', friendly_http_error(response, 'Send test SMS'))
        except Exception as exc:
            QMessageBox.warning(self, 'Test SMS', friendly_exception_message(exc, 'Send test SMS'))

    def restore_backup(self) -> None:
        file_name = self.restore_file_name.text().strip()
        if not file_name:
            QMessageBox.warning(self, "Restore", "Enter a backup file name")
            return

        try:
            response = asyncio.run(self.api_client.post("/api/settings/backups/restore", json={"file_name": file_name}))
            response.raise_for_status()
        except Exception as exc:
            QMessageBox.warning(self, "Restore", friendly_exception_message(exc, "Restore backup"))
            return
        QMessageBox.information(self, "Restore", "Backup restored. Restart app if data view is stale.")