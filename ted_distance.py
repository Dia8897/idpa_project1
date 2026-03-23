import argparse
import json
from functools import lru_cache
from pathlib import Path


DEFAULT_TREE_DIR = Path("data/trees_tokens")
_ACTIVE_SOURCE_SUBTREES = frozenset()
_ACTIVE_TARGET_SUBTREES = frozenset()


def load_tree(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["tree"]
        # This opens a JSON file and returns only the "tree" part.


def node_label(node: dict) -> str:
    return str(node.get("label", ""))
    # {"label": "capital", "children": [...]}
# This function extracts "capital".


def is_leaf(node: dict) -> bool:
    return len(node.get("children", [])) == 0


def clone_serializable(node: dict) -> dict:
    """
    Only keep the fields that matter to TED itself.
    Metadata such as raw_values is ignored for the distance computation.
    """
    return {
        "label": node_label(node),
        "children": [clone_serializable(child) for child in node.get("children", [])],
    }
    # This removes anything extra from the node.


def serialize_node(node: dict) -> str:
    return json.dumps(clone_serializable(node), ensure_ascii=False, sort_keys=True)
# This turns a subtree into a JSON string.


def collect_subtree_serials(node: dict) -> set[str]:
    serials = {serialize_node(node)}
    for child in node.get("children", []):
        serials.update(collect_subtree_serials(child))
    return serials


def contained_in_source_tree(node: dict) -> bool:
    return serialize_node(node) in _ACTIVE_SOURCE_SUBTREES


def contained_in_target_tree(node: dict) -> bool:
    return serialize_node(node) in _ACTIVE_TARGET_SUBTREES


def subtree_size(node: dict) -> int:
    return 1 + sum(subtree_size(child) for child in node.get("children", []))
# This counts how many nodes are inside a subtree.

def cost_del_tree(node: dict) -> int:
    """
    Nierman-Jagadish subtree deletion cost:
    - 1 if the subtree already exists somewhere in the destination tree
    - otherwise fall back to subtree size
    """
    if contained_in_target_tree(node):
        return 1
    return subtree_size(node)


def cost_ins_tree(node: dict) -> int:
    """
    Nierman-Jagadish subtree insertion cost:
    - 1 if the subtree already exists somewhere in the source tree
    - otherwise fall back to subtree size
    """
    if contained_in_source_tree(node):
        return 1
    return subtree_size(node)


def cost_upd_root(a: dict, b: dict) -> int:
    """
    Root update cost.

    Project rule:
    - identical labels => 0
    - different leaf labels => 1
    - different internal labels => replace whole subtree rather than rename it
    """
    if node_label(a) == node_label(b):
        return 0
    if is_leaf(a) and is_leaf(b):
        return 1
    return cost_del_tree(a) + cost_ins_tree(b)


@lru_cache(maxsize=None)
def ted(a_serial: str, b_serial: str) -> int:
    """
    Ordered tree edit distance based on the subtree-DP recurrence in the provided
    algorithm sketch.

    Dist[i][j] stores the best cost for transforming the first i children of A
    into the first j children of B, after accounting for the root update cost.
    """
    a = json.loads(a_serial)
    b = json.loads(b_serial)

    if node_label(a) != node_label(b) and not (is_leaf(a) and is_leaf(b)):
        return cost_del_tree(a) + cost_ins_tree(b)

    a_children = a.get("children", [])
    b_children = b.get("children", [])
    m = len(a_children)
    n = len(b_children)

    dist = [[0] * (n + 1) for _ in range(m + 1)]
    dist[0][0] = cost_upd_root(a, b)

    for i in range(1, m + 1):
        dist[i][0] = dist[i - 1][0] + cost_del_tree(a_children[i - 1])

    for j in range(1, n + 1):
        dist[0][j] = dist[0][j - 1] + cost_ins_tree(b_children[j - 1])

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            dist[i][j] = min(
                dist[i - 1][j - 1] + ted(serialize_node(a_children[i - 1]), serialize_node(b_children[j - 1])),
                dist[i - 1][j] + cost_del_tree(a_children[i - 1]),
                dist[i][j - 1] + cost_ins_tree(b_children[j - 1]),
            )

    return dist[m][n]


def normalized_similarity(distance: int, size1: int, size2: int) -> float:
    """
    Convert the distance into an intuitive similarity score in [0,1].
    """
    total = size1 + size2
    if total == 0:
        return 1.0
    return max(0.0, 1.0 - (distance / total))


def slide_similarity_formula1(distance: int) -> float:
    """
    Slide formula 1:
    Sim(A, B) = 1 / (1 + TED(A, B))
    """
    return 1.0 / (1.0 + distance)


def configure_ted_context(tree1: dict, tree2: dict):
    """
    Prepare subtree-membership state and clear the TED cache so callers that need
    both TED values and TED-based backtracking can share the same tested logic.
    """
    global _ACTIVE_SOURCE_SUBTREES, _ACTIVE_TARGET_SUBTREES

    _ACTIVE_SOURCE_SUBTREES = frozenset(collect_subtree_serials(tree1))
    _ACTIVE_TARGET_SUBTREES = frozenset(collect_subtree_serials(tree2))
    ted.cache_clear()


def ted_distance(tree1: dict, tree2: dict):
    configure_ted_context(tree1, tree2)

    size1 = subtree_size(tree1)
    size2 = subtree_size(tree2)
    distance = ted(serialize_node(tree1), serialize_node(tree2))
    similarity = normalized_similarity(distance, size1, size2)
    similarity_formula1 = slide_similarity_formula1(distance)
    common_score = (size1 + size2 - distance) / 2

    return {
        "tree_dir": str(DEFAULT_TREE_DIR),
        "size1": size1,
        "size2": size2,
        "distance": distance,
        "common_score": common_score,
        "slide_similarity_formula1": similarity_formula1,
        "normalized_similarity": similarity,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute ordered TED on tokenized country trees.")
    parser.add_argument("source", nargs="?", default="Lebanon.json", help="Source tree file name or country name")
    parser.add_argument("target", nargs="?", default="Switzerland.json", help="Target tree file name or country name")
    parser.add_argument(
        "--tree-dir",
        default=DEFAULT_TREE_DIR,
        type=Path,
        help="Directory containing tokenized tree JSON files (default: data/trees_tokens)",
    )
    args = parser.parse_args()

    source_name = Path(args.source).name if str(args.source).endswith(".json") else f"{args.source}.json"
    target_name = Path(args.target).name if str(args.target).endswith(".json") else f"{args.target}.json"
    source_path = args.tree_dir / source_name
    target_path = args.tree_dir / target_name

    if not source_path.exists() or not target_path.exists():
        raise SystemExit(f"Missing tree file(s): {source_path} or {target_path}")

    tree1 = load_tree(source_path)
    tree2 = load_tree(target_path)
    result = ted_distance(tree1, tree2)

    print("Tree directory:", result["tree_dir"])
    print("Size1:", result["size1"], "| Size2:", result["size2"])
    print("Distance:", result["distance"])
    print("Common score:", result["common_score"])
    print("Slide similarity formula 1:", round(result["slide_similarity_formula1"], 4))
    print("Normalized similarity:", round(result["normalized_similarity"], 4))
