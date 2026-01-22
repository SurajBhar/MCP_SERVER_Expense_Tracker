from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from db import connect
from utils.dates import month_start_end, add_months


def summarize(start_date: str, end_date: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
    with connect() as conn:
        query = """
            SELECT category, SUM(amount) AS total_amount
            FROM expenses
            WHERE date BETWEEN ? AND ?
        """
        params: List[Any] = [start_date, end_date]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " GROUP BY category ORDER BY category ASC"

        cur = conn.execute(query, params)
        return [dict(r) for r in cur.fetchall()]


def compare_months(month1: str, month2: str, category: Optional[str] = None) -> Dict[str, Any]:
    m1_start, m1_end = month_start_end(month1)
    m2_start, m2_end = month_start_end(month2)

    with connect() as conn:
        query = "SELECT SUM(amount) AS total FROM expenses WHERE date BETWEEN ? AND ?"
        params1: List[Any] = [m1_start, m1_end]
        params2: List[Any] = [m2_start, m2_end]

        if category:
            query += " AND category = ?"
            params1.append(category)
            params2.append(category)

        total1 = (conn.execute(query, params1).fetchone()[0]) or 0
        total2 = (conn.execute(query, params2).fetchone()[0]) or 0

    diff = total2 - total1
    pct = (diff / total1 * 100) if total1 > 0 else 0

    return {
        "month1": month1,
        "total1": round(total1, 2),
        "month2": month2,
        "total2": round(total2, 2),
        "difference": round(diff, 2),
        "percent_change": round(pct, 2),
        "category": category,
    }


def analyze_trends(
    start_date: str,
    end_date: str,
    group_by: Literal["day", "week", "month"] = "month",
) -> Dict[str, Any]:
    with connect() as conn:
        if group_by == "day":
            date_trunc = "date"
        elif group_by == "week":
            date_trunc = "strftime('%Y-W%W', date)"
        else:
            date_trunc = "strftime('%Y-%m', date)"

        query = f"""
            SELECT {date_trunc} AS period,
                   COUNT(*) AS expense_count,
                   SUM(amount) AS total,
                   AVG(amount) AS average,
                   MIN(amount) AS min_amount,
                   MAX(amount) AS max_amount
            FROM expenses
            WHERE date BETWEEN ? AND ?
            GROUP BY period
            ORDER BY period ASC
        """

        cur = conn.execute(query, (start_date, end_date))
        trends = []
        for r in cur.fetchall():
            d = dict(r)
            d["total"] = round(d["total"] or 0, 2)
            d["average"] = round(d["average"] or 0, 2)
            d["min_amount"] = round(d["min_amount"] or 0, 2)
            d["max_amount"] = round(d["max_amount"] or 0, 2)
            trends.append(d)

        return {"group_by": group_by, "start_date": start_date, "end_date": end_date, "trends": trends}


def category_analytics(start_date: str, end_date: str) -> Dict[str, Any]:
    with connect() as conn:
        total_spent = (
            conn.execute("SELECT SUM(amount) FROM expenses WHERE date BETWEEN ? AND ?", (start_date, end_date))
            .fetchone()[0]
            or 0
        )

        query = """
            SELECT category,
                   COUNT(*) as count,
                   SUM(amount) as total,
                   AVG(amount) as average,
                   MIN(amount) as min_amount,
                   MAX(amount) as max_amount
            FROM expenses
            WHERE date BETWEEN ? AND ?
            GROUP BY category
            ORDER BY total DESC
        """
        cur = conn.execute(query, (start_date, end_date))

        categories = []
        for r in cur.fetchall():
            d = dict(r)
            d["percentage"] = round((d["total"] / total_spent * 100) if total_spent > 0 else 0, 2)
            d["total"] = round(d["total"] or 0, 2)
            d["average"] = round(d["average"] or 0, 2)
            d["min_amount"] = round(d["min_amount"] or 0, 2)
            d["max_amount"] = round(d["max_amount"] or 0, 2)
            categories.append(d)

        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_spent": round(total_spent, 2),
            "categories": categories,
        }


