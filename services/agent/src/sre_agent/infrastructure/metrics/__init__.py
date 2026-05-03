from sre_agent.infrastructure.metrics.composite_adapter import CompositeMetricsAdapter
from sre_agent.infrastructure.metrics.prometheus_adapter import PrometheusMetricsAdapter

__all__ = ["CompositeMetricsAdapter", "PrometheusMetricsAdapter"]


def _maybe_azure_monitor():  # pragma: no cover
    """Optional import — only available when azure-monitor-query is installed."""
    from sre_agent.infrastructure.metrics.azure_monitor_adapter import (
        AzureMonitorMetricsAdapter,
    )

    return AzureMonitorMetricsAdapter
