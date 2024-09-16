# STL_Generation

## Overview
STL_Generation is a tool developed to facilitate the transformation of 2D/ 3D point cloud data into 3D STL files. 

## Purpose
- **2D Point Cloud to 3D STL**: Seamlessly converts 2D point cloud files into 3D STL files, enabling the physical representation of abstract data. Users can adjust the width of the connection beams and the height of the 3D model, offering flexibility to meet specific modeling requirements.

## Directions To Run As A Script

Running this program as a script will use a default value for beam diameter. If you would like to adjust beam 
diameter, please run the program as a function. 

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
1. Create a directory with the numpy files for each set of points you want to convert. Make sure to have both the adj files and xy numpy files for each set of points in the folder. Or alternatively, use the TestDataSet. If you would like to use the TestDataSet, this step can be skipped. 

2.  Run the script:

```bash
python3 numpyToSTL.py
```
3. When prompted by the program, enter the path to the directory where you stored the npy files (adj and xy). If you are using the TestDataSet, enter in that in as the path. 

4. The program will then generate the STL files, which will show up in the project directory. Additional folders/files will also be generated (pycache, csvFiles, output.txt). These folders/files are a result of intermediary steps to convert from npy to STL. Feel free to delete them if you don't have any use for them. 

## Directions To Run As A Function
**To get started,** clone the repository and navigate to the project directory:

```bash
git clone https://github.com/DMREF-networks/STL_generation.git
cd STL_generation
```
1. Create a directory with the numpy files for each set of points you want to convert. Make sure to have both the adj files and xy numpy files for each set of points in the folder. Or alternatively, use the TestDataSet. If you would like to use the TestDataSet, this step can be skipped. 

2. Import npy_to_stl in the terminal: 

```bash
from npy_to_stl import *
```

3. Call the fuction npy_to_stl(directory_with_npy_files, beam_width). If you are choosing to use the TestDataSet, simply type "TestDataSet" in place of the the directory parameter. The default value for beam width in the script is 0.04, so if you are unsure of what beam width to use, this default value can be used. 

```bash
npy_to_stl("TestDataSet", 0.04)
```

4. The program will then generate the STL files, which will show up in the project directory. Additional folders/files will also be generated (pycache, csvFiles, output.txt). These folders/files are a result of intermediary steps to convert from npy to STL. Feel free to delete them if you don't have any use for them.  