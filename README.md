# STL_Generation

## Overview
STL_Generation is a tool developed to facilitate the transformation of 2D/ 3D point cloud data into 3D STL files. 

## Key Features
- **2D Point Cloud to 3D STL**: Seamlessly converts 2D point cloud files into 3D STL files, enabling the physical representation of abstract data. Users can adjust the width of the connection beams and the height of the 3D model, offering flexibility to meet specific modeling requirements.

- **3D Point Cloud to 3D STL**: Converts "3D positional and force data from LAMMPS simulations" or "adjacency and positional data from MATLAB .mat" files to generate STL files with customizable beam width.


## Getting Started

### Installation
To set up the STL_Generation tool for use, clone the repository and navigate to the project directory:

```bash
git clone https://github.com/DMREF-networks/STL_generation.git
cd STL_generation
pip3 install -r requirements.txt
```

### 2D Point Cloud to 3D STL
Add your Point Cloud CSV File name as follows in Line Number 18: <br>
```python
point_cloud = np.loadtxt(open("./<point_cloud_file_name>.csv", "rb"), delimiter=",")
```
Customize the height and width of of the model by modifying the following in Line Number 58: <br>
```python
beams.append(create_beam(start_point, end_point, width=<width_of_each_edge>, height=<height_of_the_edge_or_3D_model>))
```
Run the Python file using the command: <br>
```bash
python3 pointCloudToSTL.py
```

### 3D Point Cloud to 3D STL
For LAMMPS data, modify the following in Line Number 178 according to your needs: <br>
```python
process_data('lammps', position_file=position_file, force_file=force_file, beam_diameter=beam_diameter, output_file="lammps_to_stl.stl")
```
For MATLAB data, modify the following in Line Number 183 according to your needs: <br>
```python
process_data("mat", mat_file=mat_file, beam_diameter=beam_diameter, output_file="mat_to_stl.stl")
```
Run the Python file using the command: <br>
```bash
python3 3D_to_STL_file.py
```


