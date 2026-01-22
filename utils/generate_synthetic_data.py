#!/usr/bin/env python3
"""
Generate synthetic expense CSV data (2023–2026) for an expense-tracking app.

Output columns:
- date (YYYY-MM-DD)
- amount (EUR, positive)
- category
- subcategory
- merchant
- description
- is_recurring (0/1)

Adjust categories/subcategories to match your app/schema configurations if needed.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional


@dataclass
class Txn:
    date: str
    amount: float
    category: str
    subcategory: str
    merchant: str
    description: str
    is_recurring: int


def clamp_day(year: int, month: int, day: int) -> int:
    last = calendar.monthrange(year, month)[1]
    return max(1, min(day, last))


def jittered_day(year: int, month: int, base_day: int, jitter: int, rng: random.Random) -> date:
    d = clamp_day(year, month, base_day + rng.randint(-jitter, jitter))
    return date(year, month, d)


def random_day_in_month(year: int, month: int, rng: random.Random, day_min: int = 1, day_max: Optional[int] = None) -> date:
    last = calendar.monthrange(year, month)[1]
    if day_max is None:
        day_max = last
    day_min = max(1, day_min)
    day_max = min(last, day_max)
    d = rng.randint(day_min, day_max)
    return date(year, month, d)


def scale_to_target(values: List[float], target: float) -> List[float]:
    s = sum(values)
    if s <= 0:
        return [round(target / max(1, len(values)), 2) for _ in values]
    factor = target / s
    return [round(v * factor, 2) for v in values]


def month_iter(start: date, end: date):
    y, m = start.year, start.month
    while True:
        first = date(y, m, 1)
        last_day = calendar.monthrange(y, m)[1]
        last = date(y, m, last_day)
        yield (y, m, first, last)
        if last >= end:
            break
        m += 1
        if m == 13:
            m = 1
            y += 1


def inflation_factor(year: int) -> float:
    # light inflation trend; tweak/remove if you want everything constant
    # 2023: 1.00, 2024: 1.03, 2025: 1.06, 2026: 1.09
    return 1.0 + 0.03 * (year - 2023)


def add_recurring(txns: List[Txn], y: int, m: int, rng: random.Random):
    # Fixed monthly items (small randomness in amount can be turned off by setting noise to 0)
    def add(base_day, jitter, amount, cat, sub, merchant, desc):
        d = jittered_day(y, m, base_day, jitter, rng)
        txns.append(
            Txn(
                date=d.isoformat(),
                amount=round(amount, 2),
                category=cat,
                subcategory=sub,
                merchant=merchant,
                description=desc,
                is_recurring=1,
            )
        )

    # Vodafone 100 + 29 (modeled as two line items)
    add(5, 2, 100.00, "Telecom", "Internet", "Vodafone", "Vodafone home internet")
    add(5, 2, 29.00, "Telecom", "Mobile", "Vodafone", "Vodafone mobile plan")

    add(2, 2, 40.00, "Health", "Gym", "Gym", "Gym subscription")
    add(1, 1, 22.00, "Subscriptions", "AI", "Claude", "Claude Code subscription")
    add(3, 2, 10.00, "Telecom", "SIM", "SIM Provider", "SIM card plan")
    add(1, 1, 25.00, "Subscriptions", "AI", "OpenAI", "ChatGPT subscription")
    add(28, 2, 63.00, "Transport", "Public Transit", "DB / Local Transit", "Deutschlandticket")
    add(15, 2, 257.00, "Insurance", "Health Insurance", "Health Insurer", "Health insurance premium")


def add_food(txns: List[Txn], y: int, m: int, rng: random.Random):
    # You said: Grocery ~120/month, Outside eating ~80/month
    infl = inflation_factor(y)

    # Groceries split into 3–6 trips
    n_grocery = rng.randint(3, 6)
    raw = [max(5.0, rng.gauss(1.0, 0.35)) for _ in range(n_grocery)]
    # convert weights to amounts
    grocery_amounts = scale_to_target([w * 30.0 for w in raw], 120.0 * infl)

    # Prefer weekly-ish spacing
    candidate_days = [2, 9, 16, 23, 27]
    rng.shuffle(candidate_days)
    days = sorted(candidate_days[:n_grocery])
    for amt, base_day in zip(grocery_amounts, days):
        d = jittered_day(y, m, base_day, 2, rng)
        txns.append(
            Txn(
                date=d.isoformat(),
                amount=float(amt),
                category="Food",
                subcategory="Groceries",
                merchant=rng.choice(["REWE", "Lidl", "Aldi", "Edeka", "Kaufland"]),
                description="Groceries",
                is_recurring=0,
            )
        )

    # Eating out split into 3–6 events
    n_out = rng.randint(3, 6)
    raw2 = [max(5.0, rng.gauss(1.0, 0.4)) for _ in range(n_out)]
    out_amounts = scale_to_target([w * 22.0 for w in raw2], 80.0 * infl)

    for amt in out_amounts:
        d = random_day_in_month(y, m, rng, day_min=4)
        txns.append(
            Txn(
                date=d.isoformat(),
                amount=float(amt),
                category="Food",
                subcategory="Eating Out",
                merchant=rng.choice(["Restaurant", "Cafe", "Fast Food", "Delivery"]),
                description="Eating out",
                is_recurring=0,
            )
        )


def add_misc(txns: List[Txn], y: int, m: int, rng: random.Random):
    infl = inflation_factor(y)

    # Occasional expenses (probabilities per month; tweak as you like)
    def maybe(p: float) -> bool:
        return rng.random() < p

    # Clothes
    if maybe(0.25):
        d = random_day_in_month(y, m, rng)
        amt = round(rng.uniform(40, 120) * infl, 2)
        txns.append(Txn(d.isoformat(), amt, "Shopping", "Clothes", "Clothing Store", "Bought clothes", 0))

    # Books
    if maybe(0.50):
        d = random_day_in_month(y, m, rng)
        amt = round(rng.uniform(15, 60) * infl, 2)
        txns.append(Txn(d.isoformat(), amt, "Shopping", "Books", "Bookstore", "Bought a book", 0))

    # Gifts
    if maybe(0.20):
        d = random_day_in_month(y, m, rng)
        amt = round(rng.uniform(50, 180) * infl, 2)
        txns.append(Txn(d.isoformat(), amt, "Gifts", "Gift", "Gift Shop", "Gift purchase", 0))

    # Games
    if maybe(0.40):
        d = random_day_in_month(y, m, rng)
        amt = round(rng.uniform(10, 60) * infl, 2)
        txns.append(Txn(d.isoformat(), amt, "Entertainment", "Games", "Steam/Store", "Bought games", 0))

    # Protein powder every 2 months (deterministic pattern)
    if m % 2 == 0:
        d = random_day_in_month(y, m, rng, day_min=6, day_max=26)
        amt = round(rng.uniform(28, 35) * infl, 2)
        txns.append(Txn(d.isoformat(), amt, "Health", "Supplements", "Nutrition Store", "Protein powder", 0))

    # A few extra realistic “small misc” items to enrich the dataset
    if maybe(0.25):
        d = random_day_in_month(y, m, rng)
        amt = round(rng.uniform(5, 35) * infl, 2)
        txns.append(Txn(d.isoformat(), amt, "Health", "Pharmacy", "Pharmacy", "Pharmacy/OTC", 0))

    if maybe(0.08):
        d = random_day_in_month(y, m, rng)
        amt = round(rng.uniform(50, 400) * infl, 2)
        txns.append(Txn(d.isoformat(), amt, "Shopping", "Electronics", "Electronics Store", "Electronics purchase", 0))


def generate(start: date, end: date, seed: int) -> List[Txn]:
    rng = random.Random(seed)
    txns: List[Txn] = []

    for y, m, month_first, month_last in month_iter(start, end):
        # skip months outside range edges
        if month_last < start or month_first > end:
            continue

        add_recurring(txns, y, m, rng)
        add_food(txns, y, m, rng)
        add_misc(txns, y, m, rng)

    # Trim any transactions outside [start, end] (because of jitter)
    trimmed: List[Txn] = []
    for t in txns:
        d = date.fromisoformat(t.date)
        if start <= d <= end:
            trimmed.append(t)

    trimmed.sort(key=lambda x: x.date)
    return trimmed


def write_csv(txns: List[Txn], out_path: str):
    fieldnames = ["date", "amount", "category", "subcategory", "merchant", "description", "is_recurring"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for t in txns:
            w.writerow(
                {
                    "date": t.date,
                    "amount": f"{t.amount:.2f}",
                    "category": t.category,
                    "subcategory": t.subcategory,
                    "merchant": t.merchant,
                    "description": t.description,
                    "is_recurring": t.is_recurring,
                }
            )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2023-01-01", help="Start date YYYY-MM-DD")
    ap.add_argument("--end", default="2026-12-31", help="End date YYYY-MM-DD")
    ap.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    ap.add_argument("--out", default="synthetic_expenses_2023_2026.csv", help="Output CSV path")
    args = ap.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    txns = generate(start, end, args.seed)
    write_csv(txns, args.out)

    print(f"Wrote {len(txns)} transactions to: {args.out}")
    print("First 10 rows:")
    for t in txns[:10]:
        print(t)


if __name__ == "__main__":
    main()
