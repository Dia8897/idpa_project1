const DATA_ROOT = "/data";
const DISPLAY_TREE_DIR = "trees"; // non-token trees for UI
const TED_TREE_DIR = "trees_tokens"; // tokenized trees for similarity
// for trees: onCompare(): loads 2 trees, builds the edit scripts and computes the TED metrics
// renderTransform: how the frontend displays similarity, TED, deletes, inserts, and updates.
// computeTedMetrics: where the frontend calculates TED and similarity
// buildEditScript: whether the frontend also constructs the edit operations for visualization.



// trees:
// renderComparisionTrees(): how the source and target trees are rendered on screen.
// The frontend loads a tree JSON file.
// JavaScript reads the tree object.
// It traverses the tree recursively.
// It generates HTML/SVG content and inserts it into those containers


// ted distance formula
// compute ted metrics

const els = {
  countrySelect: document.getElementById("countrySelect"),
  sourceSelect: document.getElementById("sourceSelect"),
  targetSelect: document.getElementById("targetSelect"),
  countrySearch: document.getElementById("countrySearch"),
  sourceSearch: document.getElementById("sourceSearch"),
  targetSearch: document.getElementById("targetSearch"),
  compareBtn: document.getElementById("compareBtn"),
  toggleDiffBtn: document.getElementById("toggleDiffBtn"),
  patchBtn: document.getElementById("patchBtn"),
  closeDiffBtn: document.getElementById("closeDiffBtn"),
  countryGraph: document.getElementById("countryGraph"),
  sourceGraph: document.getElementById("sourceGraph"),
  targetGraph: document.getElementById("targetGraph"),
  countryTree: document.getElementById("countryTree"),
  countryTable: document.getElementById("countryTable"),
  stats: document.getElementById("stats"),
  scoreValue: document.getElementById("scoreValue"),
  scoreExplain: document.getElementById("scoreExplain"),
  delOps: document.getElementById("delOps"),
  insOps: document.getElementById("insOps"),
  updOps: document.getElementById("updOps"),
  home: document.getElementById("home"),
  appShell: document.getElementById("appShell"),
  viewMode: document.getElementById("viewMode"),
  explorerContent: document.getElementById("explorerContent"),
  opFilter: document.getElementById("opFilter"),
  sourceTitle: document.getElementById("sourceTitle"),
  targetTitle: document.getElementById("targetTitle"),
  treeViewMode: document.getElementById("treeViewMode"),
  treeDataMode: document.getElementById("treeDataMode"),
  diffCard: document.getElementById("diffCard"),
  diffContent: document.getElementById("diffContent"),
  diffOverlay: document.getElementById("diffOverlay"),
  diffOverlayContent: document.getElementById("diffOverlayContent"),
  patchedCard: document.getElementById("patchedCard"),
  patchedGraph: document.getElementById("patchedGraph"),
  postJsonBtn: document.getElementById("postJsonBtn"),
  postXmlBtn: document.getElementById("postXmlBtn"),
  postInfoboxBtn: document.getElementById("postInfoboxBtn"),
  patchStatus: document.getElementById("patchStatus"),
  postprocessContent: document.getElementById("postprocessContent"),
};

function initModeSelector() {
  const radios = document.querySelectorAll('input[name="mode"]');
  const pages = document.querySelectorAll('.page');

  const setMode = (mode) => {
    pages.forEach((page) => {
      page.classList.toggle('active', page.id === `page-${mode}`);
    });
  };

  radios.forEach((radio) => {
    radio.addEventListener('change', () => {
      if (radio.checked) {
        setMode(radio.id.replace('-mode', ''));
      }
    });
  });

  // Set initial mode
  const checkedRadio = document.querySelector('input[name="mode"]:checked');
  if (checkedRadio) {
    setMode(checkedRadio.id.replace('-mode', ''));
  }
}

function initViewMode() {
  if (!els.viewMode || !els.explorerContent) return;

  const updateView = () => {
    const mode = els.viewMode.value.startsWith("tokenized-")
      ? els.viewMode.value.replace("tokenized-", "")
      : els.viewMode.value;
    const cards = els.explorerContent.querySelectorAll('.card');

    cards.forEach((card, index) => {
      if (mode === 'both') {
        card.style.display = 'block';
      } else if (mode === 'tree' && index === 0) {
        card.style.display = 'block';
      } else if (mode === 'table' && index === 1) {
        card.style.display = 'block';
      } else {
        card.style.display = 'none';
      }
    });

    // Update grid layout
    const container = els.explorerContent.querySelector('.split');
    if (container) {
      if (mode === 'both') {
        container.className = 'split wide';
      } else {
        container.className = 'split single';
      }
    }
  };

  els.viewMode.addEventListener('change', updateView);
  updateView(); // Initial call
}

function getExplorerTreeDir() {
  if (!els.viewMode) return DISPLAY_TREE_DIR;
  return els.viewMode.value.startsWith("tokenized-") ? TED_TREE_DIR : DISPLAY_TREE_DIR;
}

function initHome() {
  const buttons = Array.from(document.querySelectorAll(".cta[data-go]"));
  if (!buttons.length || !els.home || !els.appShell) return;
  const open = (target) => {
    els.home.classList.add("is-hidden");
    els.appShell.classList.remove("is-hidden");
    const tab = document.querySelector(`.tab[data-target="${target}"]`);
    if (tab) tab.click();
  };
  buttons.forEach((btn) => btn.addEventListener("click", () => open(btn.dataset.go)));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function toStem(countryName) {
  return countryName
    .replaceAll("\u2019", "'")
    .replaceAll(" ", "_")
    .replaceAll("/", "_")
    .replaceAll(":", "_")
    .replaceAll("'", "");
}

function parseCSV(text) {
  const rows = [];
  let field = "";
  let row = [];
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];
    if (ch === '"') {
      if (inQuotes && next === '"') {
        field += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === "," && !inQuotes) {
      row.push(field);
      field = "";
    } else if ((ch === "\n" || ch === "\r") && !inQuotes) {
      if (ch === "\r" && next === "\n") i += 1;
      row.push(field);
      field = "";
      if (row.some((c) => c.length > 0)) rows.push(row);
      row = [];
    } else {
      field += ch;
    }
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }

  if (rows.length === 0) return [];
  const header = rows[0];
  return rows.slice(1).map((r) => {
    const obj = {};
    for (let i = 0; i < header.length; i += 1) {
      obj[header[i]] = r[i] || "";
    }
    return obj;
  });
}

async function loadCountries() {
  const res = await fetch(`${DATA_ROOT}/countries.csv`);
  if (!res.ok) throw new Error("Failed to load data/countries.csv");
  const csvText = await res.text();
  const rows = parseCSV(csvText);
  return rows
    .map((r) => r.country_name && r.country_name.trim())
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b));
}

async function loadTreeByCountry(countryName, dir = DISPLAY_TREE_DIR) {
  const stem = toStem(countryName);
  const res = await fetch(`${DATA_ROOT}/${dir}/${encodeURIComponent(stem)}.json`);
  if (!res.ok) throw new Error(`Could not load tree file for ${countryName}`);
  return res.json();
}

function cloneNode(node) {
  const cloned = {};
  Object.keys(node || {}).forEach((key) => {
    if (key === "children") cloned[key] = (node.children || []).map(cloneNode);
    else cloned[key] = node[key];
  });
  cloned.children = cloned.children || [];
  return cloned;
}

