import re
import unicodedata

from pydantic import BaseModel, Field


class MetricDefinition(BaseModel, frozen=True):
    """Canonical business metric specification for grounded Text-to-SQL generation."""

    metric_id: str = Field(description="Unique snake_case identifier for the metric.")
    name: str = Field(description="Human-readable metric name.")
    aliases: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Search keywords and synonyms in Spanish and English.",
    )
    description: str = Field(description="Business definition and scope of the metric.")
    sql_expression: str = Field(description="Canonical PostgreSQL aggregation expression.")
    required_tables: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Tables required to compute this metric.",
    )
    mandatory_filters: tuple[str, ...] = Field(
        default_factory=tuple,
        description="SQL WHERE predicates required unless explicitly overridden.",
    )
    default_assumptions: str = Field(
        default="",
        description="Assumptions to disclose when the user query is underspecified.",
    )


DEFAULT_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        metric_id="net_revenue",
        name="Net Revenue (Ingresos Netos sin IVA)",
        aliases=(
            "ingresos",
            "ingresos netos",
            "ventas",
            "ventas netas",
            "facturacion",
            "revenue",
            "net revenue",
            "sales",
            "sin iva",
        ),
        description=(
            "Total sales revenue before tax (sin IVA) across valid orders. "
            "Use orders.subtotal_amount at order grain or discounted line amounts at item grain."
        ),
        sql_expression=(
            "SUM(orders.subtotal_amount) -- or at item grain: "
            "SUM(order_items.quantity * order_items.unit_price_applied * "
            "(1 - order_items.discount_pct / 100.0))"
        ),
        required_tables=("orders",),
        mandatory_filters=("orders.status NOT IN ('cancelled', 'refunded')",),
        default_assumptions="Excludes cancelled/refunded orders; excludes VAT/tax (sin IVA).",
    ),
    MetricDefinition(
        metric_id="gross_revenue",
        name="Gross Revenue (Ingresos Brutos con IVA)",
        aliases=(
            "ingresos brutos",
            "ventas brutas",
            "total facturado",
            "con iva",
            "gross revenue",
            "gross sales",
            "total_amount",
        ),
        description="Total billed revenue including tax and shipping across valid orders.",
        sql_expression="SUM(orders.total_amount)",
        required_tables=("orders",),
        mandatory_filters=("orders.status NOT IN ('cancelled', 'refunded')",),
        default_assumptions="Excludes cancelled/refunded orders; includes VAT/tax (con IVA).",
    ),
    MetricDefinition(
        metric_id="average_order_value",
        name="Average Order Value (Ticket Medio)",
        aliases=(
            "ticket medio",
            "pedido medio",
            "promedio por pedido",
            "gasto medio",
            "aov",
            "average order value",
            "basket size",
        ),
        description="Average net revenue per valid order.",
        sql_expression="ROUND(AVG(orders.subtotal_amount), 2)",
        required_tables=("orders",),
        mandatory_filters=("orders.status NOT IN ('cancelled', 'refunded')",),
        default_assumptions=(
            "Calculated on net subtotal_amount excluding cancelled/refunded orders."
        ),
    ),
    MetricDefinition(
        metric_id="gross_margin",
        name="Gross Profit & Margin (Margen Bruto)",
        aliases=(
            "margen",
            "margen bruto",
            "beneficio",
            "beneficio bruto",
            "rentabilidad",
            "margin",
            "gross margin",
            "profit",
            "coste",
        ),
        description=(
            "Net sales revenue minus product unit cost across sold items in valid orders."
        ),
        sql_expression=(
            "SUM(order_items.quantity * (order_items.unit_price_applied * "
            "(1 - order_items.discount_pct / 100.0) - products.unit_cost))"
        ),
        required_tables=("orders", "order_items", "products"),
        mandatory_filters=("orders.status NOT IN ('cancelled', 'refunded')",),
        default_assumptions="Net of item discounts minus products.unit_cost on valid orders.",
    ),
    MetricDefinition(
        metric_id="valid_order_count",
        name="Valid Order Count (Pedidos Completados/Válidos)",
        aliases=(
            "pedidos",
            "numero de pedidos",
            "volumen de pedidos",
            "ordenes",
            "compras",
            "order count",
            "orders",
        ),
        description="Count of distinct non-cancelled and non-refunded orders.",
        sql_expression="COUNT(DISTINCT orders.order_id)",
        required_tables=("orders",),
        mandatory_filters=("orders.status NOT IN ('cancelled', 'refunded')",),
        default_assumptions="Excludes orders with status cancelled or refunded.",
    ),
    MetricDefinition(
        metric_id="cancellation_refund_rate",
        name="Cancellation & Refund Rate (Tasa de Cancelación y Devolución)",
        aliases=(
            "cancelaciones",
            "devoluciones",
            "tasa de cancelacion",
            "tasa de devolucion",
            "reembolsos",
            "cancelled",
            "refunded",
            "cancellation rate",
            "refund rate",
        ),
        description="Percentage of all orders that ended in cancelled or refunded status.",
        sql_expression=(
            "ROUND(100.0 * COUNT(*) FILTER (WHERE orders.status IN ('cancelled', 'refunded')) "
            "/ NULLIF(COUNT(*), 0), 2)"
        ),
        required_tables=("orders",),
        mandatory_filters=(),
        default_assumptions="Evaluated over all orders including cancelled and refunded statuses.",
    ),
    MetricDefinition(
        metric_id="active_customers",
        name="Active Customers (Clientes Activos con Compra)",
        aliases=(
            "clientes",
            "clientes activos",
            "compradores",
            "segmento",
            "clientes por ciudad",
            "customers",
            "active customers",
            "buyers",
        ),
        description="Distinct customers with at least one valid (non-cancelled/refunded) order.",
        sql_expression="COUNT(DISTINCT orders.customer_id)",
        required_tables=("customers", "orders"),
        mandatory_filters=("orders.status NOT IN ('cancelled', 'refunded')",),
        default_assumptions="Counts customers with at least one non-cancelled/refunded order.",
    ),
)