def get_statistics(start_date: str, end_date: str) -> Dict[str, Any]:
    with connect() as conn:
        stats = conn.execute(
            """
            SELECT COUNT(*) as count,
                   SUM(amount) as total,
                   AVG(amount) as average,
                   MIN(amount) as min_amount,
                   MAX(amount) as max_amount
            FROM expenses
            WHERE date BETWEEN ? AND ?
            """,
            (start_date, end_date),
        ).fetchone()

        expensive_day = conn.execute(
            """
            SELECT date, SUM(amount) as daily_total
            FROM expenses
            WHERE date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY daily_total DESC
            LIMIT 1
            """,
            (start_date, end_date),
        ).fetchone()

        top_category = conn.execute(
            """
            SELECT category, SUM(amount) as category_total
            FROM expenses
            WHERE date BETWEEN ? AND ?
            GROUP BY category
            ORDER BY category_total DESC
            LIMIT 1
            """,
            (start_date, end_date),
        ).fetchone()

    days_diff = (datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days + 1
    total = stats["total"] or 0
    daily_avg = (total / days_diff) if days_diff > 0 else 0

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_expenses": stats["count"],
        "total_spent": round(total, 2),
        "average_expense": round(stats["average"] or 0, 2),
        "min_expense": round(stats["min_amount"] or 0, 2),
        "max_expense": round(stats["max_amount"] or 0, 2),
        "daily_average": round(daily_avg, 2),
        "most_expensive_day": {
            "date": expensive_day["date"] if expensive_day else None,
            "total": round(expensive_day["daily_total"], 2) if expensive_day else 0,
        },
        "top_category": {
            "category": top_category["category"] if top_category else None,
            "total": round(top_category["category_total"], 2) if top_category else 0,
        },
    }


def forecast_expenses(months_ahead: int = 3, based_on_last_months: int = 6) -> Dict[str, Any]:
    """Simple moving average forecast using historical monthly totals."""
    today = datetime.now()
    base_year, base_month = today.year, today.month

    # Approx history window start: first day of month N months ago
    hist_year, hist_month = add_months(base_year, base_month, -based_on_last_months)
    history_start = f"{hist_year:04d}-{hist_month:02d}-01"
    history_end = today.strftime("%Y-%m-%d")

    with connect() as conn:
        cur = conn.execute(
            """
            SELECT category, AVG(monthly_total) as avg_monthly_spend
            FROM (
                SELECT category,
                       strftime('%Y-%m', date) as month,
                       SUM(amount) as monthly_total
                FROM expenses
                WHERE date BETWEEN ? AND ?
                GROUP BY category, month
            )
            GROUP BY category
            """,
            (history_start, history_end),
        )

        category_forecasts = []
        for category, avg_spend in cur.fetchall():
            projections = []
            for i in range(1, months_ahead + 1):
                fy, fm = add_months(base_year, base_month, i)
                projections.append({"month": f"{fy:04d}-{fm:02d}", "projected_amount": round(avg_spend or 0, 2)})

            category_forecasts.append(
                {
                    "category": category,
                    "historical_avg_monthly": round(avg_spend or 0, 2),
                    "projections": projections,
                }
            )

        total_monthly_avg = sum(cf["historical_avg_monthly"] for cf in category_forecasts)
        total_projections = []
        for i in range(1, months_ahead + 1):
            fy, fm = add_months(base_year, base_month, i)
            total_projections.append({"month": f"{fy:04d}-{fm:02d}", "projected_total": round(total_monthly_avg, 2)})

    return {
        "based_on_months": based_on_last_months,
        "history_period": f"{history_start} to {history_end}",
        "forecast_months": months_ahead,
        "total_forecast": {"monthly_average": round(total_monthly_avg, 2), "projections": total_projections},
        "category_forecasts": category_forecasts,
    }


def tax_summary(year: int, category: Optional[str] = None) -> Dict[str, Any]:
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    with connect() as conn:
        query = """
            SELECT id, date, amount, category, subcategory, note, payment_method
            FROM expenses
            WHERE date BETWEEN ? AND ?
              AND tax_deductible = 1
        """
        params: List[Any] = [start_date, end_date]
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY date ASC"

        cur = conn.execute(query, params)
        tax_expenses = [dict(r) for r in cur.fetchall()]

    tax_categories: Dict[str, List[Dict[str, Any]]] = {
        "Werbungskosten (Work-related)": [],
        "Gesundheitskosten (Health)": [],
        "Versicherungen (Insurance)": [],
        "Spenden (Donations)": [],
        "Sonstige (Other)": [],
    }
    totals = {k: 0.0 for k in tax_categories.keys()}

    for exp in tax_expenses:
        cat = exp["category"]
        amount = float(exp["amount"] or 0)

        if cat in ["business", "education", "subscriptions"]:
            bucket = "Werbungskosten (Work-related)"
        elif cat == "health":
            bucket = "Gesundheitskosten (Health)"
        elif "insurance" in (exp.get("subcategory") or "").lower():
            bucket = "Versicherungen (Insurance)"
        elif cat == "gifts_donations":
            bucket = "Spenden (Donations)"
        else:
            bucket = "Sonstige (Other)"

        tax_categories[bucket].append(exp)
        totals[bucket] += amount

    summary = []
    for tax_cat, exps in tax_categories.items():
        if exps:
            summary.append({"tax_category": tax_cat, "total": round(totals[tax_cat], 2), "count": len(exps), "expenses": exps})

    return {
        "year": year,
        "filter_category": category,
        "grand_total": round(sum(totals.values()), 2),
        "total_count": len(tax_expenses),
        "summary": summary,
    }
