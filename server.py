"""
Expense Tracker MCP Server (FastMCP)

This file is the *entrypoint* for the local Expense Tracker MCP server.

Why this file exists:
- FastMCP discovers tools by importing this file and reading the `mcp` object.
- All `@mcp.tool()` functions defined here are exposed to MCP clients (LLMs / apps).
- The actual business logic lives in `services/*` so that:
  1) tools remain thin wrappers,
  2) internal logic stays normal Python callables (no "'FunctionTool' object is not callable" issues),
  3) you can unit-test service functions without MCP.

How to run (development):
- From the repo root (this folder contains server.py):
    uv run fastmcp dev server.py

If FastMCP cannot infer the server object, specify it explicitly:
    uv run fastmcp dev server.py:mcp

Data files:
- SQLite DB: `data/expenses.db` (auto-created)
- Categories schema: `data/categories.json` (served via resource `expense://categories`)

Date formats:
- `date`, `start_date`, `end_date`: "YYYY-MM-DD"
- `month1`, `month2`: "YYYY-MM"

Default date range behavior:
- Many tools accept optional `start_date` and `end_date`.
  If omitted:
    - end_date defaults to today
    - start_date defaults to the first day of end_date's month
  This avoids Pydantic validation failures when an LLM passes only `end_date`.

Tool Overview (what to call for what)
-------------------------------------

CRUD / Data entry:
- add_expense(date, amount, category, ...)
    Add one expense row.
- list_expenses(start_date?, end_date?)
    List expenses in the inclusive date range (defaults to current month-to-date).
- edit_expense(id, ...)
    Update one or more fields of an existing expense.
- delete_expense(id)
    Delete an expense row by its database id.
- search_expenses(...)
    Flexible filter query (dates optional; if no dates, searches all rows).

Analytics:
- summarize(start_date?, end_date?, category?)
    Group totals by category.
- category_analytics(start_date?, end_date?)
    Counts, totals, averages, min/max and share (%) per category.
- analyze_trends(start_date?, end_date?, group_by=day|week|month)
    Trend analysis grouped by time period.
- get_statistics(start_date?, end_date?)
    Quick stats (total spent, avg expense, top category, most expensive day).
- compare_months(month1, month2, category?)
    Compare spending between two months.
- forecast_expenses(months_ahead=3, based_on_last_months=6)
    Simple moving-average forecast based on historical monthly totals.
- tax_summary(year, category?)
    Summary for tax-deductible expenses grouped into common German tax buckets.

Reports / Export / Import:
- generate_html_report(start_date?, end_date?, output_path?)
    Creates an interactive HTML report (Plotly) and returns the file path.
- generate_charts(start_date?, end_date?, chart_types="pie,bar,line", output_dir?)
    Creates PNG charts (Matplotlib headless-safe) and returns generated file paths.
- export_data(start_date?, end_date?, format="csv|json|excel", include_analytics=False, output_path?)
    Export data to a file; returns the file path.
- import_expenses(file_path, format="csv|json")
    Import expenses from a file path on disk.

Resource:
- expense://categories
    Returns the content of `data/categories.json` (freshly read on every request).

Notes:
- This file uses ONLY absolute imports (no leading dots) because `fastmcp dev server.py`
  imports this as a standalone module (not a package), and relative imports would fail.

"""

from __future__ import annotations

from fastmcp import FastMCP
from typing import Optional, Literal, Any, Dict, List

from db import init_db
init_db()
from config import CATEGORIES_PATH
from utils.dates import normalize_date_range

from services.expenses_service import (
    add_expense as add_expense_impl,
    list_expenses as list_expenses_impl,
    edit_expense as edit_expense_impl,
    delete_expense as delete_expense_impl,
    search_expenses as search_expenses_impl,
)

