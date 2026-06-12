# Decentralized P2P Federated Drug Discovery — Project Documentation

**Repository:** https://github.com/Alien0427/Updated_FL_Drug_Discovery  
**Team Members:** Shiven Patro · Devananditha Vimalkumar  
**Course:** Decentralized Federated Learning  

---

## 1. Project Overview

This project implements a **fully decentralized, Peer-to-Peer (P2P) Federated Learning system** for drug-target interaction discovery. The system allows multiple research nodes — each holding a private partition of a drug-target interaction graph — to collaboratively train a neural network model without any of them sharing their raw data.

The underlying dataset is derived from **ChEMBL / BioSNAP drug-target interaction data**, partitioned into three private graph files (one per peer). Each peer trains a local **PyTorch Graph Neural Network (LinkPredictor)** on its private partition and participates in **Federated Averaging (FedAvg)** to produce a global model — all without a central coordinator.

---

## 2. Fulfillment of Requirements

The following table maps each of the specified requirements to the exact implementation in the codebase.

| # | Requirement (as specified) | Implementation |
|---|---------------------------|----------------|
| 1 | No dedicated coordinator. Any node can initiate a `global_retrieve` query. | `GET /global_retrieve` is registered on **every** peer. Any port (8001–800N) can initiate a full federated query. Proven by firing the query at `Peer_4`, the last-joined node. |
| 2 | Every node is both a **client** (holds private graph, runs local model) and a **routing/aggregation peer**. | Each `peer_node.py` instance loads its own `.graphml` partition, trains its own `LinkPredictor` model, forwards DHT queries, runs FedAvg aggregation, and broadcasts the global model back to participants. |
| 3 | Query propagates via **DHT (Kademlia) — PREFERRED**, with bounded TTL fallback. | `NODE_ID` = SHA-256(peer name + port), 256-bit integer. `calculate_xor_distance()` implements Kademlia XOR metric. `POST /dht_retrieve` is the TTL-decremented forwarding endpoint. Fault-tolerant fallback marks dead peers `OFFLINE` and continues via surviving peers. |
| 4 | Each node keeps a **partial view of the network** (membership list). | `KNOWN_PEERS` dict — each peer stores only discovered neighbors. A background `heartbeat_loop` (every 10 s) pings all known peers and performs gossip-based discovery by fetching each active peer's routing table. |
| 5 | Exactly-once ledger replaced with a **CRDT-based distributed log**. | `CRDT_LEDGER` (LWW-Map, in-memory, per-peer). `merge_crdt_event()` applies Last-Writer-Wins conflict resolution. `crdt_gossip_loop` runs every 15 s, automatically propagating ledger events across all peers without any central database. |

---

## 3. System Architecture

```
                  ┌─────────────────────────────────────────────────┐
                  │           Decentralized P2P Overlay              │
                  │                                                   │
          ┌───────┴──────┐   DHT (Kademlia)   ┌───────────────────┐ │
          │   Peer_1     │◄──────────────────►│     Peer_2        │ │
          │  :8001       │                    │    :8002          │ │
          │  client_1    │   gossip / CRDT    │   client_2        │ │
          │  graph.graphml│◄─────────────────►│   graph.graphml   │ │
          └──────┬───────┘                    └─────────┬─────────┘ │
                 │                                      │            │
                 │          ┌────────────────┐          │            │
                 └─────────►│    Peer_3      │◄─────────┘           │
                            │   :8003        │                       │
                 ┌─────────►│  client_3      │◄─────────┐           │
                 │          │  graph.graphml │          │            │
                 │          └────────────────┘          │            │
                 │                                      │            │
          ┌──────┴───────┐                    ┌─────────┴─────────┐ │
          │   Peer_4     │◄──────────────────►│   Peer_N ...      │ │
          │  :8004       │   FedAvg weights   │   :800N           │ │
          └──────────────┘                    └───────────────────┘ │
                  └─────────────────────────────────────────────────┘

  Any peer can initiate → DHT routes → all peers train locally →
  FedAvg aggregates → global model disseminated back to all participants →
  CRDT ledger event gossiped to all nodes automatically
```

