# Supplier Evaluation Dashboard

Group 3 — Digital Lab App Development, SoSe 2026.

A Streamlit dashboard that helps a procurement team **evaluate and compare suppliers**
across four criteria (delivery time, quality, price, communication), compute an
overall score, and flag underperformers.

## Architecture

This is a **single Streamlit app** — there is no separate backend/API server.
Streamlit runs `app.py` as one process that both computes the data (backend
logic: loading CSVs, aggregating scores) and renders the UI (frontend: the
page you see in the browser). Starting it starts both at once.

## Get the code

Clone the repository:

```bash
git clone https://github.com/Nodolas/uni_aufgabe.git
cd uni_aufgabe
```

## Run it

1. **Install dependencies** (one-time setup):

   ```bash
   pip install -r requirements.txt
   ```

2. **Start the app** (this launches the "backend" logic and the "frontend" UI together):

   ```bash
   python -m streamlit run app.py
   ```

   On macOS/Linux you can also use `python3` instead of `python`.

3. Streamlit prints a local URL, and should open it automatically. If not,
   open it yourself:

   ```
   http://localhost:8501
   ```

4. To stop the app, go back to the terminal and press `Ctrl+C`.

Runs locally or in GitHub Codespaces.

The CSV files in `data/` are already generated and committed.

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
requirements.txt   # Python dependencies
data/              # the four CSV tables
README.md
```

## Repository

https://github.com/Nodolas/uni_aufgabe
