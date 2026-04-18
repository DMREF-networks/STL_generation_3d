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

Make sure none of the files have the same name, or some files might get overwritten. Furthermore, anything after the adj or xy will be cut off. The sample files in the delaunay, delaunay_centroidal, gabriel, voronoi, and gabriel folders all work with this format, but as you can see, the kick factor (or a factor) is after the adj/xy so it doesn't get included in the STL name. This is something that currently needs to be fixed. 

5. Next, you will also be prompted to enter the desired matrix height and desired beam diameter. 

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

By default the adjacency matrix is treated as binary: every non-zero
entry produces a beam of the diameter you entered at the prompt.

To make the thickness vary per beam, encode a weight in the adjacency
matrix (or, for the npy path, in a 3rd column of the edge list). The
beam diameter for edge (i, j) is then

    diameter_ij = beam_diameter * adjacency_matrix[i, j]

So a binary matrix (entries = 1) reproduces the original uniform
behaviour, and non-binary weights scale each beam independently. Choose
your weight units so `beam_diameter * weight` lands in millimetres —
e.g. set the prompt to 1.0 and store the raw diameter in the matrix, or
set the prompt to a reference diameter and store unit-less scale
factors. Junction spheres automatically grow to cover the thickest
incident beam at each node.

For the npy edge-list path, save `adj` files as an `(E, 3)` array where
the 3rd column is the weight. `(E, 2)` arrays keep working unchanged
(weight = 1).

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

Both methods respect the same adjacency-matrix / edge-list convention
for variable thickness.