---

## 4. File-by-File Breakdown

---

### `peer_node.py` — The Complete P2P System (1,572 lines)

> **This is the entire system.** Every peer in the network runs this same file with different `--port`, `--name`, and `--file` arguments. There is no separate coordinator, no separate client — one file does everything.

**How to start a peer:**
```bash
python peer_node.py --port 8001 --file data/client_1_graph.graphml --name Peer_1
python peer_node.py --port 8002 --file data/client_2_graph.graphml --name Peer_2 --bootstrap http://localhost:8001
```

**Internal components:**

| Component | Lines | What it does |
|-----------|-------|-------------|
| `_generate_node_id()` | 53–57 | Derives a stable 256-bit Kademlia node ID via SHA-256 of peer identity |
| `KNOWN_PEERS` dict | 69 | Membership list — partial view of the network (Req 4) |
| `CRDT_LEDGER` dict | 83 | In-memory LWW-Map distributed log (Req 5) |
| `mark_peer_offline()` | 95–104 | Immediately marks a peer as `OFFLINE` on network failure |
| `heartbeat_loop()` | 111–171 | Background task — pings peers every 10 s, performs gossip-based peer discovery |
| `crdt_gossip_loop()` | 178–225 | Background task — anti-entropy sync of CRDT ledger every 15 s |
| `lifespan()` | 230–296 | Startup: bootstrap into network; Shutdown: cancel background tasks |
| `load_peer_graph()` | 302–312 | Loads private `.graphml` partition using NetworkX |
| `LinkPredictor` | 315–350 | PyTorch MLP with learned embeddings; supports classification (drug-target interaction) and regression (binding affinity) |
| `state_dict_to_lists()` / `lists_to_state_dict()` | 353–364 | Serialize/deserialize PyTorch model weights for HTTP transmission |
| `aggregate_models()` | ~900 | FedAvg — element-wise averaging of all peer weight tensors |
| `merge_crdt_event()` | ~850 | LWW merge rule — newer timestamp wins, stale updates ignored |

**API Endpoints exposed on every peer:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ping` | GET | Health check; returns node identity and DHT node_id |
| `/peers` | GET | Returns `KNOWN_PEERS` — the partial network membership list |
| `/bootstrap` | POST | New peer calls this to join the network; returns routing table |
| `/closest_peers` | GET | Kademlia: returns k-closest peers by XOR distance |
| `/dht_retrieve` | POST | Internal DHT forwarding endpoint (decrements TTL, forwards query) |
| `/local_retrieve` | GET | Trains local model on private graph, returns predictions |
| `/global_retrieve` | GET | **Main feature** — initiates a full federated query + FedAvg |
| `/receive_global_model` | POST | Receives FedAvg model after dissemination; evaluates locally |
| `/crdt_sync` | POST | Receives another peer's ledger; merges via LWW; returns own ledger |
| `/crdt_state` | GET | Inspect the full CRDT ledger (equivalent to the old audit dashboard) |

**The `/global_retrieve` execution flow:**
```
1. Generate unique query_id (UUID)
2. Record query_started event in CRDT_LEDGER
3. Identify all ACTIVE peers from KNOWN_PEERS
4. Route to each peer via DHT /dht_retrieve (XOR-distance routing, TTL-bounded)
5. Each peer runs /local_retrieve → trains local PyTorch model → returns weights
6. FedAvg: element-wise average all weight tensors layer by layer
7. Record completion event in CRDT_LEDGER
8. Broadcast FedAvg model to all participants via /receive_global_model (fire-and-forget)
9. Return aggregated metrics + model summary to caller
```

---

### `launch_network.py` — Network Orchestrator & Live CLI Dashboard (350 lines)

> Single-command tool to spawn and monitor the entire swarm. Designed for the live demo.

**How to run:**
```bash
python launch_network.py --nodes 4
python launch_network.py --nodes 4 --base-port 8001
```

**What it does:**
- Spawns `N` peer processes using `subprocess.Popen`, each running `peer_node.py`
- Node 1 is the **seed** (no bootstrap); Nodes 2–N bootstrap via Node 1
- Graph files are assigned cyclically: `client_1 → client_2 → client_3 → client_1 → ...`
- Every 2 seconds: clears terminal, polls `/ping`, `/peers`, `/crdt_state` on all ports
- Renders a **live colour-coded ASCII table**:
  - 🟢 Green = `ALIVE` / fully meshed
  - 🟡 Yellow = `BOOTING` / partial mesh
  - 🔵 Cyan = CRDT events detected
- `Ctrl+C` → calls `.terminate()` on all child processes → clean shutdown

**Sample dashboard output:**
```
+=================================================================+
|    P2P DRUG DISCOVERY  --  NETWORK ORCHESTRATOR DASHBOARD      |
+=================================================================+
  Nodes: 4  |  Uptime: 45s  |  Refresh: every 2s  |  Ctrl+C to shutdown

