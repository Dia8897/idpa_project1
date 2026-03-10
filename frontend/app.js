const DATA_ROOT = "../data";

const els = {
  countrySelect: document.getElementById("countrySelect"),
  sourceSelect: document.getElementById("sourceSelect"),
  targetSelect: document.getElementById("targetSelect"),
  compareBtn: document.getElementById("compareBtn"),
  countryGraph: document.getElementById("countryGraph"),
  sourceGraph: document.getElementById("sourceGraph"),
  targetGraph: document.getElementById("targetGraph"),
  countryTree: document.getElementById("countryTree"),
  countryTable: document.getElementById("countryTable"),
  stats: document.getElementById("stats"),
  delOps: document.getElementById("delOps"),
  insOps: document.getElementById("insOps"),
  updOps: document.getElementById("updOps"),
};

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

async function loadTreeByCountry(countryName) {
  const stem = toStem(countryName);
  const res = await fetch(`${DATA_ROOT}/trees/${encodeURIComponent(stem)}.json`);
  if (!res.ok) throw new Error(`Could not load tree file for ${countryName}`);
  return res.json();
}

function treeNodeHtml(node) {
  const label = escapeHtml(node.label || "");
  const children = node.children || [];
  if (children.length === 0) return `<li><span>${label}</span></li>`;
  const kids = children.map(treeNodeHtml).join("");
  return `<li><details open><summary><span class="node">${label}</span></summary><ul>${kids}</ul></details></li>`;
}

