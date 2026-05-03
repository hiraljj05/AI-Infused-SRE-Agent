from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings

from sre_agent.application.agent_graph import AgentGraphFactory
from sre_agent.application.agent_graph.nodes import AgentNodes
from sre_agent.application.saga import (
    ApprovalSagaScheduler,
    InsightsMonitorScheduler,
    JiraStatusPoller,
    SLAMonitorScheduler,
    WeeklyDigestScheduler,
)
from sre_agent.application.use_cases.log_insights import LogInsightsUseCase
from sre_agent.application.saga.approval_saga import SagaTimeouts
from sre_agent.application.use_cases import (
    AnswerOperationalQueryUseCase,
    CreateIncidentTicketUseCase,
    DetectIncidentUseCase,
    DiagnoseIncidentUseCase,
    ExecuteFixUseCase,
    GatherEvidenceUseCase,
    GeneratePostmortemUseCase,
    OnboardAppUseCase,
    ParseChatIntentUseCase,
    ProposeRemediationUseCase,
    RequestApprovalUseCase,
    ResolveApprovalUseCase,
    RunOnDemandInvestigationUseCase,
    SatisfySLAUseCase,
    StartSLATrackersUseCase,
    TriageIncidentUseCase,
    VerifyResolutionUseCase,
)
from sre_agent.application.use_cases.close_incident_with_human_resolution import (
    CloseIncidentWithHumanResolutionUseCase,
)
from sre_agent.application.use_cases.extract_lessons_learnt import (
    ExtractLessonsLearntUseCase,
)
from sre_agent.application.use_cases.find_similar_incidents import (
    FindSimilarIncidentsUseCase,
)
from sre_agent.application.use_cases.run_advisory_conversation import (
    RunAdvisoryConversationUseCase,
)
from sre_agent.common.config import AppSettings
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.infrastructure.embeddings import SentenceTransformersEmbeddingsAdapter
from sre_agent.infrastructure.grafana import GrafanaAdapter
from sre_agent.infrastructure.ticketing import (
    JiraCloudAdapter,
    LogOnlyEmailAdapter,
    LogOnlyJiraAdapter,
    SmtpEmailAdapter,
)
from sre_agent.infrastructure.k8s import KubernetesAdapter
from sre_agent.infrastructure.knowledge import (
    PgVectorKnowledgeAdapter,
    PgVectorLessonsAdapter,
    YamlEscalationLookupAdapter,
    YamlServiceCatalogAdapter,
)
from sre_agent.domain.ports.knowledge import KnowledgePort
from sre_agent.domain.ports.lessons import SimilarLessonsPort
from sre_agent.infrastructure.llm import OpenRouterLLMAdapter
from sre_agent.infrastructure.logs import ElasticsearchLogsAdapter, LokiLogsAdapter
from sre_agent.infrastructure.messaging import (
    TeamsApprovalNotificationAdapter,
    TeamsStatusNotificationAdapter,
)
from sre_agent.infrastructure.messaging.teams_adapter import ConversationReferenceStore
from sre_agent.infrastructure.metrics import (
    CompositeMetricsAdapter,
    PrometheusMetricsAdapter,
)
from sre_agent.infrastructure.persistence.postgres.uow import (
    SqlAlchemyUnitOfWork,
    make_engine,
    make_session_factory,
)


UoWFactory = Callable[[], UnitOfWork]


@dataclass(slots=True)
class Container:
    settings: AppSettings
    uow_factory: UoWFactory
    llm: OpenRouterLLMAdapter
    embeddings: SentenceTransformersEmbeddingsAdapter
    knowledge: KnowledgePort
    lessons_vec: SimilarLessonsPort
    metrics: Any
    logs: Any
    k8s: KubernetesAdapter
    service_catalog: YamlServiceCatalogAdapter
    escalation: YamlEscalationLookupAdapter
    grafana: GrafanaAdapter
    ticketing: Any
    teams_adapter: BotFrameworkAdapter
    conversation_refs: ConversationReferenceStore
    approval_notifier: TeamsApprovalNotificationAdapter
    status_notifier: TeamsStatusNotificationAdapter
    detect_uc: DetectIncidentUseCase
    triage_uc: TriageIncidentUseCase
    gather_uc: GatherEvidenceUseCase
    diagnose_uc: DiagnoseIncidentUseCase
    propose_uc: ProposeRemediationUseCase
    request_approval_uc: RequestApprovalUseCase
    resolve_approval_uc: ResolveApprovalUseCase
    execute_uc: ExecuteFixUseCase
    verify_uc: VerifyResolutionUseCase
    postmortem_uc: GeneratePostmortemUseCase
    answer_query_uc: AnswerOperationalQueryUseCase
    onboard_app_uc: OnboardAppUseCase
    create_ticket_uc: CreateIncidentTicketUseCase
    parse_intent_uc: ParseChatIntentUseCase
    investigate_uc: RunOnDemandInvestigationUseCase
    start_slas_uc: StartSLATrackersUseCase
    satisfy_sla_uc: SatisfySLAUseCase
    extract_lessons_uc: ExtractLessonsLearntUseCase
    close_incident_uc: CloseIncidentWithHumanResolutionUseCase
    find_similar_uc: FindSimilarIncidentsUseCase
    advisor_uc: RunAdvisoryConversationUseCase
    agent_graph_factory: AgentGraphFactory
    saga: ApprovalSagaScheduler
    sla_monitor: SLAMonitorScheduler
    digest_scheduler: WeeklyDigestScheduler
    insights_uc: LogInsightsUseCase
    insights_monitor: InsightsMonitorScheduler
    jira_status_poller: JiraStatusPoller


