from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
import app.main as main
from sdk.python.audit_trail import ActionLog, hash_action as sdk_hash_action

def fresh_client(tmp_path):
    main.store = main.Store(str(tmp_path / 'audit.db'))
    return TestClient(main.app)

def action(i=1):
    return {'agent_id': f'agent-{i}', 'action_type': 'payment', 'input_hash': 'abc', 'output_hash': 'def', 'timestamp': '2026-05-08T00:00:00Z', 'description': f'paid invoice {i}'}

def test_hash_is_canonical_and_merkle_proof_verifies():
    a = action(1); h1 = main.hash_action(a); h2 = main.hash_action(dict(reversed(list(a.items())))); assert h1 == h2
    leaves = [main.hash_action(action(i)) for i in range(4)]; root = main.merkle_root(leaves); proof = main.merkle_proof(leaves, 2); assert main.verify_proof(leaves[2], proof, root, 2)

def test_python_sdk_hash_matches_service_schema():
    payload = action(42)
    sdk_action = ActionLog(**payload)
    assert sdk_hash_action(sdk_action) == main.hash_action(payload)
    assert sdk_hash_action(payload) == main.hash_action(payload)

def test_log_commit_verify_api(tmp_path):
    client = fresh_client(tmp_path)
    for i in range(3):
        r = client.post('/api/actions', json=action(i)); assert r.status_code == 200; assert r.json()['status'] == 'queued'
    commit = client.post('/api/batches/commit'); assert commit.status_code == 200; assert commit.json()['actions'] == 3
    verify = client.post('/api/verify', json=action(1)); assert verify.status_code == 200; assert verify.json()['verified'] is True; assert len(verify.json()['proof']) >= 2

def test_explorer_and_capacity_metadata(tmp_path):
    client = fresh_client(tmp_path); h = client.get('/health').json(); assert h['max_batch_size'] == 100
    assert client.get('/').status_code == 200; assert 'On-chain AI Audit Trail' in client.get('/').text

def test_verify_unseen_and_batch_limit_shape(tmp_path):
    client = fresh_client(tmp_path); unseen = client.post('/api/verify', json=action(99)).json(); assert unseen['verified'] is False; assert unseen['reason'] == 'hash not found'
    for i in range(105): client.post('/api/actions', json=action(i))
    commit = client.post('/api/batches/commit').json(); assert commit['actions'] == 100
