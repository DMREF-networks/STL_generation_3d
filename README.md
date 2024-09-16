# STL_Generation

## Overview
STL_Generation is a tool developed to facilitate the transformation of 2D/ 3D point cloud data into 3D STL files. 

## Purpose
- **2D Point Cloud to 3D STL**: Seamlessly converts 2D point cloud files into 3D STL files, enabling the physical representation of abstract data. Users can adjust the width of the connection beams and the height of the 3D model, offering flexibility to meet specific modeling requirements.

## Directions
**To get started,** clone the repository, navigate to the project directory and then checkout a branch:

```bash
git clone https://github.com/DMREF-networks/STL_generation.git
cd STL_generation
git checkout numpy_to_stl_conversion
```
If the checkout command doesn't work, type in the following: 

```bash
git branch -a
```
This will show you the actual names of the branches (they might be remote). Use the git checkout command and
type in the full name of the numpy_to_stl_conversion branch. 

**Next, install the required dependencies:**
```bash
pip3 install -r requirements.txt
```

**To run the conversion:**
1. Create a directory with the numpy files for each set of points you want to convert. Make sure to have both the adj files and xy numpy files for each set of points in the folder. 

2.  Run the script:

```bash
python3 numpyToSTL.py
```
3. When prompted by the program, enter the path to the directory where you stored the files. The program will
then also prompt you to enter your desired output directory (where you want the STL files stored).