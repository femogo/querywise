import math
import re
import unicodedata
from collections import Counter

from pydantic import BaseModel, Field


class VerifiedQuery(BaseModel, frozen=True):
    """Audited few-shot SQL example aligned with the querywise PostgreSQL schema."""

    query_id: str = Field(description="Unique snake_case identifier for the verified query.")
    question: str = Field(description="Representative natural-language business question.")
    tags: tuple[str, ...] = Field(default_factory=tuple)
    sql: str = Field(description="Verified read-only PostgreSQL SELECT query.")
    tables_used: tuple[str, ...] = Field(default_factory=tuple)
    explanation: str = Field(default="")


DEFAULT_VERIFIED_QUERIES: tuple[VerifiedQuery, ...] = (
    VerifiedQuery(
        query_id="net_revenue_by_category",
        question="¿Cuáles son los ingresos netos y unidades vendidas por categoría de producto?",
        tags=("ingresos", "ventas", "categoria", "unidades", "productos", "revenue", "category"),
        sql=(
            "SELECT c.name AS category_name, c.department, SUM(oi.quantity) AS units_sold, "
            "ROUND(SUM(oi.quantity * oi.unit_price_applied * "
            "(1 - oi.discount_pct / 100.0)), 2) AS net_revenue "
            "FROM categories c "
            "JOIN products p ON p.category_id = c.category_id "
            "JOIN order_items oi ON oi.product_id = p.product_id "
            "JOIN orders o ON o.order_id = oi.order_id "
            "WHERE o.status NOT IN ('cancelled', 'refunded') "
            "GROUP BY c.category_id, c.name, c.department ORDER BY net_revenue DESC"
        ),
        tables_used=("categories", "products", "order_items", "orders"),
        explanation="Joins categories -> products -> order_items -> orders filtering valid orders.",
    ),
    VerifiedQuery(
        query_id="gross_margin_vs_target_by_category",
        question=(
            "¿Cuál es el margen bruto y margen porcentual real "
            "frente al objetivo por categoría?"
        ),
        tags=(
            "margen",
            "margen bruto",
            "beneficio",
            "rentabilidad",
            "objetivo",
            "categoria",
            "margin",
        ),
        sql=(
            "SELECT c.name AS category_name, c.target_margin_pct, "
            "ROUND(SUM(oi.quantity * (oi.unit_price_applied * "
            "(1 - oi.discount_pct / 100.0) - p.unit_cost)), 2) AS gross_profit, "
            "ROUND(100.0 * SUM(oi.quantity * (oi.unit_price_applied * "
            "(1 - oi.discount_pct / 100.0) - p.unit_cost)) / "
            "NULLIF(SUM(oi.quantity * oi.unit_price_applied * "
            "(1 - oi.discount_pct / 100.0)), 0), 2) AS realized_margin_pct "
            "FROM categories c "
            "JOIN products p ON p.category_id = c.category_id "
            "JOIN order_items oi ON oi.product_id = p.product_id "
            "JOIN orders o ON o.order_id = oi.order_id "
            "WHERE o.status NOT IN ('cancelled', 'refunded') "
            "GROUP BY c.category_id, c.name, c.target_margin_pct ORDER BY gross_profit DESC"
        ),
        tables_used=("categories", "products", "order_items", "orders"),
        explanation=(
            "Computes net discounted revenue minus unit_cost and compares with target_margin_pct."
        ),
    ),
    VerifiedQuery(
        query_id="aov_and_revenue_by_channel",
        question="Compara pedidos, ticket medio, ingresos netos y brutos por canal de venta",
        tags=(
            "canal",
            "ticket medio",
            "ingresos brutos",
            "ingresos netos",
            "iva",
            "channel",
            "aov",
        ),
        sql=(
            "SELECT o.channel, COUNT(DISTINCT o.order_id) AS valid_orders, "
            "ROUND(AVG(o.subtotal_amount), 2) AS average_order_value, "
            "ROUND(SUM(o.subtotal_amount), 2) AS net_revenue, "
            "ROUND(SUM(o.total_amount), 2) AS gross_revenue "
            "FROM orders o WHERE o.status NOT IN ('cancelled', 'refunded') "
            "GROUP BY o.channel ORDER BY net_revenue DESC"
        ),
        tables_used=("orders",),
        explanation="Aggregates valid orders at order grain avoiding line-item duplication.",
    ),
    VerifiedQuery(
        query_id="top_customers_by_spend",
        question="¿Quiénes son los 10 mejores clientes por facturación neta y qué segmento tienen?",
        tags=(
            "clientes",
            "mejores clientes",
            "segmento",
            "vip",
            "corporate",
            "customers",
            "segment",
        ),
        sql=(
            "SELECT cu.customer_id, cu.full_name, cu.segment, cu.country, cu.city, "
            "COUNT(DISTINCT o.order_id) AS valid_orders, "
            "ROUND(SUM(o.subtotal_amount), 2) AS net_revenue "
            "FROM customers cu JOIN orders o ON o.customer_id = cu.customer_id "
            "WHERE o.status NOT IN ('cancelled', 'refunded') "
            "GROUP BY cu.customer_id, cu.full_name, cu.segment, cu.country, cu.city "
            "ORDER BY net_revenue DESC LIMIT 10"
        ),
        tables_used=("customers", "orders"),
        explanation=(
            "Selects only non-PII customer columns (excludes email, tax_id, password_hash)."
        ),
    ),
    VerifiedQuery(
        query_id="monthly_revenue_trend",
        question="Muestra la evolución mensual de ingresos netos y pedidos válidos",
        tags=("mensual", "mes", "evolucion", "tendencia", "historico", "monthly", "trend"),
        sql=(
            "SELECT DATE_TRUNC('month', o.created_at)::DATE AS order_month, "
            "COUNT(DISTINCT o.order_id) AS valid_orders, "
            "ROUND(SUM(o.subtotal_amount), 2) AS net_revenue "
            "FROM orders o WHERE o.status NOT IN ('cancelled', 'refunded') "
            "GROUP BY DATE_TRUNC('month', o.created_at) ORDER BY order_month ASC"
        ),
        tables_used=("orders",),
        explanation="Uses DATE_TRUNC('month', o.created_at) for chronological monthly rollups.",
    ),
    VerifiedQuery(
        query_id="cancellation_rate_by_channel",
        question="¿Cuál es la tasa de cancelación y devolución por canal de venta?",
        tags=("cancelacion", "devolucion", "tasa", "estado", "cancelled", "refunded"),
        sql=(
            "SELECT o.channel, COUNT(*) AS total_orders, "
            "COUNT(*) FILTER (WHERE o.status IN ('cancelled', 'refunded')) AS lost_orders, "
            "ROUND(100.0 * COUNT(*) FILTER (WHERE o.status IN ('cancelled', 'refunded')) / "
            "NULLIF(COUNT(*), 0), 2) AS cancellation_refund_pct "
            "FROM orders o GROUP BY o.channel ORDER BY cancellation_refund_pct DESC"
        ),
        tables_used=("orders",),
        explanation=(
            "Includes all order statuses in the denominator to compute accurate loss rates."
        ),
    ),
    VerifiedQuery(
        query_id="active_products_low_stock",
        question=(
            "¿Qué productos activos tienen menos de 25 unidades en "
            "stock y cuánto han vendido?"
        ),
        tags=("stock", "inventario", "productos activos", "sku", "inventory", "products"),
        sql=(
            "SELECT p.sku, p.name AS product_name, c.name AS category_name, p.stock_quantity, "
            "COALESCE(SUM(oi.quantity) FILTER "
            "(WHERE o.status NOT IN ('cancelled', 'refunded')), 0) AS valid_units_sold "
            "FROM products p JOIN categories c ON c.category_id = p.category_id "
            "LEFT JOIN order_items oi ON oi.product_id = p.product_id "
            "LEFT JOIN orders o ON o.order_id = oi.order_id "
            "WHERE p.is_active = TRUE AND p.stock_quantity < 25 "
            "GROUP BY p.product_id, p.sku, p.name, c.name, p.stock_quantity "
            "ORDER BY p.stock_quantity ASC"
        ),
        tables_used=("products", "categories", "order_items", "orders"),
        explanation="Uses LEFT JOIN so active low-stock products with zero sales still appear.",
    ),
    VerifiedQuery(
        query_id="open_support_tickets_by_priority",
        question=(
            "¿Cuántos tickets de soporte abiertos o en progreso hay "
            "por prioridad y categoría?"
        ),
        tags=("soporte", "tickets", "incidencias", "prioridad", "abiertos", "support", "priority"),
        sql=(
            "SELECT st.priority, st.category, COUNT(*) AS open_tickets "
            "FROM support_tickets st WHERE st.status IN ('open', 'in_progress') "
            "GROUP BY st.priority, st.category ORDER BY open_tickets DESC"
        ),
        tables_used=("support_tickets",),
        explanation="Filters support_tickets to active unresolved statuses (open, in_progress).",
    ),
)

