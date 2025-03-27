# STL_Generation

## Overview
STL_Generation is a tool developed to facilitate the transformation of 2D/3D point cloud data (in either .npy or .csv format) into 3D STL files. 

## Purpose
- Converts 2D point cloud files into 3D STL files, enabling the physical representation of abstract data. Users can adjust the width of the connection beams and the height of the 3D model, offering flexibility to meet specific modeling requirements.

## Directions To Run As A Script

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

5. Next, you will also be prompted to enter the desired matrix height and desired beam diameter. 

6. The program will then generate the STL files, which will show up in the project directory. Additional folders/files will also be generated (pycache, csvFiles, output.txt). These folders/files are a result of intermediary steps to convert from npy to STL. To delete these files, run the following commands:

```bash
chmod +x clean.sh

./clean.sh

```