from services.analytics_service import (
    summarize as summarize_impl,
    compare_months as compare_months_impl,
    analyze_trends as analyze_trends_impl,
    category_analytics as category_analytics_impl,
    forecast_expenses as forecast_expenses_impl,
    get_statistics as get_statistics_impl,
    tax_summary as tax_summary_impl,
)

from services.reports_service import (
    generate_html_report as generate_html_report_impl,
    generate_charts as generate_charts_impl,
)

from services.io_service import (
    export_data as export_data_impl,
    import_expenses as import_expenses_impl,
)

# FastMCP server object discovered by the CLI.
mcp = FastMCP("ExpenseTracker")


def _range(start_date: Optional[str], end_date: Optional[str]) -> tuple[str, str]:
    """
    Normalize optional (start_date, end_date) into a concrete inclusive range.

    Rules:
    - If end_date is None -> today (YYYY-MM-DD)
    - If start_date is None -> first day of end_date's month (YYYY-MM-01)

    This helps MCP clients/LLMs which sometimes omit one of the bounds.
    """
    r = normalize_date_range(start_date, end_date)
    return r.start_date, r.end_date


# ---------- CRUD ----------
@mcp.tool()
def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = "",
    tax_deductible: int = 0,
    currency: str = "EUR",
    payment_method: str = "",
) -> Dict[str, Any]:
    """
    Add a new expense row to the database.

    Args:
        date: Expense date as "YYYY-MM-DD".
        amount: Numeric amount (positive for expenses; if you want income, store separately or use negative).
        category: High-level category (e.g., "food", "transport", "subscriptions").
        subcategory: Optional finer-grained label.
        note: Optional free text note.
        tax_deductible: 1 if tax deductible, else 0.
        currency: Currency code (default "EUR").
        payment_method: Optional payment method (e.g., "card", "cash", "bank_transfer").

    Returns:
        {"status": "ok", "id": <new_row_id>}
    """
    return add_expense_impl(date, amount, category, subcategory, note, tax_deductible, currency, payment_method)


