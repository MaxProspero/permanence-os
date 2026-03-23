#!/usr/bin/env python3
"""
PERMANENCE OS -- Personal Finance Tracker

Plain-text ledger + SQLite for structured queries.  Two storage layers:
  1. SQLite at permanence_storage/finance.db   -- structured queries, summaries
  2. Plain text at permanence_storage/finance.ledger -- permanent append-only record

Transaction types: income, expense, transfer, investment

Default accounts: Checking, Savings, Credit Card, Investment, Cash
Default categories organized under Income / Expenses / Transfers

Usage:
  python scripts/finance_tracker.py --action add --date 2026-03-21 --desc "Coffee" --amount 4.50 --category Food
  python scripts/finance_tracker.py --action balance
  python scripts/finance_tracker.py --action summary --period month
  python scripts/finance_tracker.py --action list --limit 20
  python scripts/finance_tracker.py --action export

API endpoints (served by dashboard_api.py):
  GET  /api/finance/transactions?start=2026-03-01&category=Food
  POST /api/finance/transactions
  GET  /api/finance/balance
  GET  /api/finance/summary?period=month
  DELETE /api/finance/transactions/{id}
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = Path(
    os.getenv("PERMANENCE_STORAGE_DIR", str(BASE_DIR / "permanence_storage"))
)
DEFAULT_DB_PATH = str(STORAGE_DIR / "finance.db")
DEFAULT_LEDGER_PATH = str(STORAGE_DIR / "finance.ledger")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_TXN_TYPES = frozenset({"income", "expense", "transfer", "investment"})

DEFAULT_ACCOUNTS = [
    {"name": "Checking", "type": "checking", "balance": 0.0, "currency": "USD"},
    {"name": "Savings", "type": "savings", "balance": 0.0, "currency": "USD"},
    {"name": "Credit Card", "type": "credit", "balance": 0.0, "currency": "USD"},
    {"name": "Investment", "type": "investment", "balance": 0.0, "currency": "USD"},
    {"name": "Cash", "type": "cash", "balance": 0.0, "currency": "USD"},
]

DEFAULT_CATEGORIES = [
    # Income
    {"name": "Salary", "parent_category": "Income", "budget_monthly": 0.0},
    {"name": "Freelance", "parent_category": "Income", "budget_monthly": 0.0},
    {"name": "Investment Returns", "parent_category": "Income", "budget_monthly": 0.0},
    {"name": "Other Income", "parent_category": "Income", "budget_monthly": 0.0},
    # Expenses
    {"name": "Housing", "parent_category": "Expenses", "budget_monthly": 0.0},
    {"name": "Food", "parent_category": "Expenses", "budget_monthly": 0.0},
    {"name": "Transport", "parent_category": "Expenses", "budget_monthly": 0.0},
    {"name": "Utilities", "parent_category": "Expenses", "budget_monthly": 0.0},
    {"name": "Entertainment", "parent_category": "Expenses", "budget_monthly": 0.0},
    {"name": "Shopping", "parent_category": "Expenses", "budget_monthly": 0.0},
    {"name": "Health", "parent_category": "Expenses", "budget_monthly": 0.0},
    {"name": "Education", "parent_category": "Expenses", "budget_monthly": 0.0},
    {"name": "Subscriptions", "parent_category": "Expenses", "budget_monthly": 0.0},
    # Transfers
    {"name": "To Savings", "parent_category": "Transfers", "budget_monthly": 0.0},
    {"name": "To Investment", "parent_category": "Transfers", "budget_monthly": 0.0},
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _generate_id() -> str:
    """Generate a 12-character hex ID."""
    seed = _now_iso() + os.urandom(8).hex()
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def _parse_date(date_str: str) -> Optional[str]:
    """Parse and validate a date string. Returns YYYY-MM-DD or None."""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    account TEXT NOT NULL DEFAULT 'Checking',
    type TEXT NOT NULL DEFAULT 'expense',
    tags TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL DEFAULT 'checking',
    balance REAL NOT NULL DEFAULT 0.0,
    currency TEXT NOT NULL DEFAULT 'USD',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    parent_category TEXT NOT NULL DEFAULT '',
    budget_monthly REAL NOT NULL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_txn_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_txn_account ON transactions(account);
CREATE INDEX IF NOT EXISTS idx_txn_type ON transactions(type);
"""


