import csv
import json
import os
import random
import sqlite3
from datetime import datetime

from fastmcp import FastMCP


# Use a persistent directory for the database so data survives server restarts.
# Change DATA_DIR to a volume-mounted path if deploying on Railway/Render/Fly etc.
DATA_DIR = os.environ.get("DATA_DIR", os.path.expanduser("~/.expensetracker"))
DB_PATH = os.path.join(DATA_DIR, "myexpenses.db")
EXPORT_DIR = os.path.join(DATA_DIR, "exports")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

mcp = FastMCP("ExpenseTracker")


# =========================================================
# DATABASE SETUP
# =========================================================


def init_db():
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                type TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'INR',

                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',

                tags TEXT DEFAULT '',
                note TEXT DEFAULT '',

                date TEXT NOT NULL,

                recurring INTEGER DEFAULT 0,
                recurring_type TEXT DEFAULT '',

                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

                deleted INTEGER DEFAULT 0
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                month TEXT NOT NULL,
                UNIQUE(category, month)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS savings_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_name TEXT NOT NULL,
                target_amount REAL NOT NULL,
                current_amount REAL DEFAULT 0,
                deadline TEXT DEFAULT ''
            )
            """
        )


init_db()


# =========================================================
# HELPERS
# =========================================================


def dict_fetchall(cursor):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# =========================================================
# TRANSACTION TOOLS
# =========================================================


@mcp.tool()
def add_transaction(
    type: str,
    amount: float,
    category: str,
    date: str,
    subcategory: str = "",
    tags: str = "",
    note: str = "",
    currency: str = "INR",
):
    """Create a new transaction."""

    if type not in ["expense", "income"]:
        return {"status": "error", "message": "type must be expense or income"}

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:

        cur = conn.execute(
            """
            INSERT INTO transactions(
                type,
                amount,
                currency,
                category,
                subcategory,
                tags,
                note,
                date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                type,
                amount,
                currency,
                category,
                subcategory,
                tags,
                note,
                date,
            ),
        )

        return {
            "status": "ok",
            "transaction_id": cur.lastrowid,
        }


@mcp.tool()
def update_transaction(
    transaction_id: int,
    amount: float = None,
    category: str = None,
    subcategory: str = None,
    tags: str = None,
    note: str = None,
    date: str = None,
):
    """Update an existing transaction."""

    updates = []
    params = []

    if amount is not None:
        updates.append("amount = ?")
        params.append(amount)

    if category is not None:
        updates.append("category = ?")
        params.append(category)

    if subcategory is not None:
        updates.append("subcategory = ?")
        params.append(subcategory)

    if tags is not None:
        updates.append("tags = ?")
        params.append(tags)

    if note is not None:
        updates.append("note = ?")
        params.append(note)

    if date is not None:
        updates.append("date = ?")
        params.append(date)

    updates.append("updated_at = CURRENT_TIMESTAMP")

    if not params:
        return {
            "status": "error",
            "message": "No fields provided to update",
        }

    params.append(transaction_id)

    query = f"""
        UPDATE transactions
        SET {', '.join(updates)}
        WHERE id = ?
    """

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:
        conn.execute(query, params)

    return {
        "status": "ok",
        "transaction_id": transaction_id,
    }