+------------+--------+------------+---------------+--------------------+--------------------+
| Node       |   Port | Status     | Known Peers   | CRDT Ledger        | DHT ID Prefix      |
+------------+--------+------------+---------------+--------------------+--------------------+
| Peer_1     |   8001 | [ALIVE]    | 3             | 5                  | a3f2d1c0b4e9...    |
| Peer_2     |   8002 | [ALIVE]    | 3             | 5                  | 7b8c910ef213...    |
| Peer_3     |   8003 | [ALIVE]    | 3             | 5                  | 2d4f6a8c0e1b...    |
| Peer_4     |   8004 | [ALIVE]    | 3             | 5                  | f1e3d5c7b9a0...    |
+------------+--------+------------+---------------+--------------------+--------------------+

  Alive: 4/4  |  Fully Meshed: 4/4  |  Total CRDT Events: 20
```

---

### `test_commit4.py` — CRDT Ledger Verification (Requirement 5)

> Proves that the CRDT LWW-Map correctly replaces the old SQLite exactly-once ledger.

**Requires:** 2 peer nodes running on ports 8001 and 8002.

| Test | Assertion |
|------|-----------|
| Test 1 | Fresh peer has an empty CRDT ledger at boot |
| Test 2 | After `global_retrieve`, exactly one event is committed to the ledger |
| Test 3 | LWW merge: newer timestamp overwrites older; stale timestamp is ignored |
| Test 4 | Batch sync: 3 new events merged in one `/crdt_sync` call |
| Test 5 | Re-sending the same batch: all 3 events ignored (idempotent — no duplicates) |
| Test 6 | Cross-peer: Peer_1's ledger pushed to Peer_2; Peer_2 grows accordingly |
| Test 7 | Final `/crdt_state` shows all committed events with correct structure |

---

### `test_commit5.py` — DHT Kademlia Routing Verification (Requirement 3)

> Proves that the Kademlia XOR-distance routing is correctly implemented.

**Requires:** 2 peer nodes.

- Verifies `/ping` returns a valid 256-bit `node_id`
- Verifies `/closest_peers` returns peers sorted by XOR distance
- Confirms XOR distance property: `distance(A, B) = distance(B, A)`

---

### `test_commit6.py` — FedAvg Aggregation Verification (Requirement 2)

> Proves that the local model training and federated averaging work correctly.

**Requires:** 2 peer nodes.

- Fires `/global_retrieve` and verifies valid metric output
- Confirms `federated_link_prediction_metrics` contains `precision`, `recall`, `f1_score`
- Confirms FedAvg model has correct layer structure: `embeddings.weight`, `mlp.0.weight`, `mlp.0.bias`

---

### `test_commit7.py` — DHT Query Propagation Verification (Requirement 3)

> Proves queries propagate correctly through the DHT with TTL control.

**Requires:** 3 peer nodes.

- Tests TTL = 1 (query stays local, does not propagate beyond 1 hop)
- Tests TTL = 3 (query reaches all 3 peers)
- Verifies TTL is correctly decremented at each forwarding hop
- Verifies participating peers list matches TTL-reachable nodes

---

### `test_commit8.py` — Anti-Entropy CRDT Gossip Verification (Requirement 5)

> Proves the gossip loop automatically propagates CRDT events without manual intervention.

**Requires:** 3 peer nodes.

- Commits an event to Peer_1's ledger via a query
- Does **not** call `/crdt_sync` manually on any other peer
- Waits 20 seconds for the background `crdt_gossip_loop` to fire
- Asserts that Peer_2 and Peer_3 automatically have the event

---

### `test_commit9.py` — Fault Tolerance Verification (Requirement 3) ⭐ Self-Spawning

> Proves the system degrades gracefully when a peer dies mid-query and recovers when it comes back.

**No manual setup required** — spawns its own 3-node swarm.

| Phase | Action | Expected Result |
|-------|--------|----------------|
| Setup | Boot 3 peers, form mesh | All 3 nodes ALIVE |
| Fault injection | Kill Peer_2's process mid-query | Query still returns results from Peer_1 and Peer_3 |
| Membership update | Check Peer_1's KNOWN_PEERS | Peer_2 status = `"offline"` |
| Recovery | Restart Peer_2 | Heartbeat detects Peer_2 back ONLINE within 10 s |

---

### `test_commit10.py` — Model Dissemination Verification (Requirement 2) ⭐ Self-Spawning

> Proves that after FedAvg, the initiating peer broadcasts the global model to all participants, and each peer evaluates it against their local holdout set.

**No manual setup required** — spawns its own 3-node swarm.

- Verifies `dissemination_targets` is non-empty in the `global_retrieve` response
- Calls `/receive_global_model` on Peer_2 and Peer_3 directly
- Verifies each peer reconstructs the FedAvg model from JSON weights
- Verifies each peer returns both `local_metrics` (before) and `global_metrics` (after) — proving the before-vs-after comparison is logged

---

### `test_commit11.py` — Grand Finale End-to-End Test ⭐ Self-Spawning

> The complete automated verification of all requirements working together in a single test run.

**No manual setup required** — spawns its own 4-node swarm.

| Step | What is tested | Requirement |
|------|---------------|-------------|
| 1 | Spawn 4-node swarm | Setup |
| 2 | All 4 nodes respond on `/ping` | Req 1, 2 |
| 3 | Full gossip mesh: all peers know N-1 others | Req 4 |
| 4 | Fire `global_retrieve` at Peer_4 (last-joined node) | **Req 1** |
| 5 | Peer_4 CRDT ledger ≥ 1 after the query | Req 5 |
| 6 | CRDT event propagates to all 4 nodes within 30 s | **Req 5** |
| 7 | All 4 processes terminate cleanly on `.terminate()` | Req 3 (fault tolerance) |

**Result from latest test run:**
```
ALL TESTS PASSED - Commit 11 Network Orchestrator verified

  Alive: 4/4  |  Fully Meshed: 4/4  |  Total CRDT Events: 20
  dissemination_targets: ['Peer_2', 'Peer_3', 'Peer_1']
  federated_metrics: { precision: 0.58, recall: 0.68, f1_score: 0.63 }
  CRDT event propagated to all 4 nodes [PASS]
  All 4 processes terminated cleanly [PASS]
