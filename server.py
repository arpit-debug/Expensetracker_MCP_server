import csv
import json
import os
import random
from datetime import datetime

from fastmcp import FastMCP
from supabase import create_client, Client
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

EXPORT_DIR = os.environ.get("EXPORT_DIR", os.path.expanduser("~/.expensetracker/exports"))
os.makedirs(EXPORT_DIR, exist_ok=True)

mcp = FastMCP("ExpenseTracker")


# =========================================================
# HELPERS
# =========================================================

def _rows(response) -> list[dict]:
    return response.data or []

def _first(response) -> dict | None:
    data = response.data
    return data[0] if data else None


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

    res = supabase.table("transactions").insert({
        "type": type,
        "amount": amount,
        "currency": currency,
        "category": category,
        "subcategory": subcategory,
        "tags": tags,
        "note": note,
        "date": date,
    }).execute()

    row = _first(res)
    return {"status": "ok", "transaction_id": row["id"] if row else None}


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
    updates = {"updated_at": datetime.utcnow().isoformat()}
    if amount is not None: updates["amount"] = amount
    if category is not None: updates["category"] = category
    if subcategory is not None: updates["subcategory"] = subcategory
    if tags is not None: updates["tags"] = tags
    if note is not None: updates["note"] = note
    if date is not None: updates["date"] = date

    if len(updates) == 1:
        return {"status": "error", "message": "No fields provided to update"}

    supabase.table("transactions").update(updates).eq("id", transaction_id).execute()
    return {"status": "ok", "transaction_id": transaction_id}


