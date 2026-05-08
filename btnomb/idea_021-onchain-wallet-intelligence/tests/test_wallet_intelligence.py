from fastapi.testclient import TestClient
import app.main as main

class FakeRpc:
    def __init__(self, chain): self.chain = chain
    def latest_block(self): return 100
    def block(self, n):
        return {"transactions": [
            {"hash":"0xaaa", "from":"0xd8da6bf26964af9d7eed9e03e53415d37aa96045", "to":"0x0000000000000000000000000000000000000001", "value":hex(2*10**18), "input":"0x"},
            {"hash":"0xbbb", "from":"0x0000000000000000000000000000000000000002", "to":"0x0000000000000000000000000000000000000003", "value":"0x0", "input":"0x38ed17390000"},
        ]}

def fresh_client(tmp_path, monkeypatch):
    main.store = main.Store(str(tmp_path / "wallet.db"))
    monkeypatch.setattr(main, "RpcClient", FakeRpc)
    return TestClient(main.app)

def test_seeds_50_wallets_custom_watchlist_and_poll(tmp_path, monkeypatch):
    client = fresh_client(tmp_path, monkeypatch)
    assert client.get('/health').json()['wallets'] >= 50
    sub = client.post('/api/subscribers', json={"email":"alerts@example.com", "telegram_chat_id":"123", "min_score":50})
    assert sub.status_code == 200
    custom = client.post('/api/watchlists', json={"subscriber_id":1,"address":"0x0000000000000000000000000000000000000003","label":"custom whale","chain":"base"})
    assert custom.status_code == 200
    poll = client.post('/api/poll?chains=base&blocks=1')
    assert poll.status_code == 200
    assert poll.json()['wallets_tracked'] >= 50
    assert poll.json()['new_alerts'] >= 1
    alerts = client.get('/api/alerts?min_score=50').json()
    assert alerts
    assert any(a['event_type'] in {'transfer','swap'} for a in alerts)
    deliveries = client.get('/api/deliveries').json()
    assert deliveries
    assert deliveries[0]['status'] == 'stored'

def test_parse_swap_transfer_and_context_scores():
    wallet = {"label":"alpha", "tier":"top_trader", "tier_score":90, "address":"0x1"}
    swap = main.TxEvent(chain='base', tx_hash='0x1', block_number=1, from_address='0x1', to_address='0x2', value_eth=5, input_data='0x38ed1739abcdef')
    parsed = main.parse_transaction(swap, wallet)
    assert parsed['event_type'] == 'swap'
    assert parsed['conviction_score'] == 100
    assert 'top_trader' in parsed['context']
    transfer = main.TxEvent(chain='ethereum', tx_hash='0x2', block_number=1, from_address='0x1', value_eth=1, input_data='0x')
    assert main.parse_transaction(transfer, wallet)['event_type'] == 'transfer'

def test_dashboard_and_payment_gate(tmp_path, monkeypatch):
    client = fresh_client(tmp_path, monkeypatch)
    dash = client.get('/')
    assert dash.status_code == 200
    assert 'On-Chain Wallet Intelligence' in dash.text
    assert client.get('/api/payments/x402/requirements').json()['network'] == 'base'
    assert client.get('/api/export').status_code == 402
    assert client.get('/api/export', headers={'X-PAYMENT':'demo'}).status_code == 200

def test_match_event_to_to_address_and_chain_filter(tmp_path, monkeypatch):
    client = fresh_client(tmp_path, monkeypatch)
    wallet = {"address":"0x0000000000000000000000000000000000000003", "label":"custom", "chain":"base"}
    tx = {"hash":"0xabc", "from":"0x0000000000000000000000000000000000000001", "to":wallet['address'], "value":"0x0", "input":"0xa9059cbb0000"}
    event, matched = main.match_event(tx, 'base', 7, {wallet['address']: wallet})
    assert matched['label'] == 'custom'
    assert event.block_number == 7