def _get_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get or create the finance database with default data."""
    path = db_path or os.environ.get("PERMANENCE_FINANCE_DB", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_SQL)

    # Seed default accounts if empty
    count = conn.execute("SELECT COUNT(*) as cnt FROM accounts").fetchone()["cnt"]
    if count == 0:
        now = _now_iso()
        for acct in DEFAULT_ACCOUNTS:
            acct_id = _generate_id()
            conn.execute(
                """INSERT OR IGNORE INTO accounts (id, name, type, balance, currency, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (acct_id, acct["name"], acct["type"], acct["balance"],
                 acct["currency"], now),
            )

    # Seed default categories if empty
    count = conn.execute("SELECT COUNT(*) as cnt FROM categories").fetchone()["cnt"]
    if count == 0:
        for cat in DEFAULT_CATEGORIES:
            cat_id = _generate_id()
            conn.execute(
                """INSERT OR IGNORE INTO categories (id, name, parent_category, budget_monthly)
                   VALUES (?, ?, ?, ?)""",
                (cat_id, cat["name"], cat["parent_category"], cat["budget_monthly"]),
            )

    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Ledger file
# ---------------------------------------------------------------------------


def _append_ledger(
    date: str,
    description: str,
    amount: float,
    category: str,
    account: str,
    txn_type: str,
    ledger_path: Optional[str] = None,
) -> None:
    """Append a transaction to the plain-text ledger file."""
    path = ledger_path or os.environ.get("PERMANENCE_LEDGER", DEFAULT_LEDGER_PATH)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        # Determine debit/credit accounts based on type
        if txn_type == "income":
            debit_account = f"Assets:{account}"
            credit_account = f"Income:{category}"
            entry = (
                f"{date} {description}\n"
                f"    {debit_account}    ${amount:.2f}\n"
                f"    {credit_account}  -${amount:.2f}\n"
            )
        elif txn_type == "expense":
            debit_account = f"Expenses:{category}"
            credit_account = f"Assets:{account}"
            entry = (
                f"{date} {description}\n"
                f"    {debit_account}    ${amount:.2f}\n"
                f"    {credit_account}  -${amount:.2f}\n"
            )
        elif txn_type == "transfer":
            entry = (
                f"{date} {description}\n"
                f"    {category}    ${amount:.2f}\n"
                f"    Assets:{account}  -${amount:.2f}\n"
            )
        else:  # investment
            entry = (
                f"{date} {description}\n"
                f"    Assets:Investment    ${amount:.2f}\n"
                f"    Assets:{account}  -${amount:.2f}\n"
            )

        with open(path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except OSError:
        pass  # Ledger write failure is non-fatal


# ---------------------------------------------------------------------------
# Transaction CRUD
# ---------------------------------------------------------------------------


def add_transaction(
    date: str,
    description: str,
    amount: float,
    category: str,
    account: str = "Checking",
    type: str = "expense",
    tags: Optional[List[str]] = None,
    notes: str = "",
    db_path: Optional[str] = None,
    ledger_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Add a new transaction.

    Args:
        date: Transaction date (YYYY-MM-DD).
        description: What the transaction was for.
        amount: Positive number (sign determined by type).
        category: Category name (e.g. Food, Salary).
        account: Account name (e.g. Checking, Savings).
        type: One of income, expense, transfer, investment.
        tags: Optional list of tags.
        notes: Optional notes.

    Returns:
        Dict with ok, transaction dict.
    """
    if type not in VALID_TXN_TYPES:
        return {
            "ok": False,
            "error": f"Invalid type '{type}'. Must be one of: {sorted(VALID_TXN_TYPES)}",
        }

    parsed_date = _parse_date(date)
    if not parsed_date:
        return {"ok": False, "error": f"Invalid date format: {date}"}

    if amount <= 0:
        return {"ok": False, "error": "Amount must be positive"}

    if not description or not description.strip():
        return {"ok": False, "error": "Description cannot be empty"}

    txn_id = _generate_id()
    now = _now_iso()

    try:
        conn = _get_db(db_path)

        # Verify account exists
        acct = conn.execute(
            "SELECT name FROM accounts WHERE name = ?", (account,)
        ).fetchone()
        if not acct:
            conn.close()
            return {"ok": False, "error": f"Account '{account}' not found"}

        conn.execute(
            """INSERT INTO transactions
               (id, date, description, amount, category, account, type, tags, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (txn_id, parsed_date, description.strip(), amount, category,
             account, type, json.dumps(tags or []), notes, now),
        )

        # Update account balance
        if type == "income":
            conn.execute(
                "UPDATE accounts SET balance = balance + ? WHERE name = ?",
                (amount, account),
            )
        elif type == "expense":
            conn.execute(
                "UPDATE accounts SET balance = balance - ? WHERE name = ?",
                (amount, account),
            )
        elif type == "transfer":
            conn.execute(
                "UPDATE accounts SET balance = balance - ? WHERE name = ?",
                (amount, account),
            )
            # Try to credit the target account from category name
            target = category.replace("To ", "")
            conn.execute(
                "UPDATE accounts SET balance = balance + ? WHERE name = ?",
                (amount, target),
            )
        elif type == "investment":
            conn.execute(
                "UPDATE accounts SET balance = balance - ? WHERE name = ?",
                (amount, account),
            )
            conn.execute(
                "UPDATE accounts SET balance = balance + ? WHERE name = ?",
                (amount, "Investment"),
            )

        conn.commit()
        conn.close()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"Database error: {exc}"}

    # Append to ledger (non-fatal)
    _append_ledger(parsed_date, description.strip(), amount, category,
                   account, type, ledger_path=ledger_path)

    return {
        "ok": True,
        "transaction": {
            "id": txn_id,
            "date": parsed_date,
            "description": description.strip(),
            "amount": amount,
            "category": category,
            "account": account,
            "type": type,
            "tags": tags or [],
            "notes": notes,
            "created_at": now,
        },
    }


def get_transactions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    account: Optional[str] = None,
    txn_type: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> List[dict[str, Any]]:
    """
    Get transactions with optional filters.

    Args:
        start_date: Filter from this date (inclusive).
        end_date: Filter to this date (inclusive).
        category: Filter by category.
        account: Filter by account.
        txn_type: Filter by transaction type.
        limit: Maximum results.

    Returns:
        List of transaction dicts.
    """
    try:
        conn = _get_db(db_path)
        query = "SELECT * FROM transactions WHERE 1=1"
        params: list[Any] = []

        if start_date:
            parsed = _parse_date(start_date)
            if parsed:
                query += " AND date >= ?"
                params.append(parsed)

        if end_date:
            parsed = _parse_date(end_date)
            if parsed:
                query += " AND date <= ?"
                params.append(parsed)

        if category:
            query += " AND category = ?"
            params.append(category)

        if account:
            query += " AND account = ?"
            params.append(account)

        if txn_type:
            query += " AND type = ?"
            params.append(txn_type)

        query += " ORDER BY date DESC, created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()
    except sqlite3.Error:
        return []

    results = []
    for row in rows:
        txn = dict(row)
        try:
            txn["tags"] = json.loads(txn.get("tags", "[]"))
        except (json.JSONDecodeError, TypeError):
            txn["tags"] = []
        results.append(txn)

    return results


def delete_transaction(
    txn_id: str,
    db_path: Optional[str] = None,
) -> bool:
    """
    Delete a transaction by ID and reverse its balance effect.

    Returns True if deleted successfully.
    """
    try:
        conn = _get_db(db_path)
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (txn_id,)
        ).fetchone()

        if not row:
            conn.close()
            return False

        txn = dict(row)
        amount = txn["amount"]
        account = txn["account"]
        txn_type = txn["type"]
        category = txn["category"]

        # Reverse balance change
        if txn_type == "income":
            conn.execute(
                "UPDATE accounts SET balance = balance - ? WHERE name = ?",
                (amount, account),
            )
        elif txn_type == "expense":
            conn.execute(
                "UPDATE accounts SET balance = balance + ? WHERE name = ?",
                (amount, account),
            )
        elif txn_type == "transfer":
            conn.execute(
                "UPDATE accounts SET balance = balance + ? WHERE name = ?",
                (amount, account),
            )
            target = category.replace("To ", "")
            conn.execute(
                "UPDATE accounts SET balance = balance - ? WHERE name = ?",
                (amount, target),
            )
        elif txn_type == "investment":
            conn.execute(
                "UPDATE accounts SET balance = balance + ? WHERE name = ?",
                (amount, account),
            )
            conn.execute(
                "UPDATE accounts SET balance = balance - ? WHERE name = ?",
                (amount, "Investment"),
            )

        conn.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error:
        return False