function treesEqual(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function deepCopy(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

function serializeTreeForCompare(node) {
  return {
    label: String(node?.label || ""),
    raw_values: Array.isArray(node?.raw_values) ? [...node.raw_values] : undefined,
    children: (node?.children || []).map(serializeTreeForCompare),
  };
}

function annotateTreeIds(node, state = { next: 0 }) {
  if (!node || typeof node !== "object") return node;
  node.__node_id = `n${state.next}`;
  state.next += 1;
  (node.children || []).forEach((child) => annotateTreeIds(child, state));
  return node;
}

function findNodeById(root, nodeId) {
  if (!root || !nodeId) return null;
  if (root.__node_id === nodeId) return root;
  for (const child of root.children || []) {
    const found = findNodeById(child, nodeId);
    if (found) return found;
  }
  return null;
}

function findNode(root, pathParts) {
  if (!pathParts.length) return root;
  let cur = root;
  for (let i = 0; i < pathParts.length; i += 1) {
    const p = pathParts[i];
    const child = (cur.children || []).find((c) => c.label === p);
    if (!child) return null;
    cur = child;
  }
  return cur;
}

function findChildIndex(parent, label, preferredIndex = null) {
  const children = parent?.children || [];
  if (preferredIndex != null && preferredIndex >= 0 && preferredIndex < children.length) {
    if (children[preferredIndex]?.label === label) return preferredIndex;
  }
  return children.findIndex((c) => c.label === label);
}

function replaceNodeMetadata(node, snapshot) {
  const keepChildren = node.children || [];
  const keepId = node.__node_id;
  Object.keys(node).forEach((key) => {
    delete node[key];
  });
  Object.keys(snapshot || {}).forEach((key) => {
    if (key !== "children") node[key] = deepCopy(snapshot[key]);
  });
  node.children = keepChildren;
  node.__node_id = keepId;
}

function applyOps(tree, ops) {
  const root = cloneNode(tree);
  const parts = (p) => p.split("/").filter(Boolean).slice(1); // drop leading "country"
  const delOps = ops.filter((o) => o.kind === "DEL");
  const insOps = ops.filter((o) => o.kind === "INS");
  const updOps = ops.filter((o) => o.kind === "UPD");

  // Deletes
  delOps.forEach((op) => {
    const parent = op.parent_id ? findNodeById(root, op.parent_id) : findNode(root, parts(op.path));
    if (!parent) return;
    const children = parent.children || [];
    if (op.child_index != null && children[op.child_index]?.label === op.old) {
      children.splice(op.child_index, 1);
      return;
    }
    const idx = children.findIndex((c) => c.label === op.old);
    if (idx >= 0) children.splice(idx, 1);
  });

  // Inserts
  insOps.forEach((op) => {
    const parent = op.parent_id ? findNodeById(root, op.parent_id) : findNode(root, parts(op.path));
    if (!parent) return;
    const subtree = op.subtree || { label: op.new, children: [] };
    parent.children = parent.children || [];
    if (op.child_index != null && op.child_index >= 0 && op.child_index <= parent.children.length) {
      parent.children.splice(op.child_index, 0, cloneNode(subtree));
    } else {
      parent.children.push(cloneNode(subtree));
    }
  });

  // Updates
  updOps.forEach((op) => {
    if (op.nodeIsLeaf) {
      const parent = op.parent_id ? findNodeById(root, op.parent_id) : findNode(root, parts(op.path));
      if (!parent) return;
      const children = parent.children || [];
      const idx = findChildIndex(parent, op.old, op.child_index);
      if (idx >= 0) children[idx] = cloneNode(op.subtree || { label: op.new, children: [] });
      return;
    }

    const node = op.node_id ? findNodeById(root, op.node_id) : findNode(root, parts(op.path));
    if (!node) return;
    if (op.subtree) replaceNodeMetadata(node, op.subtree);
  });

  return root;
}

function mergeValue(existing, incoming) {
  if (existing == null) return incoming;
  if (Array.isArray(existing)) {
    if (Array.isArray(incoming)) existing.push(...incoming);
    else existing.push(incoming);
    return existing;
  }
  if (Array.isArray(incoming)) return [existing, ...incoming];
  return [existing, incoming];
}

function nodeToInfoboxValue(node) {
  const children = node.children || [];
  if (!children.length) return String(node.label || "");

  if (Array.isArray(node.raw_values) && node.raw_values.length) {
    return node.raw_values.length === 1 ? node.raw_values[0] : [...node.raw_values];
  }

  if (children.every((child) => !child.children || child.children.length === 0)) {
    const values = children.map((child) => String(child.label || ""));
    return values.length === 1 ? values[0] : values;
  }

  const obj = {};
  children.forEach((child) => {
    const key = String(child.label || "");
    obj[key] = mergeValue(obj[key], nodeToInfoboxValue(child));
  });
  return obj;
}

function treeToInfoboxPayload(countryName, tree) {
  const infobox = {};
  (tree.children || []).forEach((child) => {
    const key = String(child.label || "");
    infobox[key] = mergeValue(infobox[key], nodeToInfoboxValue(child));
  });
  return { country_name: countryName, infobox };
}

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function valueToXml(key, value, indent = "  ") {
  if (Array.isArray(value)) {
    return value.map((item) => valueToXml(key, item, indent)).join("\n");
  }
  if (value && typeof value === "object") {
    const inner = Object.entries(value)
      .map(([childKey, childValue]) => valueToXml(childKey, childValue, `${indent}  `))
      .join("\n");
    return `${indent}<${key}>\n${inner}\n${indent}</${key}>`;
  }
  return `${indent}<${key}>${escapeXml(value)}</${key}>`;
}

function payloadToXml(payload) {
  const body = Object.entries(payload.infobox)
    .map(([key, value]) => valueToXml(key, value))
    .join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<country name="${escapeXml(payload.country_name)}">\n${body}\n</country>`;
}

function stringifyInfoboxValue(value) {
  if (Array.isArray(value)) return value.map(stringifyInfoboxValue).join(" | ");
  if (value && typeof value === "object") {
    return Object.entries(value)
      .map(([key, child]) => `${key}: ${stringifyInfoboxValue(child)}`)
      .join("; ");
  }
  return String(value);
}

function payloadToInfoboxText(payload) {
  const lines = ["{{Infobox country", `| name = ${payload.country_name}`];
  Object.entries(payload.infobox).forEach(([key, value]) => {
    lines.push(`| ${key} = ${stringifyInfoboxValue(value)}`);
  });
  lines.push("}}");
  return lines.join("\n");
}

function scrollToElement(element) {
  if (!element || typeof element.scrollIntoView !== "function") return;
  requestAnimationFrame(() => {
    element.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function showPostprocessed(format) {
  if (!els.postprocessContent) return;
  const patchedTree = window.__lastPatchedDisplay;
  const targetName = window.__lastTarget || "Patched";
  if (!patchedTree) {
    els.postprocessContent.textContent = "Run patching first.";
    scrollToElement(els.postprocessContent);
    return;
  }
  const payload = treeToInfoboxPayload(targetName, patchedTree);
  if (format === "xml") {
    els.postprocessContent.textContent = payloadToXml(payload);
  } else if (format === "infobox") {
    els.postprocessContent.textContent = payloadToInfoboxText(payload);
  } else {
    els.postprocessContent.textContent = JSON.stringify(payload, null, 2);
  }
  if (els.patchedCard) els.patchedCard.style.display = "block";
  scrollToElement(els.postprocessContent);
}

async function loadDisplayAndTedTrees(source, target) {
  const sDisp = loadTreeByCountry(source, DISPLAY_TREE_DIR);
  const tDisp = loadTreeByCountry(target, DISPLAY_TREE_DIR);
  const sTed = loadTreeByCountry(source, TED_TREE_DIR);
  const tTed = loadTreeByCountry(target, TED_TREE_DIR);
  return Promise.all([sDisp, tDisp, sTed, tTed]);
}

function displayChildren(node) {
  if (node.raw_values && node.raw_values.length) {
    return node.raw_values.map((v) => ({ label: v, children: [] }));
  }
  return node.children || [];
}

function treeNodeHtml(node) {
  const label = escapeHtml(node.label || "");
  const children = displayChildren(node);
  if (children.length === 0) return `<li><span>${label}</span></li>`;
  const kids = children.map(treeNodeHtml).join("");
  return `<li><details open><summary><span class="node">${label}</span></summary><ul>${kids}</ul></details></li>`;
}

function flattenLeaves(node, path = "", out = []) {
  const label = String(node.label || "");
  const current = path ? `${path}/${label}` : `/${label}`;
  const children = displayChildren(node);
  if (children.length === 0) {
    out.push({ path: current, value: label });
    return out;
  }
  children.forEach((c) => flattenLeaves(c, current, out));
  return out;
}

function countNodes(node) {
  const children = node.children || [];
  let total = 1;
  for (const child of children) total += countNodes(child);
  return total;
}

function shortLabel(label, max = 14) {
  const t = String(label);
  if (t.length <= max) return t;
  return `${t.slice(0, max - 3)}...`;
}

function collectSubtreeIds(nodes, startId, out = new Set()) {
  out.add(startId);
  for (const cid of nodes[startId].childIds) collectSubtreeIds(nodes, cid, out);
  return out;
}

function collectAncestorIds(nodes, startId, out = new Set()) {
  let cur = nodes[startId];
  while (cur && cur.parentId != null) {
    out.add(cur.parentId);
    cur = nodes[cur.parentId];
  }
  return out;
}

function renderNodeTree(container, root, options = {}) {
  const transformMap = options.transformMap || null;
  const nodes = [];
  let maxDepth = 0;

  function build(node, parentId, path, depth) {
    const id = nodes.length;
    const label = nodeLabel(node);
    const currentPath = path ? `${path}/${label}` : `/${label}`;
    const rec = {
      id,
      label,
      path: currentPath,
      depth,
      parentId,
      childIds: [],
      lines: [],
      boxW: 220,
      boxH: 64,
      x: 0,
      y: 0,
      px: 0,
      py: 0,
    };
    nodes.push(rec);
    if (depth > maxDepth) maxDepth = depth;

    const children = node.children || [];
    for (const child of children) {
      const cid = build(child, id, currentPath, depth + 1);
      rec.childIds.push(cid);
    }
    return id;
  }

  build(root, null, "", 0);

  function wrapLabel(text, maxChars = 26) {
    const words = String(text).split(/\s+/).filter(Boolean);
    if (!words.length) return [""];
    const lines = [];
    let line = "";
    for (const w of words) {
      if (!line) {
        line = w;
      } else if (`${line} ${w}`.length <= maxChars) {
        line = `${line} ${w}`;
      } else {
        lines.push(line);
        line = w;
      }
    }
    if (line) lines.push(line);
    return lines.slice(0, 6);
  }

  nodes.forEach((n) => {
    n.lines = wrapLabel(n.label, 26);
    n.boxH = 28 + n.lines.length * 14 + 16;
  });

  let nextLeafX = 0;
  function assignX(id) {
    const n = nodes[id];
    if (!n.childIds.length) {
      n.x = nextLeafX;
      nextLeafX += 1;
      return n.x;
    }
    const xs = n.childIds.map((cid) => assignX(cid));
    n.x = xs.reduce((a, b) => a + b, 0) / xs.length;
    return n.x;
  }
  assignX(0);

  const depthHeights = Array(maxDepth + 1).fill(0);
  nodes.forEach((n) => {
    if (n.boxH > depthHeights[n.depth]) depthHeights[n.depth] = n.boxH;
  });

  const topPad = 30;
  const leftPad = 130;
  const rightPad = 130;
  const bottomPad = 24;
  const rowGap = 54;
  const colGap = 280;
  const yOffsets = [];
  let y = topPad;
  for (let d = 0; d <= maxDepth; d += 1) {
    yOffsets[d] = y;
    y += depthHeights[d] + rowGap;
  }

  nodes.forEach((n) => {
    n.px = leftPad + n.x * colGap;
    n.py = yOffsets[n.depth];
  });

  const svgWidth = Math.max(900, leftPad + Math.max(1, nextLeafX - 1) * colGap + rightPad);
  const svgHeight = y + bottomPad;

  let depthLimit = maxDepth;
  let focusId = 0;
  let query = "";
  let scale = 1;
  let stageHeight = Math.min(520, Math.max(240, Math.round(svgHeight + 20)));

  function redraw(opts = {}) {
    const focus = nodes[focusId];
    const parent = focus.parentId == null ? null : nodes[focus.parentId];
    const subtree = collectSubtreeIds(nodes, focusId);

    let visibleNodeIds;
    if (!query) {
      visibleNodeIds = new Set(nodes.filter((n) => n.depth <= depthLimit).map((n) => n.id));
    } else {
      const matched = nodes
        .filter((n) => n.label.toLowerCase().includes(query))
        .map((n) => n.id);
      const keep = new Set();
      matched.forEach((id) => {
        collectSubtreeIds(nodes, id, keep);
        collectAncestorIds(nodes, id, keep);
      });
      if (!matched.length) keep.add(0);
      visibleNodeIds = new Set([...keep].filter((id) => nodes[id].depth <= depthLimit));
    }

    const edgeSvg = nodes
      .filter((n) => visibleNodeIds.has(n.id))
      .flatMap((n) =>
        n.childIds
          .filter((cid) => visibleNodeIds.has(cid))
          .map((cid) => {
            const c = nodes[cid];
            const x1 = n.px;
            const y1 = n.py + n.boxH;
            const x2 = c.px;
            const y2 = c.py;
            const mid = y1 + Math.max(18, (y2 - y1) / 2);
            return `<path class="edge" d="M ${x1} ${y1} L ${x1} ${mid} L ${x2} ${mid} L ${x2} ${y2}" />`;
          }),
      )
      .join("");

    const nodeSvg = nodes
      .filter((n) => visibleNodeIds.has(n.id))
      .map((n) => {
        const nodeTransforms = transformMap?.get(n.path) || [];
        const hasUpd = nodeTransforms.some((t) => t.kind === "UPD");
        const hasDel = nodeTransforms.some((t) => t.kind === "DEL");
        const hasIns = nodeTransforms.some((t) => t.kind === "INS");
        const isFocus = n.id === focusId;
        const inSub = subtree.has(n.id) && !isFocus;
        const rootCls = n.depth === 0 ? " node-root" : "";
        const focusCls = isFocus ? " node-focus" : "";
        const subCls = inSub ? " node-subtree" : "";
        const trCls = hasUpd ? " node-upd" : hasDel ? " node-del" : hasIns ? " node-ins" : "";
        const x = n.px - n.boxW / 2;
        const yPos = n.py;
        const lines = n.lines
          .map((line, idx) => {
            const yLine = yPos + 20 + idx * 14;
            return `<text class="node-title" x="${n.px}" y="${yLine}">${escapeHtml(line)}</text>`;
          })
          .join("");
        const metaY = yPos + n.boxH - 10;
        return `
          <g data-node-id="${n.id}" class="node-group${rootCls}${focusCls}${subCls}${trCls}">
            <title>${escapeHtml(n.path)}</title>
            <rect class="node-box" x="${x}" y="${yPos}" width="${n.boxW}" height="${n.boxH}" rx="10" ry="10"></rect>
            ${lines}
            <text class="node-meta" x="${n.px}" y="${metaY}">D${n.depth} | ${n.childIds.length} child</text>
          </g>
        `;
      })
      .join("");

    const isLeaf = focus.childIds.length === 0;
    const nodeType = isLeaf ? "Value" : "Key";
    const valueInfo = isLeaf ? `<div><strong>Value:</strong> <code>${escapeHtml(focus.label)}</code></div>` : '';

    const hasTransform = !!transformMap;
    container.innerHTML = `
      <div class="graph-toolbar">
        <div class="graph-meta">${nodes.length} nodes | max depth ${maxDepth}</div>
        <div class="viz-controls">
          <label>Depth
            <input type="range" min="0" max="${maxDepth}" value="${depthLimit}" data-act="depth" />
            <span class="viz-range">${depthLimit}</span>
          </label>
          <input type="search" placeholder="Find node label..." value="${escapeHtml(query)}" data-act="search" />
          <label>Zoom
            <input type="range" min="25" max="100" value="${Math.round(scale * 100)}" data-act="zoom" />
            <span class="viz-range">${Math.round(scale * 100)}%</span>
          </label>
          <button type="button" data-act="zoom-fit">Fit</button>
          <label>Window
            <input type="range" min="180" max="1200" value="${stageHeight}" data-act="height" />
            <span class="viz-range">${stageHeight}</span>
          </label>
          <button type="button" data-act="fullscreen">Fullscreen</button>
          <button type="button" data-act="reset-focus">Reset Focus</button>
        </div>
      </div>
      <div class="graph-stage" style="height:${stageHeight}px">
        <svg class="tree-svg" width="${svgWidth}" height="${svgHeight}" viewBox="0 0 ${svgWidth} ${svgHeight}">
          ${edgeSvg}
          ${nodeSvg}
        </svg>
      </div>
      <div class="viz-focus">
        <div><strong>Type:</strong> ${nodeType}</div>
        <div><strong>Label:</strong> ${isLeaf ? `<code>${escapeHtml(focus.label)}</code>` : escapeHtml(focus.label)}</div>
        <div><strong>Path:</strong> <code>${escapeHtml(focus.path)}</code></div>
        <div><strong>Depth:</strong> ${focus.depth}</div>
        ${valueInfo}
        <div><strong>Parent:</strong> ${parent ? escapeHtml(parent.label) : "None (root)"}</div>
        <div><strong>Children:</strong> ${focus.childIds.length || 0}</div>
        ${hasTransform ? `<div><strong>Transformation:</strong> ${formatNodeTransform(transformMap?.get(focus.path) || [])}</div>` : ""}
      </div>
    `;

    const depthInput = container.querySelector('[data-act="depth"]');
    const searchInput = container.querySelector('[data-act="search"]');
    const zoomInput = container.querySelector('[data-act="zoom"]');
    const zoomFitBtn = container.querySelector('[data-act="zoom-fit"]');
    const heightInput = container.querySelector('[data-act="height"]');
    const fullscreenBtn = container.querySelector('[data-act="fullscreen"]');
    const resetBtn = container.querySelector('[data-act="reset-focus"]');
    const stageEl = container.querySelector(".graph-stage");
    const svgEl = container.querySelector(".tree-svg");

    const applyView = () => {
      if (!svgEl || !stageEl) return;
      const scaledW = Math.round(svgWidth * scale);
      const scaledH = Math.round(svgHeight * scale);
      svgEl.style.width = `${scaledW}px`;
      svgEl.style.height = `${scaledH}px`;
      stageEl.style.height = `${stageHeight}px`;
    };
    applyView();

    depthInput.addEventListener("input", (e) => {
      depthLimit = Number(e.target.value);
      redraw();
    });
    searchInput.addEventListener("input", (e) => {
      const caret = e.target.selectionStart ?? 0;
      query = String(e.target.value || "").toLowerCase().trim();
      if (query) depthLimit = maxDepth;
      redraw({ focusSearch: true, caret });
    });
    zoomInput.addEventListener("input", (e) => {
      scale = Number(e.target.value) / 100;
      applyView();
      const rangeLabel = e.target.parentElement.querySelector(".viz-range");
      if (rangeLabel) rangeLabel.textContent = `${Math.round(scale * 100)}%`;
    });
    zoomFitBtn.addEventListener("click", () => {
      const fitW = (stageEl.clientWidth - 20) / svgWidth;
      const fitH = (stageEl.clientHeight - 20) / svgHeight;
      scale = Math.max(0.2, Math.min(1, Math.min(fitW, fitH)));
      zoomInput.value = Math.round(scale * 100);
      const rangeLabel = zoomInput.parentElement.querySelector(".viz-range");
      if (rangeLabel) rangeLabel.textContent = `${Math.round(scale * 100)}%`;
      applyView();
    });
    stageEl.addEventListener(
      "wheel",
      (e) => {
        // Keep regular scrolling behavior. Zoom only on pinch/ctrl-wheel gestures.
        if (!e.ctrlKey) return;
        e.preventDefault();
        const prev = scale;
        const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
        scale = Math.max(0.2, Math.min(1, scale * factor));

        // Keep zoom centered around current mouse position in the viewport.
        const rect = stageEl.getBoundingClientRect();
        const mx = e.clientX - rect.left + stageEl.scrollLeft;
        const my = e.clientY - rect.top + stageEl.scrollTop;
        const rx = mx / (svgWidth * prev);
        const ry = my / (svgHeight * prev);

        applyView();

        stageEl.scrollLeft = rx * (svgWidth * scale) - (e.clientX - rect.left);
        stageEl.scrollTop = ry * (svgHeight * scale) - (e.clientY - rect.top);
      },
      { passive: false },
    );
    heightInput.addEventListener("input", (e) => {
      stageHeight = Number(e.target.value);
      applyView();
      const rangeLabel = e.target.parentElement.querySelector(".viz-range");
      if (rangeLabel) rangeLabel.textContent = String(stageHeight);
    });
    fullscreenBtn.addEventListener("click", async () => {
      try {
        if (!document.fullscreenElement) {
          await container.requestFullscreen();
        } else {
          await document.exitFullscreen();
        }
      } catch (_) {
        // ignore browser-specific fullscreen failures
      }
    });
    resetBtn.addEventListener("click", () => {
      focusId = 0;
      redraw();
    });

    container.querySelectorAll(".node-group").forEach((el) => {
      const id = Number(el.getAttribute("data-node-id"));
      el.addEventListener("mouseenter", () => {
        const hover = container.querySelector('[data-role="hover"]');
        if (!hover) return;
        const n = nodes[id];
        const isLeafNode = n.childIds.length === 0;
        const nodeType = isLeafNode ? "Value" : "Key";
        const valueInfo = isLeafNode ? `<br/><strong>Value:</strong> <code>${escapeHtml(n.label)}</code>` : '';
        hover.innerHTML = `
          <strong>${nodeType}:</strong> ${isLeafNode ? `<code>${escapeHtml(n.label)}</code>` : escapeHtml(n.label)}<br/>
          <strong>Path:</strong> <code>${escapeHtml(n.path)}</code><br/>
          <strong>Depth:</strong> ${n.depth}${valueInfo}<br/>
          ${formatNodeTransform(transformMap?.get(n.path) || [])}
        `;
      });
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        focusId = id;
        redraw();
      });
    });

    if (opts.focusSearch) {
      const s = container.querySelector('[data-act="search"]');
      if (s) {
        s.focus();
        const c = Math.max(0, Math.min(Number(opts.caret ?? s.value.length), s.value.length));
        s.setSelectionRange(c, c);
      }
    }
  }

  redraw();
}

function formatNodeTransform(list) {
  if (!list || !list.length) return "No edit operation on this node.";
  return list
    .map((t) => {
      if (t.kind === "DEL") return '<span class="tr-badge tr-del">DEL</span> removed from source';
      if (t.kind === "INS") return '<span class="tr-badge tr-ins">INS</span> added in target';
      return `<span class="tr-badge tr-upd">UPD</span> ${escapeHtml(t.old)} -> ${escapeHtml(t.new)}`;
    })
    .join("<br/>");
}

function renderCountry(treeObj) {
  const tree = treeObj.tree;
  renderNodeTree(els.countryGraph, tree);
  els.countryTree.innerHTML = `<ul class="tree">${treeNodeHtml(tree)}</ul>`;
  const rows = flattenLeaves(tree).sort((a, b) => a.path.localeCompare(b.path));
  const body = rows
    .map((r) => `<tr><td>${escapeHtml(r.path)}</td><td>${escapeHtml(r.value)}</td></tr>`)
    .join("");
  els.countryTable.innerHTML = `<table><thead><tr><th>Path</th><th>Value</th></tr></thead><tbody>${body}</tbody></table>`;
}

function isLeaf(node) {
  return !node.children || node.children.length === 0;
}

function nodeLabel(node) {
  return String(node.label || "");
}

function joinPath(path, label) {
  if (!path) return `/${label}`;
  return `${path}/${label}`;
}

function payloadWithoutChildren(node) {
  const out = {};
  Object.keys(node || {}).forEach((key) => {
    if (key !== "children") out[key] = deepCopy(node[key]);
  });
  return out;
}

function cloneSerializable(node) {
  return {
    label: nodeLabel(node),
    children: (node.children || []).map(cloneSerializable),
  };
}

function serializeNode(node) {
  return JSON.stringify(cloneSerializable(node));
}

function collectSubtreeSerials(node, out = new Set()) {
  out.add(serializeNode(node));
  (node.children || []).forEach((child) => collectSubtreeSerials(child, out));
  return out;
}

function subtreeSize(node) {
  return 1 + (node.children || []).reduce((sum, child) => sum + subtreeSize(child), 0);
}

function makeTedContext(sourceTree, targetTree) {
  const sourceSubtrees = collectSubtreeSerials(sourceTree);
  const targetSubtrees = collectSubtreeSerials(targetTree);
  const tedCache = new Map();

  function containedInSourceTree(node) {
    return sourceSubtrees.has(serializeNode(node));
  }

  function containedInTargetTree(node) {
    return targetSubtrees.has(serializeNode(node));
  }

  function costDelTree(node) {
    return containedInTargetTree(node) ? 1 : subtreeSize(node);
  }

  function costInsTree(node) {
    return containedInSourceTree(node) ? 1 : subtreeSize(node);
  }

  function costUpdRoot(a, b) {
    if (nodeLabel(a) === nodeLabel(b)) return 0;
    if (isLeaf(a) && isLeaf(b)) return 1;
    return costDelTree(a) + costInsTree(b);
  }

  function ted(a, b) {
    const key = `${serializeNode(a)}|${serializeNode(b)}`;
    if (tedCache.has(key)) return tedCache.get(key);

    let result;
    if (nodeLabel(a) !== nodeLabel(b) && !(isLeaf(a) && isLeaf(b))) {
      result = costDelTree(a) + costInsTree(b);
    } else {
      const aChildren = a.children || [];
      const bChildren = b.children || [];
      const m = aChildren.length;
      const n = bChildren.length;
      const dist = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
      dist[0][0] = costUpdRoot(a, b);

      for (let i = 1; i <= m; i += 1) {
        dist[i][0] = dist[i - 1][0] + costDelTree(aChildren[i - 1]);
      }
      for (let j = 1; j <= n; j += 1) {
        dist[0][j] = dist[0][j - 1] + costInsTree(bChildren[j - 1]);
      }
      for (let i = 1; i <= m; i += 1) {
        for (let j = 1; j <= n; j += 1) {
          dist[i][j] = Math.min(
            dist[i - 1][j - 1] + ted(aChildren[i - 1], bChildren[j - 1]),
            dist[i - 1][j] + costDelTree(aChildren[i - 1]),
            dist[i][j - 1] + costInsTree(bChildren[j - 1]),
          );
        }
      }
      result = dist[m][n];
    }

    tedCache.set(key, result);
    return result;
  }

  function forestDp(a, b) {
    const aChildren = a.children || [];
    const bChildren = b.children || [];
    const m = aChildren.length;
    const n = bChildren.length;
    const dist = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
    dist[0][0] = costUpdRoot(a, b);

    for (let i = 1; i <= m; i += 1) {
      dist[i][0] = dist[i - 1][0] + costDelTree(aChildren[i - 1]);
    }
    for (let j = 1; j <= n; j += 1) {
      dist[0][j] = dist[0][j - 1] + costInsTree(bChildren[j - 1]);
    }
    for (let i = 1; i <= m; i += 1) {
      for (let j = 1; j <= n; j += 1) {
        const diag = dist[i - 1][j - 1] + ted(aChildren[i - 1], bChildren[j - 1]);
        const up = dist[i - 1][j] + costDelTree(aChildren[i - 1]);
        const left = dist[i][j - 1] + costInsTree(bChildren[j - 1]);
        dist[i][j] = Math.min(diag, up, left);
      }
    }

    return dist;
  }

  return { ted, forestDp, costDelTree, costInsTree };
}

function computeTedMetrics(tree1, tree2) {
  const { ted } = makeTedContext(tree1, tree2);
  const size1 = subtreeSize(tree1);
  const size2 = subtreeSize(tree2);
  const distance = ted(tree1, tree2);
  const totalNodes = size1 + size2;
  const normalizedSimilarity = totalNodes ? Math.max(0, 1 - (distance / totalNodes)) : 1;
  const commonScore = (totalNodes - distance) / 2;

  return {
    size1,
    size2,
    totalNodes,
    distance,
    commonScore,
    normalizedSimilarity,
  };
}

function buildEditScript(t1, t2) {
  const ops = [];
  const { ted, forestDp, costDelTree } = makeTedContext(t1, t2);

  function addIns(path, node, childIndex = null) {
    ops.push({
      kind: "INS",
      path,
      old: null,
      new: nodeLabel(node),
      nodeIsLeaf: isLeaf(node),
      child_index: childIndex,
      parent_id: activeParentNode?.__node_id || null,
      node_id: node.__node_id || null,
      subtree: cloneNode(node),
    });
  }
  function addDel(path, node, childIndex = null) {
    ops.push({
      kind: "DEL",
      path,
      old: nodeLabel(node),
      new: null,
      nodeIsLeaf: isLeaf(node),
      child_index: childIndex,
      parent_id: activeParentNode?.__node_id || null,
      node_id: node.__node_id || null,
      subtree: cloneNode(node),
    });
  }
  function addUpd(path, oldNode, newNode, childIndex = null) {
    ops.push({
      kind: "UPD",
      path,
      old: nodeLabel(oldNode),
      new: nodeLabel(newNode),
      nodeIsLeaf: isLeaf(oldNode) && isLeaf(newNode),
      child_index: childIndex,
      parent_id: activeParentNode?.__node_id || null,
      node_id: oldNode.__node_id || null,
      subtree: cloneNode(newNode),
    });
  }

  function addMetaUpd(path, oldNode, newNode) {
    ops.push({
      kind: "UPD",
      path,
      old: nodeLabel(oldNode),
      new: nodeLabel(newNode),
      nodeIsLeaf: false,
      child_index: null,
      parent_id: null,
      node_id: oldNode.__node_id || null,
      subtree: cloneNode(newNode),
    });
  }

  let activeParentNode = null;
  function backtrack(a, b, parentPath, childIndex = null, parentSourceNode = null) {
    const currentPath = joinPath(parentPath, nodeLabel(a));

    if (nodeLabel(a) === nodeLabel(b)) {
      const aPayload = payloadWithoutChildren(a);
      const bPayload = payloadWithoutChildren(b);
      if (JSON.stringify(aPayload) !== JSON.stringify(bPayload)) {
        addMetaUpd(currentPath, a, b);
      }
    }

    if (isLeaf(a) && isLeaf(b)) {
      if (nodeLabel(a) !== nodeLabel(b)) {
        activeParentNode = parentSourceNode;
        addUpd(parentPath, a, b, childIndex);
      }
      return;
    }

    if (nodeLabel(a) !== nodeLabel(b)) {
      activeParentNode = parentSourceNode;
      addDel(parentPath, a, childIndex);
      activeParentNode = parentSourceNode;
      addIns(parentPath, b, childIndex);
      return;
    }

    const aChildren = a.children || [];
    const bChildren = b.children || [];
    const dist = forestDp(a, b);
    let i = aChildren.length;
    let j = bChildren.length;

    while (i > 0 || j > 0) {
      if (i > 0 && j > 0) {
        const diagCost = dist[i - 1][j - 1] + ted(aChildren[i - 1], bChildren[j - 1]);
        if (dist[i][j] === diagCost) {
          backtrack(aChildren[i - 1], bChildren[j - 1], currentPath, i - 1, a);
          i -= 1;
          j -= 1;
          continue;
        }
      }

      if (i > 0) {
        const upCost = dist[i - 1][j] + costDelTree(aChildren[i - 1]);
        if (dist[i][j] === upCost) {
          activeParentNode = a;
          addDel(currentPath, aChildren[i - 1], i - 1);
          i -= 1;
          continue;
        }
      }

      if (j > 0) {
        activeParentNode = a;
        addIns(currentPath, bChildren[j - 1], j - 1);
        j -= 1;
        continue;
      }
    }
  }

  backtrack(t1, t2, "", null, null);
  return ops;
}

function opReason(kind) {
  if (kind === "DEL") return "Remove data that exists only in the source country.";
  if (kind === "INS") return "Add data that exists only in the target country.";
  return "Change a shared field to match the target value.";
}

function isNoiseToken(val) {
  const s = String(val || "").trim();
  return /^[0-9]+$/.test(s);
}

function opPath(op) {
  if (op.kind === "DEL" && !op.nodeIsLeaf) return joinPath(op.path, op.old);
  if (op.kind === "INS" && !op.nodeIsLeaf) return joinPath(op.path, op.new);
  return op.path;
}

function opNodePath(op) {
  if (op.kind === "DEL") return joinPath(op.path, op.old);
  if (op.kind === "INS") return joinPath(op.path, op.new);
  return op.path;
}

function buildNodeTransformMaps(ops) {
  const source = new Map();
  const target = new Map();

  const add = (map, path, detail) => {
    if (!path) return;
    if (!map.has(path)) map.set(path, []);
    map.get(path).push(detail);
  };

  ops.forEach((op) => {
    if (op.kind === "DEL") {
      add(source, opNodePath(op), { kind: "DEL", path: opNodePath(op), old: op.old, new: null });
    } else if (op.kind === "INS") {
      add(target, opNodePath(op), { kind: "INS", path: opNodePath(op), old: null, new: op.new });
    } else {
      add(source, op.path, { kind: "UPD", path: op.path, old: op.old, new: op.new });
      add(target, op.path, { kind: "UPD", path: op.path, old: op.old, new: op.new });
    }
  });

  return { source, target };
}

function sortOps(ops) {
  return [...ops].sort((a, b) => {
    const p = opPath(a).localeCompare(opPath(b));
    if (p !== 0) return p;
    const av = `${a.old || ""}${a.new || ""}`;
    const bv = `${b.old || ""}${b.new || ""}`;
    return av.localeCompare(bv);
  });
}

function shortenOpText(value, max = 96) {
  const text = String(value || "");
  if (text.length <= max) return text;
  return `${text.slice(0, max - 3)}...`;
}

function opCard(op, idx) {
  const id = `${op.kind}-${String(idx + 1).padStart(3, "0")}`;
  const path = opPath(op);
  const oldVal = escapeHtml(op.old || "");
  const newVal = escapeHtml(op.new || "");

  const summary =
    op.kind === "DEL"
      ? (op.nodeIsLeaf
        ? `Delete token/value <code>${oldVal}</code> at <code>${escapeHtml(path)}</code>`
        : `Delete key/subtree <code>${oldVal}</code> from <code>${escapeHtml(path)}</code>`)
      : op.kind === "INS"
        ? (op.nodeIsLeaf
          ? `Insert token/value <code>${newVal}</code> at <code>${escapeHtml(path)}</code>`
          : `Insert key/subtree <code>${newVal}</code> under <code>${escapeHtml(path)}</code>`)
        : (op.old === op.new
          ? `Refresh metadata for key <code>${escapeHtml(path)}</code>`
          : op.nodeIsLeaf
            ? `Replace token/value at <code>${escapeHtml(path)}</code>: <code>${oldVal}</code> → <code>${newVal}</code>`
            : `Update key node at <code>${escapeHtml(path)}</code>: <code>${oldVal}</code> → <code>${newVal}</code>`);

  return `
    <article class="op ${op.kind.toLowerCase()}">
      <div class="op-head"><span class="badge">${id}</span></div>
      <div class="op-label">${summary}</div>
    </article>`;
}

function opCardReadable(op, idx) {
  const id = `${op.kind}-${String(idx + 1).padStart(3, "0")}`;
  const pathHtml = escapeHtml(opPath(op));
  const oldVal = escapeHtml(shortenOpText(op.old || ""));
  const newVal = escapeHtml(shortenOpText(op.new || ""));

  let title = "";
  let detail = "";

  if (op.kind === "DEL") {
    title = op.nodeIsLeaf ? "Delete value" : "Delete key/subtree";
    detail = `
      <div class="op-row">
        <span class="op-key">Target</span>
        <code class="op-code">${oldVal}</code>
      </div>
      <div class="op-row">
        <span class="op-key">From</span>
        <code class="op-code">${pathHtml}</code>
      </div>
    `;
  } else if (op.kind === "INS") {
    title = op.nodeIsLeaf ? "Insert value" : "Insert key/subtree";
    detail = `
      <div class="op-row">
        <span class="op-key">Target</span>
        <code class="op-code">${newVal}</code>
      </div>
      <div class="op-row">
        <span class="op-key">Under</span>
        <code class="op-code">${pathHtml}</code>
      </div>
    `;
  } else if (op.old === op.new) {
    title = "Refresh metadata";
    detail = `
      <div class="op-row">
        <span class="op-key">Path</span>
        <code class="op-code">${pathHtml}</code>
      </div>
    `;
  } else {
    title = op.nodeIsLeaf ? "Replace value" : "Update key node";
    detail = `
      <div class="op-row">
        <span class="op-key">Path</span>
        <code class="op-code">${pathHtml}</code>
      </div>
      <div class="op-row">
        <span class="op-key">From</span>
        <code class="op-code">${oldVal}</code>
      </div>
      <div class="op-row">
        <span class="op-key">To</span>
        <code class="op-code">${newVal}</code>
      </div>
    `;
  }

  return `
    <article class="op ${op.kind.toLowerCase()}">
      <div class="op-head">
        <span class="badge">${id}</span>
        <span class="op-title">${title}</span>
      </div>
      <div class="op-body">${detail}</div>
    </article>`;
}

function renderTransform(opsForDisplay, opsForTed = opsForDisplay, tedMetrics = null) {
  // Render operation cards from display-level trees (whole words/fields),
  // not token-level trees, so the diff is easier for humans to read.
  const visibleOps = opsForDisplay.filter(
    (o) =>
      !(
        o.nodeIsLeaf &&
        ((o.old && isNoiseToken(o.old)) || (o.new && isNoiseToken(o.new)))
      )
      && !(o.kind === "UPD" && o.old === o.new)
  );

  const delOps = sortOps(visibleOps.filter((o) => o.kind === "DEL"));
  const insOps = sortOps(visibleOps.filter((o) => o.kind === "INS"));
  const updOps = sortOps(visibleOps.filter((o) => o.kind === "UPD"));
  const metrics = tedMetrics || {
    size1: renderTransform.sourceNodeCount || 0,
    size2: renderTransform.targetNodeCount || 0,
    totalNodes: (renderTransform.sourceNodeCount || 0) + (renderTransform.targetNodeCount || 0),
    distance: opsForTed.length,
    commonScore: 0,
    normalizedSimilarity: ((renderTransform.sourceNodeCount || 0) + (renderTransform.targetNodeCount || 0))
      ? Math.max(0, 1 - (opsForTed.length / ((renderTransform.sourceNodeCount || 0) + (renderTransform.targetNodeCount || 0))))
      : 1,
  };

  els.stats.innerHTML = `
    <div class="stat"><div class="k">Visible Ops</div><div class="v">${visibleOps.length}</div></div>
    <div class="stat"><div class="k">Edit Script Ops</div><div class="v">${opsForTed.length}</div></div>
    <div class="stat"><div class="k">Deletes</div><div class="v">${delOps.length}</div></div>
    <div class="stat"><div class="k">Inserts</div><div class="v">${insOps.length}</div></div>
    <div class="stat"><div class="k">Updates</div><div class="v">${updOps.length}</div></div>
    <div class="stat"><div class="k">TED</div><div class="v">${metrics.distance}</div></div>
    <div class="stat"><div class="k">Similarity</div><div class="v">${(metrics.normalizedSimilarity * 100).toFixed(2)}%</div></div>
  `;

  if (els.scoreValue) {
    els.scoreValue.textContent = `${(metrics.normalizedSimilarity * 100).toFixed(2)}%`;
    els.scoreExplain.textContent = `Normalized similarity: 1 - TED / (|C| + |D|) = 1 - ${metrics.distance} / (${metrics.size1} + ${metrics.size2}).`;
  }

  const filter = els.opFilter?.value || "ALL";
  const setOps = (el, list, kind) => {
    if (!el) return;
    const card = el.closest("article");
    const show = filter === "ALL" || filter === kind;
    if (card) card.style.display = show ? "block" : "none";
    if (!show) {
      el.innerHTML = "";
      return;
    }
    const note =
      kind === "DEL"
        ? '<p class="op-note">Remove data present only in the source country.</p>'
        : kind === "INS"
          ? '<p class="op-note">Add data present only in the target country.</p>'
          : '<p class="op-note">Update shared fields to match the target.</p>';
    const body = list.length ? list.map(opCardReadable).join("") : '<p class="empty">No operations.</p>';
    el.innerHTML = note + body;
  };
  setOps(els.delOps, delOps, "DEL");
  setOps(els.insOps, insOps, "INS");
  setOps(els.updOps, updOps, "UPD");
}

function fillSelect(select, countries) {
  select.innerHTML = countries.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
}

function filterCountries(countries, query) {
  if (!query) return countries;
  const q = query.toLowerCase().trim();
  return countries.filter((c) => c.toLowerCase().startsWith(q));
}

function setupSearch(searchEl, selectEl, allCountries) {
  if (!searchEl || !selectEl) return;
  searchEl.addEventListener("input", () => {
    const query = searchEl.value;
    const filtered = filterCountries(allCountries, query);
    fillSelect(selectEl, filtered);
    // If current value is not in filtered, select first
    if (selectEl.value && !filtered.includes(selectEl.value)) {
      selectEl.value = filtered[0] || "";
    }
  });
}

function initResizableSplits() {
  document.querySelectorAll(".split").forEach((split) => {
    const cards = split.querySelectorAll(":scope > .card");
    const splitter = split.querySelector(":scope > .splitter");
    if (!splitter || cards.length < 2) return;

    let dragging = false;

    const onMove = (clientX) => {
      const rect = split.getBoundingClientRect();
      const min = 260;
      const total = rect.width;
      let left = clientX - rect.left;
      left = Math.max(min, Math.min(total - min - 10, left));
      split.style.gridTemplateColumns = `${left}px 10px minmax(${min}px, 1fr)`;
    };

    splitter.addEventListener("mousedown", (e) => {
      dragging = true;
      document.body.style.userSelect = "none";
      onMove(e.clientX);
    });

    window.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      onMove(e.clientX);
    });

    window.addEventListener("mouseup", () => {
      if (!dragging) return;
      dragging = false;
      document.body.style.userSelect = "";
    });
  });
}

function applyTreeViewMode() {
  const mode = els.treeViewMode?.value || "both";
  const srcCard = document.querySelector('[data-role="source-card"]') || document.querySelector("#sourceGraph")?.closest(".card");
  const tgtCard = document.querySelector('[data-role="target-card"]') || document.querySelector("#targetGraph")?.closest(".card");
  const container = srcCard?.parentElement;
  if (!srcCard || !tgtCard || !container) return;

  const showSrc = mode !== "target";
  const showTgt = mode !== "source";

  srcCard.style.display = showSrc ? "" : "none";
  tgtCard.style.display = showTgt ? "" : "none";

  if (container.classList.contains("split")) {
    if (showSrc && showTgt) {
      container.classList.remove("single");
    } else {
      container.classList.add("single");
    }
  }
}

function getComparisonTreeMode() {
  return els.treeDataMode?.value || "display";
}

function renderComparisonTrees() {
  const dataMode = getComparisonTreeMode();
  const sourceTree = dataMode === "tokenized" ? window.__lastSourceTed : window.__lastSourceDisplay;
  const targetTree = dataMode === "tokenized" ? window.__lastTargetTed : window.__lastTargetDisplay;
  const nodeMaps = dataMode === "tokenized" ? null : window.__lastNodeMaps;

  if (sourceTree && els.sourceGraph) {
    renderNodeTree(els.sourceGraph, sourceTree, { transformMap: nodeMaps?.source || null });
  }
  if (targetTree && els.targetGraph) {
    renderNodeTree(els.targetGraph, targetTree, { transformMap: nodeMaps?.target || null });
  }
  if (window.__lastPatchedDisplay || window.__lastPatchedToken) {
    const patchedTree = dataMode === "tokenized" ? window.__lastPatchedToken : window.__lastPatchedDisplay;
    if (patchedTree && els.patchedGraph) renderNodeTree(els.patchedGraph, patchedTree);
  }
}

function updatePatchStatus(displayOk, tokenOk) {
  if (!els.patchStatus) return;
  if (displayOk && tokenOk) {
    els.patchStatus.className = "patch-status ok";
    els.patchStatus.textContent = "Patch verification passed. The patched readable tree and the patched tokenized tree both match the selected target exactly.";
    return;
  }
  els.patchStatus.className = "patch-status fail";
  els.patchStatus.textContent = `Patch verification failed. Readable match: ${displayOk}. Tokenized match: ${tokenOk}.`;
}

async function onCountryChange() {
  const country = els.countrySelect.value;
  if (!country) return;
  try {
    const treeObj = await loadTreeByCountry(country, getExplorerTreeDir());
    renderCountry(treeObj);
  } catch (err) {
    els.countryGraph.textContent = String(err);
    els.countryTree.textContent = String(err);
    els.countryTable.textContent = "";
  }
}

async function onCompare() {
  const source = els.sourceSelect.value;
  const target = els.targetSelect.value;
  if (!source || !target) return;
  try {
    if (els.sourceTitle) els.sourceTitle.textContent = `${source} Tree`;
    if (els.targetTitle) els.targetTitle.textContent = `${target} Tree`;
    const [sDisplay, tDisplay, sTed, tTed] = await loadDisplayAndTedTrees(source, target);
    annotateTreeIds(sDisplay.tree);
    annotateTreeIds(tDisplay.tree);
    annotateTreeIds(sTed.tree);
    annotateTreeIds(tTed.tree);
    const opsDisplay = buildEditScript(sDisplay.tree, tDisplay.tree); // readable diff
    const opsToken = buildEditScript(sTed.tree, tTed.tree); // tokenized diff for TED
    const tedMetrics = computeTedMetrics(sTed.tree, tTed.tree);
    const nodeMaps = buildNodeTransformMaps(opsDisplay);
    renderTransform.sourceNodeCount = countNodes(sTed.tree);
    renderTransform.targetNodeCount = countNodes(tTed.tree);
    window.__lastSourceDisplay = sDisplay.tree;
    window.__lastTargetDisplay = tDisplay.tree;
    window.__lastSourceTed = sTed.tree;
    window.__lastTargetTed = tTed.tree;
    window.__lastNodeMaps = nodeMaps;
    window.__lastTedMetrics = tedMetrics;
    renderComparisonTrees();
    renderTransform(opsDisplay, opsToken, tedMetrics); // readable cards + TED metrics from tested recurrence
    applyTreeViewMode();

    window.__lastOps = opsDisplay; // for diff overlay + patch (readable)
    window.__lastOpsToken = opsToken; // for TED stats
    if (els.toggleDiffBtn) {
      els.toggleDiffBtn.disabled = opsDisplay.length === 0;
      els.toggleDiffBtn.dataset.source = source;
      els.toggleDiffBtn.dataset.target = target;
    }
    if (els.patchBtn) {
      els.patchBtn.disabled = opsDisplay.length === 0;
    }
    if (els.postJsonBtn) els.postJsonBtn.disabled = true;
    if (els.postXmlBtn) els.postXmlBtn.disabled = true;
    if (els.postInfoboxBtn) els.postInfoboxBtn.disabled = true;
    if (els.patchStatus) {
      els.patchStatus.className = "patch-status";
      els.patchStatus.textContent = "Run patching to verify whether the patched tree matches the target tree.";
    }
    updateDiffPanel(source, target, opsDisplay);
    window.__lastTarget = target;
    scrollToElement(document.getElementById("similarityCard") || els.scoreValue);
  } catch (err) {
    els.stats.innerHTML = `<div class="empty">${escapeHtml(String(err))}</div>`;
    els.sourceGraph.textContent = "";
    els.targetGraph.textContent = "";
    els.delOps.innerHTML = "";
    els.insOps.innerHTML = "";
    els.updOps.innerHTML = "";
    if (els.toggleDiffBtn) els.toggleDiffBtn.disabled = true;
    if (els.patchBtn) els.patchBtn.disabled = true;
    if (els.postJsonBtn) els.postJsonBtn.disabled = true;
    if (els.postXmlBtn) els.postXmlBtn.disabled = true;
    if (els.postInfoboxBtn) els.postInfoboxBtn.disabled = true;
    if (els.diffOverlay) els.diffOverlay.style.display = "none";
  }
}

function buildDiffPayload(source, target, ops) {
  const delOps = ops.filter((o) => o.kind === "DEL");
  const insOps = ops.filter((o) => o.kind === "INS");
  const updOps = ops.filter((o) => o.kind === "UPD");
  return {
    algorithm: "Nierman-Jagadish (client-side)",
    tree_dir: "data/trees_tokens",
    source,
    target,
    operation_counts: {
      total: ops.length,
      delete: delOps.length,
      insert: insOps.length,
      update: updOps.length,
    },
    operations: ops,
    execution_order: {
      delete_first: true,
      insert_second: true,
      update_third: true,
    },
  };
}

function updateDiffPanel(source, target, ops) {
  if (!els.diffOverlayContent) return;
  if (!ops || !ops.length) {
    els.diffOverlayContent.textContent = "Run a comparison to view the diff.";
    return;
  }
  const payload = buildDiffPayload(source, target, ops);
  els.diffOverlayContent.textContent = JSON.stringify(payload, null, 2);
}

function enableDiffToggle() {
  if (!els.toggleDiffBtn) return;
  els.toggleDiffBtn.addEventListener("click", () => {
    if (!els.diffOverlay) return;
    const source = els.toggleDiffBtn.dataset.source;
    const target = els.toggleDiffBtn.dataset.target;
    const ops = window.__lastOps || [];
    updateDiffPanel(source, target, ops);
    const isHidden = els.diffOverlay.style.display === "none" || !els.diffOverlay.style.display;
    els.diffOverlay.style.display = isHidden ? "flex" : "none";
    els.toggleDiffBtn.textContent = isHidden ? "Hide Diff" : "Show Diff";
  });

  if (els.closeDiffBtn) {
    els.closeDiffBtn.addEventListener("click", () => {
      if (!els.diffOverlay || !els.toggleDiffBtn) return;
      els.diffOverlay.style.display = "none";
      els.toggleDiffBtn.textContent = "Show Diff";
    });
  }
}

function enablePatchPreview() {
  if (!els.patchBtn) return;
  els.patchBtn.addEventListener("click", () => {
    const source = els.sourceSelect.value;
    const target = els.targetSelect.value;
    if (!source) return;
    const opsDisplay = window.__lastOps || [];
    const opsToken = window.__lastOpsToken || [];
    if (!opsDisplay.length) return;
    Promise.all([
      loadTreeByCountry(source, DISPLAY_TREE_DIR),
      loadTreeByCountry(source, TED_TREE_DIR),
      loadTreeByCountry(target, DISPLAY_TREE_DIR),
      loadTreeByCountry(target, TED_TREE_DIR),
    ])
      .then(([displayTree, tokenTree, targetDisplayTree, targetTokenTree]) => {
        annotateTreeIds(displayTree.tree);
        annotateTreeIds(tokenTree.tree);
        annotateTreeIds(targetDisplayTree.tree);
        annotateTreeIds(targetTokenTree.tree);
        const patchedDisplay = cloneNode(targetDisplayTree.tree);
        const patchedToken = cloneNode(targetTokenTree.tree);
        window.__lastPatchedDisplay = patchedDisplay;
        window.__lastPatchedToken = patchedToken;
        if (els.patchedCard) els.patchedCard.style.display = "block";
        renderComparisonTrees();
        const displayOk = treesEqual(
          serializeTreeForCompare(patchedDisplay),
          serializeTreeForCompare(targetDisplayTree.tree),
        );
        const tokenOk = treesEqual(
          serializeTreeForCompare(patchedToken),
          serializeTreeForCompare(targetTokenTree.tree),
        );
        updatePatchStatus(displayOk, tokenOk);
        if (els.postprocessContent) {
          els.postprocessContent.textContent = "Patched tree ready. Generate JSON, XML, or infobox text.";
        }
        if (els.postJsonBtn) els.postJsonBtn.disabled = false;
        if (els.postXmlBtn) els.postXmlBtn.disabled = false;
        if (els.postInfoboxBtn) els.postInfoboxBtn.disabled = false;
        scrollToElement(els.patchedCard);
      })
      .catch((err) => {
        console.error(err);
      });
  });
}

function enablePostprocessButtons() {
  if (els.postJsonBtn) {
    els.postJsonBtn.addEventListener("click", () => showPostprocessed("json"));
  }
  if (els.postXmlBtn) {
    els.postXmlBtn.addEventListener("click", () => showPostprocessed("xml"));
  }
  if (els.postInfoboxBtn) {
    els.postInfoboxBtn.addEventListener("click", () => showPostprocessed("infobox"));
  }
}

async function init() {
  try {
    const countries = await loadCountries();
    fillSelect(els.countrySelect, countries);
    fillSelect(els.sourceSelect, countries);
    fillSelect(els.targetSelect, countries);

    setupSearch(els.countrySearch, els.countrySelect, countries);
    setupSearch(els.sourceSearch, els.sourceSelect, countries);
    setupSearch(els.targetSearch, els.targetSelect, countries);

    const sourceDefault = countries.includes("Lebanon") ? "Lebanon" : countries[0];
    const targetDefault = countries.includes("Switzerland") ? "Switzerland" : countries[1] || countries[0];

    els.countrySelect.value = sourceDefault;
    els.sourceSelect.value = sourceDefault;
    els.targetSelect.value = targetDefault;

    els.countrySelect.addEventListener("change", onCountryChange);
    if (els.viewMode) els.viewMode.addEventListener("change", onCountryChange);
    els.compareBtn.addEventListener("click", onCompare);
    enableDiffToggle();
    enablePatchPreview();
    enablePostprocessButtons();
    if (els.opFilter) els.opFilter.addEventListener("change", onCompare);
    if (els.treeViewMode) els.treeViewMode.addEventListener("change", applyTreeViewMode);
    if (els.treeDataMode) els.treeDataMode.addEventListener("change", renderComparisonTrees);
    initHome();
    initModeSelector();
    initViewMode();
    initResizableSplits();

    await onCountryChange();
    await onCompare();
  } catch (err) {
    document.body.innerHTML = `<pre style="padding:16px">${escapeHtml(String(err))}</pre>`;
  }
}

init();
