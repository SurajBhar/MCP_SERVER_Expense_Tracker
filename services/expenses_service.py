from __future__ import annotations

from typing import Any, Dict, List, Optional

from db import connect
from config import DEFAULT_CURRENCY


def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = "",
    tax_deductible: int = 0,
    currency: str = DEFAULT_CURRENCY,
    payment_method: str = "",
) -> Dict[str, Any]:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO expenses(date, amount, category, subcategory, note, tax_deductible, currency, payment_method)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (date, amount, category, subcategory, note, tax_deductible, currency, payment_method),
        )
        return {"status": "ok", "id": cur.lastrowid}


def list_expenses(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT id, date, amount, category, subcategory, note, tax_deductible, currency, payment_method
            FROM expenses
            WHERE date BETWEEN ? AND ?
            ORDER BY date DESC, id DESC
            """,
            (start_date, end_date),
        )
        return [dict(r) for r in cur.fetchall()]


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
    with connect() as conn:
        cur = conn.execute("SELECT * FROM expenses WHERE id = ?", (id,))
        existing = cur.fetchone()
        if not existing:
            return {"status": "error", "message": f"Expense with id {id} not found"}

        updates: List[str] = []
        params: List[Any] = []

        if date is not None:
            updates.append("date = ?")
            params.append(date)
        if amount is not None:
            updates.append("amount = ?")
            params.append(amount)
        if category is not None:
            updates.append("category = ?")
            params.append(category)
        if subcategory is not None:
            updates.append("subcategory = ?")
            params.append(subcategory)
        if note is not None:
            updates.append("note = ?")
            params.append(note)
        if tax_deductible is not None:
            updates.append("tax_deductible = ?")
            params.append(tax_deductible)
        if currency is not None:
            updates.append("currency = ?")
            params.append(currency)
        if payment_method is not None:
            updates.append("payment_method = ?")
            params.append(payment_method)

        if not updates:
            return {"status": "error", "message": "No fields to update"}

        params.append(id)
        query = f"UPDATE expenses SET {', '.join(updates)} WHERE id = ?"
        conn.execute(query, params)

        cur = conn.execute("SELECT * FROM expenses WHERE id = ?", (id,))
        updated = cur.fetchone()
        return {"status": "ok", "expense": dict(updated) if updated else None}


def delete_expense(id: int) -> Dict[str, Any]:
    with connect() as conn:
        cur = conn.execute("SELECT 1 FROM expenses WHERE id = ?", (id,))
        if not cur.fetchone():
            return {"status": "error", "message": f"Expense with id {id} not found"}

        conn.execute("DELETE FROM expenses WHERE id = ?", (id,))
        return {"status": "ok", "message": f"Expense {id} deleted successfully"}


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
    with connect() as conn:
        query = """
            SELECT id, date, amount, category, subcategory, note, tax_deductible, currency, payment_method
            FROM expenses
            WHERE 1=1
        """
        params: List[Any] = []

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        if category:
            query += " AND category = ?"
            params.append(category)
        if min_amount is not None:
            query += " AND amount >= ?"
            params.append(min_amount)
        if max_amount is not None:
            query += " AND amount <= ?"
            params.append(max_amount)
        if note_contains:
            query += " AND note LIKE ?"
            params.append(f"%{note_contains}%")
        if tax_deductible is not None:
            query += " AND tax_deductible = ?"
            params.append(tax_deductible)

        query += " ORDER BY date DESC, id DESC LIMIT ? OFFSET ?"
        query_params = params + [limit, offset]

        cur = conn.execute(query, query_params)
        results = [dict(r) for r in cur.fetchall()]

        count_query = "SELECT COUNT(*) FROM expenses WHERE 1=1"
        count_query += query.split("WHERE 1=1", 1)[1].split("ORDER BY", 1)[0]  # reuse same filters
        total_count = conn.execute(count_query, params).fetchone()[0]

        return {"results": results, "total_count": total_count, "limit": limit, "offset": offset}
