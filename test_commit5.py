"""Commit 5 test script: DHT Query Propagation & TTL."""
import json
import time
import httpx

BASE1 = "http://localhost:8001"
BASE2 = "http://localhost:8002"
BASE3 = "http://localhost:8003"


def section(title):
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print("=" * 65)


# ------------------------------------------------------------------
# TEST 1: Check ping to all three nodes
# ------------------------------------------------------------------
section("TEST 1: Verifying all 3 nodes are alive")
for url in [BASE1, BASE2, BASE3]:
    r = httpx.get(f"{url}/ping")
    print(f"Ping {url}:", r.json())
    assert r.status_code == 200

# ------------------------------------------------------------------
# TEST 2: Register peers with each other bidirectionally
# ------------------------------------------------------------------
section("TEST 2: Register peers with each other")
# Peer 1 links
r = httpx.post(f"{BASE1}/add_peer?url={BASE2}")
print("Peer_1 add Peer_2:", r.json())
r = httpx.post(f"{BASE1}/add_peer?url={BASE3}")
print("Peer_1 add Peer_3:", r.json())

# Peer 2 links
r = httpx.post(f"{BASE2}/add_peer?url={BASE1}")
print("Peer_2 add Peer_1:", r.json())
r = httpx.post(f"{BASE2}/add_peer?url={BASE3}")
print("Peer_2 add Peer_3:", r.json())

# Peer 3 links
r = httpx.post(f"{BASE3}/add_peer?url={BASE1}")
print("Peer_3 add Peer_1:", r.json())
r = httpx.post(f"{BASE3}/add_peer?url={BASE2}")
print("Peer_3 add Peer_2:", r.json())

# Wait 12 seconds for background heartbeats to populate the node_ids in KNOWN_PEERS
print("\nWaiting 12 seconds for heartbeat exchanges to resolve node_ids...")
for i in range(12, 0, -1):
    print(f"  waiting {i}s...")
    time.sleep(1)

# Check peers lists
section("Verifying known peers resolved node_ids")
for base, name in [(BASE1, "Peer_1"), (BASE2, "Peer_2"), (BASE3, "Peer_3")]:
    r = httpx.get(f"{base}/peers")
    data = r.json()
    print(f"{name} knows about {data['total_known']} peers:")
    for url, info in data["peers"].items():
        print(f"  - {url}: status={info.get('status')}, node_id={info.get('node_id')}")
        assert info.get("node_id") is not None, f"FAIL: {name} did not resolve node_id for {url}"

# ------------------------------------------------------------------
# TEST 3: The Ripple Test — global retrieve with TTL
# ------------------------------------------------------------------
section("TEST 3: Initiating DHT Query Propagation with global_retrieve")
start_time = time.time()
# Query Peer_1 with a drug query and ttl=2
r = httpx.get(f"{BASE1}/global_retrieve?drug_id=DB00001&ttl=2", timeout=90.0)
elapsed = time.time() - start_time
print(f"Query completed in {elapsed:.2f} seconds")

assert r.status_code == 200, f"FAIL: global_retrieve returned status {r.status_code}"
data = r.json()

print("\nResponse Metadata:")
print(f"  Query: {data.get('query')}")
print(f"  Initiator: {data.get('initiator_peer')}")
print(f"  Routing Mode: {data.get('routing_mode')}")
print(f"  Available Peers: {data.get('available_peers')}")
print(f"  Evidence Paths Count: {data.get('evidence_paths_count')}")

# Verify all 3 peers responded and returned their data
raw_resps = data.get("raw_responses", [])
print(f"\nReceived {len(raw_resps)} raw responses (should be 3):")
peers_responded = []
for resp in raw_resps:
    peer_id = resp.get("peer_id")
    status = resp.get("status")
    has_weights = "model_weights" in resp
    print(f"  - {peer_id}: status={status}, has_model_weights={has_weights}")
    peers_responded.append(peer_id)

assert len(raw_resps) == 3, f"FAIL: expected 3 raw responses, got {len(raw_resps)}"
assert "Peer_1" in peers_responded, "FAIL: Peer_1 response missing"
assert "Peer_2" in peers_responded, "FAIL: Peer_2 response missing"
assert "Peer_3" in peers_responded, "FAIL: Peer_3 response missing"

print("\n" + "=" * 65)
print("  ALL TESTS PASSED - Commit 5 DHT propagation verified successfully")
print("=" * 65)
