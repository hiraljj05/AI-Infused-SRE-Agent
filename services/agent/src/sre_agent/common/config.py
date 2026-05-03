from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["dev", "test", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    http_port: int = 8000

    # LLM
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-3.5-sonnet"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = "https://github.com/sre-agent"
    openrouter_app_name: str = "SRE-Agent"

    # Embeddings
    embeddings_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embeddings_dim: int = 384

    # Persistence
    postgres_dsn: str = "postgresql+asyncpg://sre:sre@localhost:5432/sre_agent"
    redis_url: str = "redis://localhost:6379/0"

    # Vector DB
    # vector_backend: "pgvector" (default — uses postgres_dsn) or "qdrant" (legacy).
    vector_backend: Literal["pgvector", "qdrant"] = "pgvector"
    # Qdrant (only used when vector_backend == "qdrant")
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""  # required for Qdrant Cloud; empty for local
    qdrant_collection: str = "sre_knowledge"
    qdrant_lessons_collection: str = "lessons_learnt"

    # Metrics / logs
    prometheus_url: str = "http://localhost:9090"
    loki_url: str = "http://localhost:3100"

    # Elasticsearch (optional alternative to Loki)
    elasticsearch_url: str = ""
    elasticsearch_index_pattern: str = "logs-*"
    elasticsearch_username: str = ""
    elasticsearch_password: str = ""
    elasticsearch_api_key: str = ""
    elasticsearch_service_field: str = "service.name"
    elasticsearch_message_field: str = "message"
    elasticsearch_verify_tls: bool = True

    # Azure Monitor (optional supplement to Prometheus)
    azure_monitor_workspace_id: str = ""  # Log Analytics workspace ID for KQL queries
    azure_monitor_subscription_id: str = ""
    azure_monitor_resource_group: str = ""

    # Grafana
    grafana_url: str = "http://localhost:3001"
    grafana_username: str = "admin"
    grafana_password: str = "admin"
    grafana_api_key: str = ""

    # Jira (Atlassian Cloud); empty -> log-only adapter
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_status_poll_seconds: int = 30

    # Email (SMTP); empty host -> log-only adapter
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "sre-agent@example.com"
    smtp_use_tls: bool = True

    # Kubernetes
    kubeconfig: str | None = None
    k8s_in_cluster: bool = False
    target_namespace: str = "demo-store"

    # Teams
    microsoft_app_id: str = ""
    microsoft_app_password: str = ""
    microsoft_app_tenant_id: str = ""
    microsoft_app_type: str = "SingleTenant"

    # HIL saga
    hil_primary_timeout_seconds: int = 300
    hil_secondary_timeout_seconds: int = 180
    hil_commander_timeout_seconds: int = 120
    rca_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_auto_remediation_blast_radius: Literal["low", "medium", "high"] = "low"

    # OTEL
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "sre-agent"
    otel_resource_attributes: str = "service.name=sre-agent,service.version=0.1.0"

    # Reports
    weekly_digest_interval_seconds: int = 7 * 24 * 60 * 60  # 7 days; lower for demos

    # Azure AD OIDC (dashboard SSO)
    aad_tenant_id: str = ""  # "common" for multi-tenant + personal MS accounts
    aad_client_id: str = ""
    aad_client_secret: str = ""
    aad_redirect_uri: str = "http://localhost:8000/auth/callback"
    aad_post_login_redirect: str = "http://localhost:3030/"
    auth_session_secret: str = "dev-secret-change-me"
    auth_admin_emails: str = ""  # comma-separated emails granted admin role
    auth_required: bool = False  # when True, mutating endpoints require login


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
