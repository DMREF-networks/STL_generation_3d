# STL Generation 3D

STL Generation 3D converts network data into 3D-printable STL meshes.
Inputs are node positions plus connectivity data, either as CSV files or
NumPy `.npy` files. Outputs are STL files and optional HTML previews.

## Setup

Clone the repository, create a virtual environment, and install the
Python dependencies:

```bash
git clone https://github.com/DMREF-networks/STL_generation_3d.git
cd STL_generation_3d
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover
```

On Windows, activate the environment with:

```bat
.\.venv\Scripts\activate
```

The project is currently checked with Python `3.8.10`. It uses
`trimesh`, `manifold3d`, `shapely`, `numpy`, `scipy`, `matplotlib`, and
`plotly`.

## Personal Configs And Outputs

The committed sample configs are meant as examples. For day-to-day use,
keep your own configs and generated STL/HTML files in local working
folders such as:

```text
local_configs/
local_output/
```

Those folders are ignored by Git so collaborators can create their own
inputs and outputs without mixing them into the shared repository
history.

## Input Files

Each network needs:

- an `xy` file containing node positions
- an `adj` file containing connectivity

The interactive converter pairs files by name:

```text
name_xy.csv
name_adj.csv
```

or:

```text
name_xy.npy
name_adj.npy
```

Suffixes after `_xy` and `_adj` are preserved, so these are also paired:

```text
network_xy_0.1.npy
network_adj_0.1.npy
```

Position files may have two columns (`x, y`) or three columns
(`x, y, z`). Two-dimensional positions are automatically placed on
`z = 0`.

Adjacency data can be either:

- a square adjacency matrix, where nonzero entries are edges
- an edge list, commonly `(source, target)`,
  `(source, target, thickness)`, `(source, target, material)`, or
  `(source, target, thickness, material)`

For `.npy` edge-list inputs, the existing sample data uses an `(E, 3)`
array.

## Standard STL Generation

Run the interactive script:

```bash
python npyToSTLScript.py
```

The script prompts for:

- input type: `csv` or `npy`
- input directory
- beam diameter in millimeters
- model side length in millimeters
- whether adjacency values should control beam thickness
- meshing method: `cylinders` or `planar`

Generated STL and HTML preview files are written to the current working
directory.

## Browser UI That Generates STLs

Run the local browser UI with:

```bash
python material_stl_ui.py
```

The script opens a browser page with form controls for the common
configuration choices: input files, connectivity format, material source,
beam size, thickness mode, junction policy, node material, and output
folder. Use the `Browse` and `Choose` buttons to select local files and
folders through the file explorer, or paste paths directly into the
fields. Keep the Python process running while using the page. The
browser provides the interface, and the local Python process does the
meshing and file writes.

The normal UI workflow is to set the form controls and click
`Generate STLs`. Each generation also writes a matching JSON config file
into the output folder so the parameters can be reused later. If you
already have a JSON config, use `Load Config` to populate the form before
generating. The advanced JSON panel is still available for manual edits,
but it is not required for the normal workflow.

If the file picker cannot open in your environment, paste the file path
into the field instead.

## Beam Thickness

By default, adjacency values are treated as binary connectivity. Every
nonzero edge uses the beam diameter entered at the prompt.

If variable thickness is enabled, adjacency values become scale factors:

```text
edge_diameter = beam_diameter * adjacency_value
```

For edge-list inputs, the thickness defaults are:

- two columns, `source,target`: every edge uses weight `1.0`
- three numeric columns, `source,target,thickness`: the third column is
  used only when variable thickness is enabled
- if variable thickness is disabled, every edge uses weight `1.0`

## Meshing Methods

The converter supports two methods:

- `cylinders`: creates a cylinder for each edge and a sphere at each
  connected node, then merges the geometry with a 3D boolean union.
  This works for 2D and 3D networks.
- `planar`: creates 2D rectangles and discs, unions them with Shapely,
  then extrudes the result. This is only for flat 2D networks, but it is
  usually more robust for thin planar networks.

Node junctions are sized per node. Each junction sphere or disc uses the
thickest beam touching that node. Isolated nodes do not get junction
geometry.

## Multi-Material STL Output

STL does not reliably store material metadata inside a single file. The
supported multi-material workflow is to export one STL per material in
the same coordinate frame. Slicers can then import the files together and
assign each file to a different material or extruder.

Use the config-driven generator for multi-material output:

```bash
python config_to_stl.py sample_configs/multimaterial_test.json
```

That sample writes files like:

```text
test_multimaterial_rigid.stl
test_multimaterial_flexible.stl
test_multimaterial_conductive.stl
test_multimaterial_preview.html
```

### Config Format

Config paths are resolved relative to the JSON config file.

For adjacency matrices, keep the adjacency matrix numeric and add a
same-shape material matrix:

```json
{
  "output_dir": "../samples_output/material_demo",
  "default_material": "rigid",
  "geometry": {
    "beam_diameter_mm": 3.0,
    "cube_side_length_mm": 80,
    "variable_thickness": true,
    "node_material": "rigid",
    "node_material_priority": true,
    "node_radius_scale": 1.0,
    "boolean_union": true
  },
  "jobs": [
    {
      "name": "test_multimaterial",
      "positions": "demo_xy.csv",
      "adjacency": "demo_adj.csv",
      "adjacency_format": "auto",
      "material_matrix": "demo_material_matrix.csv"
    }
  ]
}
```

The material matrix must have the same shape as the adjacency matrix.
Cell `(i, j)` names the material for edge `(i, j)`. Empty, `0`, `none`,
`null`, or `nan` cells fall back to `default_material`.

For edge-list inputs, material can be carried directly in the edge file:

```csv
source,target,thickness,material
0,1,1.0,rigid
1,2,0.6,flexible
```

