# Supplier Evaluation Dashboard

Group 3 — Digital Lab App Development, SoSe 2026.

A Streamlit dashboard that helps a procurement team **evaluate and compare suppliers**
across four criteria (delivery time, quality, price, communication), compute an
overall score, and flag underperformers.

## Run it

```bash
pip install -r requirements.txt
python3 -m streamlit run app.py
```

Runs locally or in GitHub Codespaces. The app opens in your browser at
`http://localhost:8501`.

## Regenerate the sample data (optional)

The CSV files in `data/` are already generated and committed. To recreate them:

```bash
python generate_data.py
```

## Data model

Four related tables, one CSV each in `data/`:

| Table            | Key columns                                                        | Relationship |
|------------------|--------------------------------------------------------------------|--------------|
| `categories.csv` | `category_id`, `category_name`, `description`                      | —            |
| `suppliers.csv`  | `supplier_id`, `supplier_name`, `country`, `category_id`, `contact_email` | `category_id` → categories |
| `orders.csv`     | `order_id`, `supplier_id`, `order_date`, `amount_eur`, `status`    | `supplier_id` → suppliers |
| `ratings.csv`    | `rating_id`, `order_id`, `supplier_id`, `delivery_time`, `quality`, `price`, `communication` | `order_id` → orders, `supplier_id` → suppliers |

Ratings are on a **1–5 scale**, recorded per order. A supplier's score for each
criterion is the average of its order ratings; the **overall score** is the mean
of the four criterion averages.

```
categories (1) ──< suppliers (1) ──< orders (1) ──< ratings
```

## Features

**Required**
- Table of all suppliers with average score per criterion + overall score
- Overall score derived from individual order ratings
- Underperforming suppliers flagged so they stand out
- Filter by category; summary numbers (# suppliers, average score, # underperformers)
- Bar chart ranking suppliers by overall score
- Drill-down into one supplier (criterion breakdown + their orders)

**Nice-to-have (bonus)**
- Adjustable underperformer threshold (sidebar slider)
- Conditional row highlighting (red = below threshold, green = top scorers)
- Country filter

## Files

```
app.py             # the Streamlit application
styles.py          # custom CSS: fonts, palette, subtle animations
generate_data.py   # (re)generates the CSV sample data
requirements.txt   # Python dependencies
data/              # the four CSV tables
README.md
```