def build_container(*, settings: AppSettings, knowledge_base_root: Path) -> Container:
    # One async engine, one connection pool — shared by UoW + pgvector adapters.
    pg_engine = make_engine(settings.postgres_dsn)
    session_factory = make_session_factory(pg_engine)

    def uow_factory() -> UnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    # LLM + embeddings
    llm = OpenRouterLLMAdapter(
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        base_url=settings.openrouter_base_url,
        site_url=settings.openrouter_site_url,
        app_name=settings.openrouter_app_name,
    )
    embeddings = SentenceTransformersEmbeddingsAdapter(
        model_name=settings.embeddings_model,
        expected_dim=settings.embeddings_dim,
    )

    # Knowledge base — pgvector on the same Postgres as relational data.
    knowledge: KnowledgePort = PgVectorKnowledgeAdapter(engine=pg_engine, embeddings=embeddings)
    lessons_vec: SimilarLessonsPort = PgVectorLessonsAdapter(engine=pg_engine, embeddings=embeddings)
    service_catalog = YamlServiceCatalogAdapter(knowledge_base_root / "services")
    import os as _os
    _commander = _os.environ.get("INCIDENT_COMMANDER", "incident-commanders")
    escalation = YamlEscalationLookupAdapter(
        catalog=service_catalog,
        default_commander_group=_commander,
        default_primary=_os.environ.get("DEFAULT_ON_CALL_PRIMARY") or _commander,
        default_secondary=_os.environ.get("DEFAULT_ON_CALL_SECONDARY") or _commander,
    )

    # Observability adapters — auto-detect: prefer ELK if configured, else Loki
    prom = PrometheusMetricsAdapter(url=settings.prometheus_url)
    metrics: Any = prom
    if settings.azure_monitor_workspace_id:
        try:
            from sre_agent.infrastructure.metrics.azure_monitor_adapter import (
                AzureMonitorMetricsAdapter,
            )

            azure_metrics = AzureMonitorMetricsAdapter(
                workspace_id=settings.azure_monitor_workspace_id
            )
            metrics = CompositeMetricsAdapter(backends=[prom, azure_metrics])
        except ImportError:
            # azure-monitor-query not installed — stick with Prometheus only.
            pass
    if settings.elasticsearch_url:
        logs = ElasticsearchLogsAdapter(
            url=settings.elasticsearch_url,
            index_pattern=settings.elasticsearch_index_pattern,
            username=settings.elasticsearch_username or None,
            password=settings.elasticsearch_password or None,
            api_key=settings.elasticsearch_api_key or None,
            service_field=settings.elasticsearch_service_field,
            message_field=settings.elasticsearch_message_field,
            verify_tls=settings.elasticsearch_verify_tls,
        )
    else:
        logs = LokiLogsAdapter(url=settings.loki_url)
    k8s = KubernetesAdapter(
        in_cluster=settings.k8s_in_cluster,
        kubeconfig=settings.kubeconfig,
    )
    grafana = GrafanaAdapter(
        url=settings.grafana_url,
        api_key=settings.grafana_api_key or None,
        username=settings.grafana_username if not settings.grafana_api_key else None,
        password=settings.grafana_password if not settings.grafana_api_key else None,
    )

    # Teams adapter — for SingleTenant bots we MUST pass channel_auth_tenant
    # so the OAuth token endpoint is per-tenant (/{tenant}/...) instead of /common/...
    bot_settings = BotFrameworkAdapterSettings(
        app_id=settings.microsoft_app_id,
        app_password=settings.microsoft_app_password,
        channel_auth_tenant=(
            settings.microsoft_app_tenant_id
            if (settings.microsoft_app_type or "").lower() == "singletenant"
            else None
        ),
    )
    teams_adapter = BotFrameworkAdapter(bot_settings)
    conv_refs = ConversationReferenceStore()
    approval_notifier = TeamsApprovalNotificationAdapter(
        adapter=teams_adapter,
        bot_app_id=settings.microsoft_app_id,
        references=conv_refs,
    )
    status_notifier = TeamsStatusNotificationAdapter(
        adapter=teams_adapter,
        bot_app_id=settings.microsoft_app_id,
        references=conv_refs,
    )

    # Use cases
    detect_uc = DetectIncidentUseCase(uow=uow_factory())
    triage_uc = TriageIncidentUseCase(uow=uow_factory(), service_catalog=service_catalog)
    gather_uc = GatherEvidenceUseCase(
        uow=uow_factory(), metrics=metrics, logs=logs, k8s=k8s
    )
    diagnose_uc = DiagnoseIncidentUseCase(uow=uow_factory(), llm=llm, knowledge=knowledge)
    propose_uc = ProposeRemediationUseCase(uow=uow_factory(), llm=llm, knowledge=knowledge)
    request_approval_uc = RequestApprovalUseCase(
        uow=uow_factory(), escalation=escalation, notifier=approval_notifier
    )
    resolve_approval_uc = ResolveApprovalUseCase(uow=uow_factory())
    execute_uc = ExecuteFixUseCase(uow=uow_factory(), k8s=k8s)
    verify_uc = VerifyResolutionUseCase(uow=uow_factory(), metrics=metrics)
    postmortem_uc = GeneratePostmortemUseCase(uow=uow_factory(), llm=llm)
    answer_query_uc = AnswerOperationalQueryUseCase(
        uow=uow_factory(), llm=llm, knowledge=knowledge
    )
    onboard_app_uc = OnboardAppUseCase(
        uow=uow_factory(), knowledge=knowledge, grafana=grafana
    )

    # Ticketing + email adapters: real if configured, else log-only fallback
    if settings.jira_base_url and settings.jira_email and settings.jira_api_token:
        ticketing = JiraCloudAdapter(
            base_url=settings.jira_base_url,
            email=settings.jira_email,
            api_token=settings.jira_api_token,
        )
    else:
        ticketing = LogOnlyJiraAdapter()
    if settings.smtp_host:
        email_adapter = SmtpEmailAdapter(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            from_address=settings.smtp_from_address,
            use_tls=settings.smtp_use_tls,
        )
    else:
        email_adapter = LogOnlyEmailAdapter()
    create_ticket_uc = CreateIncidentTicketUseCase(
        uow=uow_factory(),
        ticketing=ticketing,
        email=email_adapter,
        status_notifier=status_notifier,
    )
    parse_intent_uc = ParseChatIntentUseCase(llm=llm)
    investigate_uc = RunOnDemandInvestigationUseCase(
        detect=detect_uc,
        triage=triage_uc,
        gather=gather_uc,
        diagnose=diagnose_uc,
        propose=propose_uc,
    )
    start_slas_uc = StartSLATrackersUseCase(uow=uow_factory())
    satisfy_sla_uc = SatisfySLAUseCase(uow=uow_factory())
    # Lessons-learnt extraction (uses lessons repo via UoW + similar lessons port)
    # We need a thin LessonsRepository wrapper outside UoW for the use case (it manages its own session via UoW).
    extract_lessons_uc = ExtractLessonsLearntUseCase(
        uow=uow_factory(),
        llm=llm,
        similar_lessons=lessons_vec,
    )
    close_incident_uc = CloseIncidentWithHumanResolutionUseCase(
        uow=uow_factory(),
        similar_lessons=lessons_vec,
    )
    find_similar_uc = FindSimilarIncidentsUseCase(
        uow=uow_factory(),
        similar=lessons_vec,
    )
    advisor_uc = RunAdvisoryConversationUseCase(llm=llm, knowledge=knowledge)

    nodes = AgentNodes(
        uow_factory=uow_factory,
        detect=detect_uc,
        triage=triage_uc,
        gather=gather_uc,
        diagnose=diagnose_uc,
        propose=propose_uc,
        request_approval=request_approval_uc,
        execute=execute_uc,
        verify=verify_uc,
        postmortem=postmortem_uc,
        create_ticket=create_ticket_uc,
        start_slas=start_slas_uc,
        satisfy_sla=satisfy_sla_uc,
        find_similar=find_similar_uc,
        ticketing=ticketing,
    )
    graph_factory = AgentGraphFactory(nodes)

    saga = ApprovalSagaScheduler(
        uow_factory=uow_factory,
        notifier=approval_notifier,
        timeouts=SagaTimeouts(
            primary_seconds=settings.hil_primary_timeout_seconds,
            secondary_seconds=settings.hil_secondary_timeout_seconds,
            commander_seconds=settings.hil_commander_timeout_seconds,
        ),
    )
    sla_monitor = SLAMonitorScheduler(
        uow_factory=uow_factory,
        status_notifier=status_notifier,
        tick_seconds=30,
    )
    digest_scheduler = WeeklyDigestScheduler(
        uow_factory=uow_factory,
        interval_seconds=settings.weekly_digest_interval_seconds,
        startup_delay_seconds=120,
    )
    insights_uc = LogInsightsUseCase(logs=logs, llm=llm)
    insights_monitor = InsightsMonitorScheduler(
        uow_factory=uow_factory,
        insights_uc=insights_uc,
        tick_seconds=90,
        window_minutes=15,
    )
    jira_status_poller = JiraStatusPoller(
        uow_factory=uow_factory,
        ticketing=ticketing,
        tick_seconds=settings.jira_status_poll_seconds,
    )

    return Container(
        settings=settings,
        uow_factory=uow_factory,
        llm=llm,
        embeddings=embeddings,
        knowledge=knowledge,
        lessons_vec=lessons_vec,
        metrics=metrics,
        logs=logs,
        k8s=k8s,
        service_catalog=service_catalog,
        escalation=escalation,
        grafana=grafana,
        ticketing=ticketing,
        teams_adapter=teams_adapter,
        conversation_refs=conv_refs,
        approval_notifier=approval_notifier,
        status_notifier=status_notifier,
        detect_uc=detect_uc,
        triage_uc=triage_uc,
        gather_uc=gather_uc,
        diagnose_uc=diagnose_uc,
        propose_uc=propose_uc,
        request_approval_uc=request_approval_uc,
        resolve_approval_uc=resolve_approval_uc,
        execute_uc=execute_uc,
        verify_uc=verify_uc,
        postmortem_uc=postmortem_uc,
        answer_query_uc=answer_query_uc,
        onboard_app_uc=onboard_app_uc,
        create_ticket_uc=create_ticket_uc,
        parse_intent_uc=parse_intent_uc,
        investigate_uc=investigate_uc,
        start_slas_uc=start_slas_uc,
        satisfy_sla_uc=satisfy_sla_uc,
        extract_lessons_uc=extract_lessons_uc,
        close_incident_uc=close_incident_uc,
        find_similar_uc=find_similar_uc,
        advisor_uc=advisor_uc,
        agent_graph_factory=graph_factory,
        saga=saga,
        sla_monitor=sla_monitor,
        digest_scheduler=digest_scheduler,
        insights_uc=insights_uc,
        insights_monitor=insights_monitor,
        jira_status_poller=jira_status_poller,
    )


