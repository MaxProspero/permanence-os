#!/usr/bin/env python3
"""
Tests for scripts/finance_tracker.py -- Personal Finance Tracker
25 tests covering transactions, balances, summaries, accounts, import/export.
"""

import csv
import io
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import finance_tracker


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary database path."""
    return str(tmp_path / "test_finance.db")


@pytest.fixture
def tmp_ledger(tmp_path):
    """Provide a temporary ledger path."""
    return str(tmp_path / "test_finance.ledger")


@pytest.fixture
def seeded_db(tmp_db, tmp_ledger):
    """Database with sample transactions."""
    finance_tracker.add_transaction(
        date="2026-03-01", description="Paycheck",
        amount=5000.0, category="Salary", account="Checking",
        type="income", db_path=tmp_db, ledger_path=tmp_ledger,
    )
    finance_tracker.add_transaction(
        date="2026-03-05", description="Grocery Store",
        amount=85.50, category="Food", account="Checking",
        type="expense", db_path=tmp_db, ledger_path=tmp_ledger,
    )
    finance_tracker.add_transaction(
        date="2026-03-10", description="Electric Bill",
        amount=120.00, category="Utilities", account="Checking",
        type="expense", db_path=tmp_db, ledger_path=tmp_ledger,
    )
    finance_tracker.add_transaction(
        date="2026-03-12", description="Movie Tickets",
        amount=25.00, category="Entertainment", account="Checking",
        type="expense", db_path=tmp_db, ledger_path=tmp_ledger,
    )
    return {"db_path": tmp_db, "ledger_path": tmp_ledger}


# ---------------------------------------------------------------------------
# Default setup
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_accounts_created(self, tmp_db):
        bal = finance_tracker.get_balance(db_path=tmp_db)
        names = [a["name"] for a in bal["accounts"]]
        assert "Checking" in names
        assert "Savings" in names
        assert "Credit Card" in names
        assert "Investment" in names
        assert "Cash" in names

    def test_default_categories_created(self, tmp_db):
        conn = finance_tracker._get_db(tmp_db)
        rows = conn.execute("SELECT name FROM categories").fetchall()
        conn.close()
        cat_names = [r["name"] for r in rows]
        assert "Salary" in cat_names
        assert "Food" in cat_names
        assert "Housing" in cat_names
        assert "To Savings" in cat_names


# ---------------------------------------------------------------------------
# Add transactions
# ---------------------------------------------------------------------------


class TestAddTransaction:
    def test_add_income(self, tmp_db, tmp_ledger):
        result = finance_tracker.add_transaction(
            date="2026-03-01", description="Freelance Payment",
            amount=1500.0, category="Freelance", account="Checking",
            type="income", db_path=tmp_db, ledger_path=tmp_ledger,
        )
        assert result["ok"] is True
        assert result["transaction"]["type"] == "income"
        assert result["transaction"]["amount"] == 1500.0

    def test_add_expense(self, tmp_db, tmp_ledger):
        result = finance_tracker.add_transaction(
            date="2026-03-15", description="Coffee Shop",
            amount=4.50, category="Food", account="Checking",
            type="expense", db_path=tmp_db, ledger_path=tmp_ledger,
        )
        assert result["ok"] is True
        assert result["transaction"]["type"] == "expense"

    def test_add_transfer(self, tmp_db, tmp_ledger):
        result = finance_tracker.add_transaction(
            date="2026-03-20", description="Save for emergency fund",
            amount=500.0, category="To Savings", account="Checking",
            type="transfer", db_path=tmp_db, ledger_path=tmp_ledger,
        )
        assert result["ok"] is True
        assert result["transaction"]["type"] == "transfer"

    def test_add_investment(self, tmp_db, tmp_ledger):
        result = finance_tracker.add_transaction(
            date="2026-03-20", description="Buy index fund",
            amount=1000.0, category="Investment Returns",
            account="Checking", type="investment",
            db_path=tmp_db, ledger_path=tmp_ledger,
        )
        assert result["ok"] is True
        assert result["transaction"]["type"] == "investment"

    def test_invalid_type_rejected(self, tmp_db):
        result = finance_tracker.add_transaction(
            date="2026-03-01", description="Test",
            amount=10.0, category="Food", type="invalid_type",
            db_path=tmp_db,
        )
        assert result["ok"] is False
        assert "invalid" in result["error"].lower()

    def test_negative_amount_rejected(self, tmp_db):
        result = finance_tracker.add_transaction(
            date="2026-03-01", description="Test",
            amount=-10.0, category="Food", db_path=tmp_db,
        )
        assert result["ok"] is False
        assert "positive" in result["error"].lower()

    def test_invalid_date_rejected(self, tmp_db):
        result = finance_tracker.add_transaction(
            date="not-a-date", description="Test",
            amount=10.0, category="Food", db_path=tmp_db,
        )
        assert result["ok"] is False
        assert "date" in result["error"].lower()

    def test_empty_description_rejected(self, tmp_db):
        result = finance_tracker.add_transaction(
            date="2026-03-01", description="",
            amount=10.0, category="Food", db_path=tmp_db,
        )
        assert result["ok"] is False

    def test_nonexistent_account_rejected(self, tmp_db):
        result = finance_tracker.add_transaction(
            date="2026-03-01", description="Test",
            amount=10.0, category="Food", account="Nonexistent",
            db_path=tmp_db,
        )
        assert result["ok"] is False
        assert "not found" in result["error"].lower()


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------


class TestBalance:
    def test_get_balance_all_accounts(self, seeded_db):
        bal = finance_tracker.get_balance(db_path=seeded_db["db_path"])
        assert len(bal["accounts"]) == 5
        assert "total" in bal

    def test_get_balance_single_account(self, seeded_db):
        bal = finance_tracker.get_balance(
            account="Checking", db_path=seeded_db["db_path"],
        )
        assert len(bal["accounts"]) == 1
        assert bal["accounts"][0]["name"] == "Checking"

    def test_income_increases_balance(self, tmp_db, tmp_ledger):
        finance_tracker.add_transaction(
            date="2026-03-01", description="Paycheck",
            amount=3000.0, category="Salary", account="Checking",
            type="income", db_path=tmp_db, ledger_path=tmp_ledger,
        )
        bal = finance_tracker.get_balance(account="Checking", db_path=tmp_db)
        assert bal["accounts"][0]["balance"] == 3000.0

    def test_expense_decreases_balance(self, tmp_db, tmp_ledger):
        finance_tracker.add_transaction(
            date="2026-03-01", description="Paycheck",
            amount=1000.0, category="Salary", account="Checking",
            type="income", db_path=tmp_db, ledger_path=tmp_ledger,
        )
        finance_tracker.add_transaction(
            date="2026-03-02", description="Rent",
            amount=800.0, category="Housing", account="Checking",
            type="expense", db_path=tmp_db, ledger_path=tmp_ledger,
        )
        bal = finance_tracker.get_balance(account="Checking", db_path=tmp_db)
        assert bal["accounts"][0]["balance"] == 200.0

    def test_total_balance_calculation(self, seeded_db):
        bal = finance_tracker.get_balance(db_path=seeded_db["db_path"])
        # income 5000 - expenses (85.5 + 120 + 25) = 4769.5
        checking = next(a for a in bal["accounts"] if a["name"] == "Checking")
        assert checking["balance"] == pytest.approx(4769.5)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_monthly_summary(self, seeded_db):
        summary = finance_tracker.get_summary(
            period="month", db_path=seeded_db["db_path"],
        )
        assert summary["period"] == "month"
        assert "income" in summary
        assert "expenses" in summary
        assert "net" in summary
        assert "by_category" in summary

    def test_summary_income_total(self, seeded_db):
        summary = finance_tracker.get_summary(
            period="all", db_path=seeded_db["db_path"],
        )
        assert summary["income"] == pytest.approx(5000.0)

    def test_summary_expense_total(self, seeded_db):
        summary = finance_tracker.get_summary(
            period="all", db_path=seeded_db["db_path"],
        )
        assert summary["expenses"] == pytest.approx(230.5)

    def test_summary_net_calculation(self, seeded_db):
        summary = finance_tracker.get_summary(
            period="all", db_path=seeded_db["db_path"],
        )
        assert summary["net"] == pytest.approx(5000.0 - 230.5)

    def test_category_breakdown(self, seeded_db):
        summary = finance_tracker.get_summary(
            period="all", db_path=seeded_db["db_path"],
        )
        assert "Food" in summary["by_category"]
        assert summary["by_category"]["Food"] == pytest.approx(85.5)


# ---------------------------------------------------------------------------
# Get / Delete transactions
# ---------------------------------------------------------------------------


class TestTransactionOps:
    def test_get_transactions_returns_list(self, seeded_db):
        txns = finance_tracker.get_transactions(db_path=seeded_db["db_path"])
        assert len(txns) == 4

    def test_date_range_filter(self, seeded_db):
        txns = finance_tracker.get_transactions(
            start_date="2026-03-05",
            end_date="2026-03-10",
            db_path=seeded_db["db_path"],
        )
        assert len(txns) == 2  # Grocery + Electric

    def test_category_filter(self, seeded_db):
        txns = finance_tracker.get_transactions(
            category="Food",
            db_path=seeded_db["db_path"],
        )
        assert len(txns) == 1
        assert txns[0]["description"] == "Grocery Store"

    def test_delete_transaction(self, seeded_db):
        txns = finance_tracker.get_transactions(db_path=seeded_db["db_path"])
        txn_id = txns[0]["id"]
        assert finance_tracker.delete_transaction(txn_id, db_path=seeded_db["db_path"])

        remaining = finance_tracker.get_transactions(db_path=seeded_db["db_path"])
        assert len(remaining) == 3

    def test_delete_nonexistent_returns_false(self, seeded_db):
        assert not finance_tracker.delete_transaction(
            "nonexistent", db_path=seeded_db["db_path"],
        )


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------


class TestExportImport:
    def test_export_ledger_format(self, seeded_db):
        ledger = finance_tracker.export_ledger(db_path=seeded_db["db_path"])
        assert "Permanence OS Finance Ledger" in ledger
        assert "Paycheck" in ledger
        assert "$5000.00" in ledger

    def test_import_csv(self, tmp_db, tmp_path, tmp_ledger):
        csv_file = tmp_path / "import.csv"
        csv_file.write_text(
            "date,description,amount,category,type\n"
            "2026-03-01,Test Income,1000.00,Salary,income\n"
            "2026-03-02,Test Expense,50.00,Food,expense\n"
        )
        result = finance_tracker.import_csv(
            path=str(csv_file),
            account="Checking",
            db_path=tmp_db,
            ledger_path=tmp_ledger,
        )
        assert result["ok"] is True
        assert result["imported"] == 2
        assert len(result["errors"]) == 0


# ---------------------------------------------------------------------------
# Account management
# ---------------------------------------------------------------------------


class TestAccounts:
    def test_add_account(self, tmp_db):
        result = finance_tracker.add_account(
            name="Brokerage",
            type="investment",
            balance=10000.0,
            db_path=tmp_db,
        )
        assert result["ok"] is True
        assert result["account"]["name"] == "Brokerage"

    def test_add_duplicate_account_fails(self, tmp_db):
        finance_tracker.add_account(name="Test Account", db_path=tmp_db)
        result = finance_tracker.add_account(name="Test Account", db_path=tmp_db)
        assert result["ok"] is False
        assert "already exists" in result["error"]

    def test_add_account_empty_name_fails(self, tmp_db):
        result = finance_tracker.add_account(name="", db_path=tmp_db)
        assert result["ok"] is False
