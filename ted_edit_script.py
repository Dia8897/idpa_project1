import argparse
# to run the file from the terminal with country names
import json
# to have the diff as json
from pathlib import Path
# helps with file paths

import ted_distance as td


DEFAULT_TREE_DIR = Path("data/trees_tokens")
# read trees
DIFF_DIR = Path("data/diffs")
# write

DIFF_DIR.mkdir(parents=True, exist_ok=True)
# create the folder if it does not exist and do nothing if it exists

load_tree = td.load_tree
# opens a json tree file
node_label = td.node_label
# returns the label of the tree
is_leaf = td.is_leaf
# checks if a node is a leaf node

# This is just shorthand. Instead of writing td.load_tree, the file can write load_tree


def join_path(path: str, label: str) -> str:
    if not path:
        return f"/{label}"
    return f"{path}/{label}"
    # This function builds readable paths like:
# /country
# /country/capital
# /country/government/president
# It is only for making the output human-readable.


def clone_node(node: dict) -> dict:
    cloned = {}
    for key, value in node.items():
        if key == "children":
            cloned[key] = [clone_node(child) for child in value]
        else:
            cloned[key] = value
    cloned.setdefault("children", [])
    return cloned
# This makes a deep copy of a node and all its children.
# Why does the script need this?
# Because when it stores an operation like:
# delete this subtree
# insert that subtree
# it wants to save the subtree content inside the operation safely, without accidentally modifying the original tree later.


def payload_without_children(node: dict) -> dict:
    return {k: v for k, v in node.items() if k != "children"}
# This keeps all fields except children
# because tree may contain extra metadata besides "label" and "children"
# So this lets the script detect:
# "The structural node is the same, but some metadata changed.""
# That later becomes a metadata update operation


def forest_dp(a: dict, b: dict):
    # It rebuilds the same DP table used in td.ted(...), but here the table is used for backtracking.
    """
    Build the dynamic-programming table from the subtree algorithm shown in the
    handout image. The table is used both for the final TED value and for
    backtracking the edit script.
    """
    a_children = a.get("children", [])
    # Take the list of children of node a.
    # If a has no "children" key, use [].
    b_children = b.get("children", [])
    m = len(a_children)
    n = len(b_children)
    # does not count grandchildren

    dist = [[0] * (n + 1) for _ in range(m + 1)]
    # (m + 1) rows × (n + 1) columns
    # +1 because:
    # row 0 = comparing with no children from A
    # column 0 = comparing with no children from B
    # Dist = new [0..M][0..N]
    #0..M  → M+1 values
    # 0..N  → N+1 values

    dist[0][0] = td.cost_upd_root(a, b)

    for i in range(1, m + 1):
        dist[i][0] = dist[i - 1][0] + td.cost_del_tree(a_children[i - 1])

    for j in range(1, n + 1):
        dist[0][j] = dist[0][j - 1] + td.cost_ins_tree(b_children[j - 1])

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            diag = dist[i - 1][j - 1] + td.ted(
                td.serialize_node(a_children[i - 1]),
                td.serialize_node(b_children[j - 1]),
            )
            up = dist[i - 1][j] + td.cost_del_tree(a_children[i - 1])
            left = dist[i][j - 1] + td.cost_ins_tree(b_children[j - 1])
            dist[i][j] = min(diag, up, left)
            #the minimum cost to transform the first i children of a into the first j children of b, after taking into account the cost of the roots a and b

    return dist


