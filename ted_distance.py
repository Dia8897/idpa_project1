import argparse
import json
from functools import lru_cache
from pathlib import Path


DEFAULT_TREE_DIR = Path("data/trees_tokens")


def load_tree(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["tree"]
# It opens a JSON file and returns only the "tree" part.

def node_label(node: dict) -> str:
    return str(node.get("label", ""))
# get the label of a node
# node_label({"label": "capital", "children": []})
# extract: "capital"

def count_nodes(node: dict) -> int:
    total = 1
    for child in node.get("children", []):
        total += count_nodes(child)
    return total
# count how many nodes a tree has (total of root + children + ... )


def serialize_node(node: dict) -> str:
    # We serialize the subtree so the memoized similarity function can use
    # immutable string keys instead of mutable dict objects.
    return json.dumps(
        {
            "label": node_label(node),
            "children": [json.loads(serialize_node(child)) for child in node.get("children", [])],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
# convert a subtree into a string

@lru_cache(maxsize=None)
def nj_similarity(a_serial: str, b_serial: str) -> int:
    # It takes two serialized subtrees and returns a similarity score
    """
    Nierman-Jagadish style subtree similarity.

    Interpretation:
    - If root labels differ, the two subtrees contribute nothing.
    - If root labels match, we align the ordered child lists using a weighted
      LCS-style dynamic program.
    - The score is 1 for the matching roots plus the best child alignment score.
    """
    a = json.loads(a_serial)
    b = json.loads(b_serial)
    # Earlier they were turned into strings.
    # Now they are converted back into dictionaries.

    if node_label(a) != node_label(b):
        return 0
    # if the two roots have different labels, they contribute nothing
    # "capital" vs "currency" → similarity = 0

    a_children = a.get("children", [])
    b_children = b.get("children", [])
    rows = len(a_children)
    cols = len(b_children)

    dp = [[0] * (cols + 1) for _ in range(rows + 1)]
    # This is a dynamic programming matrix.
    # dp[i][j] = best similarity score using:
    # first i children of tree A
    # first j children of tree B

    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            match_weight = nj_similarity(
                serialize_node(a_children[i - 1]),
                serialize_node(b_children[j - 1]),
            )
            dp[i][j] = max(
                dp[i - 1][j],                  # skip a child from tree A
                dp[i][j - 1],                  # skip a child from tree B
                dp[i - 1][j - 1] + match_weight,  # match these two children
            )

    return 1 + dp[rows][cols]


def nj_similarity_and_distance(tree1: dict, tree2: dict):
    # convert similarity into distance
    """
    Compute a similarity score and a TED-like distance from tokenized trees.

    This is not an elementary-cost TED implementation. It is a similarity-first
    formulation based on the Nierman-Jagadish idea:

        distance = |T1| + |T2| - 2 * common_score

    where common_score is the recursively computed subtree similarity.
    """
    common_score = nj_similarity(serialize_node(tree1), serialize_node(tree2))
    size1 = count_nodes(tree1)
    size2 = count_nodes(tree2)
    distance = size1 + size2 - 2 * common_score
    normalized_similarity = (2 * common_score) / (size1 + size2) if (size1 + size2) else 1.0

    return {
        "common_score": common_score,
        "size1": size1,
        "size2": size2,
        "distance": distance,
        "normalized_similarity": normalized_similarity,
        "tree_dir": str(DEFAULT_TREE_DIR),
    }


if __name__ == "__main__":
    # terminal input section
    parser = argparse.ArgumentParser(description="Compute NJ-style TED similarity on tokenized country trees.")
    parser.add_argument("source", nargs="?", default="Lebanon.json", help="Source tree file name or country name")
    parser.add_argument("target", nargs="?", default="Switzerland.json", help="Target tree file name or country name")
    parser.add_argument(
        "--tree-dir",
        default=DEFAULT_TREE_DIR,
        type=Path,
        help="Directory containing tokenized tree JSON files (default: data/trees_tokens)",
    )
    # This lets you choose another folder if needed.
    args = parser.parse_args()
    # This stores the user input.

    source_name = Path(args.source).name if str(args.source).endswith(".json") else f"{args.source}.json"
    target_name = Path(args.target).name if str(args.target).endswith(".json") else f"{args.target}.json"

# This allows both styles:
# Lebanon
# Lebanon.json
# Both become Lebanon.json.
    source_path = args.tree_dir / source_name
    target_path = args.tree_dir / target_name

    if not source_path.exists() or not target_path.exists():
        raise SystemExit(f"Missing tree file(s): {source_path} or {target_path}")
# So the program stops nicely if a file is missing.

# load trees
    tree1 = load_tree(source_path)
    tree2 = load_tree(target_path)

# compute result
    result = nj_similarity_and_distance(tree1, tree2)

# print final output
    print("Tree directory:", result["tree_dir"])
    print("Common score:", result["common_score"])
    print("Size1:", result["size1"], "| Size2:", result["size2"])
    print("Distance:", result["distance"])
    print("Normalized similarity:", round(result["normalized_similarity"], 4))
