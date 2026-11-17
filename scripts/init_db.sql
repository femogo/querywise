-- ============================================================================
-- Esquema de negocio querywise + Rol de solo lectura (Capa 3 Defensa)
-- ============================================================================

CREATE TABLE IF NOT EXISTS categories (
    category_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    department VARCHAR(100) NOT NULL,
    target_margin_pct NUMERIC(5, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    sku VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    unit_cost NUMERIC(10, 2) NOT NULL CHECK (unit_cost >= 0),
    list_price NUMERIC(10, 2) NOT NULL CHECK (list_price >= 0),
    stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id SERIAL PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(180) NOT NULL UNIQUE,
    segment VARCHAR(30) NOT NULL CHECK (segment IN ('retail', 'vip', 'corporate')),
    country VARCHAR(60) NOT NULL,
    city VARCHAR(80) NOT NULL,
    -- Columnas PII sensibles que el validador AST debe bloquear
    tax_id VARCHAR(30) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    registered_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'paid', 'shipped', 'delivered', 'cancelled', 'refunded')),
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('web', 'mobile', 'b2b_portal')),
    subtotal_amount NUMERIC(12, 2) NOT NULL,
    tax_amount NUMERIC(12, 2) NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    shipped_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_applied NUMERIC(10, 2) NOT NULL,
    discount_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.00
);

CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_id INTEGER NULL REFERENCES orders(order_id),
    category VARCHAR(50) NOT NULL,
    priority VARCHAR(20) NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    subject VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

-- Tabla estrictamente privada: querywise_ro NO tendra acceso ni siquiera de lectura
CREATE TABLE IF NOT EXISTS internal_audit_logs (
    log_id SERIAL PRIMARY KEY,
    actor VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    secret_token_ref VARCHAR(255) NOT NULL,
    logged_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indices para consultas analiticas frecuentes
CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);

-- ============================================================================
-- Creacion del rol de solo lectura (querywise_ro) y privilegios minimos
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'querywise_ro') THEN
        CREATE ROLE querywise_ro LOGIN PASSWORD 'change_me_ro';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE querywise TO querywise_ro;
GRANT USAGE ON SCHEMA public TO querywise_ro;

-- Solo SELECT en las 6 tablas de negocio permitidas
GRANT SELECT ON TABLE
    categories,
    products,
    customers,
    orders,
    order_items,
    support_tickets
TO querywise_ro;

-- Revocar explicitamente acceso a tablas internas y permisos de escritura
REVOKE ALL ON TABLE internal_audit_logs FROM querywise_ro;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;