# STL_Generation

## Overview
STL_Generation is a tool developed to facilitate the transformation of 3D point cloud data (in either .npy or .csv format) into 3D STL files. 

## Purpose
- Converts point cloud files into 3D STL files, enabling the physical representation of abstract data. Users can adjust the width of the connection beams and the height of the 3D model, offering flexibility to meet specific modeling requirements.

## Directions

**To get started,** clone the repository and navigate to the project directory:

```bash
git clone https://github.com/DMREF-networks/STL_generation.git
cd STL_generation
```

**Next, install the required dependencies:**
```bash
pip3 install -r requirements.txt
```

**To run the conversion:**
1. Create a directory with the numpy files for each set of points you want to convert. Make sure to have both the adj files and xy numpy files for each set of points in the folder. Alternatively, you can use the provided test samples for any of the 4 available configuration types (delaunay, delaunay_centroidal, gabriel, or voronoi).

2.  Run the script:

```bash
python3 npyToSTLScript.py
```

3. You will then be prompted by the program to choose what file format your files are in. For now, the program only supports .csv and .npy. 

4. When prompted by the program, enter the path to the directory where you stored the npy or csv files (adj and xy). 

IMPORTANT NOTE: If the folder contains the point clouds and adjacency matrices for more than one STL file, make sure they are all either csv OR npy. The code currently does not support a mix. Furthermore, the matching between the xy and adj files relies on the fact that the files are in the following format: 

name_adj.csv, name_xy.csv OR name_adj.npy, name_xy.npy

Files may include matching suffixes after `_adj` and `_xy` (for example,
`network_adj_0.1.npy` and `network_xy_0.1.npy`). Those suffixes are
preserved in the STL and HTML output names.

5. Next, you will be prompted for the desired matrix side length, desired
beam diameter, whether to use variable beam thickness, and the meshing
method.

6. The program will then generate the STL files, which will show up in the project directory. Additional folders/files will also be generated (pycache, csvFiles, output.txt). These folders/files are a result of intermediary steps to convert from npy to STL. To delete these files, run the following commands:

For MacOS/Linux:

```bash
chmod +x clean.sh

./clean.sh

```

For Windows:

```bash
.\clean.bat
```

## Variable beam thickness

By default, adjacency values are treated as binary connectivity: every
non-zero entry produces a beam of the diameter you entered at the prompt.
This is true even when a NumPy `adj` file is an `(E, 3)` edge list. The
3rd column is ignored unless variable beam thickness is explicitly
enabled.

To make the thickness vary per beam, answer `y` to the variable-thickness
prompt (or pass `variable_thickness=True` when calling the Python
functions), then encode a weight in the adjacency matrix or, for the npy
path, in a 3rd column of the edge list. The beam diameter for edge (i, j)
is then

    diameter_ij = beam_diameter * adjacency_matrix[i, j]

So a binary matrix (entries = 1) reproduces the original uniform
behaviour, and non-binary weights scale each beam independently. Choose
your weight units so `beam_diameter * weight` lands in millimetres —
e.g. set the prompt to 1.0 and store the raw diameter in the matrix, or
set the prompt to a reference diameter and store unit-less scale
factors.

### Junction sphere sizing

Each junction sphere is sized **per-node** to that node's thickest
incident beam — *not* a single system-wide value. So a node where only
thin beams meet gets a thin sphere (no oversized bulge), while a node
with a thick beam attached gets a sphere large enough to fill the
junction cavity. Endpoint nodes get a sphere matching their single
incident beam; isolated nodes get no sphere at all. The same per-node
rule is used by the planar method for its merge-time discs.

For the npy edge-list path, save `adj` files as an `(E, 3)` array where
the 3rd column is the weight, then enable variable thickness. `(E, 2)`
arrays keep working unchanged (weight = 1).

## 2D networks

If your `xy` file has only two columns, the beams will be laid flat on
the z = 0 plane. No flag needed — the code promotes `(N, 2)` positions
to `(N, 3)` with `z = 0` automatically.

## HTML viewer

Every STL is accompanied by an interactive `.html` file of the same
basename. Open it in any browser for a 3D preview of the network, with
beams coloured by diameter. Requires `plotly` (already listed in
`requirements.txt`).

## Methods: cylinders vs. planar

The script prompts for a method:

- **`cylinders`** (default): original approach — each beam is a 3D
  cylinder, junctions are spheres. Works for any network (2D or 3D).
- **`planar`**: each beam is a 2D rectangle and each node is a 2D disc;
  shapely unions them in the plane, and the merged polygon is extruded
  to a single uniform-thickness slab. Only valid for **flat / 2D**
  networks, but it's dramatically more robust for thin beams, avoids
  the junction-gap problem entirely, and produces a much smaller mesh
  (shapely's planar boolean is far more reliable than trimesh's 3D
  boolean union). Requires `shapely` and prompts for an extrusion depth
  in millimetres (default = the beam diameter you entered).

Both methods use constant beam thickness by default and respect
adjacency-matrix / edge-list thickness weights only when variable
thickness is enabled.
