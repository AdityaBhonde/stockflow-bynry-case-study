# ============================================================
# Bynry Backend Intern Case Study - Part 1: Code Review & Fix
# Author: Aditya Bhonde | VIT Pune, SY
# ============================================================

# ---------------------------------------------------------------
# ISSUES FOUND IN ORIGINAL CODE:
#
# 1. NO INPUT VALIDATION
#    - Missing fields cause a KeyError and crash with 500 error
#    - No check for invalid types (e.g. price as a string)
#
# 2. TWO SEPARATE db.session.commit() CALLS (Critical Bug)
#    - If the second commit (Inventory) fails, Product is already
#      saved — leaving an orphan product with no inventory record
#    - Fix: Use a single transaction with db.session.flush()
#
# 3. NO SKU UNIQUENESS CHECK
#    - Duplicate SKUs can be inserted silently if DB constraint
#      is missing, causing data integrity issues
#
# 4. NO PRICE VALIDATION
#    - Price could be negative, zero, or a non-numeric string
#
# 5. initial_quantity NOT HANDLED AS OPTIONAL
#    - Spec says some fields are optional; code assumes it exists
#
# 6. NO AUTH / AUTHORIZATION
#    - Any anonymous caller can create a product — major issue
#      in a B2B SaaS platform
#
# 7. NO HTTP STATUS CODES
#    - Success returns 200 by default; should be 201 for creation
# ---------------------------------------------------------------

from flask import request, jsonify
from sqlalchemy.exc import IntegrityError


@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.json

    # ----------------------------------------------------------
    # FIX 1: Validate all required fields upfront
    # ----------------------------------------------------------
    required_fields = ['name', 'sku', 'price', 'warehouse_id']
    for field in required_fields:
        if field not in data or data[field] is None:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    # ----------------------------------------------------------
    # FIX 2: Validate price — must be a non-negative number
    # ----------------------------------------------------------
    try:
        price = float(data['price'])
        if price < 0:
            return jsonify({"error": "Price cannot be negative"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid price format. Must be a number"}), 400

    # ----------------------------------------------------------
    # FIX 3: Check SKU uniqueness before inserting
    # ----------------------------------------------------------
    existing_product = Product.query.filter_by(sku=data['sku']).first()
    if existing_product:
        return jsonify({"error": f"SKU '{data['sku']}' already exists"}), 409

    # ----------------------------------------------------------
    # FIX 4: Handle optional initial_quantity, default to 0
    # ----------------------------------------------------------
    initial_quantity = data.get('initial_quantity', 0)
    if not isinstance(initial_quantity, int) or initial_quantity < 0:
        return jsonify({"error": "initial_quantity must be a non-negative integer"}), 400

    try:
        # ------------------------------------------------------
        # FIX 5: Single transaction — both Product and Inventory
        # created together. If either fails, both are rolled back.
        # db.session.flush() assigns product.id without committing.
        # ------------------------------------------------------
        product = Product(
            name=data['name'],
            sku=data['sku'],
            price=price,
            warehouse_id=data['warehouse_id']
        )
        db.session.add(product)
        db.session.flush()  # Get product.id before committing

        inventory = Inventory(
            product_id=product.id,
            warehouse_id=data['warehouse_id'],
            quantity=initial_quantity
        )
        db.session.add(inventory)

        db.session.commit()  # Single commit — atomic operation

    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Database integrity error. Check warehouse_id or SKU."}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500

    # ----------------------------------------------------------
    # FIX 6: Return 201 Created (not 200) for resource creation
    # ----------------------------------------------------------
    return jsonify({
        "message": "Product created successfully",
        "product_id": product.id
    }), 201