```

---

### `check_requirements.py` — Automated Requirement Coverage Checker

> Scans `peer_node.py` for 22 specific code tokens, one for each sub-point of the 5 requirements, and prints `[OK]` or `[MISSING]` for each.

**Run:**
```bash
python check_requirements.py
```

**Output:**
```
  Ma'am's Requirement Coverage -- peer_node.py
  =================================================================
  [OK]       Req 1 - Any node can initiate global_retrieve
  [OK]       Req 1 - No dedicated coordinator (endpoint on all)
  [OK]       Req 2 - Private graph per node
  [OK]       Req 2 - Local PyTorch model training
  [OK]       Req 2 - Local model evaluation
  [OK]       Req 2 - Node acts as routing peer (DHT forward)
  [OK]       Req 2 - Node acts as aggregation peer (FedAvg)
  [OK]       Req 2 - Model Dissemination after FedAvg
  [OK]       Req 3 - DHT preferred (Kademlia XOR distance)
  [OK]       Req 3 - Kademlia Node ID (SHA-256 hash)
  [OK]       Req 3 - DHT query propagation endpoint
  [OK]       Req 3 - Bounded TTL on propagation
  [OK]       Req 3 - Fallback routing (Fault Tolerance)
  [OK]       Req 4 - Membership list (KNOWN_PEERS)
  [OK]       Req 4 - Heartbeat loop (liveness tracking)
  [OK]       Req 4 - Gossip-based peer discovery
  [OK]       Req 4 - Bootstrap endpoint (network entry)
  [OK]       Req 5 - CRDT Ledger replacing exact-once log
  [OK]       Req 5 - LWW merge strategy
  [OK]       Req 5 - Anti-entropy gossip loop
  [OK]       Req 5 - CRDT sync endpoint
  [OK]       Req 5 - CRDT state endpoint
  =================================================================
  Total lines in peer_node.py : 1572
  Result: ALL PRESENT -- fully implemented
