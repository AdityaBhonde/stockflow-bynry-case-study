-- ============================================================
-- Bynry Backend Intern Case Study - Part 2: Database Design
-- Author: Aditya Bhonde | VIT Pune, SY
-- ============================================================

-- ---------------------------------------------------------------
-- DESIGN DECISIONS:
--
-- 1. NUMERIC(10,2) for price instead of FLOAT
--    Avoids floating point precision bugs when dealing with money
--
-- 2. inventory_logs for audit trail + sales velocity calculation
--    Every stock change is recorded with a reason. This powers
--    the low-stock alert's "days_until_stockout" calculation.
--
-- 3. UNIQUE(product_id, warehouse_id) in inventory table
--    Prevents duplicate rows for same product in same warehouse
--
-- 4. low_stock_threshold lives on products table
--    Allows per-product thresholds instead of a global value
--
-- 5. bundle_items table for product bundles
--    Self-referential join on products for bundle → component
--
-- 6. Indexes added on commonly queried/filtered columns
-- ---------------------------------------------------------------

-- ---------------------------------------------------------------
-- QUESTIONS I WOULD ASK THE PRODUCT TEAM:
--
-- 1. Can a product belong to multiple companies, or is the
--    catalog per-company?
-- 2. What defines "recent sales activity" — last 7 or 30 days?
--    Is this configurable per company?
-- 3. Can one product have multiple suppliers?
-- 4. Can inventory go below zero (backorders allowed)?
-- 5. Are bundle stock levels calculated from components, or
--    tracked separately?
-- 6. Do we need multi-currency support for pricing?
-- 7. Is there a concept of "reserved" stock for pending orders?
-- 8. Should we support soft-deletes (is_deleted flag) for
--    products that are discontinued?
-- ---------------------------------------------------------------


-- Companies using StockFlow
CREATE TABLE companies (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);


-- Warehouses belong to a company
CREATE TABLE warehouses (
    id          SERIAL PRIMARY KEY,
    company_id  INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    location    VARCHAR(500),
    created_at  TIMESTAMP DEFAULT NOW()
);


-- Suppliers are linked to companies
CREATE TABLE suppliers (
    id              SERIAL PRIMARY KEY,
    company_id      INT NOT NULL REFERENCES companies(id),
    name            VARCHAR(255) NOT NULL,
    contact_email   VARCHAR(255),
    phone           VARCHAR(50),
    created_at      TIMESTAMP DEFAULT NOW()
);


-- Master product catalog per company
CREATE TABLE products (
    id                  SERIAL PRIMARY KEY,
    company_id          INT NOT NULL REFERENCES companies(id),
    supplier_id         INT REFERENCES suppliers(id) ON DELETE SET NULL,
    name                VARCHAR(255) NOT NULL,
    sku                 VARCHAR(100) NOT NULL UNIQUE,         -- globally unique
    price               NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    product_type        VARCHAR(50) DEFAULT 'standard',      -- 'standard' or 'bundle'
    low_stock_threshold INT DEFAULT 10 CHECK (low_stock_threshold >= 0),
    created_at          TIMESTAMP DEFAULT NOW()
);


-- Inventory per product per warehouse (many-to-many)
CREATE TABLE inventory (
    id              SERIAL PRIMARY KEY,
    product_id      INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    warehouse_id    INT NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    quantity        INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (product_id, warehouse_id)   -- one row per product per warehouse
);


-- Audit log — every inventory change is recorded here
-- Used for: audit trail + sales velocity (days_until_stockout)
CREATE TABLE inventory_logs (
    id              SERIAL PRIMARY KEY,
    product_id      INT NOT NULL REFERENCES products(id),
    warehouse_id    INT NOT NULL REFERENCES warehouses(id),
    change_quantity INT NOT NULL,       -- positive = restock, negative = sale/removal
    reason          VARCHAR(100),       -- 'sale', 'restock', 'adjustment', 'return'
    created_at      TIMESTAMP DEFAULT NOW()
);


-- Bundle products contain other products (self-referential)
CREATE TABLE bundle_items (
    id              SERIAL PRIMARY KEY,
    bundle_id       INT NOT NULL REFERENCES products(id),
    component_id    INT NOT NULL REFERENCES products(id),
    quantity        INT NOT NULL DEFAULT 1 CHECK (quantity > 0),
    UNIQUE (bundle_id, component_id)    -- no duplicate components in a bundle
);


-- ---------------------------------------------------------------
-- INDEXES — for performance on common query patterns
-- ---------------------------------------------------------------

-- Low-stock alert query filters by company and joins inventory + products
CREATE INDEX idx_products_company      ON products(company_id);
CREATE INDEX idx_inventory_product     ON inventory(product_id);
CREATE INDEX idx_inventory_warehouse   ON inventory(warehouse_id);

-- inventory_logs is queried by product, warehouse, and date range frequently
CREATE INDEX idx_logs_product          ON inventory_logs(product_id);
CREATE INDEX idx_logs_warehouse        ON inventory_logs(warehouse_id);
CREATE INDEX idx_logs_created_at       ON inventory_logs(created_at);

-- Warehouses are often filtered by company
CREATE INDEX idx_warehouses_company    ON warehouses(company_id);
