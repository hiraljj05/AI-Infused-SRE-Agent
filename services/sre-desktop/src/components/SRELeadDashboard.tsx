import { useState } from 'react';

export function SRELeadDashboard() {
  const [activeTab, setActiveTab] = useState('app');

  return (
    <div className="flex h-full w-full bg-[var(--color-n8)] overflow-hidden text-[var(--color-n0)] font-[Poppins]">
      {/* SIDEBAR */}
      <aside className="w-[208px] bg-white border-r border-[var(--color-n7)] flex flex-col shrink-0">
        <div className="p-3.5 px-4 border-b border-[var(--color-n7)] flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--color-sre-primary)] to-[var(--color-sre-pink)] flex items-center justify-center text-white text-sm font-bold">C</div>
          <div>
            <div className="text-[12.5px] font-bold text-[var(--color-n0)] leading-tight">CentificAI</div>
            <div className="text-[10px] text-[var(--color-n4)] mt-0.5">SRE Agent</div>
          </div>
        </div>

        {/* Product Switcher */}
        <div className="p-2.5 px-3 border-b border-[var(--color-n7)] bg-[#FAFBFD]">
          <div className="text-[9px] font-bold tracking-widest text-[var(--color-n5)] uppercase mb-1.5">Product</div>
          <div className="w-full p-2 px-2.5 border border-[var(--color-sre-primary-border)] rounded-lg bg-white flex items-center gap-2 cursor-pointer hover:bg-[var(--color-sre-primary-light)] transition-colors">
            <div className="w-[26px] h-[26px] rounded-md bg-gradient-to-br from-[var(--color-sre-primary)] to-[var(--color-sre-pink)] flex items-center justify-center text-white text-xs font-bold shrink-0">AC</div>
            <div className="flex-1 min-w-0">
              <div className="text-[11.5px] font-bold text-[var(--color-n0)] leading-tight truncate">Aegis Commerce</div>
              <div className="text-[9.5px] text-[var(--color-n4)] mt-px">12 services · T1</div>
            </div>
            <div className="text-[10px] text-[var(--color-n4)] shrink-0">▾</div>
          </div>
        </div>

        {/* User */}
        <div className="p-2.5 px-4 flex items-center gap-2.5 bg-[#FAFBFD] border-b border-[var(--color-n7)]">
          <div className="w-[30px] h-[30px] rounded-full bg-gradient-to-br from-[var(--color-sre-primary-light)] to-[var(--color-sre-pink-light)] flex items-center justify-center text-[11px] font-bold text-[var(--color-sre-primary)]">SM</div>
          <div>
            <div className="text-[11.5px] font-semibold text-[var(--color-n1)] leading-tight">Sarah Mitchell</div>
            <div className="text-[10px] text-[var(--color-n4)] mt-0.5">SRE Lead</div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-2.5 overflow-y-auto">
          <div className="text-[9.5px] font-bold tracking-widest text-[var(--color-n5)] uppercase px-4 py-2">Operations</div>
          <div className="flex items-center gap-2.5 px-4 py-1.5 cursor-pointer text-xs font-semibold bg-[var(--color-sre-primary-light)] text-[var(--color-sre-primary)] border-l-4 border-[var(--color-sre-primary)]">
            <span className="w-4 text-center text-[13px]">📊</span><span>Overview</span>
          </div>
          <div className="flex items-center gap-2.5 px-4 py-1.5 cursor-pointer text-xs font-medium text-[var(--color-n3)] hover:bg-[var(--color-n8)] hover:text-[var(--color-n0)] border-l-4 border-transparent transition-all">
            <span className="w-4 text-center text-[13px]">🚨</span><span>Incidents</span>
          </div>
          <div className="flex items-center gap-2.5 px-4 py-1.5 cursor-pointer text-xs font-medium text-[var(--color-n3)] hover:bg-[var(--color-n8)] hover:text-[var(--color-n0)] border-l-4 border-transparent transition-all">
            <span className="w-4 text-center text-[13px]">🎯</span><span>SLOs & Deploys</span>
          </div>
          
          <div className="text-[9.5px] font-bold tracking-widest text-[var(--color-n5)] uppercase px-4 py-2 mt-2">Analysis</div>
          <div className="flex items-center gap-2.5 px-4 py-1.5 cursor-pointer text-xs font-medium text-[var(--color-n3)] hover:bg-[var(--color-n8)] hover:text-[var(--color-n0)] border-l-4 border-transparent transition-all">
            <span className="w-4 text-center text-[13px]">🔍</span><span>RCA Console</span>
          </div>
          <div className="flex items-center gap-2.5 px-4 py-1.5 cursor-pointer text-xs font-medium text-[var(--color-n3)] hover:bg-[var(--color-n8)] hover:text-[var(--color-n0)] border-l-4 border-transparent transition-all">
            <span className="w-4 text-center text-[13px]">📖</span><span>Runbooks</span>
          </div>

          <div className="text-[9.5px] font-bold tracking-widest text-[var(--color-n5)] uppercase px-4 py-2 mt-2">Governance</div>
          <div className="flex items-center gap-2.5 px-4 py-1.5 cursor-pointer text-xs font-medium text-[var(--color-n3)] hover:bg-[var(--color-n8)] hover:text-[var(--color-n0)] border-l-4 border-transparent transition-all">
            <span className="w-4 text-center text-[13px]">✅</span><span>HIL Queue</span>
          </div>
        </nav>
      </aside>

      {/* MAIN */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Topbar */}
        <div className="h-14 shrink-0 bg-white border-b border-[var(--color-n7)] px-5 flex items-center justify-between gap-4">
          <div className="flex flex-col gap-0.5 min-w-0">
            <div className="text-sm font-bold text-[var(--color-n0)] flex items-center gap-2">
              Operations Overview
              <span className="inline-flex items-center gap-1.5 bg-[var(--color-sre-primary-light)] border border-[var(--color-sre-primary-border)] rounded-full px-2 py-0.5 text-[10px] font-bold text-[var(--color-sre-primary)]">◉ Aegis Commerce</span>
            </div>
            <div className="text-[11px] text-[var(--color-n4)]">Live monitoring · 12 services · 3 environments</div>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <div className="flex items-center gap-1.5 bg-[var(--color-sre-success-light)] border border-[rgba(22,163,74,0.3)] rounded-full px-2.5 py-1 text-[10px] font-bold text-[var(--color-sre-success)]">
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-sre-success)] animate-pulse"></div>LIVE
            </div>
            <div className="text-[11px] text-[var(--color-n3)] font-medium bg-[var(--color-n8)] px-2.5 py-1 rounded-full">
              {new Date().toLocaleDateString('en-US', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })} · {new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
            </div>
            <div className="w-7 h-7 rounded-lg bg-[var(--color-n8)] border border-[var(--color-n7)] flex items-center justify-center cursor-pointer text-[13px] text-[var(--color-n3)] hover:bg-[var(--color-sre-primary-light)] hover:text-[var(--color-sre-primary)] hover:border-[var(--color-sre-primary-border)] transition-colors">
              🔔
            </div>
          </div>
        </div>

        {/* Content Canvas */}
        <div className="flex-1 relative overflow-hidden bg-[#F1F5F9] p-4 flex flex-col">
          {/* Hero Lead */}
          <div className="rounded-xl p-3 px-4 flex items-center justify-between gap-3 shrink-0 text-white mb-3" style={{ background: 'linear-gradient(90deg,#A855F7 0%,#6B8EF0 50%,#01CAB8 100%)' }}>
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-[34px] h-[34px] rounded-lg bg-white/20 border border-white/30 flex items-center justify-center text-base shrink-0">🛰️</div>
              <div>
                <div className="text-[12.5px] font-bold">SRE Agent · Continuous monitoring across App, Infra & Transactions</div>
                <div className="text-[10.5px] text-white/80 mt-px">Prometheus · Datadog · CloudWatch · APM · Synthetic · Last sync 18s ago</div>
              </div>
            </div>
            <div className="flex gap-5 shrink-0">
              <div className="text-center"><div className="text-base font-bold leading-none text-[#FCA5A5]">3</div><div className="text-[9px] text-white/75 uppercase tracking-[0.6px] mt-1">Active</div></div>
              <div className="text-center"><div className="text-base font-bold leading-none text-[#86EFAC]">97.3%</div><div className="text-[9px] text-white/75 uppercase tracking-[0.6px] mt-1">Avg SLO</div></div>
              <div className="text-center"><div className="text-base font-bold leading-none text-white">2.1m</div><div className="text-[9px] text-white/75 uppercase tracking-[0.6px] mt-1">MTTD</div></div>
              <div className="text-center"><div className="text-base font-bold leading-none text-white">42m</div><div className="text-[9px] text-white/75 uppercase tracking-[0.6px] mt-1">MTTR</div></div>
            </div>
          </div>

          {/* Layer Tabs */}
          <div className="flex gap-1.5 bg-white border border-[var(--color-n7)] rounded-xl p-1 shrink-0 mb-3">
            {[
              { id: 'app', icon: '⚙️', name: 'Application', sub: 'Services, APIs, SLOs, deploys', mini: 'Svc 12 · SLO 97.3%' },
              { id: 'infra', icon: '🖥️', name: 'Infrastructure', sub: 'Hosts, DBs, queues, network', mini: 'CPU 62% · Mem 71%' },
              { id: 'txn', icon: '💳', name: 'Transactional', sub: 'Funnels, business KPIs, SLIs', mini: 'Success 98.6% · TPS 2.4k' },
              { id: 'agent', icon: '🤖', name: 'Agent Metrics', sub: 'LLM, RCA, HIL, ingestion', mini: 'Tok 4.2M · Err 0.8%' }
            ].map(tab => (
              <div 
                key={tab.id} 
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 p-2 px-3 rounded-lg cursor-pointer flex items-center gap-2 transition-colors ${activeTab === tab.id ? 'bg-gradient-to-br from-[var(--color-sre-primary-light)] to-[var(--color-sre-cyan-light)]' : 'hover:bg-[var(--color-n8)]'}`}
              >
                <div className={`w-[30px] h-[30px] rounded-lg flex items-center justify-center text-sm text-white shrink-0 ${tab.id === 'app' ? 'bg-gradient-to-br from-[#5929d0] to-[#9B8EDE]' : tab.id === 'infra' ? 'bg-gradient-to-br from-[#0E2E89] to-[#22D3EE]' : tab.id === 'txn' ? 'bg-gradient-to-br from-[#CF008B] to-[#E4902E]' : 'bg-gradient-to-br from-[#01CAB8] to-[#5929d0]'}`}>
                  {tab.icon}
                </div>
                <div className="min-w-0 flex-1">
                  <div className={`text-[11.5px] font-bold leading-tight ${activeTab === tab.id ? 'text-[var(--color-sre-primary)]' : 'text-[var(--color-n1)]'}`}>{tab.name}</div>
                  <div className="text-[9.5px] text-[var(--color-n4)] mt-0.5 truncate">{tab.sub}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Tab Content Panes */}
          <div className="flex-1 relative overflow-hidden">
            {activeTab === 'app' && (
              <div className="absolute inset-0 flex flex-col gap-2.5 overflow-hidden">
                {/* NL Bar */}
                <div className="bg-white border-[1.5px] border-[var(--color-sre-primary-border)] rounded-full p-1.5 pl-2.5 flex items-center gap-2 shadow-[0_2px_8px_rgba(89,41,208,0.12)] shrink-0">
                  <div className="w-[26px] h-[26px] rounded-md bg-gradient-to-br from-[var(--color-sre-primary-light)] to-[var(--color-sre-cyan-light)] flex items-center justify-center text-[13px] shrink-0">🤖</div>
                  <input type="text" placeholder="Ask SRE Agent — e.g. 'Blast radius of INC-001?' or 'SLO for payments-api'" className="flex-1 border-none outline-none bg-transparent font-[Poppins] text-[11.5px] text-[var(--color-n2)]" />
                  <div className="flex gap-1">
                    {['Active P1s', 'Error budget', 'Runbooks'].map(chip => (
                      <div key={chip} className="bg-[var(--color-n8)] border border-[var(--color-n7)] rounded-full px-2 py-1 text-[9.5px] text-[var(--color-n3)] cursor-pointer whitespace-nowrap hover:bg-[var(--color-sre-primary-light)] hover:text-[var(--color-sre-primary)] hover:border-[var(--color-sre-primary-border)]">{chip}</div>
                    ))}
                  </div>
                  <button className="w-[26px] h-[26px] rounded-full border-none shrink-0 bg-gradient-to-br from-[var(--color-sre-primary)] to-[var(--color-sre-cyan)] text-white cursor-pointer flex items-center justify-center text-[11px] font-bold">➤</button>
                </div>

                {/* KPI Row */}
                <div className="grid grid-cols-4 gap-2 shrink-0">
                  <div className="bg-white border border-[var(--color-n7)] rounded-lg p-2.5 px-3 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-0.5 before:bg-[var(--color-sre-error)]">
                    <div className="text-[9.5px] font-semibold text-[var(--color-n4)] uppercase tracking-[0.06em] mb-1">Active Incidents</div>
                    <div className="text-[22px] font-bold leading-none text-[var(--color-sre-error)]">3</div>
                    <div className="text-[10px] font-semibold mt-1 text-[var(--color-sre-error)]">▲ 1 vs last hour</div>
                  </div>
                  <div className="bg-white border border-[var(--color-n7)] rounded-lg p-2.5 px-3 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-0.5 before:bg-[var(--color-sre-success)]">
                    <div className="text-[9.5px] font-semibold text-[var(--color-n4)] uppercase tracking-[0.06em] mb-1">MTTD P1</div>
                    <div className="text-[22px] font-bold leading-none text-[var(--color-sre-success)]">2.1m</div>
                    <div className="text-[10px] font-semibold mt-1 text-[var(--color-sre-success)]">▼ 0.4m</div>
                  </div>
                  <div className="bg-white border border-[var(--color-n7)] rounded-lg p-2.5 px-3 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-0.5 before:bg-[var(--color-sre-success)]">
                    <div className="text-[9.5px] font-semibold text-[var(--color-n4)] uppercase tracking-[0.06em] mb-1">MTTR P1</div>
                    <div className="text-[22px] font-bold leading-none text-[var(--color-sre-success)]">42m</div>
                    <div className="text-[10px] font-semibold mt-1 text-[var(--color-sre-success)]">▼ 8m</div>
                  </div>
                  <div className="bg-white border border-[var(--color-n7)] rounded-lg p-2.5 px-3 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-full before:h-0.5 before:bg-[var(--color-sre-primary)]">
                    <div className="text-[9.5px] font-semibold text-[var(--color-n4)] uppercase tracking-[0.06em] mb-1">SLO Compliance</div>
                    <div className="text-[22px] font-bold leading-none text-[var(--color-sre-primary)]">97.3%</div>
                    <div className="text-[10px] font-semibold mt-1 text-[var(--color-sre-success)]">▲ 0.6%</div>
                  </div>
                </div>

                <div className="flex-1 grid grid-cols-[1fr_290px] gap-2.5 min-h-0">
                  <div className="flex flex-col gap-2.5 min-h-0 overflow-hidden">
                    <div className="grid grid-cols-2 gap-2.5 flex-1 min-h-0">
                      {/* Incidents Card */}
                      <div className="bg-white border border-[var(--color-n7)] rounded-lg shadow-sm p-3 flex flex-col min-h-0">
                        <div className="flex items-center justify-between mb-2.5 shrink-0">
                          <div className="text-xs font-bold text-[var(--color-n1)] flex items-center gap-1.5"><div className="w-5 h-5 rounded bg-[var(--color-sre-primary-light)] flex items-center justify-center text-[11px]">🚨</div>Active Incidents <span className="bg-[var(--color-sre-primary)] text-white text-[8.5px] font-bold px-1.5 py-0.5 rounded-full ml-1">3</span></div>
                          <span className="text-[10.5px] text-[var(--color-sre-primary)] font-semibold cursor-pointer hover:underline">All →</span>
                        </div>
                        <div className="flex flex-col gap-1.5 overflow-y-auto min-h-0 pr-0.5">
                          <div className="border border-[var(--color-n7)] rounded-lg p-2 px-2.5 grid grid-cols-[auto_1fr_auto] items-center gap-2.5 cursor-pointer hover:shadow-md transition-all border-l-[3px] border-l-[var(--color-sre-error)]" style={{ background: 'linear-gradient(90deg,#FFF8F8,#fff 30%)' }}>
                            <div className="rounded-md px-1.5 py-0.5 text-[9.5px] font-bold min-w-[28px] text-center bg-[var(--color-sre-error-light)] text-[var(--color-sre-error)]">P1</div>
                            <div className="min-w-0">
                              <div className="text-[11.5px] font-semibold text-[var(--color-n0)] truncate">INC-001 · payments-api 5xx spike</div>
                              <div className="text-[10px] text-[var(--color-n5)] mt-px flex gap-2"><span>18m</span><span>Blast 3 svc</span><span>RCA 87%</span></div>
                            </div>
                            <button className="text-[10px] font-semibold px-2.5 py-1 rounded-md border-none cursor-pointer bg-[var(--color-sre-success)] text-white hover:bg-[#15803D]">Approve rollback</button>
                          </div>
                          
                          <div className="border border-[var(--color-n7)] rounded-lg p-2 px-2.5 grid grid-cols-[auto_1fr_auto] items-center gap-2.5 cursor-pointer hover:shadow-md transition-all border-l-[3px] border-l-[var(--color-sre-warning)]" style={{ background: 'linear-gradient(90deg,#FFFDF5,#fff 30%)' }}>
                            <div className="rounded-md px-1.5 py-0.5 text-[9.5px] font-bold min-w-[28px] text-center bg-[var(--color-sre-warning-light)] text-[#92400E]">P2</div>
                            <div className="min-w-0">
                              <div className="text-[11.5px] font-semibold text-[var(--color-n0)] truncate">INC-002 · orders-api latency (p95 820ms)</div>
                              <div className="text-[10px] text-[var(--color-n5)] mt-px flex gap-2"><span>42m</span><span>Blast 1 svc</span><span>RCA 72%</span></div>
                            </div>
                            <button className="text-[10px] font-semibold px-2.5 py-1 rounded-md border border-[var(--color-sre-primary-border)] cursor-pointer bg-[var(--color-sre-primary-light)] text-[var(--color-sre-primary)] hover:bg-[var(--color-sre-primary)] hover:text-white">Review</button>
                          </div>

                          <div className="border border-[var(--color-n7)] rounded-lg p-2 px-2.5 grid grid-cols-[auto_1fr_auto] items-center gap-2.5 cursor-pointer hover:shadow-md transition-all border-l-[3px] border-l-[var(--color-sre-primary)] bg-white">
                            <div className="rounded-md px-1.5 py-0.5 text-[9.5px] font-bold min-w-[28px] text-center bg-[var(--color-sre-primary-light)] text-[var(--color-sre-primary)]">P3</div>
                            <div className="min-w-0">
                              <div className="text-[11.5px] font-semibold text-[var(--color-n0)] truncate">INC-003 · Cert expiry · api-gateway</div>
                              <div className="text-[10px] text-[var(--color-n5)] mt-px flex gap-2"><span>1h 12m</span><span>Blast 0</span><span>RCA 99%</span></div>
                            </div>
                            <button className="text-[10px] font-semibold px-2.5 py-1 rounded-md border border-[var(--color-sre-primary-border)] cursor-pointer bg-[var(--color-sre-primary-light)] text-[var(--color-sre-primary)] hover:bg-[var(--color-sre-primary)] hover:text-white">Review</button>
                          </div>
                        </div>
                      </div>

                      {/* Service Health Card */}
                      <div className="bg-white border border-[var(--color-n7)] rounded-lg shadow-sm p-3 flex flex-col min-h-0">
                        <div className="flex items-center justify-between mb-2.5 shrink-0">
                          <div className="text-xs font-bold text-[var(--color-n1)] flex items-center gap-1.5"><div className="w-5 h-5 rounded bg-[var(--color-sre-primary-light)] flex items-center justify-center text-[11px]">🗺️</div>Service Health</div>
                          <span className="text-[9.5px] text-[var(--color-n5)]">12 svc · auto-refresh 60s</span>
                        </div>
                        <div className="grid grid-cols-2 gap-1.5 overflow-y-auto min-h-0">
                          {[
                            { name: 'payments-api', tier: 'T1', status: 'P1', color: 'var(--color-sre-error)', border: 'var(--color-sre-error)', up: '98.1% · INC-001', pulse: true },
                            { name: 'orders-api', tier: 'T1', status: 'Degraded', color: '#D97706', border: '#F59E0B', up: '99.1% · lat ↑', pulse: false },
                            { name: 'web-frontend', tier: 'T1', status: 'Healthy', color: 'var(--color-sre-success)', border: '#22C55E', up: '99.97%', pulse: false },
                            { name: 'auth-service', tier: 'T1', status: 'Healthy', color: 'var(--color-sre-success)', border: '#22C55E', up: '99.95%', pulse: false },
                            { name: 'cart-service', tier: 'T1', status: 'Healthy', color: 'var(--color-sre-success)', border: '#22C55E', up: '99.94%', pulse: false },
                            { name: 'search-api', tier: 'T2', status: 'Healthy', color: 'var(--color-sre-success)', border: '#22C55E', up: '99.93%', pulse: false }
                          ].map(svc => (
                            <div key={svc.name} className="border border-[var(--color-n7)] rounded-md p-2 bg-white flex flex-col gap-1 cursor-pointer hover:shadow-sm transition-shadow" style={{ borderLeft: `3px solid ${svc.border}` }}>
                              <div className="flex items-center justify-between">
                                <div className="text-[10.5px] font-semibold text-[var(--color-n1)]">{svc.name}</div>
                                <div className="text-[8.5px] text-[var(--color-n5)] bg-[var(--color-n8)] px-1 rounded-sm font-semibold">{svc.tier}</div>
                              </div>
                              <div className="flex items-center gap-1 text-[9.5px] font-semibold">
                                <div className={`w-1.5 h-1.5 rounded-full ${svc.pulse ? 'animate-pulse' : ''}`} style={{ backgroundColor: svc.border, boxShadow: `0 0 4px ${svc.color}80` }}></div>
                                <span style={{ color: svc.color }}>{svc.status}</span>
                              </div>
                              <div className="text-[9px] text-[var(--color-n5)]">{svc.up}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Bottom twin row */}
                    <div className="grid grid-cols-2 gap-2.5 shrink-0 h-[210px]">
                      <div className="bg-white border border-[var(--color-n7)] rounded-lg shadow-sm p-3 flex flex-col min-h-0">
                        <div className="flex items-center justify-between mb-2.5 shrink-0">
                          <div className="text-xs font-bold text-[var(--color-n1)] flex items-center gap-1.5"><div className="w-5 h-5 rounded bg-[var(--color-sre-primary-light)] flex items-center justify-center text-[11px]">🎯</div>SLO Compliance</div>
                          <span className="text-[10.5px] text-[var(--color-sre-primary)] font-semibold cursor-pointer hover:underline">All →</span>
                        </div>
                        <div className="flex flex-col gap-2 overflow-y-auto min-h-0 pr-1">
                          {/* Item 1 */}
                          <div>
                            <div className="flex justify-between items-baseline mb-1">
                              <div className="text-[11px] font-semibold text-[var(--color-n1)]">payments-api</div>
                              <div className="text-[11.5px] font-bold text-[var(--color-sre-error)]">94.2%</div>
                            </div>
                            <div className="h-1.5 rounded-full bg-[var(--color-n8)] overflow-hidden">
                              <div className="h-full rounded-full bg-[var(--color-sre-error)]" style={{ width: '94%' }}></div>
                            </div>
                            <div className="flex justify-between mt-1 text-[9px] text-[var(--color-n5)]">
                              <span>Target 99.9% · Burnt 58%</span><span className="text-[var(--color-sre-warning)] font-semibold">🔥 2.3× burn</span>
                            </div>
                          </div>
                          {/* Item 2 */}
                          <div>
                            <div className="flex justify-between items-baseline mb-1">
                              <div className="text-[11px] font-semibold text-[var(--color-n1)]">orders-api</div>
                              <div className="text-[11.5px] font-bold text-[#D97706]">98.4%</div>
                            </div>
                            <div className="h-1.5 rounded-full bg-[var(--color-n8)] overflow-hidden">
                              <div className="h-full rounded-full bg-[var(--color-sre-warning)]" style={{ width: '98%' }}></div>
                            </div>
                            <div className="flex justify-between mt-1 text-[9px] text-[var(--color-n5)]">
                              <span>Target 99.5% · Burnt 32%</span><span>1.1× burn</span>
                            </div>
                          </div>
                          {/* Item 3 */}
                          <div>
                            <div className="flex justify-between items-baseline mb-1">
                              <div className="text-[11px] font-semibold text-[var(--color-n1)]">web-frontend</div>
                              <div className="text-[11.5px] font-bold text-[var(--color-sre-success)]">99.97%</div>
                            </div>
                            <div className="h-1.5 rounded-full bg-[var(--color-n8)] overflow-hidden">
                              <div className="h-full rounded-full bg-[var(--color-sre-success)]" style={{ width: '99.97%' }}></div>
                            </div>
                            <div className="flex justify-between mt-1 text-[9px] text-[var(--color-n5)]">
                              <span>Target 99.9% · Burnt 8%</span><span>0.3× burn</span>
                            </div>
                          </div>
                        </div>
                      </div>

                      <div className="bg-white border border-[var(--color-n7)] rounded-lg shadow-sm p-3 flex flex-col min-h-0">
                        <div className="flex items-center justify-between mb-2.5 shrink-0">
                          <div className="text-xs font-bold text-[var(--color-n1)] flex items-center gap-1.5"><div className="w-5 h-5 rounded bg-[var(--color-sre-primary-light)] flex items-center justify-center text-[11px]">🚀</div>Deployment Health</div>
                          <span className="text-[10.5px] text-[var(--color-sre-primary)] font-semibold cursor-pointer hover:underline">All →</span>
                        </div>
                        <div className="flex flex-col gap-2 overflow-y-auto min-h-0">
                          <div className="border border-[var(--color-n7)] rounded-lg p-2 px-2.5 bg-white grid grid-cols-[1fr_auto_auto_auto] items-center gap-2.5">
                            <div><div className="text-[10.5px] font-semibold text-[var(--color-n1)]">payments-api</div><div className="text-[9.5px] text-[var(--color-n5)] mt-px">v2.4.1 · canary 25%</div></div>
                            <div className="text-[9.5px] text-[var(--color-n4)]">T+18m</div>
                            <span className="bg-[var(--color-sre-error-light)] text-[var(--color-sre-error)] rounded-full px-2 py-0.5 text-[9.5px] font-bold">FAILED</span>
                            <button className="text-[10px] font-semibold px-2 py-1 rounded bg-[var(--color-sre-success)] text-white">Rollback</button>
                          </div>
                          <div className="border border-[var(--color-n7)] rounded-lg p-2 px-2.5 bg-white grid grid-cols-[1fr_auto_auto_auto] items-center gap-2.5">
                            <div><div className="text-[10.5px] font-semibold text-[var(--color-n1)]">web-frontend</div><div className="text-[9.5px] text-[var(--color-n5)] mt-px">v5.2.0 · full</div></div>
                            <div className="text-[9.5px] text-[var(--color-n4)]">T+9m</div>
                            <span className="bg-[var(--color-sre-primary-light)] text-[var(--color-sre-primary)] rounded-full px-2 py-0.5 text-[9.5px] font-bold">MONITOR</span>
                            <button className="text-[10px] font-semibold px-2 py-1 rounded border border-[var(--color-sre-primary-border)] bg-[var(--color-sre-primary-light)] text-[var(--color-sre-primary)]">Details</button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Aside Commentary */}
                  <aside className="border border-[var(--color-sre-primary-border)] rounded-xl flex flex-col min-h-0 overflow-hidden" style={{ background: 'linear-gradient(180deg,#FAF8FF 0%,#FFFFFF 100%)' }}>
                    <div className="p-2.5 px-3 flex items-center justify-between border-b border-[var(--color-sre-primary-border)] shrink-0">
                      <div className="text-[11.5px] font-bold text-[var(--color-n0)] flex items-center gap-1.5">📡 Live Commentary</div>
                      <div className="flex items-center gap-1.5 bg-[var(--color-sre-success-light)] border border-[rgba(22,163,74,0.3)] rounded-full px-2.5 py-1 text-[10px] font-bold text-[var(--color-sre-success)]">
                        <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-sre-success)] animate-pulse"></div>LIVE
                      </div>
                    </div>
                    <div className="p-2 px-2.5 grid grid-cols-2 gap-1.5 shrink-0">
                      <div className="bg-white border border-[var(--color-sre-primary-border)] rounded-lg p-2 px-2.5">
                        <div className="text-[15px] font-bold text-[var(--color-sre-primary)] leading-none">12</div>
                        <div className="text-[9px] text-[var(--color-n5)] mt-1">HIL queued</div>
                      </div>
                      <div className="bg-white border border-[var(--color-sre-primary-border)] rounded-lg p-2 px-2.5">
                        <div className="text-[15px] font-bold text-[var(--color-sre-primary)] leading-none">71%</div>
                        <div className="text-[9px] text-[var(--color-n5)] mt-1">Auto-fix rate</div>
                      </div>
                    </div>
                    <div className="flex-1 overflow-y-auto p-1.5 px-2.5 pb-2.5 space-y-2.5">
                      <div>
                        <div className="text-[9.5px] font-bold text-[var(--color-sre-primary)] mb-1 flex items-center justify-between">🔴 INC-001 <span className="text-[9px] text-[var(--color-n5)] font-normal">6 events</span></div>
                        <div className="p-1.5 px-2 rounded-md bg-[rgba(89,41,208,0.05)] mb-1">
                          <div className="flex items-center gap-1 mb-0.5"><span className="rounded-full px-1 py-0.5 text-[8px] font-bold uppercase bg-[#DBEAFE] text-[#1D4ED8]">Detect</span><span className="text-[8.5px] text-[var(--color-n5)]">09:12:08</span></div>
                          <div className="text-[10px] text-[var(--color-n2)] leading-[1.35]">Error rate 4.2% on payments-api (baseline 0.08%). Z 18.4.</div>
                        </div>
                        <div className="p-1.5 px-2 rounded-md bg-[rgba(89,41,208,0.05)] mb-1">
                          <div className="flex items-center gap-1 mb-0.5"><span className="rounded-full px-1 py-0.5 text-[8px] font-bold uppercase bg-[var(--color-sre-success-light)] text-[var(--color-sre-success)]">RCA</span><span className="text-[8.5px] text-[var(--color-n5)]">09:12:41</span></div>
                          <div className="text-[10px] text-[var(--color-n2)] leading-[1.35]">Correlated with deploy v2.4.1 (T-8m). Confidence 87%.</div>
                        </div>
                        <div className="p-1.5 px-2 rounded-md bg-[rgba(89,41,208,0.05)] mb-1">
                          <div className="flex items-center gap-1 mb-0.5"><span className="rounded-full px-1 py-0.5 text-[8px] font-bold uppercase bg-[var(--color-sre-warning-light)] text-[#92400E]">Page</span><span className="text-[8.5px] text-[var(--color-n5)]">09:13:02</span></div>
                          <div className="text-[10px] text-[var(--color-n2)] leading-[1.35]">On-call paged: S. Mitchell. Blast: 3 services.</div>
                        </div>
                        <div className="p-1.5 px-2 rounded-md bg-[rgba(89,41,208,0.05)] mb-1">
                          <div className="flex items-center gap-1 mb-0.5"><span className="rounded-full px-1 py-0.5 text-[8px] font-bold uppercase bg-[#F3E8FF] text-[#7C3AED]">HIL</span><span className="text-[8.5px] text-[var(--color-n5)]">09:13:47</span></div>
                          <div className="text-[10px] text-[var(--color-n2)] leading-[1.35]">Rollback v2.4.0 proposed. Awaiting approval.</div>
                        </div>
                      </div>
                    </div>
                  </aside>
                </div>
              </div>
            )}
            
            {/* OTHER TABS WOULD GO HERE (Infra, Txn, Agent) */}
            {activeTab !== 'app' && (
              <div className="absolute inset-0 flex items-center justify-center text-[var(--color-n4)]">
                <div className="text-center">
                  <div className="text-4xl mb-2 opacity-50">{activeTab === 'infra' ? '🖥️' : activeTab === 'txn' ? '💳' : '🤖'}</div>
                  <div className="text-lg font-semibold">{activeTab.toUpperCase()} View Selected</div>
                  <div className="text-sm mt-2">Displaying simulated content for SRE Lead.</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