async def open_checkpointer(settings: AppSettings) -> Any:
    """Open a LangGraph checkpointer tied to Postgres via a long-lived connection pool.

    Falls back to MemorySaver if the Postgres extension is unavailable. The pool is
    attached to the returned saver so callers can keep a reference to the pool and
    close it on shutdown.
    """
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool

        # asyncpg accepts ?ssl=require; libpq (used by psycopg) wants ?sslmode=require.
        # Translate so the same .env DSN works for both connection pools. Also map
        # boolean-ish values ("true"/"1") to "require" since libpq is strict.
        psycopg_dsn = settings.postgres_dsn.replace("postgresql+asyncpg://", "postgresql://")
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

        _p = urlsplit(psycopg_dsn)
        _q = []
        for k, v in parse_qsl(_p.query, keep_blank_values=True):
            if k == "ssl":
                k = "sslmode"
            if k == "sslmode" and v.lower() in ("true", "1"):
                v = "require"
            _q.append((k, v))
        psycopg_dsn = urlunsplit(_p._replace(query=urlencode(_q)))
        pool = AsyncConnectionPool(
            conninfo=psycopg_dsn,
            max_size=10,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": _row_factory()},
            open=False,
        )
        await pool.open()
        saver = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
        await saver.setup()
        saver._pool = pool  # type: ignore[attr-defined]  # hold a reference for shutdown
        return saver
    except Exception:
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()


def _row_factory() -> Any:
    from psycopg.rows import dict_row

    return dict_row
