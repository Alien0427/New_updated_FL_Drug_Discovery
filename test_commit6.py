"""Commit 6 test script: Dynamic Initiator FedAvg Aggregation."""
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
# Link nodes and wait for heartbeat
# ------------------------------------------------------------------
section("Setup: linking 3 nodes bidirectionally")
for src, dst in [(BASE1, BASE2), (BASE1, BASE3), (BASE2, BASE1),
                 (BASE2, BASE3), (BASE3, BASE1), (BASE3, BASE2)]:
    r = httpx.post(f"{src}/add_peer?url={dst}")
    print(f"  {src} -> {dst}: {r.json()['result']}")

print("\nWaiting 12s for heartbeats to populate node_ids...")
for i in range(12, 0, -1):
    print(f"  {i}s...", end=" ", flush=True)
    time.sleep(1)
print()

# ------------------------------------------------------------------
# TEST 1: global_retrieve returns FedAvg structure
# ------------------------------------------------------------------
section("TEST 1: FedAvg aggregation in global_retrieve")
start = time.time()
r = httpx.get(f"{BASE1}/global_retrieve?drug_id=DB00001&ttl=2", timeout=90.0)
elapsed = time.time() - start
assert r.status_code == 200, f"FAIL: status {r.status_code}"
data = r.json()
print(f"Query completed in {elapsed:.2f}s")

# Check mandatory keys present
for key in ["completeness_score", "global_confidence", "available_peers",
            "missing_peers", "federated_link_prediction_metrics",
            "global_aggregated_model", "raw_responses",
            "peer_link_prediction_metrics", "routing_mode", "crdt_update_id"]:
    assert key in data, f"FAIL: key '{key}' missing from response"
print("  -> All required keys present  [PASS]")

# ------------------------------------------------------------------
# TEST 2: completeness_score shows 3/3
# ------------------------------------------------------------------
section("TEST 2: completeness_score")
cs = data["completeness_score"]
print(f"  completeness_score = {cs}")
assert cs == "3/3", f"FAIL: expected '3/3', got '{cs}'"
print("  -> completeness_score = 3/3  [PASS]")

# ------------------------------------------------------------------
# TEST 3: all 3 peers in available_peers
# ------------------------------------------------------------------
section("TEST 3: available_peers contains all 3 nodes")
ap = data["available_peers"]
print(f"  available_peers = {ap}")
assert "Peer_1" in ap, "FAIL: Peer_1 missing"
assert "Peer_2" in ap, "FAIL: Peer_2 missing"
assert "Peer_3" in ap, "FAIL: Peer_3 missing"
assert len(ap) == 3, f"FAIL: expected 3 entries, got {len(ap)}"
print("  -> All 3 peers present  [PASS]")

# ------------------------------------------------------------------
# TEST 4: federated_link_prediction_metrics is averaged
# ------------------------------------------------------------------
section("TEST 4: federated_link_prediction_metrics (averaged)")
fm = data["federated_link_prediction_metrics"]
print(json.dumps(fm, indent=2))
assert "precision" in fm, "FAIL: precision missing"
assert "recall" in fm, "FAIL: recall missing"
assert "f1_score" in fm, "FAIL: f1_score missing"
assert "top_50_precision" in fm, "FAIL: top_50_precision missing"
assert 0.0 <= fm["precision"] <= 1.0, "FAIL: precision out of range"
assert 0.0 <= fm["recall"] <= 1.0, "FAIL: recall out of range"
assert 0.0 <= fm["f1_score"] <= 1.0, "FAIL: f1_score out of range"
# Verify it's actually an average (not just copying one peer)
pm = data["peer_link_prediction_metrics"]
avg_prec = round(sum(pm[p]["precision"] for p in pm) / len(pm), 4)
assert abs(fm["precision"] - avg_prec) < 0.001, "FAIL: precision is not averaged correctly"
print(f"  -> Federated precision = {fm['precision']} (verified average)  [PASS]")

# ------------------------------------------------------------------
# TEST 5: global_aggregated_model shows shape info (not raw weights)
# ------------------------------------------------------------------
section("TEST 5: global_aggregated_model has shape summaries")
gam = data["global_aggregated_model"]
print(json.dumps(gam, indent=2))
assert len(gam) > 0, "FAIL: global_aggregated_model is empty"
for layer, info in gam.items():
    assert "shape" in info, f"FAIL: layer '{layer}' missing 'shape' key"
    assert isinstance(info["shape"], list), f"FAIL: shape for '{layer}' is not a list"
print("  -> All layers have shape summaries  [PASS]")

# ------------------------------------------------------------------
# TEST 6: raw_responses are sanitized (no model_weights blobs)
# ------------------------------------------------------------------
section("TEST 6: raw_responses are sanitized")
rr = data["raw_responses"]
print(f"  {len(rr)} raw responses returned")
assert len(rr) == 3, f"FAIL: expected 3 sanitized responses, got {len(rr)}"
for resp in rr:
    assert "model_weights" not in resp, f"FAIL: model_weights still present in response for {resp.get('peer_id')}"
    assert "model_weights_summary" in resp, f"FAIL: model_weights_summary missing for {resp.get('peer_id')}"
    print(f"  - {resp.get('peer_id')}: model_weights=absent, model_weights_summary=present  [OK]")
print("  -> All raw_responses sanitized  [PASS]")

# ------------------------------------------------------------------
# TEST 7: global_confidence is a float between 0 and 1
# ------------------------------------------------------------------
section("TEST 7: global_confidence is valid")
gc = data["global_confidence"]
print(f"  global_confidence = {gc}")
assert isinstance(gc, float), f"FAIL: expected float, got {type(gc)}"
assert 0.0 <= gc <= 1.0, f"FAIL: confidence {gc} out of range"
print("  -> global_confidence valid  [PASS]")

print("\n" + "=" * 65)
print("  ALL 7 TESTS PASSED - Commit 6 FedAvg verified successfully")
print("=" * 65)
