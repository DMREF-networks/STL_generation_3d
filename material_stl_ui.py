"""Local browser UI that generates STL files.

The page runs in a regular browser, while this small Python server performs
the local filesystem reads/writes and calls the STL generation code.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from config_to_stl import generate_from_config_data


DEFAULT_CONFIG_PATH = Path("sample_configs/multimaterial_test.json")


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Material STL Generator</title>
  <style>
    :root {
      --bg: #f5f6f3;
      --panel: #ffffff;
      --panel-2: #fbfbf8;
      --border: #d8ddd6;
      --text: #20262e;
      --muted: #626b76;
      --accent: #0f766e;
      --accent-dark: #115e59;
      --secondary: #6d5dfc;
      --danger: #b42318;
      --code: #111827;
      --shadow: 0 8px 24px rgba(31, 41, 55, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.4;
    }
    header {
      min-height: 60px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 10px 18px;
      border-bottom: 1px solid var(--border);
      background: var(--panel);
      box-shadow: 0 1px 0 rgba(31, 41, 55, 0.03);
    }
    h1 {
      margin: 0;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0;
    }
    h2 {
      margin: 0;
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    main {
      display: grid;
      grid-template-columns: minmax(520px, 1.08fr) minmax(420px, 0.92fr);
      gap: 16px;
      padding: 16px;
      min-height: calc(100vh - 60px);
    }
    section {
      min-width: 0;
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .section-head {
      min-height: 44px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 8px 12px;
      border-bottom: 1px solid var(--border);
      background: var(--panel-2);
    }
    .content {
      padding: 12px;
    }
    .stack {
      display: grid;
      gap: 14px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .row {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }
    .field-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      align-items: end;
    }
    label {
      display: grid;
      gap: 5px;
      min-width: 0;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .label-title {
      display: flex;
      align-items: center;
      gap: 6px;
      min-width: 0;
    }
    input, select, textarea {
      width: 100%;
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      font: inherit;
    }
    input, select {
      height: 34px;
      padding: 0 9px;
    }
    input[type="checkbox"] {
      width: 16px;
      height: 16px;
      padding: 0;
      accent-color: var(--accent);
    }
    input[type="color"] {
      width: 44px;
      padding: 2px;
    }
    textarea {
      min-height: 290px;
      resize: vertical;
      padding: 12px;
      color: var(--code);
      font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
      tab-size: 2;
    }
    button {
      height: 34px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0 12px;
      background: white;
      color: var(--text);
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      white-space: nowrap;
    }
    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: white;
    }
    button.primary:hover { background: var(--accent-dark); }
    button.secondary {
      border-color: #c8c5ff;
      color: #342f9b;
      background: #f5f3ff;
    }
    button.icon {
      width: 34px;
      padding: 0;
      font-size: 17px;
      line-height: 1;
    }
    button:disabled {
      opacity: 0.58;
      cursor: wait;
    }
    .check {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 34px;
      color: var(--text);
      font-size: 14px;
      font-weight: 550;
    }
    .tooltip {
      position: relative;
      display: inline-grid;
      place-items: center;
      flex: 0 0 auto;
      width: 18px;
      height: 18px;
      border: 1px solid var(--border);
      border-radius: 50%;
      background: var(--panel-2);
      color: var(--muted);
      cursor: help;
      font-size: 12px;
      font-weight: 800;
      line-height: 1;
    }
    .tooltip::after {
      content: attr(data-tooltip);
      position: absolute;
      left: 50%;
      bottom: calc(100% + 8px);
      z-index: 10;
      width: 310px;
      max-width: calc(100vw - 32px);
      padding: 9px 10px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: #111827;
      color: #fff;
      box-shadow: var(--shadow);
      font-size: 12px;
      font-weight: 600;
      line-height: 1.35;
      opacity: 0;
      pointer-events: none;
      text-align: left;
      transform: translate(-50%, 4px);
      transition: opacity 120ms ease, transform 120ms ease;
      white-space: normal;
    }
    .tooltip:hover::after,
    .tooltip:focus::after {
      opacity: 1;
      transform: translate(-50%, 0);
    }
    .hint {
      color: var(--muted);
      font-size: 12px;
    }
    .status {
      min-height: 38px;
      display: flex;
      align-items: center;
      padding: 0 12px;
      border-bottom: 1px solid var(--border);
      background: var(--panel-2);
      color: var(--muted);
      overflow-wrap: anywhere;
    }
    .status.error { color: var(--danger); }
    table {
      width: 100%;
      table-layout: fixed;
      border-collapse: collapse;
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }
    th, td {
      padding: 8px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: middle;
      overflow-wrap: anywhere;
    }
    th {
      color: var(--muted);
      background: var(--panel-2);
      font-size: 12px;
      font-weight: 750;
    }
    tr:last-child td { border-bottom: 0; }
    .materials th:last-child,
    .materials td:last-child {
      width: 48px;
      text-align: center;
    }
    .edge-map th:last-child,
    .edge-map td:last-child {
      width: 48px;
      text-align: center;
    }
    .swatch-name {
      display: grid;
      grid-template-columns: 44px minmax(0, 1fr);
      gap: 8px;
      align-items: center;
    }
    .result {
      padding: 12px;
      overflow: auto;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-bottom: 12px;
    }
    .metric {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
      background: var(--panel-2);
    }
    .metric strong {
      display: block;
      font-size: 18px;
      line-height: 1.1;
    }
    .metric span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    a {
      color: var(--accent-dark);
      font-weight: 700;
      text-decoration: none;
    }
    a:hover { text-decoration: underline; }
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 0;
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--danger);
      background: #fff;
    }
    details {
      border-top: 1px solid var(--border);
      padding-top: 10px;
    }
    summary {
      cursor: pointer;
      color: var(--muted);
      font-weight: 750;
    }
    .full { grid-column: 1 / -1; }
    .hidden { display: none; }
    @media (max-width: 1020px) {
      header { align-items: stretch; flex-direction: column; }
      main { grid-template-columns: 1fr; }
    }
    @media (max-width: 680px) {
      .grid, .summary { grid-template-columns: 1fr; }
      .field-row { grid-template-columns: 1fr; }
      .row { flex-wrap: wrap; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Material STL Generator</h1>
    <div class="row">
      <button id="generate" class="primary">Generate STLs</button>
    </div>
  </header>

  <main>
    <section>
      <div class="section-head">
        <h2>Configuration</h2>
        <div class="row">
          <button id="openConfig">Load Config</button>
        </div>
      </div>
      <div class="content stack">
        <input id="configPath" type="hidden" value="sample_configs/multimaterial_test.json">

        <div class="grid">
          <label>Job name
            <input id="jobName" value="test_multimaterial">
          </label>
          <div class="field-row">
            <label>Output folder
              <input id="outputDir" value="../samples_output/material_demo">
            </label>
            <button class="browse-dir" data-target="outputDir">Choose</button>
          </div>
          <div class="field-row">
            <label>Node positions file
              <input id="positions" value="demo_xy.csv">
            </label>
            <button class="browse" data-target="positions" data-kind="positions">Choose</button>
          </div>
          <div class="field-row">
            <label>Node diameters file
              <input id="nodeDiameters" placeholder="optional .npy/.csv/.pkl path">
            </label>
            <button class="browse" data-target="nodeDiameters" data-kind="node_diameters">Choose</button>
          </div>
          <div class="field-row">
            <label>Adjacency or edge-list file
              <input id="adjacency" value="demo_adj.csv">
            </label>
            <button class="browse" data-target="adjacency" data-kind="adjacency">Choose</button>
          </div>
          <label>Connectivity format
            <select id="adjacencyFormat">
              <option value="auto">Auto detect</option>
              <option value="matrix">Adjacency matrix</option>
              <option value="edge_list">Edge list</option>
            </select>
          </label>
          <label id="edgeListInterpretationRow">Edge list interpretation
            <select id="edgeListInterpretation">
              <option value="legacy">Legacy: source,target[,length]</option>
              <option value="thickness">Column 3 is thickness</option>
              <option value="material">Column 3 is material code</option>
              <option value="thickness_material">Column 3 thickness, column 4 material code</option>
            </select>
          </label>
          <label>Extra material assignment
            <select id="materialMode">
              <option value="default">Use default / edge-list setting</option>
              <option value="matrix">Material matrix file</option>
              <option value="edge_table">Separate edge-material table</option>
            </select>
          </label>
          <div id="materialMatrixRow" class="field-row">
            <label>Material matrix file
              <input id="materialMatrix" value="demo_material_matrix.csv">
            </label>
            <button class="browse" data-target="materialMatrix" data-kind="material_matrix">Choose</button>
          </div>
          <div id="edgeMaterialsRow" class="field-row hidden">
            <label>Edge-material table
              <input id="edgeMaterials" placeholder="optional CSV path">
            </label>
            <button class="browse" data-target="edgeMaterials" data-kind="edge_materials">Choose</button>
          </div>
        </div>

        <div class="grid">
          <label>Default edge material
            <select id="defaultMaterial"></select>
          </label>
          <label>
            <span class="label-title">
              Node material mode
              <span
                class="tooltip"
                tabindex="0"
                aria-label="Node material mode help"
                data-tooltip="Choose whether every node sphere uses one dedicated material, or node spheres are assigned from the beam materials that touch them. A dedicated node material is usually clearest for multi-material prints."
              >?</span>
            </span>
            <select id="nodeMaterialMode">
              <option value="fixed">Use one material for all nodes</option>
              <option value="auto">Use connected beam materials for nodes</option>
            </select>
          </label>
          <label id="nodeMaterialRow">Node material
            <select id="nodeMaterial"></select>
          </label>
          <label id="junctionPolicyRow">
            <span class="label-title">
              Mixed-node handling
              <span
                class="tooltip"
                tabindex="0"
                aria-label="Mixed-node handling help"
                data-tooltip="Only used when node material mode is set to connected beam materials. Separate writes mixed-material nodes into the mixed-node material. Dominant writes each mixed node into the incident beam material with the largest total weight."
              >?</span>
            </span>
            <select id="junctionPolicy">
              <option value="separate">Separate mixed nodes</option>
              <option value="dominant">Dominant incident material</option>
            </select>
          </label>
          <label id="mixedJunctionMaterialRow">Mixed-node material
            <select id="mixedJunctionMaterial"></select>
          </label>
          <label>Beam cross-section
            <select id="beamCrossSection">
              <option value="circular">Circular</option>
              <option value="square">Square</option>
            </select>
          </label>
          <label>Beam size mm
            <input id="beamDiameter" type="number" step="0.001" min="0" value="0.25">
          </label>
          <label>Side length mm
            <input id="sideLength" type="number" step="0.001" min="0" value="30">
          </label>
          <label class="check">
            <input id="variableThickness" type="checkbox" checked>
            Use adjacency or thickness values
            <span
              class="tooltip"
              tabindex="0"
              aria-label="Adjacency or thickness values help"
              data-tooltip="When on, adjacency matrix values or edge-list thickness/weight columns scale beam diameter. When off, nonzero values only mean an edge exists and all beams use the base diameter."
            >?</span>
          </label>
          <label class="check">
            <input id="booleanUnion" type="checkbox" checked>
            Boolean union per material
            <span
              class="tooltip"
              tabindex="0"
              aria-label="Boolean union per material help"
              data-tooltip="Merges overlapping pieces within each material into cleaner STL geometry. It never combines different materials. Leave on for final prints; turn off only if generation is slow or the union fails."
            >?</span>
          </label>
        </div>

        <div class="stack">
          <div class="section-head">
            <h2>Materials</h2>
            <button id="addMaterial" class="secondary">Add Material</button>
          </div>
          <table class="materials">
            <thead>
              <tr>
                <th>Material</th>
                <th></th>
              </tr>
            </thead>
            <tbody id="materialsBody"></tbody>
          </table>
        </div>

        <div id="edgeMaterialMapSection" class="stack hidden">
          <div class="section-head">
            <h2>Edge Material Codes</h2>
            <button id="addEdgeMaterialMap" class="secondary">Add Code</button>
          </div>
          <table class="edge-map">
            <thead>
              <tr>
                <th>Edge value</th>
                <th>Material</th>
                <th></th>
              </tr>
            </thead>
            <tbody id="edgeMaterialMapBody"></tbody>
          </table>
        </div>

        <details>
          <summary>Advanced JSON</summary>
          <div class="stack" style="margin-top: 10px;">
            <div class="row">
              <button id="applyJson">Apply JSON to Form</button>
              <button id="refreshJson">Refresh From Form</button>
            </div>
            <textarea id="configJson" spellcheck="false"></textarea>
          </div>
        </details>
      </div>
    </section>

    <section>
      <div id="status" class="status">Ready</div>
      <div id="result" class="result"></div>
    </section>
  </main>

  <script>
    const ids = [
      "configPath", "jobName", "outputDir", "positions", "nodeDiameters", "adjacency",
      "adjacencyFormat", "edgeListInterpretation", "materialMode", "materialMatrix", "edgeMaterials",
      "defaultMaterial", "nodeMaterialMode", "nodeMaterial", "mixedJunctionMaterial",
      "junctionPolicy", "beamCrossSection", "beamDiameter", "sideLength", "variableThickness",
      "booleanUnion", "configJson"
    ];
    const el = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));
    const materialsBody = document.getElementById("materialsBody");
    const edgeMaterialMapBody = document.getElementById("edgeMaterialMapBody");
    const statusEl = document.getElementById("status");
    const resultEl = document.getElementById("result");
    const materialMatrixRow = document.getElementById("materialMatrixRow");
    const edgeMaterialsRow = document.getElementById("edgeMaterialsRow");
    const edgeListInterpretationRow = document.getElementById("edgeListInterpretationRow");
    const edgeMaterialMapSection = document.getElementById("edgeMaterialMapSection");
    const nodeMaterialRow = document.getElementById("nodeMaterialRow");
    const junctionPolicyRow = document.getElementById("junctionPolicyRow");
    const mixedJunctionMaterialRow = document.getElementById("mixedJunctionMaterialRow");
    const buttons = [...document.querySelectorAll("button")];

    const defaultMaterials = [
      ["rigid", "#2563eb"],
      ["flexible", "#dc2626"],
      ["conductive", "#059669"]
    ];

    let jsonDirty = false;

    function setBusy(busy) {
      buttons.forEach(button => button.disabled = busy);
    }

    function setStatus(text, isError = false) {
      statusEl.textContent = text;
      statusEl.classList.toggle("error", isError);
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function escapeAttr(value) {
      return escapeHtml(value).replaceAll("'", "&#39;");
    }

    function fileLink(path, label) {
      return `<a target="_blank" rel="noreferrer" href="/file?path=${encodeURIComponent(path)}">${escapeHtml(label)}</a>`;
    }

    async function post(url, body) {
      const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body || {})
      });
      const payload = await response.json();
      if (!response.ok || payload.error) {
        throw new Error(payload.error || response.statusText);
      }
      return payload;
    }

    function addMaterialRow(name = "", color = "#2563eb") {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>
          <div class="swatch-name">
            <input class="material-color" type="color" value="${escapeAttr(color)}" aria-label="Material color">
            <input class="material-name" value="${escapeAttr(name)}" aria-label="Material name">
          </div>
        </td>
        <td><button class="icon remove-material" title="Remove material" aria-label="Remove material">x</button></td>
      `;
      materialsBody.appendChild(row);
      row.querySelector(".remove-material").addEventListener("click", () => {
        row.remove();
        render();
      });
      row.querySelectorAll("input").forEach(input => input.addEventListener("input", render));
    }

    function materialEntries() {
      const entries = [];
      materialsBody.querySelectorAll("tr").forEach(row => {
        const name = row.querySelector(".material-name").value.trim();
        const color = row.querySelector(".material-color").value || "#2563eb";
        if (name) entries.push([name, color]);
      });
      return entries;
    }

    function materialsObject() {
      return Object.fromEntries(materialEntries().map(([name, color]) => [name, { color }]));
    }

    function usesEdgeMaterialMap() {
      return ["material", "thickness_material"].includes(el.edgeListInterpretation.value);
    }

    function addEdgeMaterialMapRow(code = "", material = "") {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td><input class="edge-code" value="${escapeAttr(code)}" aria-label="Edge material code"></td>
        <td><select class="edge-material" aria-label="Mapped material"></select></td>
        <td><button class="icon remove-edge-map" title="Remove code" aria-label="Remove code">x</button></td>
      `;
      edgeMaterialMapBody.appendChild(row);
      row.querySelector(".remove-edge-map").addEventListener("click", () => {
        row.remove();
        render();
      });
      row.querySelector(".edge-code").addEventListener("input", render);
      row.querySelector(".edge-material").addEventListener("change", render);
      updateEdgeMaterialMapSelect(row, material);
    }

    function edgeMaterialMapObject() {
      const result = {};
      edgeMaterialMapBody.querySelectorAll("tr").forEach(row => {
        const code = row.querySelector(".edge-code").value.trim();
        const material = row.querySelector(".edge-material").value;
        if (code && material) result[code] = material;
      });
      return result;
    }

    function updateEdgeMaterialMapSelect(row, preferred = "") {
      const names = materialEntries().map(([name]) => name);
      const select = row.querySelector(".edge-material");
      setSelectOptions(select, names, { preferred: preferred || select.value });
    }

    function updateEdgeMaterialMapSelects() {
      edgeMaterialMapBody.querySelectorAll("tr").forEach(row => updateEdgeMaterialMapSelect(row));
    }

    function ensureDefaultEdgeMaterialMapRows() {
      if (!usesEdgeMaterialMap() || edgeMaterialMapBody.children.length > 0) return;
      const names = materialEntries().map(([name]) => name);
      addEdgeMaterialMapRow("0", names[0] || "");
      addEdgeMaterialMapRow("1", names[1] || names[0] || "");
    }

    function setSelectOptions(select, values, options = {}) {
      const previous = select.value;
      select.innerHTML = "";
      if (options.blankLabel) {
        const blank = document.createElement("option");
        blank.value = "";
        blank.textContent = options.blankLabel;
        select.appendChild(blank);
      }
      values.forEach(value => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      });
      if (previous && values.includes(previous)) {
        select.value = previous;
      } else if (options.preferred && values.includes(options.preferred)) {
        select.value = options.preferred;
      } else if (!options.blankLabel && values.length) {
        select.value = values[0];
      }
    }

    function updateMaterialSelects() {
      const names = materialEntries().map(([name]) => name);
      const defaultName = names.includes(el.defaultMaterial.value) ? el.defaultMaterial.value : names[0] || "default";
      const nodeName = names.includes(el.nodeMaterial.value)
        ? el.nodeMaterial.value
        : defaultName;
      const mixedName = names.includes(el.mixedJunctionMaterial.value)
        ? el.mixedJunctionMaterial.value
        : defaultName;
      setSelectOptions(el.defaultMaterial, names, { preferred: defaultName });
      setSelectOptions(el.nodeMaterial, names, { preferred: nodeName });
      setSelectOptions(el.mixedJunctionMaterial, names, { preferred: mixedName });
      updateEdgeMaterialMapSelects();
    }

    function buildConfig() {
      const fixedNodeMaterial = el.nodeMaterialMode.value === "fixed";
      const fallbackMaterial = el.defaultMaterial.value || materialEntries()[0]?.[0] || "default";
      const geometry = {
        beam_diameter_mm: Number(el.beamDiameter.value),
        beam_cross_section: el.beamCrossSection.value,
        cube_side_length_mm: Number(el.sideLength.value),
        variable_thickness: el.adjacencyFormat.value === "edge_list"
          ? ["thickness", "thickness_material"].includes(el.edgeListInterpretation.value)
          : el.variableThickness.checked,
        boolean_union: el.booleanUnion.checked
      };
      if (fixedNodeMaterial) {
        geometry.node_material = el.nodeMaterial.value || fallbackMaterial;
      } else {
        geometry.junction_policy = el.junctionPolicy.value;
        if (el.junctionPolicy.value === "separate") {
          geometry.mixed_junction_material = el.mixedJunctionMaterial.value || fallbackMaterial;
        }
      }

      const job = {
        name: el.jobName.value.trim() || "network",
        positions: el.positions.value.trim(),
        adjacency: el.adjacency.value.trim(),
        adjacency_format: el.adjacencyFormat.value
      };
      if (el.nodeDiameters.value.trim()) {
        job.node_diameters = el.nodeDiameters.value.trim();
      }
      if (el.adjacencyFormat.value === "edge_list") {
        job.edge_list_interpretation = el.edgeListInterpretation.value;
        if (usesEdgeMaterialMap()) {
          job.edge_material_map = edgeMaterialMapObject();
        }
      }
      if (el.materialMode.value === "matrix" && el.materialMatrix.value.trim()) {
        job.material_matrix = el.materialMatrix.value.trim();
      }
      if (el.materialMode.value === "edge_table" && el.edgeMaterials.value.trim()) {
        job.edge_materials = el.edgeMaterials.value.trim();
      }

      return {
        output_dir: el.outputDir.value.trim() || ".",
        default_material: el.defaultMaterial.value || "default",
        geometry,
        materials: materialsObject(),
        jobs: [job]
      };
    }

    function validate(config) {
      const job = config.jobs[0];
      const errors = [];
      if (!job.positions) errors.push("Node positions file is required.");
      if (!job.adjacency) errors.push("Adjacency or edge-list file is required.");
      if (!(config.geometry.beam_diameter_mm > 0)) errors.push("Beam size must be greater than zero.");
      if (!(config.geometry.cube_side_length_mm > 0)) errors.push("Side length must be greater than zero.");
      if (Object.keys(config.materials).length === 0) errors.push("At least one material is required.");
      if (config.jobs[0].adjacency_format === "edge_list" && el.materialMode.value === "matrix") {
        errors.push("A material matrix only applies to adjacency matrix inputs.");
      }
      if (job.adjacency_format === "edge_list" && usesEdgeMaterialMap() && Object.keys(edgeMaterialMapObject()).length === 0) {
        errors.push("Add at least one edge material code mapping.");
      }
      if (errors.length) setStatus(errors.join(" "), true);
      else if (!jsonDirty) setStatus("Ready");
    }

    function render(options = {}) {
      updateMaterialSelects();
      const isEdgeList = el.adjacencyFormat.value === "edge_list";
      edgeListInterpretationRow.classList.toggle("hidden", !isEdgeList);
      materialMatrixRow.classList.toggle("hidden", el.materialMode.value !== "matrix");
      edgeMaterialsRow.classList.toggle("hidden", el.materialMode.value !== "edge_table");
      edgeMaterialMapSection.classList.toggle("hidden", !isEdgeList || !usesEdgeMaterialMap());
      el.variableThickness.disabled = isEdgeList;
      const fixedNodeMaterial = el.nodeMaterialMode.value === "fixed";
      nodeMaterialRow.classList.toggle("hidden", !fixedNodeMaterial);
      junctionPolicyRow.classList.toggle("hidden", fixedNodeMaterial);
      mixedJunctionMaterialRow.classList.toggle("hidden", fixedNodeMaterial || el.junctionPolicy.value !== "separate");
      const config = buildConfig();
      if (!jsonDirty || options.forceJson) {
        el.configJson.value = JSON.stringify(config, null, 2);
        jsonDirty = false;
      }
      validate(config);
    }

    function loadConfigObject(config, path = "") {
      const job = (Array.isArray(config.jobs) && config.jobs[0]) || config;
      const geometry = { ...(config.geometry || {}), ...(job.geometry || {}) };
      const materials = { ...(config.materials || {}), ...(job.materials || {}) };
      const configuredDefaultMaterial = job.default_material || config.default_material;
      [configuredDefaultMaterial, geometry.node_material, geometry.mixed_junction_material]
        .filter(Boolean)
        .forEach(name => {
          if (!materials[name]) materials[name] = { color: "#4b5563" };
        });

      el.configPath.value = path || el.configPath.value;
      el.jobName.value = job.name || "network";
      el.outputDir.value = config.output_dir || job.output_dir || ".";
      el.positions.value = job.positions || job.xy || "";
      el.nodeDiameters.value = job.node_diameters || job.node_diameters_file || job.node_diameter_file || "";
      el.adjacency.value = job.adjacency || job.adj || "";
      el.adjacencyFormat.value = job.adjacency_format || "auto";
      el.edgeListInterpretation.value = inferEdgeListInterpretation(job, geometry);
      el.materialMatrix.value = job.material_matrix || job.materials_matrix || "";
      el.edgeMaterials.value = job.edge_materials || "";
      el.materialMode.value = job.material_matrix || job.materials_matrix
        ? "matrix"
        : job.edge_materials
          ? "edge_table"
          : "default";
      el.beamCrossSection.value = ["circular", "square"].includes(geometry.beam_cross_section || geometry.cross_section)
        ? (geometry.beam_cross_section || geometry.cross_section)
        : "circular";
      el.beamDiameter.value = geometry.beam_diameter_mm || geometry.beam_diameter || 1;
      el.sideLength.value = geometry.cube_side_length_mm || geometry.cube_side_length || 1;
      el.nodeMaterialMode.value = geometry.node_material ? "fixed" : "auto";
      el.junctionPolicy.value = ["separate", "dominant"].includes(geometry.junction_policy)
        ? geometry.junction_policy
        : "separate";
      el.variableThickness.checked = Boolean(geometry.variable_thickness);
      el.booleanUnion.checked = geometry.boolean_union !== false;

      materialsBody.innerHTML = "";
      const entries = Object.keys(materials).length
        ? Object.entries(materials).map(([name, value]) => [name, (value && value.color) || "#2563eb"])
        : defaultMaterials;
      entries.forEach(([name, color]) => addMaterialRow(name, color));
      edgeMaterialMapBody.innerHTML = "";
      const edgeMaterialMap = job.edge_material_map || job.material_code_map || {};
      Object.entries(edgeMaterialMap).forEach(([code, material]) => addEdgeMaterialMapRow(code, material));
      ensureDefaultEdgeMaterialMapRows();
      updateMaterialSelects();
      el.defaultMaterial.value = job.default_material || config.default_material || materialEntries()[0]?.[0] || "default";
      el.nodeMaterial.value = geometry.node_material || el.defaultMaterial.value;
      el.mixedJunctionMaterial.value = geometry.mixed_junction_material || el.defaultMaterial.value;
      jsonDirty = false;
      render({ forceJson: true });
    }

    function inferEdgeListInterpretation(job, geometry) {
      if (job.edge_list_interpretation || job.edge_interpretation) {
        return job.edge_list_interpretation || job.edge_interpretation;
      }
      const columns = job.edge_columns || {};
      const hasMaterial = columns.material !== undefined;
      const hasThickness = columns.thickness !== undefined || columns.weight !== undefined;
      if (hasMaterial && hasThickness) return "thickness_material";
      if (hasMaterial) return "material";
      if (hasThickness || geometry.variable_thickness) return "thickness";
      return "legacy";
    }

    async function loadConfig(path) {
      const payload = await post("/load", { path });
      loadConfigObject(JSON.parse(payload.text), payload.path);
      setStatus("Config loaded");
    }

    function renderResult(result, generatedConfigPath = "") {
      if (!result || !result.jobs) {
        resultEl.innerHTML = "";
        return;
      }
      const savedConfig = generatedConfigPath
        ? `<p>${fileLink(generatedConfigPath, "Saved generation config")}</p>`
        : "";
      resultEl.innerHTML = savedConfig + result.jobs.map(job => {
        const rows = (job.outputs || []).map(output => `
          <tr>
            <td>${escapeHtml(output.material)}</td>
            <td>${escapeHtml(output.faces)}</td>
            <td>${output.watertight ? "yes" : "no"}</td>
            <td>${fileLink(output.path, output.path)}</td>
          </tr>
        `).join("");
        const preview = job.preview && job.preview.path
          ? `<p>${fileLink(job.preview.path, "Open material preview")}</p>`
          : "";
        const warnings = (job.warnings || []).length
          ? `<div class="status" style="color: #92400e; border-color: #f59e0b;">${(job.warnings || []).map(escapeHtml).join("<br>")}</div>`
          : "";
        return `
          <div class="summary">
            <div class="metric"><strong>${escapeHtml(job.edge_count)}</strong><span>Edges</span></div>
            <div class="metric"><strong>${escapeHtml(job.material_count)}</strong><span>STL files</span></div>
            <div class="metric"><strong>${escapeHtml(job.name)}</strong><span>Job</span></div>
          </div>
          ${warnings}
          <table>
            <thead><tr><th>Material</th><th>Faces</th><th>Watertight</th><th>File</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
          ${preview}
        `;
      }).join("");
    }

    async function chooseFile(target, kind) {
      const payload = await post("/pick-file", { kind, initial: el[target].value });
      el[target].value = payload.path;
      render({ forceJson: true });
      return payload.path;
    }

    async function chooseDirectory(target) {
      const payload = await post("/pick-directory", { initial: el[target].value });
      el[target].value = payload.path;
      render({ forceJson: true });
      return payload.path;
    }

    document.getElementById("openConfig").addEventListener("click", async () => {
      setBusy(true);
      try {
        const path = await chooseFile("configPath", "config");
        await loadConfig(path);
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        setBusy(false);
      }
    });

    document.getElementById("generate").addEventListener("click", async () => {
      setBusy(true);
      resultEl.innerHTML = "";
      setStatus("Generating STL files...");
      try {
        if (!jsonDirty) {
          render({ forceJson: true });
        }
        const payload = await post("/generate", {
          config_path: el.configPath.value,
          config_text: el.configJson.value
        });
        renderResult(payload.result, payload.generated_config_path);
        setStatus("STL generation complete");
      } catch (error) {
        resultEl.innerHTML = `<pre>${escapeHtml(error.message)}</pre>`;
        setStatus("Generation failed", true);
      } finally {
        setBusy(false);
      }
    });

    document.getElementById("addMaterial").addEventListener("click", () => {
      addMaterialRow("material", "#2563eb");
      render({ forceJson: true });
    });

    document.getElementById("addEdgeMaterialMap").addEventListener("click", () => {
      addEdgeMaterialMapRow("", materialEntries()[0]?.[0] || "");
      render({ forceJson: true });
    });

    document.getElementById("applyJson").addEventListener("click", () => {
      try {
        loadConfigObject(JSON.parse(el.configJson.value), el.configPath.value);
        setStatus("JSON applied to form");
      } catch (error) {
        setStatus(error.message, true);
      }
    });

    document.getElementById("refreshJson").addEventListener("click", () => {
      jsonDirty = false;
      render({ forceJson: true });
      setStatus("JSON refreshed from form");
    });

    document.querySelectorAll(".browse").forEach(button => {
      button.addEventListener("click", async () => {
        setBusy(true);
        try {
          await chooseFile(button.dataset.target, button.dataset.kind);
        } catch (error) {
          setStatus(error.message, true);
        } finally {
          setBusy(false);
        }
      });
    });

    document.querySelectorAll(".browse-dir").forEach(button => {
      button.addEventListener("click", async () => {
        setBusy(true);
        try {
          await chooseDirectory(button.dataset.target);
        } catch (error) {
          setStatus(error.message, true);
        } finally {
          setBusy(false);
        }
      });
    });

    el.edgeListInterpretation.addEventListener("change", () => {
      ensureDefaultEdgeMaterialMapRows();
      render({ forceJson: true });
    });

    ["input", "change"].forEach(eventName => {
      document.querySelectorAll("input, select").forEach(node => {
        if (node.id === "configJson" || node.id === "edgeListInterpretation") return;
        node.addEventListener(eventName, () => render({ forceJson: true }));
      });
    });
    el.configJson.addEventListener("input", () => {
      jsonDirty = true;
      setStatus("Advanced JSON edited. Generate will use the JSON text.", false);
    });

    defaultMaterials.forEach(([name, color]) => addMaterialRow(name, color));
    render({ forceJson: true });
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "MaterialSTLGenerator/1.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_bytes(PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/file":
            params = parse_qs(parsed.query)
            self._send_file(params.get("path", [""])[0])
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            payload = self._read_json()
            if parsed.path == "/load":
                self._load(payload)
            elif parsed.path == "/save":
                self._save(payload)
            elif parsed.path == "/generate":
                self._generate(payload)
            elif parsed.path == "/pick-file":
                self._pick_file(payload)
            elif parsed.path == "/pick-save-file":
                self._pick_save_file(payload)
            elif parsed.path == "/pick-directory":
                self._pick_directory(payload)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json(
                {"error": f"{exc}\n\n{traceback.format_exc()}"},
                status=HTTPStatus.BAD_REQUEST,
            )

    def log_message(self, format: str, *args: Any) -> None:
        print("%s - %s" % (self.address_string(), format % args))

    def _load(self, payload: Dict[str, Any]) -> None:
        path = _resolve_path(payload.get("path") or DEFAULT_CONFIG_PATH)
        self._send_json({"path": str(path), "text": path.read_text(encoding="utf-8")})

    def _save(self, payload: Dict[str, Any]) -> None:
        path = _resolve_path(payload.get("path") or DEFAULT_CONFIG_PATH)
        text = str(payload.get("text", ""))
        json.loads(text)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip() + "\n", encoding="utf-8")
        self._send_json({"path": str(path)})

    def _generate(self, payload: Dict[str, Any]) -> None:
        config_text = str(payload.get("config_text", "")).strip()
        if not config_text:
            raise ValueError("Config text is required.")
        config = json.loads(config_text)
        path = _resolve_path(payload.get("config_path") or DEFAULT_CONFIG_PATH)
        result = generate_from_config_data(config, base_dir=path.parent)
        generated_config_path = _write_generated_config(config, result)
        self._send_json({
            "result": result,
            "generated_config_path": str(generated_config_path) if generated_config_path else "",
        })

    def _pick_file(self, payload: Dict[str, Any]) -> None:
        path = _pick_path(
            mode="open",
            kind=str(payload.get("kind") or "file"),
            initial=payload.get("initial"),
        )
        self._send_json({"path": path})

    def _pick_save_file(self, payload: Dict[str, Any]) -> None:
        path = _pick_path(
            mode="save",
            kind=str(payload.get("kind") or "config"),
            initial=payload.get("initial"),
        )
        self._send_json({"path": path})

    def _pick_directory(self, payload: Dict[str, Any]) -> None:
        path = _pick_path(mode="directory", kind="directory", initial=payload.get("initial"))
        self._send_json({"path": path})

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, indent=2).encode("utf-8")
        self._send_bytes(data, "application/json; charset=utf-8", status=status)

    def _send_file(self, value: str) -> None:
        path = _resolve_path(value)
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self._send_bytes(path.read_bytes(), content_type)

    def _send_bytes(
        self,
        data: bytes,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _write_generated_config(config: Dict[str, Any], result: Dict[str, Any]) -> Optional[Path]:
    jobs = result.get("jobs") or []
    if not jobs:
        return None
    first_job = jobs[0]
    output_dir = Path(str(first_job.get("output_dir") or ".")).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    name = _slug(first_job.get("name") or "material_config")
    path = output_dir / f"{name}_config.json"
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


def _slug(value: Any) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("._")
    return slug or "material_config"


def _resolve_path(value: Any) -> Path:
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _pick_path(mode: str, kind: str, initial: Any = None) -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise ValueError("The Browse buttons require tkinter. Paste the path into the field instead.") from exc

    initial_path = _initial_dialog_path(initial)
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise ValueError("Could not open a file picker in this environment. Paste the path into the field instead.") from exc
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        if mode == "open":
            selected = filedialog.askopenfilename(
                parent=root,
                title=_dialog_title(kind),
                initialdir=str(initial_path[0]),
                filetypes=_dialog_filetypes(kind),
            )
        elif mode == "save":
            selected = filedialog.asksaveasfilename(
                parent=root,
                title="Save config JSON",
                initialdir=str(initial_path[0]),
                initialfile=initial_path[1],
                defaultextension=".json",
                filetypes=_dialog_filetypes(kind),
            )
        elif mode == "directory":
            selected = filedialog.askdirectory(
                parent=root,
                title="Choose output folder",
                initialdir=str(initial_path[0]),
            )
        else:
            raise ValueError(f"Unknown picker mode: {mode}")
    except tk.TclError as exc:
        raise ValueError("Could not open a file picker in this environment. Paste the path into the field instead.") from exc
    finally:
        root.destroy()

    if not selected:
        raise ValueError("No file selected.")
    return str(Path(selected).expanduser().resolve())


def _initial_dialog_path(value: Any) -> Tuple[Path, str]:
    if value:
        path = _resolve_path(value)
        if path.is_dir():
            return path, ""
        return path.parent if path.parent.exists() else Path.cwd(), path.name
    return Path.cwd(), ""


def _dialog_title(kind: str) -> str:
    titles = {
        "config": "Open config JSON",
        "positions": "Choose node positions file",
        "node_diameters": "Choose node diameters file",
        "adjacency": "Choose adjacency or edge-list file",
        "material_matrix": "Choose material matrix file",
        "edge_materials": "Choose edge-material table",
    }
    return titles.get(kind, "Choose file")


def _dialog_filetypes(kind: str) -> Iterable[Tuple[str, str]]:
    if kind == "config":
        return [("JSON files", "*.json"), ("All files", "*")]
    if kind == "edge_materials":
        return [("CSV files", "*.csv"), ("All files", "*")]
    if kind in {"positions", "node_diameters", "adjacency", "material_matrix"}:
        return [("CSV, NumPy, and pickle files", "*.csv *.npy *.pkl *.pickle"), ("CSV files", "*.csv"), ("NumPy files", "*.npy"), ("Pickle files", "*.pkl *.pickle"), ("All files", "*")]
    return [("All files", "*")]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local material STL browser UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser automatically.")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Material STL Generator running at {url}", flush=True)
    print("Keep this process running while using the browser UI. Press Ctrl+C to stop.", flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
