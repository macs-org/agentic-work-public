from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
wallet="0x3333333333333333333333333333333333333333"

def test_health_dashboard_and_pricing():
    assert client.get('/health').json()['ok'] is True
    assert client.get('/').status_code == 200
    assert client.get('/pricing').json()['fee_bps'] == 100

def test_launch_trade_and_graduation_flow():
    r=client.post('/launch', json={'name':'Alpha Bot','ticker':'ALPHA','description':'Trading-free AI agent token launch demo','deployer_wallet':wallet})
    assert r.status_code==200
    addr=r.json()['token_address']
    detail=client.get(f'/tokens/{addr}').json()
    assert detail['ticker']=='ALPHA'
    trade=client.post(f'/tokens/{addr}/trade', json={'trader_wallet':wallet,'side':'buy','amount_usdc':1000})
    assert trade.status_code==200
    assert trade.json()['quote']['fee_usdc']==10
    updated=client.get(f'/tokens/{addr}').json()
    assert updated['reserve_usdc'] == 990
    assert updated['bonding_curve_progress_pct'] > 0

def test_paid_export_gate_and_openapi():
    assert client.get('/api/export').status_code == 402
    assert client.get('/api/export', headers={'X-PAYMENT':'demo'}).status_code == 200
    spec=client.get('/openapi-agent.json').json()
    assert '/launch' in spec['paths']
