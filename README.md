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
1. Create a directory with the numpy files for each set of points you want to convert. Make sure to have both the adj files and xy numpy files for each set of points in the folder. Or alternatively, use the TestDataSet. If you would like to use the TestDataSet, this step can be skipped. 

2.  Run the script:

```bash
python3 npyToSTLScript.py
```
3. When prompted by the program, enter the path to the directory where you stored the npy or csv files (adj and xy). If you are using the npyTestDataSet or csvTestDataSet, enter in that in as the path.

4. You will then be prompted by the program to choose what file format your files are in. For now, the program only supports .csv and .npy. 

5. Next, you will also be prompted to enter the desired matrix height and desired beam diameter. 

6. The program will then generate the STL files, which will show up in the project directory. Additional folders/files will also be generated (pycache, csvFiles, output.txt). These folders/files are a result of intermediary steps to convert from npy to STL. Feel free to delete them if you don't have any use for them. 

## Directions To Run As A Function

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
1. Create a directory with the numpy files for each set of points you want to convert. Make sure to have both the adj files and xy numpy files for each set of points in the folder. Or alternatively, use one of the test data sets. If you would like to use one of the test data sets, this step can be skipped. 

2. Type 'python3' in the terminal to run python. The commands in steps 3 and 4 should be run by python. 

3. Import npy_to_stl or csv_to_stl in the terminal (depending on your purposes): 

```bash
from npy_to_stl import *
```
or
```bash
from csv_to_stl import *
```

4. Call the fuction npy_to_stl(src_directory, beam_diameter, sample_height) or csv_to_stl(src_directory, beam_diameter, sample_height). If you are choosing to use one of the test data sets, simply type "csvTestDataSet" or "npyTestDataSet" in place of the the directory parameter. 

```bash
npy_to_stl("npyTestDataSet", 1.76, 80)

# This command would generate a sample 80 mm tall with beams that have a diameter of 1.76 mm. 
```
or
```bash
csv_to_stl("csvTestDataSet", 1.76, 80)

# This command would generate a sample 80 mm tall with beams that have a diameter of 1.76 mm. 
```

4. The program will then generate the STL files, which will show up in the project directory. Additional folders/files will also be generated (pycache, csvFiles, output.txt). These folders/files are a result of intermediary steps to convert from npy to STL. Feel free to delete them if you don't have any use for them.  

**Note about running the program as a function:** However you choose to run one of the functions (in a for loop, etc), make sure you do step 3 first.