@mcp.tool()
def delete_transaction(transaction_id: int):
    """Soft delete a transaction."""
    supabase.table("transactions").update({
        "deleted": 1,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", transaction_id).execute()
    return {"status": "ok", "deleted_transaction_id": transaction_id}


@mcp.tool()
def get_transaction(transaction_id: int):
    """Get a single transaction by ID."""
    res = supabase.table("transactions").select("*").eq("id", transaction_id).eq("deleted", 0).execute()
    row = _first(res)
    if not row:
        return {"status": "error", "message": "Transaction not found"}
    return row


@mcp.tool()
def list_transactions(
    limit: int = 20,
    offset: int = 0,
    month: int = None,
    year: int = None,
):
    """List transactions with pagination. Optionally filter by month (1-12) and/or year (e.g. 2026)."""
    query = supabase.table("transactions").select("*").eq("deleted", 0).order("date", desc=True).range(offset, offset + limit - 1)

    # Use date range filters because `date` is a PostgreSQL date type
    if year and month:
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-31"
        query = query.gte("date", start_date).lte("date", end_date)
    elif year:
        query = query.gte("date", f"{year}-01-01").lte("date", f"{year}-12-31")
    elif month:
        # filter by month across any year in Python
        res = query.execute()
        return [r for r in _rows(res) if datetime.strptime(r["date"], "%Y-%m-%d").month == month]

    return _rows(query.execute())


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
    query = (
        supabase.table("transactions")
        .select("*")
        .eq("deleted", 0)
        .gte("amount", min_amount)
        .lte("amount", max_amount)
        .order("date", desc=True)
    )
    if category:
        query = query.eq("category", category)
    if start_date:
        query = query.gte("date", start_date)
    if end_date:
        query = query.lte("date", end_date)

    rows = _rows(query.execute())

    # Keyword filter in Python (Supabase free tier lacks full-text search on all cols)
    if keyword:
        kw = keyword.lower()
        rows = [
            r for r in rows
            if kw in (r.get("note") or "").lower()
            or kw in (r.get("tags") or "").lower()
            or kw in (r.get("subcategory") or "").lower()
        ]
    return rows


# =========================================================
# ANALYTICS TOOLS
# =========================================================

@mcp.tool()
def monthly_summary(month: str):
    """Get monthly income, expense and savings summary. month format: YYYY-MM"""
    rows = _rows(
        supabase.table("transactions")
        .select("type, amount")
        .eq("deleted", 0)
        .gte("date", f"{month}-01")
        .lte("date", f"{month}-31")
        .execute()
    )
    income = sum(r["amount"] for r in rows if r["type"] == "income")
    expense = sum(r["amount"] for r in rows if r["type"] == "expense")
    return {"month": month, "total_income": income, "total_expense": expense, "savings": income - expense}


@mcp.tool()
def category_breakdown(month: str):
    """Get category-wise expense breakdown."""
    rows = _rows(
        supabase.table("transactions")
        .select("category, amount")
        .eq("deleted", 0)
        .eq("type", "expense")
        .gte("date", f"{month}-01")
        .lte("date", f"{month}-31")
        .execute()
    )
    totals: dict[str, float] = {}
    for r in rows:
        totals[r["category"]] = totals.get(r["category"], 0) + r["amount"]
    return [{"category": k, "total_amount": v} for k, v in sorted(totals.items(), key=lambda x: -x[1])]


# =========================================================
# BUDGET TOOLS
# =========================================================

@mcp.tool()
def set_budget(category: str, amount: float, month: str):
    """Create or update a monthly category budget."""
    supabase.table("budgets").upsert(
        {"category": category, "amount": amount, "month": month},
        on_conflict="category,month"
    ).execute()
    return {"status": "ok", "category": category, "budget": amount, "month": month}


@mcp.tool()
def get_budget_status(month: str):
    """Get budget vs actual spending."""
    budgets = _rows(supabase.table("budgets").select("*").eq("month", month).execute())
    expenses = _rows(
        supabase.table("transactions")
        .select("category, amount")
        .eq("deleted", 0)
        .eq("type", "expense")
        .gte("date", f"{month}-01")
        .lte("date", f"{month}-31")
        .execute()
    )
    spent_map: dict[str, float] = {}
    for r in expenses:
        spent_map[r["category"]] = spent_map.get(r["category"], 0) + r["amount"]

    result = []
    for b in budgets:
        spent = spent_map.get(b["category"], 0)
        result.append({**b, "spent": spent, "remaining": b["amount"] - spent})
    return result


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
    res = supabase.table("transactions").insert({
        "type": type,
        "amount": amount,
        "category": category,
        "subcategory": subcategory,
        "note": note,
        "date": date,
        "recurring": 1,
        "recurring_type": recurring_type,
    }).execute()
    row = _first(res)
    return {"status": "ok", "transaction_id": row["id"] if row else None, "recurring_type": recurring_type}


# =========================================================
# EXPORT TOOLS
# =========================================================

@mcp.tool()
def export_csv(filename: str = "transactions.csv"):
    """Export all transactions to CSV."""
    rows = _rows(
        supabase.table("transactions").select("*").eq("deleted", 0).order("date", desc=True).execute()
    )
    if not rows:
        return {"status": "error", "message": "No data found"}
    path = os.path.join(EXPORT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return {"status": "ok", "file": path}


@mcp.tool()
def export_json(filename: str = "transactions.json"):
    """Export all transactions to JSON."""
    rows = _rows(
        supabase.table("transactions").select("*").eq("deleted", 0).order("date", desc=True).execute()
    )
    path = os.path.join(EXPORT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=4)
    return {"status": "ok", "file": path}


# =========================================================
# SAVINGS GOALS
# =========================================================

@mcp.tool()
def savings_goal(goal_name: str, target_amount: float, current_amount: float = 0, deadline: str = ""):
    """Create a savings goal."""
    res = supabase.table("savings_goals").insert({
        "goal_name": goal_name,
        "target_amount": target_amount,
        "current_amount": current_amount,
        "deadline": deadline,
    }).execute()
    row = _first(res)
    return {"status": "ok", "goal_id": row["id"] if row else None}


# =========================================================
# DASHBOARD
# =========================================================

@mcp.tool()
def dashboard_stats():
    """Homepage dashboard statistics."""
    current_month = datetime.now().strftime("%Y-%m")
    summary = monthly_summary(current_month)

    total = supabase.table("transactions").select("id", count="exact").eq("deleted", 0).execute()

    expense_rows = _rows(
        supabase.table("transactions")
        .select("category, amount")
        .eq("deleted", 0)
        .eq("type", "expense")
        .execute()
    )
    totals: dict[str, float] = {}
    for r in expense_rows:
        totals[r["category"]] = totals.get(r["category"], 0) + r["amount"]
    top_category = max(totals, key=lambda k: totals[k]) if totals else None

    return {
        "current_month": current_month,
        "total_transactions": total.count,
        "monthly_income": summary["total_income"],
        "monthly_expense": summary["total_expense"],
        "monthly_savings": summary["savings"],
        "top_spending_category": top_category,
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