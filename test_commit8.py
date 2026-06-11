"""Commit 8 test: Anti-Entropy CRDT Gossip Protocol.

Flow:
1. Boot 3 nodes (using --bootstrap).
2. Trigger a CRDT transaction on Peer_1 via /global_retrieve.
3. Wait 30s for gossip to propagate.
4. Verify Peer_3 has the same ledger event (without ever calling /crdt_sync manually).
"""
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
# TEST 1: All 3 nodes alive
# ------------------------------------------------------------------
section("TEST 1: All 3 nodes alive")
for base, name in [(BASE1, "Peer_1"), (BASE2, "Peer_2"), (BASE3, "Peer_3")]:
    r = httpx.get(f"{base}/ping")
    assert r.status_code == 200, f"FAIL: {name} not responding"
    print(f"  {name}: alive")
print("  -> All 3 nodes up  [PASS]")

# ------------------------------------------------------------------
# TEST 2: Gossip tasks are running (verify via /crdt_sync endpoint exists)
# ------------------------------------------------------------------
section("TEST 2: /crdt_sync push-pull endpoint returns 'ledger' key")
r = httpx.post(f"{BASE1}/crdt_sync", json={})
assert r.status_code == 200
data = r.json()
print(f"  Response keys: {list(data.keys())}")
assert "ledger" in data, "FAIL: 'ledger' key missing from /crdt_sync response"
assert "merged" in data, "FAIL: 'merged' key missing"
assert "ignored" in data, "FAIL: 'ignored' key missing"
print("  -> /crdt_sync returns ledger  [PASS]")

# ------------------------------------------------------------------
# TEST 3: Generate a CRDT event on Peer_1
# ------------------------------------------------------------------
section("TEST 3: Generate CRDT event on Peer_1 via /global_retrieve")
print("  Waiting 12s for heartbeat/gossip to initialize peer routing tables...")
for i in range(12, 0, -1):
    print(f"  {i}s...", end=" ", flush=True)
    time.sleep(1)
print()

r = httpx.get(f"{BASE1}/global_retrieve?drug_id=DB00001&ttl=2", timeout=90.0)
assert r.status_code == 200, f"FAIL: global_retrieve status {r.status_code}"

# Check Peer_1 ledger has at least 1 event
r1 = httpx.get(f"{BASE1}/crdt_state")
p1_state = r1.json()
p1_ledger_size = p1_state["ledger_size"]
print(f"  Peer_1 ledger size after query: {p1_ledger_size}")
assert p1_ledger_size >= 1, f"FAIL: Peer_1 ledger should have >=1 event, got {p1_ledger_size}"
p1_update_ids = list(p1_state["ledger"].keys())
print(f"  Peer_1 update_ids: {[uid[:8]+'...' for uid in p1_update_ids]}")
print("  -> CRDT event generated on Peer_1  [PASS]")

# ------------------------------------------------------------------
# TEST 4: Wait for gossip to propagate to Peer_3
# ------------------------------------------------------------------
section("TEST 4: Anti-entropy gossip propagation (waiting 30s)")
print("  Doing absolutely nothing — letting background gossip loop run...")
for i in range(30, 0, -1):
    print(f"  {i}s...", end=" ", flush=True)
    time.sleep(1)
print()

# ------------------------------------------------------------------
# TEST 5: Peer_3 should now have Peer_1's CRDT events
# ------------------------------------------------------------------
section("TEST 5: Peer_3 CRDT ledger contains Peer_1's events")
r3 = httpx.get(f"{BASE3}/crdt_state")
p3_state = r3.json()
p3_ledger = p3_state["ledger"]
p3_ledger_size = p3_state["ledger_size"]
print(f"  Peer_3 ledger size: {p3_ledger_size}")
print(f"  Peer_3 update_ids: {[uid[:8]+'...' for uid in p3_ledger.keys()]}")

assert p3_ledger_size >= 1, f"FAIL: Peer_3 ledger empty — gossip did not propagate"

# Check that at least one of Peer_1's update_ids made it to Peer_3
overlapping = [uid for uid in p1_update_ids if uid in p3_ledger]
print(f"  Matching events between Peer_1 and Peer_3: {[uid[:8]+'...' for uid in overlapping]}")
assert len(overlapping) >= 1, "FAIL: None of Peer_1's events found in Peer_3's ledger!"
print("  -> Gossip successfully propagated Peer_1 events to Peer_3  [PASS]")

# ------------------------------------------------------------------
# TEST 6: Peer_2 also received the events
# ------------------------------------------------------------------
section("TEST 6: Peer_2 CRDT ledger also has the events")
r2 = httpx.get(f"{BASE2}/crdt_state")
p2_state = r2.json()
p2_ledger = p2_state["ledger"]
p2_ledger_size = p2_state["ledger_size"]
print(f"  Peer_2 ledger size: {p2_ledger_size}")
assert p2_ledger_size >= 1, "FAIL: Peer_2 ledger empty"
overlapping2 = [uid for uid in p1_update_ids if uid in p2_ledger]
assert len(overlapping2) >= 1, "FAIL: Peer_1's events not in Peer_2's ledger"
print(f"  Peer_2 has {len(overlapping2)} matching event(s)  [PASS]")

# ------------------------------------------------------------------
# TEST 7: Verify LWW — timestamps match exactly (no corruption)
# ------------------------------------------------------------------
section("TEST 7: LWW integrity — timestamps match across all peers")
for uid in p1_update_ids:
    ts_p1 = p1_state["ledger"].get(uid, {}).get("timestamp")
    ts_p3 = p3_ledger.get(uid, {}).get("timestamp")
    if ts_p3 is not None:
        assert abs(ts_p1 - ts_p3) < 0.001, f"FAIL: timestamp mismatch for {uid[:8]}: P1={ts_p1} P3={ts_p3}"
        print(f"  {uid[:8]}...: P1 ts={ts_p1:.3f} == P3 ts={ts_p3:.3f}  [OK]")
print("  -> LWW timestamps identical across peers  [PASS]")

print("\n" + "=" * 65)
print("  ALL 7 TESTS PASSED - Commit 8 Anti-Entropy Gossip verified")
print("=" * 65)