Set `"adjacency_format": "edge_list"` for that layout.

Edge-list column handling is intentionally permissive:

| Columns | Meaning |
| --- | --- |
| `source,target` | default thickness, `default_material` |
| `source,target,thickness` | thickness column plus `default_material`; thickness is used only when `geometry.variable_thickness` is `true` |
| `source,target,material` | default thickness plus per-edge material; use a header row so the third column is identified as material |
| `source,target,thickness,material` | per-edge thickness and per-edge material |

Headerless three-column edge lists are ambiguous. Numeric third columns
are treated as thickness when variable thickness is enabled. Text third
columns are treated as material. A header row is the clearest option for
teaching examples.

Node junctions are controlled by `geometry.node_material` and
`geometry.junction_policy`:

- If `geometry.node_material` is set, every node junction sphere is
  written to that material, regardless of the incident edge materials.
  By default those node spheres also reserve their physical volume:
  beam-material STLs are cut away at the node spheres so a slicer cannot
  overwrite the node material with beam material. Set
  `"node_material_priority": false` only if you intentionally want the
  older overlapping-material output.
- `geometry.node_radius_scale` controls the radius of generated junction
  spheres relative to the thickest incident beam radius. The default is
  `1.0`; values like `1.25` or `1.35` make the node material visibly
  protrude around beam junctions.
- `separate`: same-material nodes stay with that material; mixed nodes
  are written to `mixed_junction_material`.
- `dominant`: mixed nodes go to the material with the largest total
  incident edge weight.

If `geometry.node_material` is omitted, node junctions still have a
defined default behavior: nodes touching only one material are written
with that edge material, and mixed-material nodes follow
`junction_policy`. `junction_policy` can be `"separate"` or
`"dominant"`. For a single shared node material, set
`geometry.node_material` to an existing material name, such as the same
name as `default_material`. To use a separate node material, add that
material to the config first and then set `geometry.node_material` to its
name.

## Random Edge-List Material Demo

This demo is intended for teaching the full workflow from edge list and
node positions to multi-material STL files.

```bash
python examples/random_material_edge_list_demo.py
python config_to_stl.py sample_configs/random_edge_material_demo/edge_material_demo.json
```

The demo writes:

```text
sample_configs/random_edge_material_demo/edge_material_demo_xy.csv
sample_configs/random_edge_material_demo/edge_material_demo_edges.csv
sample_configs/random_edge_material_demo/edge_material_demo_node_materials.csv
sample_configs/random_edge_material_demo/edge_material_demo.json
```

The edge list has columns:

```csv
source,target,thickness,material
```

Each edge is randomly assigned to one of two edge materials. All nodes
are assigned to the same node material through `geometry.node_material`.

By default, the demo tries to use the neighboring `sr_huppi_project`
centerline-network generator if it is available at
`/home/james/sr_huppi_project`; otherwise it falls back to a small
self-contained synthetic network. To force one behavior:

```bash
python examples/random_material_edge_list_demo.py --source sr --sr-repo /path/to/sr_huppi_project
python examples/random_material_edge_list_demo.py --source synthetic
```

## Voronoi Random-Material Demo

The repository includes a deterministic Voronoi example with about 150
network nodes. Its edges are randomly split between two materials, and
all node junctions use one shared node material.

Generate or refresh the demo files with:

```bash
python examples/voronoi_random_material_demo.py
```

Generate the STL files with:

```bash
python config_to_stl.py sample_configs/voronoi_random_material_demo/voronoi_material_demo.json
```

The committed demo has 152 graph nodes and 226 edges. The edge material
split is recorded directly in:

```text
sample_configs/voronoi_random_material_demo/voronoi_material_demo_edges.csv
```

## Periodic HuPPI Network STL Demo

The HuPPI periodic demo uses the neighboring `HuPPI-Network-Analysis`
repository to generate one perturbed-lattice point pattern with disorder
strength `a = 0.5`, then builds four periodic networks clipped at the box
boundaries:

- Gabriel
- Delaunay
- Delaunay-centroidal
- Voronoi

Generate the full demo with:

```bash
python examples/huppi_periodic_network_stl_demo.py
```

The generated input/config files are contained in:

```text
sample_configs/huppi_periodic_a05_demo/
```

The STL and HTML preview outputs are written to:

```text
samples_output/huppi_periodic_a05_demo/
```

Each network folder contains three variants:

- `uniform_thickness.json`: two-column edge list, one default beam
  thickness, one material
- `variable_thickness.json`: random edge thickness weights from `0.5`
  to `2.0`; the base beam diameter is scaled so the mean beam diameter
  is about `3 mm`
- `two_materials.json`: random beam materials `beam_material_a` and
  `beam_material_b`, plus separate `node_material` junction STLs whose
  volume is subtracted from the beam STLs. These configs set
  `node_radius_scale` to `1.35` so the node material is visible in the
  HTML previews.

The committed demo inputs use a `12 x 12` underlying point pattern
(`144` points), seed `20260528`, an `80 mm` max coordinate span, and an
average beam diameter of about `3 mm`. The generated graph sizes are
listed in `sample_configs/huppi_periodic_a05_demo/manifest.json`.

## Static Config Builder

Open this file directly in a browser:

```text
material_config_builder.html
```

The builder creates and downloads JSON config files and shows the command
to run. A plain local HTML file cannot execute Python meshing code or
write STL files directly, so STL generation still happens through:

```bash
python config_to_stl.py material_config.json
```

## Cleaning Generated Files

Generated Python caches and older byproducts can be removed with:

```bash
./clean.sh
```

On Windows:

```bat
clean.bat
```

## Checks

Run the lightweight regression tests with:

```bash
python -m unittest discover
```
