import json
from fastapi.testclient import TestClient
from app.main import app, upsert_points, SOURCES, Point

client = TestClient(app)

def seed():
    for key in SOURCES:
        upsert_points(key, [Point(date=f"2026-0{i}-01", value=100+i, source_key=key) for i in range(1,8)] + [Point(date="2026-08-01", value=125, source_key=key)])

def test_health_pricing_and_dashboard():
    assert client.get('/health').json()['ok'] is True
    pricing = client.get('/pricing').json()
    assert pricing['plans']['starter']['price_usd_month'] == 99
    assert pricing['payment']['x402'] is True
    dashboard = client.get('/')
    assert dashboard.status_code == 200
    assert 'Freight Rate Anomaly Detector' in dashboard.text
    assert 'Latest anomaly signals' in dashboard.text

def test_anomaly_detection_and_context():
    seed()
    resp = client.get('/anomalies?threshold_pct=2&baseline_window=7')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data['signals']) >= 3
    assert all('context' in s and 'conviction' in s for s in data['signals'])
    assert any(s['is_anomaly'] for s in data['signals'])

def test_subscriber_and_alert_dispatch_file_outbox(tmp_path, monkeypatch):
    monkeypatch.setenv('FREIGHT_DB_PATH', str(tmp_path/'test.sqlite'))
    seed()
    sub = client.post('/subscribers', json={'email':'ops@example.com','threshold_pct':2,'baseline_window':7,'modes':['truck','rail','air']})
    assert sub.status_code == 200
    sent = client.post('/alerts/dispatch', json={'email':'ops@example.com','threshold_pct':2,'baseline_window':7,'modes':['truck','rail','air']})
    assert sent.status_code == 200
    body = sent.json()
    assert body['alerts_dispatched'] >= 1
    assert any(d['type']=='email' and d['delivered'] for d in body['deliveries'])

def test_x402_gate_and_paid_export():
    seed()
    free = client.get('/api/export')
    assert free.status_code == 402
    paid = client.get('/api/export', headers={'X-PAYMENT':'demo-paid-token'})
    assert paid.status_code == 200
    assert paid.json()['paid'] is True
