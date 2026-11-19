"""Semantic layer: business glossary, canonical metrics catalog, and verified SQL examples."""

from querywise.semantic.business_glossary import (
    DEFAULT_BUSINESS_RULES,
    BusinessRule,
    render_business_glossary,
)
from querywise.semantic.metrics_catalog import (
    DEFAULT_METRICS,
    MetricDefinition,
    render_metrics_context,
    retrieve_relevant_metrics,
)
from querywise.semantic.verified_queries import (
    DEFAULT_VERIFIED_QUERIES,
    VerifiedQuery,
    render_verified_queries_context,
    retrieve_verified_queries,
)


def build_semantic_context(
    question: str,
    top_k_metrics: int = 3,
    top_k_examples: int = 2,
) -> str:
    """Assemble glossary rules, relevant canonical metrics, and few-shot verified SQL."""
    sections = [render_business_glossary()]
    metrics_block = render_metrics_context(retrieve_relevant_metrics(question, top_k=top_k_metrics))
    if metrics_block:
        sections.append(metrics_block)
    examples_block = render_verified_queries_context(
        retrieve_verified_queries(question, top_k=top_k_examples)
    )
    if examples_block:
        sections.append(examples_block)
    return "\n\n".join(sections)


__all__ = [
    "BusinessRule",
    "DEFAULT_BUSINESS_RULES",
    "DEFAULT_METRICS",
    "DEFAULT_VERIFIED_QUERIES",
    "MetricDefinition",
    "VerifiedQuery",
    "build_semantic_context",
    "render_business_glossary",
    "render_metrics_context",
    "render_verified_queries_context",
    "retrieve_relevant_metrics",
    "retrieve_verified_queries",
]
