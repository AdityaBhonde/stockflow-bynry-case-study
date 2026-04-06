# StockFlow — Backend Intern Case Study
**Applicant:** Aditya Bhonde | VIT Pune, SY
**Role:** Backend Engineering Intern — Bynry Inc.

---

## Project Structure

```
stockflow-case-study/
│
├── README.md                          ← You are here
├── part1_code_review/
│   └── fixed_product_api.py           ← Debugged & fixed product creation endpoint
├── part2_database_design/
│   └── schema.sql                     ← Full DB schema with indexes & constraints
└── part3_api_implementation/
    └── low_stock_alerts.py            ← Low-stock alerts endpoint implementation
```

---

## Part 1 — Code Review & Debugging

**File:** `part1_code_review/fixed_product_api.py`

### Issues Found in Original Code

| # | Issue | Impact |
|---|-------|--------|
| 1 | No input validation | Missing fields crash the server with 500 error |
| 2 | Two separate `db.session.commit()` calls | If second commit fails, orphan Product record is created in DB |
| 3 | No SKU uniqueness check | Duplicate SKUs can silently enter the database |
| 4 | No price validation | Negative or non-numeric prices accepted |
| 5 | `initial_quantity` not optional | Crashes if field is not sent, despite being optional |
| 6 | No authentication | Any anonymous request can create a product |
| 7 | Returns 200 instead of 201 | Wrong HTTP status code for resource creation |

### Key Fix — Single Transaction
The most critical fix was wrapping both `Product` and `Inventory` creation in a **single transaction** using `db.session.flush()` + one `db.session.commit()`. This ensures if either operation fails, both are rolled back — no orphan data.

---

## Part 2 — Database Design

**File:** `part2_database_design/schema.sql`

### Tables Designed

| Table | Purpose |
|-------|---------|
| `companies` | Top-level B2B customers using StockFlow |
| `warehouses` | Multiple warehouses per company |
| `suppliers` | Suppliers linked to companies |
| `products` | Master product catalog with per-product threshold |
| `inventory` | Stock levels per product per warehouse |
| `inventory_logs` | Audit trail of every stock change |
| `bundle_items` | Links bundle products to their components |

### Key Design Decisions
- `NUMERIC(10,2)` for price — avoids floating point bugs with money
- `inventory_logs` stores every change with a reason — enables sales velocity calculation for `days_until_stockout`
- `low_stock_threshold` is per-product — supports different thresholds by product type
- Indexes added on `company_id`, `product_id`, `warehouse_id`, `created_at` — all heavily used in alert queries

### Questions I Would Ask the Product Team
1. Can a product exist in multiple companies, or is the catalog per-company?
2. What defines "recent sales activity" — last 7 days, 30 days? Is it configurable?
3. Can one product have multiple suppliers?
4. Can inventory go below zero (backorders)?
5. Are bundle stock levels calculated from components, or tracked separately?
6. Do we need multi-currency support?
7. Is there a concept of "reserved" stock for pending orders?
8. Should discontinued products be soft-deleted (is_deleted flag)?

---

## Part 3 — API Implementation

**File:** `part3_api_implementation/low_stock_alerts.py`

**Endpoint:** `GET /api/companies/{company_id}/alerts/low-stock`

### Assumptions Made
- "Recent sales activity" = at least 1 inventory decrease in the **last 30 days**
- `days_until_stockout` = `current_stock / avg_daily_sales` (over 30 days)
- If `avg_daily_sales` is 0, `days_until_stockout` is returned as `null`
- Products with no supplier return `"supplier": null` — not an error

### Logic Flow
1. Verify company exists → 404 if not
2. Query all inventory rows where `quantity < low_stock_threshold`
3. For each item, check if there was a sale in the last 30 days — skip if not
4. Calculate `avg_daily_sales` from `inventory_logs`
5. Compute `days_until_stockout`
6. Build and return the alert object

### Edge Cases Handled
- Company not found → `404`
- No alerts → `200` with empty list (not an error)
- No supplier on product → `supplier: null`
- No recent sales → product skipped
- Zero daily sales velocity → `days_until_stockout: null`

### What I'd Improve With More Time
- Pagination (`?page=1&limit=20`)
- Filter by warehouse (`?warehouse_id=`)
- Redis caching for high-traffic companies
- Sort alerts by `days_until_stockout` ascending (most urgent first)

---

## Tech Stack Assumed
- **Language:** Python
- **Framework:** Flask
- **ORM:** SQLAlchemy
- **Database:** PostgreSQL

---

*Submitted as part of Bynry Backend Engineering Intern application.*
