# STL Generation 3D

STL Generation 3D converts network data into 3D-printable STL meshes.
Inputs are node positions plus connectivity data, either as CSV files or
NumPy `.npy` files. Outputs are STL files and optional HTML previews.

## Setup

Clone the repository and install the Python dependencies:

```bash
git clone https://github.com/DMREF-networks/STL_generation_3d.git
cd STL_generation_3d
python -m pip install -r requirements.txt
```

The project uses `trimesh`, `manifold3d`, `shapely`, `numpy`, `scipy`,
`matplotlib`, and `plotly`.

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
- an edge list, usually `(source, target)` or `(source, target, weight)`

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

## Beam Thickness

By default, adjacency values are treated as binary connectivity. Every
nonzero edge uses the beam diameter entered at the prompt.

If variable thickness is enabled, adjacency values become scale factors:

```text
edge_diameter = beam_diameter * adjacency_value
```

For `.npy` edge-list inputs, the third column is used as the thickness
weight only when variable thickness is enabled. Otherwise every edge
uses weight `1.0`.

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
test_multimaterial_junctions.stl
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
    "beam_diameter_mm": 0.25,
    "cube_side_length_mm": 30,
    "variable_thickness": true,
    "junction_policy": "separate",
    "mixed_junction_material": "junctions",
    "boolean_union": true
  },
  "jobs": [
    {
      "name": "test_multimaterial",
      "positions": "demo_xy.csv",
      "adjacency": "demo_adj.csv",
      "adjacency_format": "matrix",
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

Mixed-material junctions are controlled by `geometry.junction_policy`:

- `separate`: same-material nodes stay with that material; mixed nodes
  are written to `mixed_junction_material`.
- `dominant`: mixed nodes go to the material with the largest total
  incident edge weight.
- `per_material`: mixed nodes are duplicated into each incident material
  STL. This can create overlapping geometry.

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
