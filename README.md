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
