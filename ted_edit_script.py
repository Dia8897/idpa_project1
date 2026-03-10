import json
import os
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
    return node_label(n)


def join_path(path: str, label: str) -> str:
    if not path:
        return f"/{label}"
    return f"{path}/{label}"


# ---------- Nierman & Jagadish similarity (match weight) ----------
@lru_cache(maxsize=None)
def sim_cached(a_serial: str, b_serial: str) -> int:
    a = json.loads(a_serial)
    b = json.loads(b_serial)
    return nj_sim(a, b)


def serialize_node(n: dict) -> str:
    return json.dumps(
        {
            "label": node_label(n),
            "children": [json.loads(serialize_node(c)) for c in n.get("children", [])],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def nj_sim(u: dict, v: dict) -> int:
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
    a, b = len(uc), len(vc)
    dp = [[0] * (b + 1) for _ in range(a + 1)]
    bt = [[None] * (b + 1) for _ in range(a + 1)]

    for i in range(1, a + 1):
        for j in range(1, b + 1):
            w = sim_cached(serialize_node(uc[i - 1]), serialize_node(vc[j - 1]))
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

    matches = []
    i, j = a, b
    while i > 0 and j > 0:
        step = bt[i][j]
        if step is None:
            break
        kind, w = step
        if kind == "DIAG":
            if w > 0:
                matches.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif kind == "UP":
            i -= 1
        else:
            j -= 1

    matches.reverse()
    return matches


# ---------- Build operations ----------
def nj_edit_script(t1: dict, t2: dict):
    ops = []

    def add_ins(path, node):
        ops.append(
            {
                "kind": "INS",
                "path": path,
                "old": None,
                "new": subtree_signature(node),
                "node_is_leaf": is_leaf(node),
            }
        )

    def add_del(path, node):
        ops.append(
            {
                "kind": "DEL",
                "path": path,
                "old": subtree_signature(node),
                "new": None,
                "node_is_leaf": is_leaf(node),
            }
        )

    def add_upd(path, old, new):
        ops.append(
            {
                "kind": "UPD",
                "path": path,
                "old": subtree_signature(old),
                "new": subtree_signature(new),
                "node_is_leaf": True,
            }
        )

    def diff(u: dict, v: dict, path: str):
        if node_label(u) != node_label(v):
            add_del(path, u)
            add_ins(path, v)
            return

        uc = u.get("children", [])
        vc = v.get("children", [])
        current = join_path(path, node_label(u))

        if len(uc) == 0 and len(vc) == 0:
            return

        if len(uc) == 1 and len(vc) == 1 and is_leaf(uc[0]) and is_leaf(vc[0]):
            if node_label(uc[0]) != node_label(vc[0]):
                add_upd(current, uc[0], vc[0])
            return

        matches = align_children(uc, vc)
        matched_u = {i for i, _ in matches}
        matched_v = {j for _, j in matches}

        for i, child in enumerate(uc):
            if i not in matched_u:
                add_del(current, child)

        for j, child in enumerate(vc):
            if j not in matched_v:
                add_ins(current, child)

        for i, j in matches:
            diff(uc[i], vc[j], current)

    diff(t1, t2, "")
    return ops


def sorted_ops(ops):
    return sorted(
        ops,
        key=lambda o: (o["path"], str(o["old"] or ""), str(o["new"] or "")),
    )


def group_ops(ops):
    del_ops = sorted_ops([o for o in ops if o["kind"] == "DEL"])
    ins_ops = sorted_ops([o for o in ops if o["kind"] == "INS"])
    upd_ops = sorted_ops([o for o in ops if o["kind"] == "UPD"])
    return del_ops, ins_ops, upd_ops


def op_reason(kind: str) -> str:
    if kind == "DEL":
        return "Remove data that exists in source but not in target."
    if kind == "INS":
        return "Add data that exists in target but not in source."
    return "Change shared field value to target value."


def op_effective_path(op: dict) -> str:
    if op["kind"] == "DEL" and not op["node_is_leaf"]:
        return join_path(op["path"], str(op["old"]))
    if op["kind"] == "INS" and not op["node_is_leaf"]:
        return join_path(op["path"], str(op["new"]))
    return op["path"]


def write_section(f, title: str, ops):
    f.write(title + "\n")
    f.write("=" * len(title) + "\n")
    if not ops:
        f.write("No operations in this section.\n\n")
        return

    for idx, op in enumerate(ops, start=1):
        code = f"{op['kind']}-{idx:03d}"
        path = op_effective_path(op)
        f.write(f"[{code}] PATH {path}\n")
        f.write(f"Reason: {op_reason(op['kind'])}\n")
        if op["kind"] == "DEL":
            f.write(f"Action: delete `{op['old']}`\n")
        elif op["kind"] == "INS":
            f.write(f"Action: insert `{op['new']}`\n")
        else:
            f.write(f"Action: update `{op['old']}` -> `{op['new']}`\n")
        f.write("\n")


def save_ops(ops, out_path, source_name: str, target_name: str):
    del_ops, ins_ops, upd_ops = group_ops(ops)
    total = len(ops)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("COUNTRY TRANSFORMATION EDIT SCRIPT\n")
        f.write("=================================\n")
        f.write(f"Source: {source_name}\n")
        f.write(f"Target: {target_name}\n")
        f.write(f"Total operations: {total}\n")
        f.write(f"Delete operations: {len(del_ops)}\n")
        f.write(f"Insert operations: {len(ins_ops)}\n")
        f.write(f"Update operations: {len(upd_ops)}\n\n")

        f.write("EXECUTION ORDER\n")
        f.write("---------------\n")
        f.write("1) Apply all deletes (remove source-only structure).\n")
        f.write("2) Apply all inserts (add target-only structure).\n")
        f.write("3) Apply all updates (align shared values).\n\n")

        write_section(f, "PHASE 1 - DELETE SOURCE-ONLY DATA", del_ops)
        write_section(f, "PHASE 2 - INSERT TARGET-ONLY DATA", ins_ops)
        write_section(f, "PHASE 3 - UPDATE SHARED DATA", upd_ops)


def summarize_ops(ops, max_show=20):
    del_ops, ins_ops, upd_ops = group_ops(ops)
    print("Ops:", len(ops), "| INS:", len(ins_ops), "DEL:", len(del_ops), "UPD:", len(upd_ops))
    print("\nSample operations:")
    for op in (del_ops + ins_ops + upd_ops)[:max_show]:
        path = op_effective_path(op)
        if op["kind"] == "DEL":
            print(f"DEL {path} : {op['old']}")
        elif op["kind"] == "INS":
            print(f"INS {path} : {op['new']}")
        else:
            print(f"UPD {path} : {op['old']} -> {op['new']}")


if __name__ == "__main__":
    A = "Lebanon.json"
    B = "Switzerland.json"  # change as needed

    t1 = load_tree(os.path.join(TREES_DIR, A))
    t2 = load_tree(os.path.join(TREES_DIR, B))

    ops = nj_edit_script(t1, t2)
    summarize_ops(ops, max_show=30)

    out_file = os.path.join(LOG_DIR, f"nj_edit_script_{A[:-5]}_TO_{B[:-5]}.txt")
    save_ops(ops, out_file, source_name=A[:-5], target_name=B[:-5])
    print("\nSaved full script to:", out_file)