_STOPWORDS = frozenset(
    {
        "de",
        "la",
        "el",
        "los",
        "las",
        "en",
        "por",
        "con",
        "para",
        "que",
        "cual",
        "cuales",
        "como",
        "del",
        "al",
        "un",
        "una",
        "son",
        "hay",
        "the",
        "and",
        "for",
        "with",
        "are",
        "what",
        "show",
    }
)


def _normalize_and_tokenize(text: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    clean = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    tokens = re.findall(r"[a-z0-9_]{2,}", clean)
    return [tok for tok in tokens if tok not in _STOPWORDS]


def _cosine_similarity(vec_a: Counter[str], vec_b: Counter[str]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a) & set(vec_b)
    if not common:
        return 0.0
    dot = sum(vec_a[tok] * vec_b[tok] for tok in common)
    norm_a = math.sqrt(sum(val * val for val in vec_a.values()))
    norm_b = math.sqrt(sum(val * val for val in vec_b.values()))
    return 0.0 if (norm_a == 0.0 or norm_b == 0.0) else dot / (norm_a * norm_b)


def retrieve_verified_queries(
    question: str,
    examples: tuple[VerifiedQuery, ...] = DEFAULT_VERIFIED_QUERIES,
    top_k: int = 2,
) -> list[VerifiedQuery]:
    """Retrieve the top_k most similar verified SQL queries for few-shot grounding."""
    if top_k <= 0 or not examples:
        return []
    q_tokens = _normalize_and_tokenize(question)
    if not q_tokens:
        return list(examples[:top_k])

    q_vec = Counter(q_tokens)
    scored: list[tuple[float, int, VerifiedQuery]] = []
    for idx, example in enumerate(examples):
        doc_tokens = _normalize_and_tokenize(example.question) + (
            _normalize_and_tokenize(" ".join(example.tags)) * 2
        )
        sim = _cosine_similarity(q_vec, Counter(doc_tokens))
        if sim > 0.0:
            scored.append((sim, -idx, example))

    if not scored:
        return list(examples[:top_k])

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored[:top_k]]


def render_verified_queries_context(queries: list[VerifiedQuery]) -> str:
    """Format retrieved verified SQL examples for the Text-to-SQL prompt."""
    if not queries:
        return ""
    lines = [
        "### VERIFIED SQL EXAMPLES (FEW-SHOT REFERENCE)",
        "Adapt these audited PostgreSQL patterns (joins, filters, safe columns) when applicable:",
        "",
    ]
    for idx, item in enumerate(queries, start=1):
        lines.append(f"{idx}. **Question**: {item.question}")
        if item.explanation:
            lines.append(f"   - Pattern note: {item.explanation}")
        lines.append(f"   ```sql\n   {item.sql}\n   ```")
    return "\n".join(lines)
