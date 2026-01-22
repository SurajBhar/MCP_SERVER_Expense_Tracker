#!/usr/bin/env python3
"""
Deterministic tax-deductible seed data for the ExpenseTracker SQLite DB.

- Outputs a CSV with columns matching our import function:
  date, amount, category, subcategory, note, tax_deductible, currency, payment_method

- Optionally inserts directly into your SQLite DB (table: expenses) if --db is provided.
  This matches the schema used in main.py (including tax_deductible/currency/payment_method). 
"""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
from typing import List, Dict


ROWS: List[Dict[str, object]] = [{'date': '2023-01-12', 'amount': 12.0, 'category': 'business', 'subcategory': 'hosting_domains', 'note': 'Domain renewal (portfolio)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2023-01-12', 'amount': 8.0, 'category': 'business', 'subcategory': 'hosting_domains', 'note': 'Hosting add-on / SSL', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2023-02-10', 'amount': 349.0, 'category': 'business', 'subcategory': 'office_supplies', 'note': 'Professional ergonomic chair for work', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2023-02-10', 'amount': 219.0, 'category': 'business', 'subcategory': 'office_supplies', 'note': 'Work desk/table (home office)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2023-03-05', 'amount': 279.0, 'category': 'business', 'subcategory': 'office_supplies', 'note': 'External monitor for work setup', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2023-03-05', 'amount': 89.0, 'category': 'business', 'subcategory': 'office_supplies', 'note': 'Ergonomic keyboard for work', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2023-03-05', 'amount': 39.0, 'category': 'business', 'subcategory': 'office_supplies', 'note': 'Laptop stand (work ergonomics)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2023-04-20', 'amount': 129.0, 'category': 'education', 'subcategory': 'courses', 'note': 'Online course (professional upskilling)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2023-05-12', 'amount': 59.0, 'category': 'education', 'subcategory': 'books', 'note': 'Technical book (work-related)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2023-06-18', 'amount': 120.0, 'category': 'business', 'subcategory': 'travel_business', 'note': 'Train ticket to conference', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2023-06-18', 'amount': 320.0, 'category': 'business', 'subcategory': 'travel_business', 'note': 'Hotel for conference trip', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2023-06-19', 'amount': 450.0, 'category': 'education', 'subcategory': 'workshops', 'note': 'Conference registration fee', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'bank_transfer'}, {'date': '2023-09-02', 'amount': 39.99, 'category': 'subscriptions', 'subcategory': 'linkedin_premium', 'note': 'LinkedIn Premium (career / professional networking)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2023-11-14', 'amount': 49.0, 'category': 'business', 'subcategory': 'office_supplies', 'note': 'Printer ink/paper for work documents', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2024-01-12', 'amount': 12.0, 'category': 'business', 'subcategory': 'hosting_domains', 'note': 'Domain renewal (portfolio)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2024-02-08', 'amount': 249.0, 'category': 'business', 'subcategory': 'office_supplies', 'note': 'Second external monitor for work (dual display)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2024-03-16', 'amount': 99.0, 'category': 'business', 'subcategory': 'office_supplies', 'note': 'Webcam + microphone for remote work', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2024-04-11', 'amount': 149.0, 'category': 'education', 'subcategory': 'exam_fees', 'note': 'Certification exam fee (work-related)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2024-06-07', 'amount': 85.0, 'category': 'business', 'subcategory': 'travel_business', 'note': 'Local transport during conference trip (tickets)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2024-06-07', 'amount': 280.0, 'category': 'business', 'subcategory': 'travel_business', 'note': 'Hotel for conference trip', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2024-06-08', 'amount': 420.0, 'category': 'education', 'subcategory': 'workshops', 'note': 'Conference registration fee', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'bank_transfer'}, {'date': '2024-09-15', 'amount': 79.0, 'category': 'education', 'subcategory': 'books', 'note': 'Reference book / textbook (work-related)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2024-10-02', 'amount': 45.0, 'category': 'business', 'subcategory': 'office_supplies', 'note': 'Notebook/Stationery for work', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2025-01-12', 'amount': 12.0, 'category': 'business', 'subcategory': 'hosting_domains', 'note': 'Domain renewal (portfolio)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2025-02-06', 'amount': 89.0, 'category': 'business', 'subcategory': 'office_supplies', 'note': 'External SSD for work backups', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2025-03-22', 'amount': 199.0, 'category': 'business', 'subcategory': 'office_supplies', 'note': 'Office chair accessories / ergonomic footrest', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2025-05-09', 'amount': 169.0, 'category': 'education', 'subcategory': 'courses', 'note': 'Advanced ML course (professional development)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2025-06-13', 'amount': 140.0, 'category': 'business', 'subcategory': 'travel_business', 'note': 'Train ticket to conference', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2025-06-13', 'amount': 360.0, 'category': 'business', 'subcategory': 'travel_business', 'note': 'Hotel for conference trip', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2025-06-14', 'amount': 475.0, 'category': 'education', 'subcategory': 'workshops', 'note': 'Conference registration fee', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'bank_transfer'}, {'date': '2025-10-18', 'amount': 59.0, 'category': 'education', 'subcategory': 'books', 'note': 'Technical book (work-related)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2025-12-03', 'amount': 35.0, 'category': 'business', 'subcategory': 'office_supplies', 'note': 'Work-related stationery / cables', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2026-01-12', 'amount': 12.0, 'category': 'business', 'subcategory': 'hosting_domains', 'note': 'Domain renewal (portfolio)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2026-02-04', 'amount': 129.0, 'category': 'business', 'subcategory': 'office_supplies', 'note': 'Desk lamp + monitor arm (ergonomics)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2026-03-08', 'amount': 59.0, 'category': 'subscriptions', 'subcategory': 'professional_development', 'note': 'Professional newsletter / learning subscription', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2026-04-17', 'amount': 199.0, 'category': 'education', 'subcategory': 'exam_fees', 'note': 'Certification exam fee (work-related)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2026-06-20', 'amount': 155.0, 'category': 'business', 'subcategory': 'travel_business', 'note': 'Train ticket to conference', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2026-06-20', 'amount': 390.0, 'category': 'business', 'subcategory': 'travel_business', 'note': 'Hotel for conference trip', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2026-06-21', 'amount': 495.0, 'category': 'education', 'subcategory': 'workshops', 'note': 'Conference registration fee', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'bank_transfer'}, {'date': '2026-09-25', 'amount': 69.0, 'category': 'education', 'subcategory': 'books', 'note': 'Technical book (work-related)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}, {'date': '2026-11-29', 'amount': 49.0, 'category': 'business', 'subcategory': 'office_supplies', 'note': 'Office supplies (printer paper/ink)', 'tax_deductible': 1, 'currency': 'EUR', 'payment_method': 'credit_card'}]


FIELDNAMES = ["date","amount","category","subcategory","note","tax_deductible","currency","payment_method"]


def write_csv(out_path: str) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for r in ROWS:
            # Ensure numeric formatting is stable
            r2 = dict(r)
            r2["amount"] = f"{float(r2['amount']):.2f}"
            w.writerow(r2)
    return len(ROWS)


def insert_into_sqlite(db_path: str) -> int:
    """
    Inserts rows into expenses table.
    Expects a table named 'expenses' with columns:
      date, amount, category, subcategory, note, tax_deductible, currency, payment_method
    """
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.executemany(
            "INSERT INTO expenses(date, amount, category, subcategory, note, tax_deductible, currency, payment_method) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    r["date"],
                    float(r["amount"]),
                    r["category"],
                    r["subcategory"],
                    r["note"],
                    int(r["tax_deductible"]),
                    r["currency"],
                    r["payment_method"],
                )
                for r in ROWS
            ],
        )
        con.commit()
        return cur.rowcount if cur.rowcount is not None else len(ROWS)
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="tax_deductible_seed.csv", help="Output CSV path")
    ap.add_argument("--db", default="", help="Optional: path to expenses.db to insert rows")
    args = ap.parse_args()

    n = write_csv(args.out)
    print(f"Wrote {n} rows to {args.out}")

    if args.db:
        inserted = insert_into_sqlite(args.db)
        print(f"Inserted {inserted} rows into SQLite DB: {args.db}")


if __name__ == "__main__":
    main()
