"""phase1 foundation schema

Revision ID: 20260524_0001
Revises:
Create Date: 2026-05-24 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260524_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False, unique=True),
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "chart_of_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_code", sa.String(length=50), nullable=False),
        sa.Column("account_name", sa.String(length=200), nullable=False),
        sa.Column("account_type", sa.Enum("asset", "liability", "equity", "income", "expense", name="accounttype"), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bank_name", sa.String(length=150), nullable=False),
        sa.Column("account_name", sa.String(length=150), nullable=False),
        sa.Column("account_number", sa.String(length=100), nullable=False),
        sa.Column("branch_name", sa.String(length=100), nullable=True),
        sa.Column("swift_code", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="BDT"),
        sa.Column("opening_balance", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("current_balance", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("customer_code", sa.String(length=50), nullable=False, unique=True),
        sa.Column("customer_name", sa.String(length=200), nullable=False),
        sa.Column("contact_person", sa.String(length=150), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("bin_no", sa.String(length=50), nullable=True),
        sa.Column("credit_limit", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("opening_balance", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("current_balance", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("supplier_code", sa.String(length=50), nullable=False, unique=True),
        sa.Column("supplier_name", sa.String(length=200), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("contact_person", sa.String(length=150), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("opening_balance", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("current_balance", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_code", sa.String(length=100), nullable=False, unique=True),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("secondary_unit", sa.String(length=50), nullable=True),
        sa.Column("conversion_factor", sa.Numeric(10, 4), nullable=True),
        sa.Column("purchase_price", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("selling_price", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("current_stock", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
        sa.Column("reorder_level", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
        sa.Column("warehouse", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "stock_ledger",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("movement_date", sa.Date(), nullable=False),
        sa.Column("movement_type", sa.Enum("IN", "OUT", "ADJUSTMENT", name="stockmovementtype"), nullable=False),
        sa.Column("quantity_in", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
        sa.Column("quantity_out", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
        sa.Column("balance_qty", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
        sa.Column("total_cost", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("document_type", sa.String(length=50), nullable=True),
        sa.Column("document_no", sa.String(length=100), nullable=True),
        sa.Column("document_status", sa.String(length=30), nullable=False, server_default="posted"),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("voucher_no", sa.String(length=100), nullable=False),
        sa.Column("voucher_type", sa.Enum("CPV", "CRV", "BPV", "BRV", "JV", "Contra", name="vouchertype"), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=False),
        sa.Column("party_type", sa.Enum("customer", "supplier", "other", name="partytype"), nullable=True),
        sa.Column("party_id", sa.Integer(), nullable=True),
        sa.Column("debit", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("credit", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference_no", sa.String(length=100), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "import_shipments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("lc_no", sa.String(length=100), nullable=True),
        sa.Column("lc_date", sa.Date(), nullable=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("shipment_date", sa.Date(), nullable=True),
        sa.Column("arrival_date", sa.Date(), nullable=True),
        sa.Column("container_no", sa.String(length=100), nullable=True),
        sa.Column("bl_no", sa.String(length=100), nullable=True),
        sa.Column("exchange_rate", sa.Numeric(10, 4), nullable=False, server_default="1.0000"),
        sa.Column("fob_cost", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("freight_cost", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("insurance_cost", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("customs_duty", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("vat", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("lc_charge", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("cf_charge", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("port_charge", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("transport_cost", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("other_cost", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("total_landed_cost", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("status", sa.Enum("draft", "arrived", "costed", "posted", name="shipmentstatus"), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "import_shipment_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("shipment_id", sa.Integer(), sa.ForeignKey("import_shipments.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("fob_unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
        sa.Column("allocated_landed_cost", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
        sa.Column("total_landed_unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
    )

    op.create_table(
        "sales_invoices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("invoice_no", sa.String(length=100), nullable=False, unique=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("vat", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("discount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("paid_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("due_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("status", sa.Enum("draft", "issued", "partial", "paid", "cancelled", name="salesinvoicestatus"), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "sales_invoice_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("sales_invoices.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
        sa.Column("cost_price", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        sa.Column("discount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
    )

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("po_no", sa.String(length=100), nullable=False, unique=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("vat", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("paid_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("due_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("status", sa.Enum("draft", "ordered", "received", "partial", "cancelled", name="purchasestatus"), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "purchase_order_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False, server_default="0.0000"),
        sa.Column("discount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
    )

    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("expense_no", sa.String(length=100), nullable=False, unique=True),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("payment_method", sa.Enum("cash", "bank", name="paymentmethod"), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), sa.ForeignKey("bank_accounts.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("table_name", sa.String(length=100), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("action_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("expenses")
    op.drop_table("purchase_order_items")
    op.drop_table("purchase_orders")
    op.drop_table("sales_invoice_items")
    op.drop_table("sales_invoices")
    op.drop_table("import_shipment_items")
    op.drop_table("import_shipments")
    op.drop_table("transactions")
    op.drop_table("stock_ledger")
    op.drop_table("products")
    op.drop_table("suppliers")
    op.drop_table("customers")
    op.drop_table("bank_accounts")
    op.drop_table("chart_of_accounts")
    op.drop_table("users")