# ---------------------------------------------------------------------------
# Balance and Summary
# ---------------------------------------------------------------------------


def get_balance(
    account: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Get account balances.

    Args:
        account: Specific account name, or None for all accounts.

    Returns:
        Dict with accounts list and total balance.
    """
    try:
        conn = _get_db(db_path)

        if account:
            rows = conn.execute(
                "SELECT name, type, balance, currency FROM accounts WHERE name = ?",
                (account,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT name, type, balance, currency FROM accounts"
            ).fetchall()

        conn.close()
    except sqlite3.Error:
        return {"accounts": [], "total": 0.0}

    accounts = [dict(row) for row in rows]
    total = sum(a["balance"] for a in accounts)

    return {
        "accounts": accounts,
        "total": round(total, 2),
    }


def get_summary(
    period: str = "month",
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Get financial summary for a period.

    Args:
        period: "month" (current month), "year" (current year), or "all".

    Returns:
        Dict with income, expenses, net, breakdown by category.
    """
    try:
        conn = _get_db(db_path)
        query = "SELECT * FROM transactions WHERE 1=1"
        params: list[Any] = []

        now = datetime.now(timezone.utc)
        if period == "month":
            start = now.strftime("%Y-%m-01")
            query += " AND date >= ?"
            params.append(start)
        elif period == "year":
            start = now.strftime("%Y-01-01")
            query += " AND date >= ?"
            params.append(start)

        rows = conn.execute(query, params).fetchall()
        conn.close()
    except sqlite3.Error:
        return {
            "period": period,
            "income": 0.0,
            "expenses": 0.0,
            "net": 0.0,
            "by_category": {},
            "transaction_count": 0,
        }

    total_income = 0.0
    total_expenses = 0.0
    by_category: dict[str, float] = {}

    for row in rows:
        amount = row["amount"]
        category = row["category"]
        txn_type = row["type"]

        if txn_type == "income":
            total_income += amount
        elif txn_type == "expense":
            total_expenses += amount

        by_category[category] = by_category.get(category, 0.0) + amount

    # Round values
    by_category = {k: round(v, 2) for k, v in by_category.items()}

    return {
        "period": period,
        "income": round(total_income, 2),
        "expenses": round(total_expenses, 2),
        "net": round(total_income - total_expenses, 2),
        "by_category": by_category,
        "transaction_count": len(rows),
    }


# ---------------------------------------------------------------------------
# Account management
# ---------------------------------------------------------------------------


def add_account(
    name: str,
    type: str = "checking",
    balance: float = 0.0,
    currency: str = "USD",
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Add a new account.

    Returns:
        Dict with ok and account details.
    """
    if not name or not name.strip():
        return {"ok": False, "error": "Account name cannot be empty"}

    acct_id = _generate_id()
    now = _now_iso()

    try:
        conn = _get_db(db_path)
        conn.execute(
            """INSERT INTO accounts (id, name, type, balance, currency, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (acct_id, name.strip(), type, balance, currency, now),
        )
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        return {"ok": False, "error": f"Account '{name}' already exists"}
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"Database error: {exc}"}

    return {
        "ok": True,
        "account": {
            "id": acct_id,
            "name": name.strip(),
            "type": type,
            "balance": balance,
            "currency": currency,
            "created_at": now,
        },
    }


# ---------------------------------------------------------------------------
# Export and Import
# ---------------------------------------------------------------------------


def export_ledger(
    db_path: Optional[str] = None,
) -> str:
    """
    Export all transactions in plain-text ledger format.

    Returns:
        Ledger-formatted string.
    """
    transactions = get_transactions(limit=10000, db_path=db_path)
    if not transactions:
        return "; No transactions recorded\n"

    lines = ["; Permanence OS Finance Ledger", f"; Exported: {_now_iso()}", ""]

    # Sort by date ascending for export
    transactions.sort(key=lambda t: t["date"])

    for txn in transactions:
        date = txn["date"]
        desc = txn["description"]
        amount = txn["amount"]
        category = txn["category"]
        account = txn["account"]
        txn_type = txn["type"]

        if txn_type == "income":
            lines.append(f"{date} {desc}")
            lines.append(f"    Assets:{account}    ${amount:.2f}")
            lines.append(f"    Income:{category}  -${amount:.2f}")
        elif txn_type == "expense":
            lines.append(f"{date} {desc}")
            lines.append(f"    Expenses:{category}    ${amount:.2f}")
            lines.append(f"    Assets:{account}  -${amount:.2f}")
        elif txn_type == "transfer":
            lines.append(f"{date} {desc}")
            lines.append(f"    {category}    ${amount:.2f}")
            lines.append(f"    Assets:{account}  -${amount:.2f}")
        else:
            lines.append(f"{date} {desc}")
            lines.append(f"    Assets:Investment    ${amount:.2f}")
            lines.append(f"    Assets:{account}  -${amount:.2f}")

        lines.append("")

    return "\n".join(lines)


def import_csv(
    path: str,
    account: str = "Checking",
    db_path: Optional[str] = None,
    ledger_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Import transactions from a bank CSV export.

    Expected CSV columns: date, description, amount, category (optional), type (optional)

    Args:
        path: Path to CSV file.
        account: Account to assign transactions to.

    Returns:
        Dict with ok, imported count, errors.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as exc:
        return {"ok": False, "error": f"Failed to read file: {exc}"}

    reader = csv.DictReader(io.StringIO(content))
    imported = 0
    errors = []

    for i, row in enumerate(reader, 1):
        date = row.get("date", "")
        description = row.get("description", "")
        amount_str = row.get("amount", "0")
        category = row.get("category", "")
        txn_type = row.get("type", "expense")

        try:
            amount = abs(float(amount_str.replace("$", "").replace(",", "")))
        except ValueError:
            errors.append(f"Row {i}: invalid amount '{amount_str}'")
            continue

        if not date or not description:
            errors.append(f"Row {i}: missing date or description")
            continue

        # Auto-detect type from negative amounts
        if float(amount_str.replace("$", "").replace(",", "")) < 0:
            txn_type = "expense"
            if not category:
                category = "Shopping"
        elif not category:
            category = "Other Income"
            txn_type = "income"

        result = add_transaction(
            date=date,
            description=description,
            amount=amount,
            category=category or "Shopping",
            account=account,
            type=txn_type,
            db_path=db_path,
            ledger_path=ledger_path,
        )

        if result["ok"]:
            imported += 1
        else:
            errors.append(f"Row {i}: {result['error']}")

    return {
        "ok": True,
        "imported": imported,
        "errors": errors,
        "total_rows": imported + len(errors),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Permanence OS -- Personal Finance Tracker"
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["add", "balance", "summary", "list", "export", "delete",
                 "import", "add-account"],
        help="Action to perform",
    )
    parser.add_argument("--date", default="", help="Transaction date (YYYY-MM-DD)")
    parser.add_argument("--desc", default="", help="Transaction description")
    parser.add_argument("--amount", type=float, default=0.0, help="Amount")
    parser.add_argument("--category", default="", help="Category")
    parser.add_argument("--account", default="Checking", help="Account name")
    parser.add_argument("--type", dest="txn_type", default="expense",
                        help="Transaction type (income, expense, transfer, investment)")
    parser.add_argument("--period", default="month",
                        help="Summary period (month, year, all)")
    parser.add_argument("--limit", type=int, default=50, help="Max items to list")
    parser.add_argument("--id", dest="txn_id", default="", help="Transaction ID")
    parser.add_argument("--file", default="", help="CSV file path for import")
    parser.add_argument("--name", default="", help="Account name for add-account")
    parser.add_argument("--start", default="", help="Start date filter")
    parser.add_argument("--end", default="", help="End date filter")
    parser.add_argument("--db-path", default=None, help="Override database path")
    parser.add_argument("--ledger-path", default=None, help="Override ledger path")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.action == "add":
        if not args.date or not args.desc or args.amount <= 0:
            print("Error: --date, --desc, and --amount (positive) are required")
            return 1
        result = add_transaction(
            date=args.date,
            description=args.desc,
            amount=args.amount,
            category=args.category or "Shopping",
            account=args.account,
            type=args.txn_type,
            db_path=args.db_path,
            ledger_path=args.ledger_path,
        )
        if result["ok"]:
            txn = result["transaction"]
            print(f"Added: {txn['id']}")
            print(f"  {txn['date']} | {txn['description']} | ${txn['amount']:.2f} | {txn['category']}")
        else:
            print(f"Error: {result['error']}")
            return 1
        return 0

    if args.action == "balance":
        bal = get_balance(
            account=args.account if args.account != "Checking" else None,
            db_path=args.db_path,
        )
        print("Account Balances:")
        for acct in bal["accounts"]:
            print(f"  {acct['name']}: ${acct['balance']:.2f} ({acct['currency']})")
        print(f"  Total: ${bal['total']:.2f}")
        return 0

    if args.action == "summary":
        summary = get_summary(period=args.period, db_path=args.db_path)
        print(f"Financial Summary ({summary['period']}):")
        print(f"  Income:   ${summary['income']:.2f}")
        print(f"  Expenses: ${summary['expenses']:.2f}")
        print(f"  Net:      ${summary['net']:.2f}")
        if summary["by_category"]:
            print("  By category:")
            for cat, amt in sorted(summary["by_category"].items()):
                print(f"    {cat}: ${amt:.2f}")
        return 0

    if args.action == "list":
        txns = get_transactions(
            start_date=args.start or None,
            end_date=args.end or None,
            category=args.category or None,
            limit=args.limit,
            db_path=args.db_path,
        )
        if not txns:
            print("No transactions found.")
        else:
            print(f"Transactions ({len(txns)}):")
            for t in txns:
                print(f"  [{t['id']}] {t['date']} | {t['description'][:40]} | "
                      f"${t['amount']:.2f} | {t['category']} ({t['type']})")
        return 0

    if args.action == "export":
        ledger = export_ledger(db_path=args.db_path)
        print(ledger)
        return 0

    if args.action == "delete":
        if not args.txn_id:
            print("Error: --id is required for delete action")
            return 1
        if delete_transaction(args.txn_id, db_path=args.db_path):
            print(f"Deleted transaction: {args.txn_id}")
        else:
            print(f"Transaction {args.txn_id} not found")
            return 1
        return 0

    if args.action == "import":
        if not args.file:
            print("Error: --file is required for import action")
            return 1
        result = import_csv(
            path=args.file,
            account=args.account,
            db_path=args.db_path,
            ledger_path=args.ledger_path,
        )
        if result["ok"]:
            print(f"Imported {result['imported']} of {result['total_rows']} rows")
            if result["errors"]:
                for err in result["errors"]:
                    print(f"  Warning: {err}")
        else:
            print(f"Error: {result['error']}")
            return 1
        return 0

    if args.action == "add-account":
        if not args.name:
            print("Error: --name is required for add-account action")
            return 1
        result = add_account(
            name=args.name,
            type=args.txn_type,
            balance=args.amount,
            db_path=args.db_path,
        )
        if result["ok"]:
            acct = result["account"]
            print(f"Added account: {acct['name']} (${acct['balance']:.2f})")
        else:
            print(f"Error: {result['error']}")
            return 1
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
