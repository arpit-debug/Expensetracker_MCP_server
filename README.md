# Expense Tracker MCP Server

An AI-powered Expense Tracker backend built using FastMCP and SQLite.

This project exposes financial management tools through the Model Context Protocol (MCP), allowing AI agents and LLMs to interact with personal finance data using natural language.

---

# Features

- Expense & Income Tracking
- Monthly Budget Management
- Savings Goal Tracking
- Transaction Search & Filtering
- Monthly Analytics & Reports
- CSV / JSON Export
- Dashboard Statistics
- Recurring Transactions
- SQLite Database Support
- MCP Tool Integration
- AI Agent Compatible

---

# Tech Stack

| Technology | Purpose |
|---|---|
| Python | Backend Language |
| FastMCP | MCP Server Framework |
| SQLite | Database |
| Async Tools | AI Tool Integration |
| JSON / CSV | Data Export |

---

# Project Structure

```bash
project/
│
├── server.py
├── myexpenses.db
├── exports/
│
└── README.md
```

---

# Installation

## Clone Repository

```bash
git clone <repository-url>
cd project
```

---

## Create Virtual Environment

```bash
python -m venv venv
```

Activate virtual environment:

### Windows

```bash
venv\Scripts\activate
```

### Linux / Mac

```bash
source venv/bin/activate
```

---

## Install Dependencies

```bash
pip install fastmcp
```

---

# Running the Server

```bash
python server.py
```

The MCP server will start using STDIO transport.

---

# Database Structure

The project uses SQLite with three main tables.

---

# 1. transactions Table

Stores all income and expense transactions.

| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary Key |
| type | TEXT | expense or income |
| amount | REAL | Transaction amount |
| currency | TEXT | Currency code |
| category | TEXT | Main category |
| subcategory | TEXT | Transaction subcategory |
| tags | TEXT | Search tags |
| note | TEXT | Extra notes |
| date | TEXT | Transaction date |
| recurring | INTEGER | Recurring flag |
| recurring_type | TEXT | monthly/yearly etc |
| created_at | TEXT | Created timestamp |
| updated_at | TEXT | Updated timestamp |
| deleted | INTEGER | Soft delete flag |

---

# 2. budgets Table

Stores monthly category budgets.

| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary Key |
| category | TEXT | Budget category |
| amount | REAL | Budget amount |
| month | TEXT | Budget month |

### Unique Constraint

```sql
UNIQUE(category, month)
```

---

# 3. savings_goals Table

Stores user savings goals.

| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary Key |
| goal_name | TEXT | Goal name |
| target_amount | REAL | Target amount |
| current_amount | REAL | Current savings |
| deadline | TEXT | Goal deadline |

---

# MCP Tools

The server exposes multiple MCP tools.

---

# Transaction Tools

## add_transaction()

Create a new expense or income transaction.

### Parameters

| Parameter | Type |
|---|---|
| type | str |
| amount | float |
| category | str |
| date | str |
| subcategory | str |
| tags | str |
| note | str |
| currency | str |

### Example

```python
add_transaction(
    type="expense",
    amount=500,
    category="Food",
    date="2026-05-16",
    note="Pizza"
)
```

---

## update_transaction()

Update an existing transaction.

---

## delete_transaction()

Soft delete a transaction.

---

## get_transaction()

Fetch transaction by ID.

---

## list_transactions()

List transactions with pagination.

---

## search_transactions()

Search transactions using filters.

### Supported Filters

- Keyword
- Category
- Date Range
- Amount Range

---

# Analytics Tools

## monthly_summary()

Returns:

- Total income
- Total expense
- Total savings

### Example

```python
monthly_summary("2026-05")
```

### Response

```json
{
  "month": "2026-05",
  "total_income": 50000,
  "total_expense": 12000,
  "savings": 38000
}
```

---

## category_breakdown()

Returns category-wise expense breakdown.

---

# Budget Tools

## set_budget()

Create or update monthly budget.

### Example

```python
set_budget(
    category="Food",
    amount=5000,
    month="2026-05"
)
```

---

## get_budget_status()

Compare budget vs actual spending.

Returns:

- Budget
- Spent
- Remaining amount

---

# Recurring Transaction Tools

## add_recurring_transaction()

Create recurring transactions like:

- Salary
- Rent
- Subscription
- Utility Bills

---

# Export Tools

## export_csv()

Export all transactions to CSV.

### Output Directory

```bash
exports/
```

---

## export_json()

Export all transactions to JSON.

---

# Savings Goal Tools

## savings_goal()

Create savings goals.

### Example

```python
savings_goal(
    goal_name="Buy Laptop",
    target_amount=100000,
    current_amount=25000,
    deadline="2026-12-31"
)
```

---

# Dashboard Tools

## dashboard_stats()

Returns dashboard statistics including:

- Monthly income
- Monthly expense
- Savings
- Total transactions
- Top spending category

---

# Utility Tools

## roll_dice()

Roll dice utility function.

---

## add_numbers()

Add two numbers.

---

# Example MCP Workflow

```text
User Prompt
     ↓
AI Agent
     ↓
MCP Tool Selection
     ↓
Expense Tracker MCP Server
     ↓
SQLite Database
     ↓
Response
```

---

# Example Natural Language Commands

```text
"Add expense of 500 for pizza"

"Show my monthly summary"

"Set food budget to 6000"

"Export transactions to CSV"

"Create savings goal for bike"
```

---

# Exported Files

Generated export files are stored inside:

```bash
exports/
```

Supported formats:

- CSV
- JSON

---

# Future Improvements

- Authentication
- Multi-user support
- REST API
- Web dashboard
- Charts & visualization
- PostgreSQL support
- AI financial insights
- Scheduled recurring transactions

---

# License

MIT License

---

# Author

Built using:

- FastMCP
- SQLite
- Python
- MCP Architecture