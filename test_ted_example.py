from ted_distance import ted_distance
from ted_edit_script import build_edit_script


def build_example_trees():
    tree_c = {
        "label": "a",
        "children": [
            {
                "label": "b",
                "children": [
                    {"label": "c", "children": []},
                    {"label": "d", "children": []},
                ],
            }
        ],
    }

    tree_d = {
        "label": "a",
        "children": [
            {
                "label": "b",
                "children": [
                    {"label": "c", "children": []},
                    {"label": "d", "children": []},
                ],
            },
            {
                "label": "b",
                "children": [
                    {"label": "c", "children": []},
                    {"label": "d", "children": []},
                ],
            },
        ],
    }

    return tree_c, tree_d


def build_second_example_trees():
    tree_s = {
        "label": "a",
        "children": [
            {
                "label": "b",
                "children": [
                    {
                        "label": "c",
                        "children": [
                            {"label": "d", "children": []},
                        ],
                    }
                ],
            }
        ],
    }

    tree_t = {
        "label": "a",
        "children": [
            {
                "label": "b",
                "children": [
                    {"label": "c", "children": []},
                    {
                        "label": "x",
                        "children": [
                            {"label": "d", "children": []},
                        ],
                    },
                ],
            }
        ],
    }

    return tree_s, tree_t


def expected_inserted_subtree():
    return {
        "label": "b",
        "children": [
            {"label": "c", "children": []},
            {"label": "d", "children": []},
        ],
    }


def subtree_symbol(node):
    children = node.get("children", [])
    if not children:
        return node["label"]
    return f'{node["label"]}(' + ", ".join(subtree_symbol(child) for child in children) + ")"


def raw_slide_style_edit_script_from_ops(ops):
    op = ops[0]
    inserted_position = op["child_index"] + 1
    inserted_subtree = subtree_symbol(op["subtree"])
    root_update_target = subtree_symbol(expected_inserted_subtree())

    parts = [
        f"InsTree({inserted_subtree}, R(C), {inserted_position})",
        "Upd(c, c)",
        "Upd(d, d)",
        f"Upd(b(c, d), {root_update_target})",
    ]
    return "< " + ", ".join(parts) + " >"


def final_slide_style_edit_script_from_ops(ops):
    op = ops[0]
    inserted_position = op["child_index"] + 1
    inserted_subtree = subtree_symbol(op["subtree"])
    return f"< InsTree({inserted_subtree}, R(C), {inserted_position}) >"


def format_generic_slide_style_script(ops, root_name):
    parts = []
    for op in ops:
        if op["kind"] == "INS":
            position = (op["child_index"] + 1) if op["child_index"] is not None else "?"
            parent_ref = f"R({op['path'].split('/')[-1]})" if op["path"] not in ("", "/a") else f"R({root_name})"
            parts.append(
                f"InsTree({subtree_symbol(op['subtree'])}, {parent_ref}, {position})"
            )
        elif op["kind"] == "DEL":
            parts.append(f"DelTree({subtree_symbol(op['subtree'])})")
        else:
            parts.append(f"Upd({op['old']}, {op['new']})")
    return "< " + ", ".join(parts) + " >"


def run_example_test():
    tree_c, tree_d = build_example_trees()

    # Uses ted_distance.py here.
    distance_result = ted_distance(tree_c, tree_d)

    # Uses ted_edit_script.py here.
    ops = build_edit_script(tree_c, tree_d)
    assert len(ops) == 1, ops

    op = ops[0]
    assert op["kind"] == "INS", op
    assert op["path"] == "/a", op
    assert op["new"] == "b", op
    assert op["subtree"] == expected_inserted_subtree(), op

    print("Lecture example test passed.")
    print("Slide distance expectation:", 1)
    print("Project distance:", distance_result["distance"])
    print("Edit script (final, slide style):", final_slide_style_edit_script_from_ops(ops))


def run_second_example_test():
    tree_s, tree_t = build_second_example_trees()

    # Uses ted_distance.py here.
    distance_result = ted_distance(tree_s, tree_t)

    # Uses ted_edit_script.py here.
    ops = build_edit_script(tree_s, tree_t)

    print("\nSecond lecture example")
    print("Slide distance expectation:", 2)
    print("Project distance:", distance_result["distance"])
    print("Project edit script (slide style):", format_generic_slide_style_script(ops, "S"))


if __name__ == "__main__":
    run_example_test()
    run_second_example_test()
