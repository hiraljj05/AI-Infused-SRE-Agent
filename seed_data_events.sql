INSERT INTO incident_events (event_id, incident_id, event_type, version, occurred_at, caused_by, payload) VALUES
('11111111-1111-1111-1111-111111111111', 'INC-OOM-DEMO', 'IncidentResolved', 1, NOW() - INTERVAL '2 days', 'agent', '{"resolution_time_seconds": 600}'),
('22222222-2222-2222-2222-222222222222', 'INC-CPU-DEMO', 'IncidentResolved', 1, NOW() - INTERVAL '5 days', 'agent', '{"resolution_time_seconds": 1500}'),
('33333333-3333-3333-3333-333333333333', 'INC-SCALE-DEMO', 'IncidentResolved', 1, NOW() - INTERVAL '10 days', 'demo_user', '{"resolution_time_seconds": 300}');