@mcp.tool()
def delete_transaction(transaction_id: int):
    """Soft delete a transaction."""

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:
        conn.execute(
            """
            UPDATE transactions
            SET deleted = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (transaction_id,),
        )

    return {
        "status": "ok",
        "deleted_transaction_id": transaction_id,
    }


@mcp.tool()
def get_transaction(transaction_id: int):
    """Get a single transaction by ID."""

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:

        cur = conn.execute(
            """
            SELECT *
            FROM transactions
            WHERE id = ?
            AND deleted = 0
            """,
            (transaction_id,),
        )

        row = cur.fetchone()

        if not row:
            return {
                "status": "error",
                "message": "Transaction not found",
            }

        cols = [d[0] for d in cur.description]

        return dict(zip(cols, row))


@mcp.tool()
def list_transactions(
    limit: int = 20,
    offset: int = 0,
    month: int = None,
    year: int = None,
):
    """List transactions with pagination. Optionally filter by month (1-12) and/or year (e.g. 2026)."""

    query = "SELECT * FROM transactions WHERE deleted = 0"
    params = []

    if year is not None:
        query += " AND strftime('%Y', date) = ?"
        params.append(str(year))

    if month is not None:
        query += " AND strftime('%m', date) = ?"
        params.append(f"{month:02d}")

    query += " ORDER BY date DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:
        cur = conn.execute(query, params)
        return dict_fetchall(cur)


@mcp.tool()
def search_transactions(
    keyword: str = "",
    category: str = "",
    start_date: str = "",
    end_date: str = "",
    min_amount: float = 0,
    max_amount: float = 999999999,
):
    """Search and filter transactions."""

    query = """
        SELECT *
        FROM transactions
        WHERE deleted = 0
        AND amount BETWEEN ? AND ?
    """

    params = [min_amount, max_amount]

    if keyword:
        query += " AND (note LIKE ? OR tags LIKE ? OR subcategory LIKE ?)"
        params.extend([
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%",
        ])

    if category:
        query += " AND category = ?"
        params.append(category)

    if start_date and end_date:
        query += " AND date BETWEEN ? AND ?"
        params.extend([start_date, end_date])

    query += " ORDER BY date DESC"

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:

        cur = conn.execute(query, params)

        return dict_fetchall(cur)


# =========================================================
# ANALYTICS TOOLS
# =========================================================


@mcp.tool()
def monthly_summary(month: str):
    """Get monthly income, expense and savings summary."""

    start_date = f"{month}-01"
    end_date = f"{month}-31"

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:

        income = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE type = 'income'
            AND deleted = 0
            AND date BETWEEN ? AND ?
            """,
            (start_date, end_date),
        ).fetchone()[0]

        expense = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE type = 'expense'
            AND deleted = 0
            AND date BETWEEN ? AND ?
            """,
            (start_date, end_date),
        ).fetchone()[0]

    return {
        "month": month,
        "total_income": income,
        "total_expense": expense,
        "savings": income - expense,
    }


@mcp.tool()
def category_breakdown(month: str):
    """Get category-wise expense breakdown."""

    start_date = f"{month}-01"
    end_date = f"{month}-31"

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:

        cur = conn.execute(
            """
            SELECT category,
                   SUM(amount) AS total_amount
            FROM transactions
            WHERE type = 'expense'
            AND deleted = 0
            AND date BETWEEN ? AND ?
            GROUP BY category
            ORDER BY total_amount DESC
            """,
            (start_date, end_date),
        )

        return dict_fetchall(cur)


# =========================================================
# BUDGET TOOLS
# =========================================================


@mcp.tool()
def set_budget(category: str, amount: float, month: str):
    """Create or update a monthly category budget."""

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:

        conn.execute(
            """
            INSERT OR REPLACE INTO budgets(
                category,
                amount,
                month
            )
            VALUES (?, ?, ?)
            """,
            (category, amount, month),
        )

    return {
        "status": "ok",
        "category": category,
        "budget": amount,
        "month": month,
    }


@mcp.tool()
def get_budget_status(month: str):
    """Get budget vs actual spending."""

    start_date = f"{month}-01"
    end_date = f"{month}-31"

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:

        cur = conn.execute(
            """
            SELECT
                b.category,
                b.amount AS budget,
                COALESCE(SUM(t.amount), 0) AS spent
            FROM budgets b
            LEFT JOIN transactions t
                ON b.category = t.category
                AND t.type = 'expense'
                AND t.deleted = 0
                AND t.date BETWEEN ? AND ?
            WHERE b.month = ?
            GROUP BY b.category, b.amount
            """,
            (start_date, end_date, month),
        )

        rows = dict_fetchall(cur)

        for row in rows:
            row["remaining"] = row["budget"] - row["spent"]

        return rows


# =========================================================
# RECURRING TRANSACTIONS
# =========================================================


@mcp.tool()
def add_recurring_transaction(
    type: str,
    amount: float,
    category: str,
    recurring_type: str,
    date: str,
    subcategory: str = "",
    note: str = "",
):
    """Create recurring transaction template."""

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:

        cur = conn.execute(
            """
            INSERT INTO transactions(
                type,
                amount,
                category,
                subcategory,
                note,
                date,
                recurring,
                recurring_type
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                type,
                amount,
                category,
                subcategory,
                note,
                date,
                recurring_type,
            ),
        )

    return {
        "status": "ok",
        "transaction_id": cur.lastrowid,
        "recurring_type": recurring_type,
    }