def _normalize_text(text: str) -> str:
    """Lowercase text and strip diacritics for accent-insensitive matching."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9_]+", " ", without_accents).strip()


def _tokenize(text: str) -> set[str]:
    """Extract normalized tokens of length >= 2."""
    return {tok for tok in _normalize_text(text).split() if len(tok) >= 2}


def retrieve_relevant_metrics(
    question: str,
    catalog: tuple[MetricDefinition, ...] = DEFAULT_METRICS,
    top_k: int = 3,
) -> list[MetricDefinition]:
    """Rank and return up to top_k metrics matching the user question."""
    if top_k <= 0 or not catalog:
        return []

    norm_q = _normalize_text(question)
    q_tokens = _tokenize(question)
    if not q_tokens:
        return list(catalog[: min(2, top_k)])

    scored: list[tuple[float, int, MetricDefinition]] = []
    for idx, metric in enumerate(catalog):
        score = 0.0
        for alias in metric.aliases:
            norm_alias = _normalize_text(alias)
            if not norm_alias:
                continue
            if norm_alias in norm_q:
                score += 4.0 + (0.5 * len(norm_alias.split()))
            else:
                alias_tokens = _tokenize(alias)
                overlap = len(q_tokens & alias_tokens)
                if overlap:
                    score += 2.0 * (overlap / len(alias_tokens))

        desc_tokens = _tokenize(f"{metric.name} {metric.description}")
        desc_overlap = len(q_tokens & desc_tokens)
        score += 0.5 * desc_overlap

        if score > 0:
            scored.append((score, -idx, metric))

    if not scored:
        # Default fallback to core revenue & order count definitions
        return [m for m in catalog if m.metric_id in {"net_revenue", "valid_order_count"}][:top_k]

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored[:top_k]]


def render_metrics_context(metrics: list[MetricDefinition]) -> str:
    """Format retrieved metrics as structured markdown for the SQL generation prompt."""
    if not metrics:
        return ""

    lines = [
        "### RELEVANT CANONICAL METRICS",
        "Use these exact formulas and filters if the question involves these concepts:",
        "",
    ]
    for metric in metrics:
        tables = ", ".join(metric.required_tables) if metric.required_tables else "none"
        filters = " AND ".join(metric.mandatory_filters) if metric.mandatory_filters else "none"
        lines.append(f"- **{metric.name}** (`{metric.metric_id}`): {metric.description}")
        lines.append(f"  - Canonical SQL: `{metric.sql_expression}`")
        lines.append(f"  - Required tables: `{tables}` | Mandatory filters: `{filters}`")
        if metric.default_assumptions:
            lines.append(f"  - Default assumption: {metric.default_assumptions}")
    return "\n".join(lines)
