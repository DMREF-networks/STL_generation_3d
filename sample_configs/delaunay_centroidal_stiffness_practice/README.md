# Delaunay-Centroidal Stiffness Practice

These files are for practicing the browser UI workflow without generating
STLs ahead of time.

Load one of these configs in `material_stl_ui.py`:

- `default_stiffness.json`
- `random_50_50_stiffness.json`
- `angle_based_stiffness.json`
- `default_bigger_nodes.json`

Both configs use the same network:

- `nodes.npy`: node positions, shape `(358, 3)`
- `node_diameters_2mm.npy`: node diameters, shape `(358,)`, all `2.0 mm`
- `edges_plain.npy`: plain edge list, shape `(467, 2)`, columns `source, target`
- edge-list files: shape `(467, 3)`
- edge-list columns: `source, target, material_code`
- beam diameter: `1.5 mm`

The config tells the UI/generator that the third edge-list column is a
material code:

```json
"edge_list_interpretation": "material",
"edge_material_map": {
  "0": "stiffness_a",
  "1": "stiffness_b"
}
```

For `random_50_50_stiffness.json`, material codes are randomly shuffled
across the edges with seed `20260617`.

For `angle_based_stiffness.json`, code `1` is used when an edge is closer
to vertical than horizontal, meaning `abs(dy) > abs(dx)`. Code `0` is
used otherwise.

For `default_stiffness.json`, all beams and junctions use
`stiffness_a`.

For `default_bigger_nodes.json`, beams use `stiffness_a`, node junctions
use `node_material`, and node diameters come from `node_diameters_2mm.npy`.
