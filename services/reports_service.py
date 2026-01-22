from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Any, Dict, Optional

from config import REPORTS_DIR
from db import connect
from services.analytics_service import get_statistics, category_analytics, analyze_trends  # absolute imports


def _resolve_output_file(output_path: Optional[str], default_filename: str, default_dir: str) -> str:
    """
    If output_path is:
    - None -> use default_dir/default_filename
    - a directory -> use output_path/default_filename
    - a file path -> use it as-is

    Also ensures the parent directory exists.
    """
    if output_path is None or str(output_path).strip() == "":
        out = os.path.join(default_dir, default_filename)
    else:
        output_path = os.path.abspath(os.path.expanduser(str(output_path)))
        if os.path.isdir(output_path):
            out = os.path.join(output_path, default_filename)
        else:
            out = output_path

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    return out


def generate_html_report(start_date: str, end_date: str, output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate an interactive HTML report with Plotly charts.

    Robust behavior:
    - If output_path is a directory, writes a default filename inside it.
    - If output_path is None, writes into config.REPORTS_DIR.
    """
    try:
        # Lazy imports
        import plotly.graph_objects as go
        import plotly.express as px

        default_name = f"expense_report_{start_date}_to_{end_date}.html"
        output_file = _resolve_output_file(output_path, default_name, str(REPORTS_DIR))

        stats = get_statistics(start_date, end_date)
        cat_analytics = category_analytics(start_date, end_date)
        trends = analyze_trends(start_date, end_date, "month")

        categories_data = cat_analytics["categories"]
        trends_data = trends["trends"]

        cat_names = [c["category"] for c in categories_data]
        cat_values = [c["total"] for c in categories_data]

        fig_pie = px.pie(values=cat_values, names=cat_names, title="Spending by Category", hole=0.3)
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")

        periods = [t["period"] for t in trends_data]
        totals = [t["total"] for t in trends_data]

        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(x=periods, y=totals, mode="lines+markers", name="Total Spending"))
        fig_line.update_layout(
            title="Spending Trends Over Time",
            xaxis_title="Period",
            yaxis_title="Amount (EUR)",
            hovermode="x unified",
        )

        top_cats = sorted(categories_data, key=lambda x: x["total"], reverse=True)[:10]
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(x=[c["category"] for c in top_cats], y=[c["total"] for c in top_cats]))
        fig_bar.update_layout(
            title="Top 10 Spending Categories",
            xaxis_title="Category",
            yaxis_title="Total Amount (EUR)",
            xaxis_tickangle=-45,
        )

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Expense Report: {start_date} to {end_date}</title>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
</head>
<body style="font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px;">
  <h1 style="text-align:center;">Expense Report</h1>
  <p style="text-align:center; color:#666;">{start_date} to {end_date}</p>

  <h2>Summary</h2>
  <ul>
    <li>Total expenses: {stats['total_expenses']}</li>
    <li>Total spent: €{stats['total_spent']:,.2f}</li>
    <li>Daily average: €{stats['daily_average']:,.2f}</li>
    <li>Average expense: €{stats['average_expense']:,.2f}</li>
    <li>Top category: {stats['top_category']['category'] or 'N/A'}</li>
  </ul>

  <div id="pie" style="margin-top: 20px;"></div>
  <div id="line" style="margin-top: 20px;"></div>
  <div id="bar" style="margin-top: 20px;"></div>

  <p style="text-align:center; color:#999; margin-top: 40px;">
    Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
  </p>

  <script>
    const pie = {json.dumps(json.loads(fig_pie.to_json()))};
    const line = {json.dumps(json.loads(fig_line.to_json()))};
    const bar = {json.dumps(json.loads(fig_bar.to_json()))};

    Plotly.newPlot('pie', pie.data, pie.layout);
    Plotly.newPlot('line', line.data, line.layout);
    Plotly.newPlot('bar', bar.data, bar.layout);
  </script>
</body>
</html>
"""

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return {"status": "ok", "file_path": output_file, "message": f"HTML report generated at {output_file}"}

    except Exception as e:
        return {"status": "error", "message": str(e)}


def generate_charts(start_date: str, end_date: str, chart_types: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate PNG charts (Matplotlib, headless-safe).

    Robust behavior:
    - If output_dir is None -> config.REPORTS_DIR
    - If output_dir doesn't exist -> created
    - No relative imports (prevents 'attempted relative import beyond top-level package')
    """
    try:
        # Backend must be set BEFORE importing pyplot
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from collections import defaultdict

        if output_dir is None or str(output_dir).strip() == "":
            out_dir = str(REPORTS_DIR)
        else:
            out_dir = os.path.abspath(os.path.expanduser(str(output_dir)))

        os.makedirs(out_dir, exist_ok=True)

        chart_type_list = [ct.strip() for ct in chart_types.split(",") if ct.strip()]
        generated_files = []

        cat_analytics = category_analytics(start_date, end_date)
        categories_data = cat_analytics["categories"]
        trends = analyze_trends(start_date, end_date, "month")
        trends_data = trends["trends"]

        for chart_type in chart_type_list:
            fig, ax = plt.subplots(figsize=(12, 6))

            if chart_type == "pie":
                cat_names = [c["category"] for c in categories_data[:8]]
                cat_values = [c["total"] for c in categories_data[:8]]
                ax.pie(cat_values, labels=cat_names, autopct="%1.1f%%", startangle=90)
                ax.set_title(f"Spending by Category\n{start_date} to {end_date}")

            elif chart_type == "bar":
                top_cats = categories_data[:10]
                ax.bar([c["category"] for c in top_cats], [c["total"] for c in top_cats])
                ax.set_ylabel("Amount (EUR)")
                ax.set_title(f"Top 10 Spending Categories\n{start_date} to {end_date}")
                ax.tick_params(axis="x", rotation=45)

            elif chart_type == "line":
                periods = [t["period"] for t in trends_data]
                totals = [t["total"] for t in trends_data]
                ax.plot(periods, totals, marker="o")
                ax.set_xlabel("Period")
                ax.set_ylabel("Amount (EUR)")
                ax.set_title(f"Spending Trends Over Time\n{start_date} to {end_date}")
                ax.tick_params(axis="x", rotation=45)

            elif chart_type == "stacked_bar":
                with connect() as conn:
                    cur = conn.execute(
                        """
                        SELECT strftime('%Y-%m', date) as month, category, SUM(amount) as total
                        FROM expenses
                        WHERE date BETWEEN ? AND ?
                        GROUP BY month, category
                        ORDER BY month, category
                        """,
                        (start_date, end_date),
                    )
                    monthly_data = defaultdict(lambda: defaultdict(float))
                    for month, category, total in cur.fetchall():
                        monthly_data[month][category] = total

                months = sorted(monthly_data.keys())
                cats = sorted({c for m in monthly_data.values() for c in m.keys()})
                bottom = [0.0] * len(months)

                for c in cats:
                    values = [monthly_data[m].get(c, 0.0) for m in months]
                    ax.bar(months, values, bottom=bottom, label=c)
                    bottom = [b + v for b, v in zip(bottom, values)]

                ax.set_title(f"Category Spending by Month\n{start_date} to {end_date}")
                ax.set_ylabel("Amount (EUR)")
                ax.tick_params(axis="x", rotation=45)
                ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=8)

            else:
                plt.close(fig)
                continue

            fig.tight_layout()
            filename = f"expense_chart_{chart_type}_{start_date}_to_{end_date}.png"
            filepath = os.path.join(out_dir, filename)
            fig.savefig(filepath, dpi=150, bbox_inches="tight")
            plt.close(fig)

            generated_files.append(filepath)

        return {"status": "ok", "generated_files": generated_files, "message": f"Generated {len(generated_files)} chart(s)"}

    except Exception as e:
        return {"status": "error", "message": str(e)}