```

---

### `data/` — Private Graph Partitions

| File | Contents |
|------|----------|
| `client_1_graph.graphml` | Partition 1 of the drug-target interaction graph (~350 KB) |
| `client_2_graph.graphml` | Partition 2 of the drug-target interaction graph (~350 KB) |
| `client_3_graph.graphml` | Partition 3 of the drug-target interaction graph (~352 KB) |
| `ChG-TargetDecagon_targets.csv.gz` | Raw ChEMBL / BioSNAP drug-target dataset used to build the graphs |

Each `.graphml` file is the **private data** of one peer. It is never transmitted over the network — only the trained model weights (FedAvg) are shared, preserving data privacy.

---

### Data Preparation Scripts (already executed — no action needed)

| File | What it did |
|------|-------------|
| `download_data.py` | Downloaded raw drug-target data from PubChem/BioSNAP |
| `data_collection.py` | Cleaned and structured the raw interaction data |
| `graph_builder.py` | Built a NetworkX graph from the cleaned CSV data |
| `partition_data.py` | Split the full graph into 3 private partitions (`client_1/2/3_graph.graphml`) |

---

## 5. Demo Workflow

### Quick Start — Full Swarm in One Command

```bash
# Terminal 1: Start the 4-node swarm with live dashboard
python launch_network.py --nodes 4
```

Watch the **Known Peers** column climb from 0 → 3 as the gossip protocol forms the mesh (takes ~15 seconds).

```bash
# Terminal 2: Fire a federated query from Peer_4 (the last-joined node)
curl "http://localhost:8004/global_retrieve?drug_id=CID000000271"
```

Observe in Terminal 1: the **CRDT Ledger** column lights up on all 4 nodes within 30 seconds — without any manual sync.

```bash
# Inspect the distributed ledger on any peer
curl "http://localhost:8001/crdt_state"

# Inspect the membership list (partial network view)
curl "http://localhost:8002/peers"

# Inspect the DHT identity (Kademlia node_id)
curl "http://localhost:8001/ping"
```

### Automated Tests (no manual peer startup needed)

```bash
python check_requirements.py   # Verify all 22 requirements [2 seconds]
python test_commit9.py         # Fault tolerance: kill and recover a peer
python test_commit10.py        # FedAvg model dissemination
python test_commit11.py        # Full grand finale: all requirements end-to-end
```

---

## 6. Technology Stack

| Layer | Technology |
|-------|-----------|
| Peer API Server | FastAPI + Uvicorn (async HTTP) |
| Neural Network | PyTorch — embedding-based MLP (`LinkPredictor`) |
| Graph Processing | NetworkX — GraphML drug-target partitions |
| DHT Routing | Custom Kademlia XOR-distance implementation |
| Distributed Log | In-memory CRDT LWW-Map with anti-entropy gossip |
| Data Science | scikit-learn (F1, precision, recall, MSE, R²) |
| Orchestration | Python `subprocess.Popen` + live ASCII dashboard |

---

*Documentation prepared by Shiven Patro and Devananditha Vimalkumar.*
