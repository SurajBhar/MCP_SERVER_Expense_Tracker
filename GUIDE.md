# How to test the 16 MCP tool's inside this expense tracker MCP server

---

## How the MCP Inspector test UI usually works

1. Open the Tools page (you already did): `#tools`
2. Click a tool name (left list).
3. In the **Arguments / Input** box, paste a JSON object.
4. Click **Run** (or equivalent).
5. Copy important values from the response (especially newly created `id`s) into later calls.

Dates should be in **`YYYY-MM-DD`** and months in **`YYYY-MM`**.

---

## 1) Resource test first: `expense://categories`

Look for a Resources section (or a “resource” tool). If you see a way to read a resource, use:

* **URI**:
  `expense://categories`

Expected result: JSON text from your `data/categories.json`.

---

## 2) CRUD tests (core DB functionality)

### 2.1 `add_expense` (create)

Paste this:

```json
{
  "date": "2026-01-10",
  "amount": 12.50,
  "category": "food",
  "subcategory": "groceries",
  "note": "Test expense 1",
  "tax_deductible": 0,
  "currency": "EUR",
  "payment_method": "card"
}
```

Expected: `{"status":"ok","id": <number>}`
Copy the returned `id` (you’ll use it below).

---

### 2.2 `list_expenses` (read list)

Paste:

```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31"
}
```

Expected: list of rows containing your inserted expense.

---

### 2.3 `edit_expense` (update)

Use the `id` you got from `add_expense`.

```json
{
  "id": 1,
  "amount": 15.75,
  "note": "Updated note: lunch + snack",
  "subcategory": "outside_eating"
}
```

Expected: `status: ok` and the updated row.

---

### 2.4 `delete_expense` (delete)

```json
{
  "id": 1
}
```

Expected: `status: ok`.
(If you try deleting again you should get a “not found” error, which is also a good test.)

---

## 3) Search & filtering tests

### 3.1 `search_expenses` (filter by date + category)

```json
{
  "start_date": "2025-01-01",
  "end_date": "2026-01-01",
  "category": "Telekom",
  "limit": 50,
  "offset": 0
}
```

Expected: `{ "results": [...], "total_count": ..., "limit": ..., "offset": ... }`

### 3.2 `search_expenses` (note contains + amount range)

```json
{
  "note_contains": "snack",
  "min_amount": 5,
  "max_amount": 50,
  "limit": 50,
  "offset": 0
}
```

Expected: matching rows (dates optional here).

---

## 4) Analytics tests

### 4.1 `summarize` (category totals)

```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31"
}
```

Expected: list like `[{ "category": "...", "total_amount": ... }, ...]`

### 4.2 `category_analytics` (counts, totals, percentages)

```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31"
}
```

Expected: totals + per-category breakdown.

### 4.3 `analyze_trends` (month grouping)

```json
{
  "start_date": "2025-01-01",
  "end_date": "2026-01-31",
  "group_by": "month"
}
```

Expected: `trends` array with `period` like `2025-01`, `2025-02`, …

### 4.4 `get_statistics` (quick stats)

```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31"
}
```

Expected: total spent, avg, min/max, top category, etc.

### 4.5 `compare_months` (month vs month)

```json
{
  "month1": "2025-12",
  "month2": "2026-01",
  "category": "food"
}
```

Expected: totals + difference + percent change.

### 4.6 `forecast_expenses` (moving average forecast)

```json
{
  "months_ahead": 3,
  "based_on_last_months": 6
}
```

Expected: projections per category and total.

### 4.7 `tax_summary` (tax-deductible rollup)

First, add at least one tax-deductible expense (example):

```json
{
  "date": "2025-06-15",
  "amount": 25.00,
  "category": "business",
  "subcategory": "work",
  "note": "Tax deductible subscription test",
  "tax_deductible": 1,
  "currency": "EUR",
  "payment_method": "card"
}
```

Then run:

```json
{
  "year": 2025
}
```

Expected: grouped summary with totals.

---

## 5) Reports & exports tests (file outputs)

These create files **on the machine where the server is running**. To avoid confusion, use **absolute paths**.

### 5.1 `generate_html_report`

**macOS/Linux example path**:

```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "output_path": "/Users/username/Desktop/expense_report_jan_2026.html"
}
```

Expected: `status: ok` + `file_path`. Open the HTML in your browser.

### 5.2 `generate_charts`

```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "chart_types": "pie,bar,line,stacked_bar",
  "output_dir": "/Users/username/Desktop/expense_charts"
}
```

Expected: `generated_files` list. Check that directory.

### 5.3 `export_data`

CSV example:

```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "format": "csv",
  "include_analytics": false,
  "output_path": "/Users/username/Desktop/expenses_jan_2026.csv"
}
```

Excel example (requires openpyxl):

```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "format": "excel",
  "include_analytics": true,
  "output_path": "/Users/username/Desktop/expenses_jan_2026.xlsx"
}
```

### 5.4 `import_expenses`

Make sure the CSV path is readable by the server process.

```json
{
  "file_path": "/Users/username/Desktop/my_expenses.csv",
  "format": "csv"
}
```

Expected: `imported_count > 0` (and `errors` empty or minimal).

If you’re on Windows paths in JSON, remember escaping backslashes, e.g.:

```json
{
  "file_path": "C:\\Users\\username\\Desktop\\my_expenses.csv",
  "format": "csv"
}
```

---

## 6) A very quick end-to-end test sequence

1. `add_expense` (create one row)
2. `list_expenses` (confirm it appears)
3. `edit_expense` (change amount/note)
4. `get_statistics` + `category_analytics` (confirm calculations)
5. `export_data` (confirm file produced)
6. `delete_expense` (cleanup)