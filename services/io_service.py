from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List, Optional, Literal

from db import connect, init_db
from services.analytics_service import get_statistics, category_analytics

EXPORT_COLUMNS = [
    "id",
    "date",
    "amount",
    "category",
    "subcategory",
    "note",
    "tax_deductible",
    "currency",
    "payment_method",
]


def _to_float(value: Any) -> float:
    """
    Robust number parsing:
    - handles "12.34"
    - handles "12,34"
    - handles whitespace
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return 0.0
    s = s.replace(",", ".")
    return float(s)


def _to_int_bool(value: Any) -> int:
    """
    Robust boolean/int parsing for tax_deductible:
    - "1", 1 -> 1
    - "true", "yes", "y" -> 1
    - "0", 0, "false", "" -> 0
    """
    if value is None:
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if int(value) != 0 else 0
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "y", "t"}:
        return 1
    return 0


def _normalize_row_keys(row: Dict[str, Any]) -> Dict[str, Any]:
    """Lowercase + strip keys to tolerate CSV header variants."""
    return {str(k).strip().lower(): v for k, v in row.items()}


def export_data(
    start_date: str,
    end_date: str,
    format: Literal["csv", "json", "excel"] = "csv",
    include_analytics: bool = False,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Export expense data to CSV / JSON / Excel.

    Robust behavior:
    - If output_path is a directory, writes a default filename inside it.
    - If output_path is None, writes into config.OUTPUTS_DIR.
    """
    try:
        init_db()

        # Lazy import here to avoid circular imports at import-time
        from config import OUTPUTS_DIR

        # Decide default filename extension
        ext = "xlsx" if format == "excel" else format
        default_name = f"expenses_{start_date}_to_{end_date}.{ext}"

        if output_path is None or str(output_path).strip() == "":
            out_file = os.path.join(str(OUTPUTS_DIR), default_name)
        else:
            output_path = os.path.abspath(os.path.expanduser(str(output_path)))
            if os.path.isdir(output_path):
                out_file = os.path.join(output_path, default_name)
            else:
                out_file = output_path

        os.makedirs(os.path.dirname(out_file) or ".", exist_ok=True)

        with connect() as conn:
            cur = conn.execute(
                """
                SELECT id, date, amount, category, subcategory, note,
                       tax_deductible, currency, payment_method
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date ASC
                """,
                (start_date, end_date),
            )
            rows = [dict(r) for r in cur.fetchall()]

        if format == "csv":
            with open(out_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else EXPORT_COLUMNS)
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)

        elif format == "json":
            payload: Dict[str, Any] = {"period": {"start": start_date, "end": end_date}, "expenses": rows}
            if include_analytics:
                payload["analytics"] = {
                    "statistics": get_statistics(start_date, end_date),
                    "category_breakdown": category_analytics(start_date, end_date),
                }
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

        elif format == "excel":
            import pandas as pd

            df = pd.DataFrame(rows, columns=EXPORT_COLUMNS)
            with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Expenses", index=False)
                if include_analytics:
                    stats = get_statistics(start_date, end_date)
                    cats = category_analytics(start_date, end_date)
                    pd.DataFrame(
                        [
                            ["Total Expenses", stats["total_expenses"]],
                            ["Total Spent (EUR)", stats["total_spent"]],
                            ["Average Expense (EUR)", stats["average_expense"]],
                            ["Daily Average (EUR)", stats["daily_average"]],
                            ["Top Category", stats["top_category"]["category"]],
                            ["Most Expensive Day", stats["most_expensive_day"]["date"]],
                        ],
                        columns=["Metric", "Value"],
                    ).to_excel(writer, sheet_name="Summary", index=False)

                    pd.DataFrame(cats["categories"]).to_excel(writer, sheet_name="Categories", index=False)

        else:
            return {"status": "error", "message": f"Unsupported format: {format}"}

        return {
            "status": "ok",
            "file_path": out_file,
            "format": format,
            "record_count": len(rows),
            "message": f"Data exported successfully to {out_file}",
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}



