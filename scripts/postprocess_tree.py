"""
Convert a rooted ordered labeled tree back into a readable infobox-like form.

Supports both tree flavors used in the project:
- non-tokenized trees in data/trees
- tokenized trees in data/trees_tokens

Output formats:
- JSON: {"country_name": ..., "infobox": {...}}
- XML:  <country>...</country>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom


def load_payload(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
    # Reads the JSON file and converts it into a Python dictionary.


def is_leaf(node: Dict[str, Any]) -> bool:
    return len(node.get("children", [])) == 0
    # Checks whether a node has no children.

def merge_value(existing: Any, incoming: Any) -> Any:
    if existing is None:
        return incoming
    if isinstance(existing, list):
        if isinstance(incoming, list):
            existing.extend(incoming)
        else:
            existing.append(incoming)
        return existing
    if isinstance(incoming, list):
        return [existing, *incoming]
    return [existing, incoming]
    # combines repeated values under the same key
    # sometimes the same key appears more than once
    # official_languages = "Arabic"
    # official_languages = "French"

    # cases: if no previous value → return new value
    # if previous is already a list → append/extend
    # if previous is single value and new is single value → make a list of both


def leaf_texts(children: List[Dict[str, Any]]) -> List[str]:
    return [str(child.get("label", "")) for child in children if is_leaf(child)]
    # Takes a list of child nodes and extracts the labels of the leaf ones.
    # children : [
    #   {"label": "Beirut", "children": []},
    #   {"label": "Bern", "children": []}
    # ]
    # it returns: ["Beirut", "Bern"]



def node_to_infobox_value(node: Dict[str, Any]) -> Any:
    # Converts one tree node back into a normal infobox value.
    children = node.get("children", [])
    if not children:
        # if no chidlren
        return str(node.get("label", ""))
        # Converts one tree node back into a normal infobox value.

    raw_values = node.get("raw_values")
 
    if raw_values:
        if len(raw_values) == 1:
            return raw_values[0]
        return list(raw_values)
           # If the node stores original full values in raw_values, use them directly.
        # useful for tokenized trees
        # If the node stores original full values in raw_values, use them directly.

    if all(is_leaf(child) for child in children):
        values = leaf_texts(children)
        if len(values) == 1:
            return values[0]
        return values
        # if all the children are leaves, collect their values
        # if only one, return a string, otherwise return a list

    obj: Dict[str, Any] = {}
    for child in children:
        key = str(child.get("label", ""))
        value = node_to_infobox_value(child)
        obj[key] = merge_value(obj.get(key), value)
         # If children are not all leaves, this means the structure is nested.
        # each child becomes a key
        # recursively reconstruct each child value
        # merge repeated keys if needed
    return obj

# TO JSON
def tree_to_infobox(tree: Dict[str, Any]) -> Dict[str, Any]:
    infobox: Dict[str, Any] = {}
    for child in tree.get("children", []):
        key = str(child.get("label", ""))
        value = node_to_infobox_value(child)
        infobox[key] = merge_value(infobox.get(key), value)
    return infobox
    # Converts the whole tree into an infobox dictionary.
    # each child of the root becomes a top-level infobox field
    # its value is reconstructed with node_to_infobox_value
# JSON uses JSON.stringify(...)
# Infobox uses payloadToInfoboxText(...)

def append_xml(parent: Element, key: str, value: Any) -> None:
    # Adds one value into the XML tree.
    # handles 3 value types: dict, list, simple text
    if isinstance(value, dict):
        node = SubElement(parent, key)
        for child_key, child_value in value.items():
            append_xml(node, child_key, child_value)
        return
        # This creates a nested XML element.

    if isinstance(value, list):
        for item in value:
            append_xml(parent, key, item)
        return
        # If a key has multiple values, repeat the same XML tag.

    node = SubElement(parent, key)
    node.text = str(value)
    # value is a simple text

# TO XML
def infobox_to_xml(country_name: str, infobox: Dict[str, Any]) -> str:
    # Converts the reconstructed infobox dictionary into a full XML document string.
    root = Element("country")
    root.set("name", country_name)
    for key, value in infobox.items():
        append_xml(root, key, value)
        # append value by value using the previous method created
    rough_xml = tostring(root, encoding="utf-8")
    parsed = minidom.parseString(rough_xml)
    pretty = parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")
    lines = [line for line in pretty.splitlines() if line.strip()]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-process a country tree back to infobox-like output.")
    parser.add_argument("--source", required=True, type=Path, help="Tree JSON file to post-process.")
    parser.add_argument("--out", required=True, type=Path, help="Output file path.")
    parser.add_argument(
        "--format",
        choices=["json", "xml"],
        default="json",
        help="Output format for the reconstructed document.",
    )
    args = parser.parse_args()

    payload = load_payload(args.source)
    country_name = payload.get("country_name", args.source.stem)
    tree = payload["tree"]
    infobox = tree_to_infobox(tree)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "xml":
        args.out.write_text(infobox_to_xml(country_name, infobox), encoding="utf-8")
    else:
        out_payload = {"country_name": country_name, "infobox": infobox}
        args.out.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {args.format.upper()} output to {args.out}")


if __name__ == "__main__":
    main()
