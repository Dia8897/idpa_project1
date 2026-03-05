import json, os
from functools import lru_cache

TREES_DIR = "data/trees"
LOG_DIR = "data/logs"
os.makedirs(LOG_DIR, exist_ok=True)

def load_tree(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["tree"]  # {"label":..., "children":[...]}

def is_leaf(n: dict) -> bool:
    return len(n.get("children", [])) == 0

def node_label(n: dict) -> str:
    return str(n.get("label", ""))

def subtree_signature(n: dict) -> str:
    """Short text for printing nodes in ops."""
    if is_leaf(n):
        return node_label(n)
    return node_label(n)

def subtree_size(n: dict) -> int:
    return 1 + sum(subtree_size(c) for c in n.get("children", []))

# ---------- Nierman & Jagadish similarity (match weight) ----------
@lru_cache(maxsize=None)
def sim_cached(a_serial: str, b_serial: str) -> int:
    """
    Cache wrapper: we cache by serialized node strings to keep it simple.
    We'll use a custom serialize() that is stable.
    """
    a = json.loads(a_serial)
    b = json.loads(b_serial)
    return nj_sim(a, b)

def serialize_node(n: dict) -> str:
    """
    Stable serialization for caching similarity.
    We do NOT include paths/ids, only label + structure.
    """
    return json.dumps(
        {"label": node_label(n), "children": [json.loads(serialize_node(c)) for c in n.get("children", [])]},
        ensure_ascii=False,
        sort_keys=True
    )

def nj_sim(u: dict, v: dict) -> int:
    """
    Nierman & Jagadish style:
      sim(u,v) = 0 if labels differ
      sim(u,v) = 1 + weighted-LCS over children using sim(child_i, child_j) as weight
    """
    if node_label(u) != node_label(v):
        return 0

    uc = u.get("children", [])
    vc = v.get("children", [])
    a, b = len(uc), len(vc)

    dp = [[0] * (b + 1) for _ in range(a + 1)]
    for i in range(1, a + 1):
        for j in range(1, b + 1):
            w = sim_cached(serialize_node(uc[i - 1]), serialize_node(vc[j - 1]))
            dp[i][j] = max(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1] + w)

    return 1 + dp[a][b]

# ---------- Alignment (weighted LCS) with backtracking ----------
def align_children(uc, vc):
    """
    Returns list of matched pairs (i,j) in increasing order
    where uc[i] matches vc[j] (by NJ sim>0).
    """
    a, b = len(uc), len(vc)
    dp = [[0] * (b + 1) for _ in range(a + 1)]
    bt = [[None] * (b + 1) for _ in range(a + 1)]

    for i in range(1, a + 1):
        for j in range(1, b + 1):
            w = sim_cached(serialize_node(uc[i - 1]), serialize_node(vc[j - 1]))
            # candidates
            up = dp[i - 1][j]
            left = dp[i][j - 1]
            diag = dp[i - 1][j - 1] + w

            best = max(up, left, diag)
            dp[i][j] = best

            if best == diag:
                bt[i][j] = ("DIAG", w)
            elif best == up:
                bt[i][j] = ("UP", 0)
            else:
                bt[i][j] = ("LEFT", 0)

    # backtrack
    matches = []
    i, j = a, b
    while i > 0 and j > 0:
        step = bt[i][j]
        if step is None:
            break
        kind, w = step
        if kind == "DIAG":
            if w > 0:  # only treat as a match if there is actual similarity (labels matched somewhere)
                matches.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif kind == "UP":
            i -= 1
        else:  # LEFT
            j -= 1

    matches.reverse()
    return matches

# ---------- Build readable edit script ----------
def nj_edit_script(t1: dict, t2: dict):
    ops = []

    def add_ins(path, node):
        ops.append(("INS", path, None, subtree_signature(node)))

    def add_del(path, node):
        ops.append(("DEL", path, subtree_signature(node), None))

    def add_upd(path, old, new):
        ops.append(("UPD", path, subtree_signature(old), subtree_signature(new)))

    def diff(u: dict, v: dict, path: str):
        # If labels differ, treat as DEL+INS (NJ wouldn't match them)
        if node_label(u) != node_label(v):
            add_del(path, u)
            add_ins(path, v)
            return

        # Same label
        uc = u.get("children", [])
        vc = v.get("children", [])

        # Leaf case: same label leaf -> no op
        if len(uc) == 0 and len(vc) == 0:
            return

        # Special case for your key->value structure:
        # If u and v are "key nodes", and each has exactly one leaf child, allow UPD on that leaf text.
        # Example: capital -> "Beirut" vs capital -> "Bern"
        if len(uc) == 1 and len(vc) == 1 and is_leaf(uc[0]) and is_leaf(vc[0]):
            if node_label(uc[0]) != node_label(vc[0]):
                add_upd(path + "/" + node_label(u), uc[0], vc[0])
            return

        # Align children using weighted LCS (NJ)
        matches = align_children(uc, vc)
        matched_u = set(i for i, _ in matches)
        matched_v = set(j for _, j in matches)

        # Deletions: children in u not matched
        for i in range(len(uc)):
            if i not in matched_u:
                add_del(path + "/" + node_label(u), uc[i])

        # Insertions: children in v not matched
        for j in range(len(vc)):
            if j not in matched_v:
                add_ins(path + "/" + node_label(u), vc[j])

        # Recurse on matched pairs
        for i, j in matches:
            diff(uc[i], vc[j], path + "/" + node_label(u))

    diff(t1, t2, "/country")
    return ops

def summarize_ops(ops, max_show=30):
    ins = sum(1 for o in ops if o[0] == "INS")
    dele = sum(1 for o in ops if o[0] == "DEL")
    upd = sum(1 for o in ops if o[0] == "UPD")

    print("Ops:", len(ops), "| INS:", ins, "DEL:", dele, "UPD:", upd)
    print("\nFirst ops:")
    for op in ops[:max_show]:
        kind, path, old, new = op
        if kind == "INS":
            print(f"INS {path} : {new}")
        elif kind == "DEL":
            print(f"DEL {path} : {old}")
        else:
            print(f"UPD {path} : {old} -> {new}")

def save_ops(ops, out_path):
    with open(out_path, "w", encoding="utf-8") as f:
        for kind, path, old, new in ops:
            if kind == "INS":
                f.write(f"INS {path} : {new}\n")
            elif kind == "DEL":
                f.write(f"DEL {path} : {old}\n")
            else:
                f.write(f"UPD {path} : {old} -> {new}\n")

if __name__ == "__main__":
    A = "Lebanon.json"
    B = "Switzerland.json"  # change as needed

    t1 = load_tree(os.path.join(TREES_DIR, A))
    t2 = load_tree(os.path.join(TREES_DIR, B))

    ops = nj_edit_script(t1, t2)
    summarize_ops(ops, max_show=30)

    out_file = os.path.join(LOG_DIR, f"nj_edit_script_{A[:-5]}_TO_{B[:-5]}.txt")
    save_ops(ops, out_file)
    print("\nSaved full script to:", out_file)