# =========================================================
# EXPORT TOOLS
# =========================================================


@mcp.tool()
def export_csv(filename: str = "transactions.csv"):
    """Export all transactions to CSV."""

    path = os.path.join(EXPORT_DIR, filename)

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:

        cur = conn.execute(
            """
            SELECT *
            FROM transactions
            WHERE deleted = 0
            ORDER BY date DESC
            """
        )

        rows = dict_fetchall(cur)

    if not rows:
        return {
            "status": "error",
            "message": "No data found",
        }

    with open(path, "w", newline="", encoding="utf-8") as f:

        writer = csv.DictWriter(f, fieldnames=rows[0].keys())

        writer.writeheader()
        writer.writerows(rows)

    return {
        "status": "ok",
        "file": path,
    }


@mcp.tool()
def export_json(filename: str = "transactions.json"):
    """Export all transactions to JSON."""

    path = os.path.join(EXPORT_DIR, filename)

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:

        cur = conn.execute(
            """
            SELECT *
            FROM transactions
            WHERE deleted = 0
            ORDER BY date DESC
            """
        )

        rows = dict_fetchall(cur)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=4)

    return {
        "status": "ok",
        "file": path,
    }


# =========================================================
# SAVINGS GOALS
# =========================================================


@mcp.tool()
def savings_goal(
    goal_name: str,
    target_amount: float,
    current_amount: float = 0,
    deadline: str = "",
):
    """Create a savings goal."""

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:

        cur = conn.execute(
            """
            INSERT INTO savings_goals(
                goal_name,
                target_amount,
                current_amount,
                deadline
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                goal_name,
                target_amount,
                current_amount,
                deadline,
            ),
        )

    return {
        "status": "ok",
        "goal_id": cur.lastrowid,
    }


# =========================================================
# DASHBOARD
# =========================================================


@mcp.tool()
def dashboard_stats():
    """Homepage dashboard statistics."""

    current_month = datetime.now().strftime("%Y-%m")

    summary = monthly_summary(current_month)

    with sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False) as conn:

        total_transactions = conn.execute(
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE deleted = 0
            """
        ).fetchone()[0]

        top_category = conn.execute(
            """
            SELECT category,
                   SUM(amount) AS total
            FROM transactions
            WHERE type = 'expense'
            AND deleted = 0
            GROUP BY category
            ORDER BY total DESC
            LIMIT 1
            """
        ).fetchone()

    return {
        "current_month": current_month,
        "total_transactions": total_transactions,
        "monthly_income": summary["total_income"],
        "monthly_expense": summary["total_expense"],
        "monthly_savings": summary["savings"],
        "top_spending_category": top_category[0] if top_category else None,
    }


# =========================================================
# UTILITY TOOLS
# =========================================================


@mcp.tool()
def roll_dice(n_dice: int = 1) -> list[int]:
    """Roll n_dice with 6 side dice and return the results."""

    return [random.randint(1, 6) for _ in range(n_dice)]


@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """Add two numbers together."""

    return a + b


# =========================================================
# MAIN
# =========================================================


if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
    # mcp.run(transport="stdio")