def import_expenses(file_path: str, format: Literal["csv", "json"] = "csv") -> Dict[str, Any]:
    """
    Import expenses from CSV or JSON into SQLite.

    Robustness guarantees:
    - Ensures DB file exists
    - Ensures schema exists (init_db + connect() enforces schema)
    - Validates file exists
    - Normalizes CSV headers
    - Parses decimal amounts with comma/dot
    - Row-level error reporting
    """
    try:
        file_path = os.path.abspath(os.path.expanduser(file_path))
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"File not found: {file_path}"}
        if not os.path.isfile(file_path):
            return {"status": "error", "message": f"Not a file: {file_path}"}

        init_db()  # safe; ensures table exists before inserting

        imported_count = 0
        errors: List[str] = []

        if format == "csv":
            with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    return {"status": "error", "message": "CSV appears to have no header row."}

                with connect() as conn:
                    for i, raw in enumerate(reader, start=1):
                        try:
                            row = _normalize_row_keys(raw)

                            # Common header variants supported
                            date = (row.get("date") or row.get("transaction_date") or row.get("booking_date") or "").strip()
                            category = (row.get("category") or row.get("cat") or "").strip()

                            amount = _to_float(row.get("amount") or row.get("value") or row.get("price"))
                            subcategory = str(row.get("subcategory") or row.get("sub_category") or "").strip()
                            note = str(row.get("note") or row.get("description") or "").strip()

                            tax_deductible = _to_int_bool(row.get("tax_deductible") or row.get("tax") or 0)
                            currency = str(row.get("currency") or "EUR").strip() or "EUR"
                            payment_method = str(row.get("payment_method") or row.get("payment") or "").strip()

                            if not date or not category:
                                errors.append(f"Row {i}: Missing required fields (date, category)")
                                continue
                            if amount == 0:
                                errors.append(f"Row {i}: amount is 0 (skipped).")
                                continue

                            conn.execute(
                                """
                                INSERT INTO expenses(date, amount, category, subcategory, note, tax_deductible, currency, payment_method)
                                VALUES (?,?,?,?,?,?,?,?)
                                """,
                                (date, amount, category, subcategory, note, tax_deductible, currency, payment_method),
                            )
                            imported_count += 1

                        except Exception as e:
                            errors.append(f"Row {i}: {str(e)}")

        elif format == "json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            expenses = data if isinstance(data, list) else data.get("expenses", [])
            if not isinstance(expenses, list):
                return {"status": "error", "message": "JSON invalid: expected a list or {'expenses': [...]}."}

            with connect() as conn:
                for i, exp in enumerate(expenses, start=1):
                    try:
                        date = str(exp.get("date") or "").strip()
                        category = str(exp.get("category") or "").strip()
                        amount = _to_float(exp.get("amount"))

                        subcategory = str(exp.get("subcategory") or "").strip()
                        note = str(exp.get("note") or "").strip()
                        tax_deductible = _to_int_bool(exp.get("tax_deductible"))
                        currency = str(exp.get("currency") or "EUR").strip() or "EUR"
                        payment_method = str(exp.get("payment_method") or "").strip()

                        if not date or not category:
                            errors.append(f"Entry {i}: Missing required fields (date, category)")
                            continue
                        if amount == 0:
                            errors.append(f"Entry {i}: amount is 0 (skipped).")
                            continue

                        conn.execute(
                            """
                            INSERT INTO expenses(date, amount, category, subcategory, note, tax_deductible, currency, payment_method)
                            VALUES (?,?,?,?,?,?,?,?)
                            """,
                            (date, amount, category, subcategory, note, tax_deductible, currency, payment_method),
                        )
                        imported_count += 1

                    except Exception as e:
                        errors.append(f"Entry {i}: {str(e)}")

        else:
            return {"status": "error", "message": f"Unsupported format: {format}"}

        return {
            "status": "ok",
            "imported_count": imported_count,
            "error_count": len(errors),
            "errors": errors[:10],
            "message": f"Successfully imported {imported_count} expenses with {len(errors)} errors",
            "file_path": file_path,
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
