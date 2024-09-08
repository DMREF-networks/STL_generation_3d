# STL_Generation

## Overview
STL_Generation is a tool developed to facilitate the transformation of 2D/ 3D point cloud data into 3D STL files. 

## Key Features
- **2D Point Cloud to 3D STL**: Seamlessly converts 2D point cloud files into 3D STL files, enabling the physical representation of abstract data. Users can adjust the width of the connection beams and the height of the 3D model, offering flexibility to meet specific modeling requirements.

- **3D Point Cloud to 3D STL**: Converts "3D positional and force data from LAMMPS simulations" or "adjacency and positional data from MATLAB .mat" files to generate STL files with customizable beam width.


## Getting Started

### Installation
**To get started,** clone the repository and navigate to the project directory:

```bash
git clone https://github.com/DMREF-networks/STL_generation.git
cd STL_generation
```
**Next, install the required dependencies:**
```bash
pip3 install -r requirements.txt
```

### 2D Point Cloud to 3D STL
**Required Steps:**
1. Create a directory with the .adj and .xy files for each set of points you want to convert
```
2.  Run the script: <br>
```bash
python3 numpyToSTL.py
```
3. When prompted by the program, enter the path to the directory where you stored the files. The program will
then also prompt you to enter your desired output directory (where you want the STL files stored).