function flattenLeaves(node, path = "", out = []) {
  const label = String(node.label || "");
  const current = path ? `${path}/${label}` : `/${label}`;
  const children = node.children || [];
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
  const leftPad = 36;
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

  const svgWidth = Math.max(900, leftPad * 2 + Math.max(1, nextLeafX - 1) * colGap + 260);
  const svgHeight = y + 24;

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

    container.innerHTML = `
      <div class="graph-toolbar">
        <div class="graph-meta">${nodes.length} nodes | max depth ${maxDepth}</div>
        <div class="viz-controls">
          <label>Depth
            <input type="range" min="0" max="${maxDepth}" value="${depthLimit}" data-act="depth" />
            <span class="viz-range">${depthLimit}</span>
          </label>
          <input type="search" placeholder="Find node label..." value="${escapeHtml(query)}" data-act="search" />
          <button type="button" data-act="zoom-out">-</button>
          <button type="button" data-act="zoom-reset">100%</button>
          <button type="button" data-act="zoom-in">+</button>
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
        <div><strong>Focused:</strong> ${escapeHtml(focus.label)}</div>
        <div><strong>Path:</strong> <code>${escapeHtml(focus.path)}</code></div>
        <div><strong>Parent:</strong> ${parent ? escapeHtml(parent.label) : "None (root)"}</div>
        <div><strong>Children:</strong> ${focus.childIds.length || 0}</div>
        <div><strong>Transformation:</strong> ${formatNodeTransform(transformMap?.get(focus.path) || [])}</div>
      </div>
      <div class="viz-hover" data-role="hover">Hover a node to preview transformation details.</div>
    `;

    const depthInput = container.querySelector('[data-act="depth"]');
    const searchInput = container.querySelector('[data-act="search"]');
    const zoomOutBtn = container.querySelector('[data-act="zoom-out"]');
    const zoomResetBtn = container.querySelector('[data-act="zoom-reset"]');
    const zoomInBtn = container.querySelector('[data-act="zoom-in"]');
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
    zoomOutBtn.addEventListener("click", () => {
      scale = Math.max(0.25, scale / 1.15);
      applyView();
    });
    zoomInBtn.addEventListener("click", () => {
      scale = Math.min(4, scale * 1.15);
      applyView();
    });
    zoomResetBtn.addEventListener("click", () => {
      scale = 1;
      applyView();
    });
    zoomFitBtn.addEventListener("click", () => {
      const fitW = (stageEl.clientWidth - 20) / svgWidth;
      const fitH = (stageEl.clientHeight - 20) / svgHeight;
      scale = Math.max(0.2, Math.min(4, Math.min(fitW, fitH)));
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
        scale = Math.max(0.2, Math.min(4, scale * factor));

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
        hover.innerHTML = `
          <strong>${escapeHtml(n.label)}</strong><br/>
          <code>${escapeHtml(n.path)}</code><br/>
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

function makeSimilarity() {
  const simCache = new Map();
  const serialCache = new WeakMap();

  function serializeNode(node) {
    if (serialCache.has(node)) return serialCache.get(node);
    const val = JSON.stringify({
      label: nodeLabel(node),
      children: (node.children || []).map((c) => JSON.parse(serializeNode(c))),
    });
    serialCache.set(node, val);
    return val;
  }

  function njSim(u, v) {
    const key = `${serializeNode(u)}|${serializeNode(v)}`;
    if (simCache.has(key)) return simCache.get(key);

    let result = 0;
    if (nodeLabel(u) === nodeLabel(v)) {
      const uc = u.children || [];
      const vc = v.children || [];
      const a = uc.length;
      const b = vc.length;
      const dp = Array.from({ length: a + 1 }, () => Array(b + 1).fill(0));
      for (let i = 1; i <= a; i += 1) {
        for (let j = 1; j <= b; j += 1) {
          const w = njSim(uc[i - 1], vc[j - 1]);
          dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1] + w);
        }
      }
      result = 1 + dp[a][b];
    }

    simCache.set(key, result);
    return result;
  }

  return njSim;
}

function alignChildren(uc, vc, sim) {
  const a = uc.length;
  const b = vc.length;
  const dp = Array.from({ length: a + 1 }, () => Array(b + 1).fill(0));
  const bt = Array.from({ length: a + 1 }, () => Array(b + 1).fill(null));

  for (let i = 1; i <= a; i += 1) {
    for (let j = 1; j <= b; j += 1) {
      const w = sim(uc[i - 1], vc[j - 1]);
      const up = dp[i - 1][j];
      const left = dp[i][j - 1];
      const diag = dp[i - 1][j - 1] + w;
      const best = Math.max(up, left, diag);
      dp[i][j] = best;
      if (best === diag) bt[i][j] = { kind: "DIAG", w };
      else if (best === up) bt[i][j] = { kind: "UP", w: 0 };
      else bt[i][j] = { kind: "LEFT", w: 0 };
    }
  }

  const matches = [];
  let i = a;
  let j = b;
  while (i > 0 && j > 0) {
    const step = bt[i][j];
    if (!step) break;
    if (step.kind === "DIAG") {
      if (step.w > 0) matches.push([i - 1, j - 1]);
      i -= 1;
      j -= 1;
    } else if (step.kind === "UP") {
      i -= 1;
    } else {
      j -= 1;
    }
  }
  return matches.reverse();
}

function buildEditScript(t1, t2) {
  const ops = [];
  const sim = makeSimilarity();

  function addIns(path, node) {
    ops.push({ kind: "INS", path, old: null, new: nodeLabel(node), nodeIsLeaf: isLeaf(node) });
  }
  function addDel(path, node) {
    ops.push({ kind: "DEL", path, old: nodeLabel(node), new: null, nodeIsLeaf: isLeaf(node) });
  }
  function addUpd(path, oldNode, newNode) {
    ops.push({
      kind: "UPD",
      path,
      old: nodeLabel(oldNode),
      new: nodeLabel(newNode),
      nodeIsLeaf: true,
    });
  }

  function diff(u, v, path) {
    if (nodeLabel(u) !== nodeLabel(v)) {
      addDel(path, u);
      addIns(path, v);
      return;
    }

    const uc = u.children || [];
    const vc = v.children || [];
    const current = joinPath(path, nodeLabel(u));

    if (uc.length === 0 && vc.length === 0) return;

    if (uc.length === 1 && vc.length === 1 && isLeaf(uc[0]) && isLeaf(vc[0])) {
      if (nodeLabel(uc[0]) !== nodeLabel(vc[0])) addUpd(current, uc[0], vc[0]);
      return;
    }

    const matches = alignChildren(uc, vc, sim);
    const matchU = new Set(matches.map((m) => m[0]));
    const matchV = new Set(matches.map((m) => m[1]));

    uc.forEach((child, idx) => {
      if (!matchU.has(idx)) addDel(current, child);
    });
    vc.forEach((child, idx) => {
      if (!matchV.has(idx)) addIns(current, child);
    });
    matches.forEach(([i, j]) => diff(uc[i], vc[j], current));
  }

  diff(t1, t2, "");
  return ops;
}

function opReason(kind) {
  if (kind === "DEL") return "Remove source-only data.";
  if (kind === "INS") return "Add target-only data.";
  return "Align shared field value.";
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

function opCard(op, idx) {
  const id = `${op.kind}-${String(idx + 1).padStart(3, "0")}`;
  const path = opPath(op);
  let action;
  if (op.kind === "DEL") action = `Delete <code>${escapeHtml(op.old)}</code>`;
  else if (op.kind === "INS") action = `Insert <code>${escapeHtml(op.new)}</code>`;
  else {
    action = `Update <code>${escapeHtml(op.old)}</code> &rarr; <code>${escapeHtml(op.new)}</code>`;
  }
  return `
    <article class="op ${op.kind.toLowerCase()}">
      <div class="op-head"><span class="badge">${id}</span><code>${escapeHtml(path)}</code></div>
      <div class="reason">${escapeHtml(opReason(op.kind))}</div>
      <div>${action}</div>
    </article>`;
}

function renderTransform(ops) {
  const delOps = sortOps(ops.filter((o) => o.kind === "DEL"));
  const insOps = sortOps(ops.filter((o) => o.kind === "INS"));
  const updOps = sortOps(ops.filter((o) => o.kind === "UPD"));
  const size1 = renderTransform.sourceNodeCount || 0;
  const size2 = renderTransform.targetNodeCount || 0;
  const totalNodes = size1 + size2;
  const ted = ops.length;
  const outputSimilarity = totalNodes ? Math.max(0, 1 - ted / totalNodes) : 1;

  els.stats.innerHTML = `
    <div class="stat"><div class="k">Total Ops</div><div class="v">${ops.length}</div></div>
    <div class="stat"><div class="k">Deletes</div><div class="v">${delOps.length}</div></div>
    <div class="stat"><div class="k">Inserts</div><div class="v">${insOps.length}</div></div>
    <div class="stat"><div class="k">Updates</div><div class="v">${updOps.length}</div></div>
    <div class="stat"><div class="k">TED (Output)</div><div class="v">${ted}</div></div>
    <div class="stat"><div class="k">Similarity (Output)</div><div class="v">${(outputSimilarity * 100).toFixed(2)}%</div></div>
  `;

  els.delOps.innerHTML = delOps.length ? delOps.map(opCard).join("") : '<p class="empty">No delete operations.</p>';
  els.insOps.innerHTML = insOps.length ? insOps.map(opCard).join("") : '<p class="empty">No insert operations.</p>';
  els.updOps.innerHTML = updOps.length ? updOps.map(opCard).join("") : '<p class="empty">No update operations.</p>';
}

function fillSelect(select, countries) {
  select.innerHTML = countries.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
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

async function onCountryChange() {
  const country = els.countrySelect.value;
  if (!country) return;
  try {
    const treeObj = await loadTreeByCountry(country);
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
    const [sObj, tObj] = await Promise.all([loadTreeByCountry(source), loadTreeByCountry(target)]);
    const ops = buildEditScript(sObj.tree, tObj.tree);
    const nodeMaps = buildNodeTransformMaps(ops);
    renderTransform.sourceNodeCount = countNodes(sObj.tree);
    renderTransform.targetNodeCount = countNodes(tObj.tree);
    renderNodeTree(els.sourceGraph, sObj.tree, { transformMap: nodeMaps.source });
    renderNodeTree(els.targetGraph, tObj.tree, { transformMap: nodeMaps.target });
    renderTransform(ops);
  } catch (err) {
    els.stats.innerHTML = `<div class="empty">${escapeHtml(String(err))}</div>`;
    els.sourceGraph.textContent = "";
    els.targetGraph.textContent = "";
    els.delOps.innerHTML = "";
    els.insOps.innerHTML = "";
    els.updOps.innerHTML = "";
  }
}

async function init() {
  try {
    const countries = await loadCountries();
    fillSelect(els.countrySelect, countries);
    fillSelect(els.sourceSelect, countries);
    fillSelect(els.targetSelect, countries);

    const sourceDefault = countries.includes("Lebanon") ? "Lebanon" : countries[0];
    const targetDefault = countries.includes("Switzerland") ? "Switzerland" : countries[1] || countries[0];

    els.countrySelect.value = sourceDefault;
    els.sourceSelect.value = sourceDefault;
    els.targetSelect.value = targetDefault;

    els.countrySelect.addEventListener("change", onCountryChange);
    els.compareBtn.addEventListener("click", onCompare);
    initResizableSplits();

    await onCountryChange();
    await onCompare();
  } catch (err) {
    document.body.innerHTML = `<pre style="padding:16px">${escapeHtml(String(err))}</pre>`;
  }
}

init();
