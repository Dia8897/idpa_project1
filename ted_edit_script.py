import argparse
import json
from functools import lru_cache
from pathlib import Path


DEFAULT_TREE_DIR = Path("data/trees_tokens")
DIFF_DIR = Path("data/diffs")
DIFF_DIR.mkdir(parents=True, exist_ok=True)
_ACTIVE_SOURCE_SUBTREES = frozenset()
_ACTIVE_TARGET_SUBTREES = frozenset()


def load_tree(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["tree"]


def node_label(node: dict) -> str:
    return str(node.get("label", ""))


def is_leaf(node: dict) -> bool:
    return len(node.get("children", [])) == 0


def join_path(path: str, label: str) -> str:
    if not path:
        return f"/{label}"
    return f"{path}/{label}"


def clone_node(node: dict) -> dict:
    cloned = {}
    for key, value in node.items():
        if key == "children":
            cloned[key] = [clone_node(child) for child in value]
        else:
            cloned[key] = value
    cloned.setdefault("children", [])
    return cloned


def payload_without_children(node: dict) -> dict:
    return {k: v for k, v in node.items() if k != "children"}


def clone_serializable(node: dict) -> dict:
    return {
        "label": node_label(node),
        "children": [clone_serializable(child) for child in node.get("children", [])],
    }


def serialize_node(node: dict) -> str:
    return json.dumps(clone_serializable(node), ensure_ascii=False, sort_keys=True)


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


def cost_del_tree(node: dict) -> int:
    if contained_in_target_tree(node):
        return 1
    return subtree_size(node)


def cost_ins_tree(node: dict) -> int:
    if contained_in_source_tree(node):
        return 1
    return subtree_size(node)


def cost_upd_root(a: dict, b: dict) -> int:
    if node_label(a) == node_label(b):
        return 0
    if is_leaf(a) and is_leaf(b):
        return 1
    return cost_del_tree(a) + cost_ins_tree(b)


@lru_cache(maxsize=None)
def ted(a_serial: str, b_serial: str) -> int:
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


def forest_dp(a: dict, b: dict):
    """
    Build the dynamic-programming table from the subtree algorithm shown in the
    handout image. The table is used both for the final TED value and for
    backtracking the edit script.
    """
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
            diag = dist[i - 1][j - 1] + ted(serialize_node(a_children[i - 1]), serialize_node(b_children[j - 1]))
            up = dist[i - 1][j] + cost_del_tree(a_children[i - 1])
            left = dist[i][j - 1] + cost_ins_tree(b_children[j - 1])
            dist[i][j] = min(diag, up, left)

    return dist


def build_edit_script(t1: dict, t2: dict):
    global _ACTIVE_SOURCE_SUBTREES, _ACTIVE_TARGET_SUBTREES

    _ACTIVE_SOURCE_SUBTREES = frozenset(collect_subtree_serials(t1))
    _ACTIVE_TARGET_SUBTREES = frozenset(collect_subtree_serials(t2))
    ted.cache_clear()

    ops = []

    def add_ins(path, node, child_index=None):
        ops.append(
            {
                "kind": "INS",
                "path": path,
                "old": None,
                "new": node_label(node),
                "node_is_leaf": is_leaf(node),
                "child_index": child_index,
                "subtree": clone_node(node),
            }
        )

    def add_del(path, node, child_index=None):
        ops.append(
            {
                "kind": "DEL",
                "path": path,
                "old": node_label(node),
                "new": None,
                "node_is_leaf": is_leaf(node),
                "child_index": child_index,
                "subtree": clone_node(node),
            }
        )

    def add_upd(path, old, new, child_index=None):
        ops.append(
            {
                "kind": "UPD",
                "path": path,
                "old": node_label(old),
                "new": node_label(new),
                "node_is_leaf": is_leaf(old) and is_leaf(new),
                "child_index": child_index,
                "subtree": clone_node(new),
            }
        )

    def add_meta_upd(node_path, old, new):
        ops.append(
            {
                "kind": "UPD",
                "path": node_path,
                "old": node_label(old),
                "new": node_label(new),
                "node_is_leaf": False,
                "child_index": None,
                "subtree": clone_node(new),
            }
        )

    def backtrack(a: dict, b: dict, parent_path: str):
        current_path = join_path(parent_path, node_label(a))

        # Preserve metadata such as raw_values when the structural node itself matches.
        if node_label(a) == node_label(b) and payload_without_children(a) != payload_without_children(b):
            add_meta_upd(current_path, a, b)

        if is_leaf(a) and is_leaf(b):
            if node_label(a) != node_label(b):
                add_upd(parent_path, a, b)
            return

        if node_label(a) != node_label(b):
            add_del(parent_path, a)
            add_ins(parent_path, b)
            return

        a_children = a.get("children", [])
        b_children = b.get("children", [])
        dist = forest_dp(a, b)
        i = len(a_children)
        j = len(b_children)

        while i > 0 or j > 0:
            if i > 0 and j > 0:
                diag_cost = dist[i - 1][j - 1] + ted(
                    serialize_node(a_children[i - 1]),
                    serialize_node(b_children[j - 1]),
                )
                if dist[i][j] == diag_cost:
                    backtrack(a_children[i - 1], b_children[j - 1], current_path)
                    i -= 1
                    j -= 1
                    continue

            if i > 0:
                up_cost = dist[i - 1][j] + cost_del_tree(a_children[i - 1])
                if dist[i][j] == up_cost:
                    add_del(current_path, a_children[i - 1], child_index=i - 1)
                    i -= 1
                    continue

            if j > 0:
                add_ins(current_path, b_children[j - 1], child_index=j - 1)
                j -= 1
                continue

    backtrack(t1, t2, "")
    return ops


def sorted_ops(ops):
    kind_rank = {"DEL": 0, "INS": 1, "UPD": 2}
    return sorted(
        ops,
        key=lambda op: (
            kind_rank.get(op["kind"], 99),
            op["path"],
            op.get("child_index") if op.get("child_index") is not None else 10**9,
            str(op["old"] or ""),
            str(op["new"] or ""),
        ),
    )


def group_ops(ops):
    ordered = sorted_ops(ops)
    return (
        [op for op in ordered if op["kind"] == "DEL"],
        [op for op in ordered if op["kind"] == "INS"],
        [op for op in ordered if op["kind"] == "UPD"],
    )


def op_reason(op: dict) -> str:
    if op["kind"] == "DEL":
        return "Delete a source subtree or token."
    if op["kind"] == "INS":
        return "Insert a target subtree or token."
    if op["node_is_leaf"]:
        return "Update token/content value."
    return "Update metadata attached to a matched structural node."


def op_effective_path(op: dict) -> str:
    if op["kind"] == "DEL" and not op["node_is_leaf"]:
        return join_path(op["path"], str(op["old"]))
    if op["kind"] == "INS" and not op["node_is_leaf"]:
        return join_path(op["path"], str(op["new"]))
    return op["path"]


def write_section(handle, title: str, ops):
    handle.write(title + "\n")
    handle.write("=" * len(title) + "\n")
    if not ops:
        handle.write("No operations in this section.\n\n")
        return

    for idx, op in enumerate(ops, start=1):
        code = f"{op['kind']}-{idx:03d}"
        handle.write(f"[{code}] PATH {op_effective_path(op)}\n")
        handle.write(f"Reason: {op_reason(op)}\n")
        if op["kind"] == "DEL":
            handle.write(f"Action: delete `{op['old']}`\n")
        elif op["kind"] == "INS":
            handle.write(f"Action: insert `{op['new']}`\n")
        else:
            handle.write(f"Action: update `{op['old']}` -> `{op['new']}`\n")
        handle.write("\n")


def save_ops_text(ops, out_path: Path, source_name: str, target_name: str):
    del_ops, ins_ops, upd_ops = group_ops(ops)
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write("COUNTRY TRANSFORMATION EDIT SCRIPT\n")
        handle.write("=================================\n")
        handle.write(f"Source: {source_name}\n")
        handle.write(f"Target: {target_name}\n")
        handle.write(f"Total operations: {len(ops)}\n")
        handle.write(f"Delete operations: {len(del_ops)}\n")
        handle.write(f"Insert operations: {len(ins_ops)}\n")
        handle.write(f"Update operations: {len(upd_ops)}\n\n")
        handle.write("EXECUTION ORDER\n")
        handle.write("---------------\n")
        handle.write("1) Apply all deletes.\n")
        handle.write("2) Apply all inserts.\n")
        handle.write("3) Apply all updates.\n\n")
        write_section(handle, "PHASE 1 - DELETE SOURCE-ONLY DATA", del_ops)
        write_section(handle, "PHASE 2 - INSERT TARGET-ONLY DATA", ins_ops)
        write_section(handle, "PHASE 3 - UPDATE SHARED DATA", upd_ops)


def save_ops_json(ops, out_path: Path, source_name: str, target_name: str, tree_dir: Path):
    del_ops, ins_ops, upd_ops = group_ops(ops)
    payload = {
        "algorithm": "Subtree-DP ordered TED",
        "tree_dir": str(tree_dir),
        "source": source_name,
        "target": target_name,
        "operation_counts": {
            "total": len(ops),
            "delete": len(del_ops),
            "insert": len(ins_ops),
            "update": len(upd_ops),
        },
        "operations": ops,
        "execution_order": {
            "delete_first": True,
            "insert_second": True,
            "update_third": True,
        },
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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
    parser = argparse.ArgumentParser(description="Compute TED diff between two tokenized country trees.")
    parser.add_argument("source", nargs="?", default="Lebanon.json", help="Source tree file name or country name")
    parser.add_argument("target", nargs="?", default="Switzerland.json", help="Target tree file name or country name")
    parser.add_argument(
        "--tree-dir",
        default=DEFAULT_TREE_DIR,
        type=Path,
        help="Directory containing tokenized tree JSON files (default: data/trees_tokens)",
    )
    parser.add_argument(
        "--out-dir",
        default=DIFF_DIR,
        type=Path,
        help="Directory to write diff outputs (default: data/diffs)",
    )
    parser.add_argument("--max-show", type=int, default=30, help="How many sample ops to print.")
    args = parser.parse_args()

    source_name = Path(args.source).name if str(args.source).endswith(".json") else f"{args.source}.json"
    target_name = Path(args.target).name if str(args.target).endswith(".json") else f"{args.target}.json"
    source_path = args.tree_dir / source_name
    target_path = args.tree_dir / target_name

    if not source_path.exists() or not target_path.exists():
        raise SystemExit(f"Missing tree file(s): {source_path} or {target_path}")

    tree1 = load_tree(source_path)
    tree2 = load_tree(target_path)
    ops = build_edit_script(tree1, tree2)
    summarize_ops(ops, max_show=args.max_show)

    stem = f"ted_edit_script_{Path(source_name).stem}_TO_{Path(target_name).stem}"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    txt_out = args.out_dir / f"{stem}.txt"
    json_out = args.out_dir / f"{stem}.json"

    save_ops_text(ops, txt_out, Path(source_name).stem, Path(target_name).stem)
    save_ops_json(ops, json_out, Path(source_name).stem, Path(target_name).stem, args.tree_dir)

    print(f"\nSaved full script to: {txt_out}")
    print(f"Saved JSON diff to : {json_out}")
