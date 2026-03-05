import json
import os
from functools import lru_cache

# ----------------- Load tree -----------------
def load_tree(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["tree"]  # {"label": ..., "children": [...]}

# ----------------- Assign stable IDs (needed for memoization) -----------------
def assign_ids(root):
    """
    Returns (nodes, root_id) where nodes[id] = node_dict.
    IDs are pre-order assigned (stable).
    """
    nodes = {}

    def dfs(node, next_id):
        my_id = next_id
        nodes[my_id] = node
        cid = my_id + 1
        child_ids = []
        for ch in node.get("children", []):
            cid, ch_id = dfs(ch, cid)
            child_ids.append(ch_id)
        # store child ids into node for quick access (not saved to disk)
        node["_child_ids"] = child_ids
        return cid, my_id

    _, root_id = dfs(root, 1)
    return nodes, root_id

# ----------------- Size of subtree -----------------
def subtree_size(nodes, u_id):
    node = nodes[u_id]
    s = 1
    for c in node.get("_child_ids", []):
        s += subtree_size(nodes, c)
    return s

# ----------------- Nierman & Jagadish-style similarity -----------------
def nj_similarity_and_distance(tree1, tree2):
    nodes1, r1 = assign_ids(tree1)
    nodes2, r2 = assign_ids(tree2)

    @lru_cache(maxsize=None)
    def sim(u_id, v_id):
        u = nodes1[u_id]
        v = nodes2[v_id]

        # labels must match to contribute
        if u["label"] != v["label"]:
            return 0

        uc = u.get("_child_ids", [])
        vc = v.get("_child_ids", [])
        a, b = len(uc), len(vc)

        # DP like weighted LCS:
        # dp[i][j] = best similarity sum using first i children of u and first j children of v
        dp = [[0] * (b + 1) for _ in range(a + 1)]

        for i in range(1, a + 1):
            for j in range(1, b + 1):
                w = sim(uc[i - 1], vc[j - 1])  # weight if we match these subtrees
                dp[i][j] = max(
                    dp[i - 1][j],           # skip u child
                    dp[i][j - 1],           # skip v child
                    dp[i - 1][j - 1] + w    # match them
                )

        # 1 for matching the root labels + best aligned children similarity
        return 1 + dp[a][b]

    s = sim(r1, r2)
    size1 = subtree_size(nodes1, r1)
    size2 = subtree_size(nodes2, r2)

    # Convert similarity to a distance-like value (common formula):
    # distance = size1 + size2 - 2 * common
    dist = size1 + size2 - 2 * s

    # Normalized similarity in [0,1]
    # 1 means identical structure+labels, 0 means no match at root labels
    norm_sim = (2 * s) / (size1 + size2) if (size1 + size2) else 1.0

    return {
        "common_score": s,
        "size1": size1,
        "size2": size2,
        "distance": dist,
        "normalized_similarity": norm_sim
    }

# ----------------- Quick test -----------------
if __name__ == "__main__":
    TDIR = "data/trees"
    A = "Lebanon.json"
    B = "Switzerland.json"   # change to any country

    t1 = load_tree(os.path.join(TDIR, A))
    t2 = load_tree(os.path.join(TDIR, B))

    res = nj_similarity_and_distance(t1, t2)
    print("Common score:", res["common_score"])
    print("Size1:", res["size1"], "| Size2:", res["size2"])
    print("Distance:", res["distance"])
    print("Normalized similarity:", round(res["normalized_similarity"], 4))