@mcp.tool()
def list_expenses(start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List expenses in an inclusive date range.

    Defaults:
        If dates are omitted, returns current month-to-date.

    Args:
        start_date: "YYYY-MM-DD" inclusive (optional).
        end_date: "YYYY-MM-DD" inclusive (optional).

    Returns:
        List of expense dicts ordered by date DESC, id DESC.
    """
    s, e = _range(start_date, end_date)
    return list_expenses_impl(s, e)


@mcp.tool()
def edit_expense(
    id: int,
    date: Optional[str] = None,
    amount: Optional[float] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    note: Optional[str] = None,
    tax_deductible: Optional[int] = None,
    currency: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update one or more fields of an existing expense row by id.

    Only fields that are not None are updated.

    Args:
        id: Expense row id.
        date, amount, category, subcategory, note, tax_deductible, currency, payment_method:
            Optional new values.

    Returns:
        On success:
            {"status": "ok", "expense": {...updated row...}}
        If id doesn't exist:
            {"status": "error", "message": "..."}
        If no fields provided:
            {"status": "error", "message": "No fields to update"}
    """
    return edit_expense_impl(id, date, amount, category, subcategory, note, tax_deductible, currency, payment_method)


@mcp.tool()
def delete_expense(id: int) -> Dict[str, Any]:
    """
    Delete an expense row by id.

    Args:
        id: Expense row id.

    Returns:
        {"status": "ok", "message": "..."} or {"status": "error", "message": "..."}
    """
    return delete_expense_impl(id)


@mcp.tool()
def search_expenses(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    note_contains: Optional[str] = None,
    tax_deductible: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Flexible search/filter over expenses (pagination supported).

    Note:
        Unlike list_expenses, this tool does NOT auto-fill missing dates.
        If you omit both start_date and end_date, it searches across all rows.

    Args:
        start_date: Filter lower bound date (inclusive), optional.
        end_date: Filter upper bound date (inclusive), optional.
        category: Exact match on category, optional.
        min_amount/max_amount: Amount bounds, optional.
        note_contains: Substring search inside note, optional.
        tax_deductible: 0 or 1, optional.
        limit: Page size (default 100).
        offset: Pagination offset (default 0).

    Returns:
        {
          "results": [...],
          "total_count": <int>,
          "limit": <int>,
          "offset": <int>
        }
    """
    return search_expenses_impl(
        start_date=start_date,
        end_date=end_date,
        category=category,
        min_amount=min_amount,
        max_amount=max_amount,
        note_contains=note_contains,
        tax_deductible=tax_deductible,
        limit=limit,
        offset=offset,
    )


# ---------- Analytics ----------
@mcp.tool()
def summarize(start_date: Optional[str] = None, end_date: Optional[str] = None, category: Optional[str] = None):
    """
    Summarize expenses by category in an inclusive date range.

    Defaults:
        Month-to-date if start_date/end_date omitted.

    Args:
        start_date: "YYYY-MM-DD" inclusive, optional.
        end_date: "YYYY-MM-DD" inclusive, optional.
        category: If provided, filters to that category (still grouped by category).

    Returns:
        List like: [{"category": "...", "total_amount": ...}, ...]
    """
    s, e = _range(start_date, end_date)
    return summarize_impl(s, e, category)


@mcp.tool()
def compare_months(month1: str, month2: str, category: Optional[str] = None):
    """
    Compare spending totals between two months.

    Args:
        month1: "YYYY-MM"
        month2: "YYYY-MM"
        category: Optional category filter.

    Returns:
        {
          "month1": "...", "total1": ...,
          "month2": "...", "total2": ...,
          "difference": ..., "percent_change": ...,
          "category": <category or None>
        }
    """
    return compare_months_impl(month1, month2, category)


@mcp.tool()
def analyze_trends(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_by: Literal["day", "week", "month"] = "month",
):
    """
    Analyze trends over time (grouped totals and basic stats per period).

    Defaults:
        Month-to-date if start_date/end_date omitted.

    Args:
        start_date: "YYYY-MM-DD" inclusive, optional.
        end_date: "YYYY-MM-DD" inclusive, optional.
        group_by: "day", "week", or "month" (default "month").

    Returns:
        {
          "group_by": "...",
          "start_date": "...",
          "end_date": "...",
          "trends": [
            {"period": "...", "expense_count": ..., "total": ..., "average": ..., "min_amount": ..., "max_amount": ...},
            ...
          ]
        }
    """
    s, e = _range(start_date, end_date)
    return analyze_trends_impl(s, e, group_by)


@mcp.tool()
def category_analytics(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """
    Category-level analytics: totals, averages, min/max, and % share by category.

    Defaults:
        Month-to-date if start_date/end_date omitted.

    Args:
        start_date: "YYYY-MM-DD" inclusive, optional.
        end_date: "YYYY-MM-DD" inclusive, optional.

    Returns:
        {
          "start_date": "...",
          "end_date": "...",
          "total_spent": ...,
          "categories": [
            {"category": "...", "count": ..., "total": ..., "average": ..., "min_amount": ..., "max_amount": ..., "percentage": ...},
            ...
          ]
        }
    """
    s, e = _range(start_date, end_date)
    return category_analytics_impl(s, e)


@mcp.tool()
def forecast_expenses(months_ahead: int = 3, based_on_last_months: int = 6):
    """
    Forecast future monthly spending (simple moving average per category).

    Args:
        months_ahead: Number of future months to project (default 3).
        based_on_last_months: Historical window size (default 6).

    Returns:
        Forecast structure including per-category projections and total monthly average.
    """
    return forecast_expenses_impl(months_ahead, based_on_last_months)


@mcp.tool()
def get_statistics(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """
    Quick stats over an inclusive date range.

    Defaults:
        Month-to-date if start_date/end_date omitted.

    Returns:
        Total count, total spent, averages, min/max, daily average,
        most expensive day, and top category.
    """
    s, e = _range(start_date, end_date)
    return get_statistics_impl(s, e)


@mcp.tool()
def tax_summary(year: int, category: Optional[str] = None):
    """
    Summarize tax-deductible expenses for a given year (German-friendly buckets).

    Args:
        year: e.g., 2025
        category: Optional filter category.

    Returns:
        {
          "year": ...,
          "grand_total": ...,
          "total_count": ...,
          "summary": [
            {"tax_category": "...", "total": ..., "count": ..., "expenses": [...]},
            ...
          ]
        }
    """
    return tax_summary_impl(year, category)


# ---------- Reports / IO ----------
@mcp.tool()
def generate_html_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    output_path: Optional[str] = None,
):
    """
    Generate an interactive HTML report (Plotly).

    Defaults:
        Month-to-date if start_date/end_date omitted.
        output_path defaults to a file in the current working directory.

    Args:
        start_date: "YYYY-MM-DD" inclusive, optional.
        end_date: "YYYY-MM-DD" inclusive, optional.
        output_path: Optional filesystem path to write HTML to.

    Returns:
        {"status": "ok", "file_path": "..."} or {"status": "error", "message": "..."}
    """
    s, e = _range(start_date, end_date)
    return generate_html_report_impl(s, e, output_path)


@mcp.tool()
def generate_charts(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    chart_types: str = "pie,bar,line",
    output_dir: Optional[str] = None,
):
    """
    Generate PNG charts (Matplotlib, headless-safe).

    Defaults:
        Month-to-date if start_date/end_date omitted.
        chart_types defaults to "pie,bar,line"

    Args:
        start_date: "YYYY-MM-DD" inclusive, optional.
        end_date: "YYYY-MM-DD" inclusive, optional.
        chart_types: Comma-separated list of: pie, bar, line, stacked_bar
        output_dir: Directory where PNGs will be saved (defaults to current working dir).

    Returns:
        {"status": "ok", "generated_files": [...]} or {"status": "error", "message": "..."}
    """
    s, e = _range(start_date, end_date)
    return generate_charts_impl(s, e, chart_types, output_dir)


@mcp.tool()
def export_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    format: Literal["csv", "json", "excel"] = "csv",
    include_analytics: bool = False,
    output_path: Optional[str] = None,
):
    """
    Export expenses to a file.

    Defaults:
        Month-to-date if start_date/end_date omitted.

    Args:
        start_date: "YYYY-MM-DD" inclusive, optional.
        end_date: "YYYY-MM-DD" inclusive, optional.
        format: "csv" | "json" | "excel"
        include_analytics: If True, adds analytics into JSON/Excel exports.
        output_path: Optional filesystem path to write the export.

    Returns:
        {"status": "ok", "file_path": "...", "format": "...", "record_count": ...} or error dict.
    """
    s, e = _range(start_date, end_date)
    return export_data_impl(s, e, format, include_analytics, output_path)


@mcp.tool()
def import_expenses(file_path: str, format: Literal["csv", "json"] = "csv"):
    """
    Import expenses from a CSV or JSON file on disk.

    Args:
        file_path: Path to CSV/JSON file on local filesystem.
        format: "csv" or "json"

    Returns:
        {"status": "ok", "imported_count": ..., "error_count": ..., "errors": [...]} or error dict.
    """
    return import_expenses_impl(file_path, format)


# ---------- Resource ----------
@mcp.resource("expense://categories", mime_type="application/json")
def categories() -> str:
    """
    Return the categories schema JSON.

    Resource URI:
        expense://categories

    This is read freshly on every request so you can edit `data/categories.json`
    without restarting the server.
    """
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return f.read()


def run() -> None:
    """
    Initialize the database (migrations + indexes) and start the MCP server.
    """
    init_db()
    mcp.run()


if __name__ == "__main__":
    run()
