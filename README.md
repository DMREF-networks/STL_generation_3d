# STL_Generation

## Overview
STL_Generation is a tool developed to facilitate the transformation of 2D point cloud data into 3D STL files. This project introduces the capability to not only convert 2D point clouds into 3D models but also to customize the dimensions of the connection beams and the overall height of the 3D model. This enhancement broadens the applicability of 3D modeling from raw data, catering to a wide range of scientific, engineering, and creative projects.

## Key Features
- **2D Point Cloud to 3D Conversion**: Seamlessly converts 2D point cloud files into 3D STL files, enabling the physical representation of abstract data.
- **Customizable Beam Width and Model Height**: Users can adjust the width of the connection beams and the height of the 3D model, offering flexibility to meet specific modeling requirements.

## Getting Started

### Installation
To set up the STL_Generation tool for use, clone the repository and navigate to the project directory:

```bash
git clone https://github.com/DMREF-networks/STL_generation.git
cd STL_generation
pip3 install -r requirements.txt
python3 pointCloudToSTL.py
```
Add your Point Cloud CSV File name as follows in Line Number 18: <br>
```python
point_cloud = np.loadtxt(open("./<point_cloud_file_name>.csv", "rb"), delimiter=",")
```
Customize the height and width of of the model by modifying the following in Line Number 58: <br>
```python
beams.append(create_beam(start_point, end_point, width=<width_of_each_edge>, height=<height_of_the_edge_or_3D_model>))
```
