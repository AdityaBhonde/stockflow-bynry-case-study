# ============================================================
# Bynry Backend Intern Case Study - Part 3: API Implementation
# Author: Aditya Bhonde | VIT Pune, SY
# ============================================================

# ---------------------------------------------------------------
# ENDPOINT: GET /api/companies/<company_id>/alerts/low-stock
#
# ASSUMPTIONS MADE:
# 1. "Recent sales activity" = at least 1 stock decrease in
#    the last 30 days (change_quantity < 0 in inventory_logs)
# 2. days_until_stockout = current_stock / avg_daily_sales
#    where avg_daily_sales is calculated over the last 30 days
# 3. If avg_daily_sales is 0 but stock is still low,
#    days_until_stockout is returned as null
# 4. Low stock condition: current quantity < low_stock_threshold
# 5. Products with no supplier return supplier as null (not error)
# 6. "30 days" window is a constant — ideally this would be
#    a config value or query param in production
# ---------------------------------------------------------------

from flask import jsonify
from datetime import datetime, timedelta
from sqlalchemy import func


@app.route('/api/companies/<int:company_id>/alerts/low-stock', methods=['GET'])
def low_stock_alerts(company_id):

    # ----------------------------------------------------------
    # Step 1: Verify the company exists
    # ----------------------------------------------------------
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"error": "Company not found"}), 404

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    # ----------------------------------------------------------
    # Step 2: Fetch all inventory rows for this company where
    # current quantity is below the product's threshold.
    # Join Product, Warehouse, and optionally Supplier.
    # ----------------------------------------------------------
    low_stock_items = (
        db.session.query(Inventory, Product, Warehouse, Supplier)
        .join(Product, Inventory.product_id == Product.id)
        .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
        .outerjoin(Supplier, Product.supplier_id == Supplier.id)  # optional
        .filter(
            Product.company_id == company_id,
            Inventory.quantity < Product.low_stock_threshold
        )
        .all()
    )

    # Return early if no items are below threshold
    if not low_stock_items:
        return jsonify({"alerts": [], "total_alerts": 0}), 200

    alerts = []

    for inventory, product, warehouse, supplier in low_stock_items:

        # ------------------------------------------------------
        # Step 3: Check if product had any sales in last 30 days
        # (Only alert for products with recent sales activity)
        # ------------------------------------------------------
        recent_sale = InventoryLog.query.filter(
            InventoryLog.product_id == product.id,
            InventoryLog.warehouse_id == warehouse.id,
            InventoryLog.change_quantity < 0,       # outgoing = sale
            InventoryLog.created_at >= thirty_days_ago
        ).first()

        # Skip products with no recent sales activity
        if not recent_sale:
            continue

        # ------------------------------------------------------
        # Step 4: Calculate average daily sales over last 30 days
        # Sum all negative changes (sales) and divide by 30
        # ------------------------------------------------------
        total_sold = db.session.query(
            func.sum(InventoryLog.change_quantity)
        ).filter(
            InventoryLog.product_id == product.id,
            InventoryLog.warehouse_id == warehouse.id,
            InventoryLog.change_quantity < 0,
            InventoryLog.created_at >= thirty_days_ago
        ).scalar() or 0

        total_sold = abs(total_sold)            # convert negative sum to positive
        avg_daily_sales = total_sold / 30       # average over 30 day window

        # ------------------------------------------------------
        # Step 5: Calculate days until stockout
        # If avg_daily_sales is 0, return null (can't divide by 0)
        # ------------------------------------------------------
        if avg_daily_sales > 0:
            days_until_stockout = round(inventory.quantity / avg_daily_sales)
        else:
            days_until_stockout = None  # Low stock but no recent sales velocity

        # ------------------------------------------------------
        # Step 6: Build the alert object for this product
        # ------------------------------------------------------
        alert = {
            "product_id": product.id,
            "product_name": product.name,
            "sku": product.sku,
            "warehouse_id": warehouse.id,
            "warehouse_name": warehouse.name,
            "current_stock": inventory.quantity,
            "threshold": product.low_stock_threshold,
            "days_until_stockout": days_until_stockout,
            "supplier": {
                "id": supplier.id,
                "name": supplier.name,
                "contact_email": supplier.contact_email
            } if supplier else None     # gracefully handle missing supplier
        }

        alerts.append(alert)

    # ----------------------------------------------------------
    # Step 7: Return final response
    # ----------------------------------------------------------
    return jsonify({
        "alerts": alerts,
        "total_alerts": len(alerts)
    }), 200


# ---------------------------------------------------------------
# EDGE CASES HANDLED:
#
# 1. Company not found           → 404 with clear error message
# 2. No low-stock items          → 200 with empty alerts list
# 3. Product has no supplier     → supplier field returned as null
# 4. No sales in last 30 days    → product skipped (not "active")
# 5. Zero avg daily sales        → days_until_stockout = null
# 6. Negative price/quantity     → prevented at DB constraint level
#
# IMPROVEMENTS FOR PRODUCTION:
#
# - Add pagination: ?page=1&limit=20
# - Add ?warehouse_id= filter to narrow by specific warehouse
# - Cache results with Redis for high-traffic companies
# - Move 30-day window to a config constant or make it a param
# - Add sorting: sort by days_until_stockout ascending (urgent first)
# ---------------------------------------------------------------