def build_edit_script(t1: dict, t2: dict):
    # It outputs a list of operations:

    # DEL (delete)
    # INS (insert)
    # UPD (update)
    td.configure_ted_context(t1, t2)
    # It prepares global information used by TED:
    # collects all subtrees in t1
    # collects all subtrees in t2
    # resets cache

    # Because your costs depend on this:
    # If subtree exists in other tree → cost = 1
    # Else → cost = full subtree size


    ops = []
    # This will store all operations like:
    # DEL /country : capital
    # INS /country : language
    # UPD /country/capital : Beirut => Bern


    # create operation objects and push them into ops
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
            # Defensive guard: do not emit leaf updates when labels are identical.
            if node_label(old) == node_label(new):
                # It refuses useless updates
                return
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
        # real content update
        # When two nodes are matched structurally, and we want to update their value


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
        # node labels are the same but the extra data (metadata) is different


    def backtrack(a: dict, b: dict, parent_path: str):
        # It recursively compares subtree a with subtree b and decides which edit operations to add
        # if they are simple values and different → UPD
        # if their structure names differ → DEL + INS
        # if their structure names match → build the DP table for their children and walk backward through it

        current_path = join_path(parent_path, node_label(a))
        # create the path of the current node
        # ex: current_path = "/country/capital"

        # Preserve metadata such as raw_values when the structural node itself matches.
        if node_label(a) == node_label(b) and payload_without_children(a) != payload_without_children(b):
            add_meta_upd(current_path, a, b)
        # if labels are the same
        # but extra information besides children is different
        # it is meta_upd
        
        if is_leaf(a) and is_leaf(b):
            if node_label(a) != node_label(b):
                add_upd(parent_path, a, b)
            # if both nodes are leaves
            # have different labels
            # update
            return

        if node_label(a) != node_label(b):
            add_del(parent_path, a)
            add_ins(parent_path, b)
            return
        # internal labels => not leaves
        # do not rename internal nodes
        # replace one subtree with another

        a_children = a.get("children", [])
        b_children = b.get("children", [])
        dist = forest_dp(a, b)
        i = len(a_children)
        j = len(b_children)
        # get children and DP matrix

        while i > 0 or j > 0:
            # keep walking until both sides are fully processed.
            if i > 0 and j > 0:
                diag_cost = dist[i - 1][j - 1] + td.ted(
                    td.serialize_node(a_children[i - 1]),
                    td.serialize_node(b_children[j - 1]),
                )
                if dist[i][j] == diag_cost:
                    backtrack(a_children[i - 1], b_children[j - 1], current_path)
                    i -= 1
                    j -= 1
                    continue

            if i > 0:
                up_cost = dist[i - 1][j] + td.cost_del_tree(a_children[i - 1])
                if dist[i][j] == up_cost:
                    add_del(current_path, a_children[i - 1], child_index=i - 1)
                    i -= 1
                    continue

            if j > 0:
                add_ins(current_path, b_children[j - 1], child_index=j - 1)
                j -= 1
                continue

    backtrack(t1, t2, "")

    def is_redundant_update(op: dict) -> bool:
        # It tries to remove updates that do not really change anything.
        """
        Remove obvious no-op updates that clutter the diff, such as:
        - leaf updates where old == new
        - internal updates where old == new and subtree carries no metadata
          beyond label/children
        """
        if op.get("kind") != "UPD":
            return False

        old = str(op.get("old") or "")
        new = str(op.get("new") or "")
        if old != new:
            return False

        if op.get("node_is_leaf", False):
            return True

        subtree = op.get("subtree") or {}
        extra_meta = [k for k in subtree.keys() if k not in {"label", "children"}]
        return len(extra_meta) == 0

    ops = [op for op in ops if not is_redundant_update(op)]
    return ops


def sorted_ops(ops):
    kind_rank = {"DEL": 0, "INS": 1, "UPD": 2}
    # priority: 0 => DEL first
    # then insert
    #then update 
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
    # This function writes one section of the text report
    handle.write(title + "\n")
    handle.write("=" * len(title) + "\n")
    if not ops:
        handle.write("No operations in this section.\n\n")
        return

    for idx, op in enumerate(ops, start=1):
        # loop over iterations
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


def save_ops_json(ops, out_path: Path, source_name: str, target_name: str, tree_dir: Path, ted_metrics: dict):
    del_ops, ins_ops, upd_ops = group_ops(ops)
    payload = {
        "algorithm": "Subtree-DP ordered TED",
        "tree_dir": str(tree_dir),
        "source": source_name,
        "target": target_name,
        "ted": {
            "distance": ted_metrics["distance"],
            "common_score": ted_metrics["common_score"],
            "slide_similarity_formula1": ted_metrics["slide_similarity_formula1"],
            "normalized_similarity": ted_metrics["normalized_similarity"],
        },
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
    ted_metrics = td.ted_distance(tree1, tree2)
    summarize_ops(ops, max_show=args.max_show)
    print("TED:", ted_metrics["distance"])
    print("Slide similarity formula 1:", round(ted_metrics["slide_similarity_formula1"], 4))
    print("Normalized similarity:", round(ted_metrics["normalized_similarity"], 4))

    stem = f"ted_edit_script_{Path(source_name).stem}_TO_{Path(target_name).stem}"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    txt_out = args.out_dir / f"{stem}.txt"
    json_out = args.out_dir / f"{stem}.json"

    save_ops_text(ops, txt_out, Path(source_name).stem, Path(target_name).stem)
    save_ops_json(ops, json_out, Path(source_name).stem, Path(target_name).stem, args.tree_dir, ted_metrics)

    print(f"\nSaved full script to: {txt_out}")
    print(f"Saved JSON diff to : {json_out}")
