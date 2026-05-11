"""DeepWalk-style graph embedding via random walks + PPMI -- pure stdlib.

Pipeline:
  1. Build a weighted bipartite graph (staff -- client).
     Edge weight = past assignment frequency / hours.
  2. Random walks: from each node, sample K walks of length L,
     transitioning to a neighbour with probability proportional to edge weight.
  3. Sliding-window co-occurrence count over walk sequences.
  4. PPMI weighting:
        n_ij     = co-occurrence count (i, j)
        n_i      = total count for node i
        N        = total pair count
        PMI      = log( (n_ij * N) / (n_i * n_j) )
        PPMI     = max(0, PMI)
  5. Each node's PPMI row is its (sparse) embedding.
  6. Cosine similarity between rows scores link strength /
     "do these two nodes share similar neighbours in the graph".

This is the "PPMI flavour" of DeepWalk (Levy & Goldberg 2014 showed
SGNS implicitly factorises PPMI - kI). We keep PPMI raw to avoid the
extra SVD step; cosine on PPMI rows is a strong link-prediction baseline.

Pure stdlib: math + random + statistics + dataclasses + collections.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from statistics import fmean


# ============================ graph =================================== #


@dataclass
class WeightedGraph:
    """Undirected weighted graph.

    nodes:        ordered list of node IDs (str)
    node_index:   id -> int (column in PPMI matrix)
    adjacency:    node_id -> list of (neighbour_id, weight)
    """
    nodes: list[str] = field(default_factory=list)
    node_index: dict[str, int] = field(default_factory=dict)
    adjacency: dict[str, list[tuple[str, float]]] = field(default_factory=dict)

    def add_node(self, node_id: str) -> None:
        if node_id not in self.node_index:
            self.node_index[node_id] = len(self.nodes)
            self.nodes.append(node_id)
            self.adjacency[node_id] = []

    def add_edge(self, u: str, v: str, weight: float = 1.0) -> None:
        self.add_node(u)
        self.add_node(v)
        self.adjacency[u].append((v, weight))
        self.adjacency[v].append((u, weight))

    def neighbours(self, node_id: str) -> list[tuple[str, float]]:
        return self.adjacency.get(node_id, [])

    def n_nodes(self) -> int:
        return len(self.nodes)


def build_bipartite_graph(
    edges: list[tuple[str, str, float]],
) -> WeightedGraph:
    """Build undirected weighted graph from a list of (u, v, weight) triples."""
    g = WeightedGraph()
    for u, v, w in edges:
        g.add_edge(u, v, w)
    return g


# ============================ random walks ============================ #


def _weighted_choice(rng: random.Random, items: list[tuple[str, float]]) -> str:
    """Sample one item from list of (id, weight) with probability ∝ weight."""
    total = sum(w for _, w in items)
    if total <= 0:
        return rng.choice(items)[0]
    r = rng.random() * total
    acc = 0.0
    for node_id, w in items:
        acc += w
        if r <= acc:
            return node_id
    return items[-1][0]


def random_walk(
    g: WeightedGraph, start: str, length: int, rng: random.Random,
) -> list[str]:
    """One random walk: length L weighted-neighbour steps starting at start."""
    walk = [start]
    cur = start
    for _ in range(length - 1):
        neigh = g.neighbours(cur)
        if not neigh:
            break
        cur = _weighted_choice(rng, neigh)
        walk.append(cur)
    return walk


def generate_walks(
    g: WeightedGraph,
    n_walks_per_node: int = 10,
    walk_length: int = 10,
    seed: int = 42,
) -> list[list[str]]:
    """Generate all walks: each node starts n_walks_per_node walks."""
    rng = random.Random(seed)
    walks: list[list[str]] = []
    for node in g.nodes:
        for _ in range(n_walks_per_node):
            walks.append(random_walk(g, node, walk_length, rng))
    return walks


# ============================ co-occurrence + PPMI ==================== #


def cooccurrence_counts(
    walks: list[list[str]], window_size: int = 5,
) -> tuple[dict[tuple[str, str], int], dict[str, int], int]:
    """Slide a symmetric window over each walk and count node co-occurrences.

    Returns (pair_counts, node_totals, total_pairs).
    """
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    node_totals: dict[str, int] = defaultdict(int)
    total = 0
    for walk in walks:
        n = len(walk)
        for i in range(n):
            for j in range(max(0, i - window_size), min(n, i + window_size + 1)):
                if i == j:
                    continue
                u, v = walk[i], walk[j]
                pair_counts[(u, v)] += 1
                node_totals[u] += 1
                total += 1
    return dict(pair_counts), dict(node_totals), total


def compute_ppmi(
    pair_counts: dict[tuple[str, str], int],
    node_totals: dict[str, int],
    total_pairs: int,
    shift: float = 0.0,
) -> dict[tuple[str, str], float]:
    """PPMI[i][j] = max(0, log( n_ij * N / (n_i * n_j) ) - shift).

    Returns sparse dict; missing pairs implicitly = 0.
    `shift` corresponds to SGNS negative-sampling correction (Levy & Goldberg 2014).
    """
    ppmi: dict[tuple[str, str], float] = {}
    for (i, j), n_ij in pair_counts.items():
        n_i = node_totals.get(i, 0)
        n_j = node_totals.get(j, 0)
        if n_i <= 0 or n_j <= 0 or n_ij <= 0:
            continue
        pmi = math.log(n_ij * total_pairs / (n_i * n_j))
        val = max(0.0, pmi - shift)
        if val > 0.0:
            ppmi[(i, j)] = val
    return ppmi


# ============================ embedding (PPMI rows) =================== #


@dataclass
class GraphEmbedding:
    graph: WeightedGraph
    ppmi: dict[tuple[str, str], float]
    rows: dict[str, dict[str, float]] = field(default_factory=dict)
    n_walks_per_node: int = 10
    walk_length: int = 10
    window_size: int = 5

    def __post_init__(self):
        # Build per-node row dicts for O(1) row access.
        rows: dict[str, dict[str, float]] = defaultdict(dict)
        for (i, j), v in self.ppmi.items():
            rows[i][j] = v
        self.rows = dict(rows)


def fit_graph_embedding(
    edges: list[tuple[str, str, float]],
    n_walks_per_node: int = 10,
    walk_length: int = 10,
    window_size: int = 5,
    shift: float = 0.0,
    seed: int = 42,
) -> GraphEmbedding:
    """Full pipeline: build graph -> walks -> co-occurrence -> PPMI."""
    g = build_bipartite_graph(edges)
    walks = generate_walks(g, n_walks_per_node, walk_length, seed=seed)
    pair_counts, node_totals, total = cooccurrence_counts(walks, window_size)
    ppmi = compute_ppmi(pair_counts, node_totals, total, shift=shift)
    return GraphEmbedding(
        graph=g, ppmi=ppmi,
        n_walks_per_node=n_walks_per_node, walk_length=walk_length, window_size=window_size,
    )


# ============================ similarity / link prediction =========== #


def cosine_dict(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    # Compute dot using smaller dict
    if len(a) > len(b):
        a, b = b, a
    dot = 0.0
    for k, v in a.items():
        if k in b:
            dot += v * b[k]
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 0.0
    return dot / (norm_a * norm_b)


def similarity(emb: GraphEmbedding, u: str, v: str) -> float:
    return cosine_dict(emb.rows.get(u, {}), emb.rows.get(v, {}))


def direct_ppmi(emb: GraphEmbedding, u: str, v: str) -> float:
    """Direct PPMI score (high = strong observed co-occurrence)."""
    return emb.ppmi.get((u, v), 0.0)


@dataclass
class LinkPrediction:
    candidate: str
    cosine_score: float
    direct_ppmi: float
    combined_score: float


def top_k_neighbours(
    emb: GraphEmbedding, query: str,
    candidate_filter=None,         # optional: callable(node_id) -> bool
    k: int = 5,
    cosine_weight: float = 0.6,
    ppmi_weight: float = 0.4,
) -> list[LinkPrediction]:
    """Rank candidates by combined cosine-on-PPMI + direct-PPMI score."""
    out: list[LinkPrediction] = []
    for node in emb.graph.nodes:
        if node == query:
            continue
        if candidate_filter is not None and not candidate_filter(node):
            continue
        cs = similarity(emb, query, node)
        pp = direct_ppmi(emb, query, node)
        combined = cosine_weight * cs + ppmi_weight * math.tanh(pp)
        out.append(LinkPrediction(node, cs, pp, combined))
    out.sort(key=lambda r: -r.combined_score)
    return out[: k]


# ============================ diagnostics =========================== #


def coverage(emb: GraphEmbedding) -> dict:
    """Fraction of nodes that have at least one PPMI entry."""
    nodes_with_rows = len(emb.rows)
    return {
        "n_nodes": emb.graph.n_nodes(),
        "n_nodes_with_ppmi": nodes_with_rows,
        "n_ppmi_pairs": len(emb.ppmi),
        "coverage_pct": nodes_with_rows / max(emb.graph.n_nodes(), 1),
    }


def avg_walk_diversity(walks: list[list[str]]) -> float:
    """Mean unique-node fraction per walk (1.0 = no revisits; 0.5 = half revisits)."""
    if not walks:
        return 0.0
    diversities = []
    for w in walks:
        if not w:
            continue
        diversities.append(len(set(w)) / len(w))
    return fmean(diversities) if diversities else 0.0
