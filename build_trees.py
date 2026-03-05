import os, json, re

INPUT_DIR = "data/infobox_json"
OUTPUT_DIR = "data/trees"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Keep this SMALL and only add mappings when you really need them
KEY_MAP = {
    "official_language": "official_languages",
    "official_languages": "official_languages",
}

def normalize_key(k: str) -> str:
    k = k.strip().lower()
    k = k.replace("\u2019", "'")  # curly apostrophe -> normal
    k = re.sub(r"\s+", " ", k)
    k = k.replace(" ", "_")
    k = re.sub(r"[^a-z0-9_]+", "", k)  # remove punctuation
    return KEY_MAP.get(k, k)

def normalize_value(v: str) -> str:
    # keep as readable text, just cleanup spacing
    v = str(v)
    v = v.replace("\u2019", "'")
    v = re.sub(r"\s+", " ", v).strip()
    return v

def make_node(label: str, children=None):
    return {"label": label, "children": children or []}

def add_value_children(parent, value):
    """
    value can be:
      - string
      - list of strings (repeated keys)
    We store ONE leaf node per value string (no tokenization).
    """
    if isinstance(value, list):
        for item in value:
            add_value_children(parent, item)
        return

    text = normalize_value(value)
    if not text:
        return

    parent["children"].append(make_node(text))

def infobox_to_tree(country_name: str, infobox: dict):
    root = make_node("country", [])

    # stable ordering for TED (deterministic)
    for raw_key in sorted(infobox.keys(), key=lambda x: x.lower()):
        key = normalize_key(raw_key)
        if not key:
            continue

        key_node = make_node(key, [])
        add_value_children(key_node, infobox[raw_key])

        if key_node["children"]:
            root["children"].append(key_node)

    return root

count = 0
for fname in os.listdir(INPUT_DIR):
    if not fname.endswith(".json"):
        continue

    in_path = os.path.join(INPUT_DIR, fname)
    with open(in_path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    country = obj.get("country_name", fname[:-5])
    infobox = obj.get("infobox", {})

    tree = infobox_to_tree(country, infobox)

    out_path = os.path.join(OUTPUT_DIR, fname)  # same filename -> overwrite
    with open(out_path, "w", encoding="utf-8") as out:
        json.dump({"country_name": country, "tree": tree}, out, ensure_ascii=False, indent=2)

    count += 1

print(f"Built {count} trees in {OUTPUT_DIR}")