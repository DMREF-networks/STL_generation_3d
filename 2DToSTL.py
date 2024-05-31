# --------------------------------------------------------------------------------
# Author: Harikrishnan Venkatesh
# Year: 2024
# Description: Code that generates a 3D STL file with a configurable width and height option from a 2D Point Cloud file
# --------------------------------------------------------------------------------

import numpy as np
from libpysal.weights import Voronoi
import shapely.geometry as sh
import trimesh
from trimesh.creation import box
import warnings
import os
from scipy.spatial import Delaunay
import networkx as nx


"""
2DToSTL.py 

This script transforms a "2D point cloud into a 3D model" where each connection (or edge) is represented as a beam. 
This script is particularly useful for visualizing networks or structures from point data. 
The use of Voronoi tessellation and the conversion to a network graph depicts the aim to simulate connections 
like those in a Delaunay triangulation for 3D modeling.
Adjustments might be necessary for the beam dimensions and the clipping bounds depending on the scale and distribution of the point data.

This script automates the process of creating a 3D printable or viewable STL file from 2D data, 
allowing for easy visualization of complex structures or networks derived from basic point data. 
The script can be adapted to handle different data sources or formats by modifying how the point cloud is loaded or how beams are generated.

Requirements:
- numpy
- libpysal.weights.Voronoi: To generate a Voronoi diagram from the point cloud.
- shapely.geometry and trimesh: For geometric operations and 3D mesh handling.
"""

# Ignore future warnings
warnings.filterwarnings("ignore", category=FutureWarning)

def create_beam(start_point, end_point, width=0.05, height=1.0):
    """Function to create a 3D beam between two points"""
    direction_2d = end_point - start_point
    length = np.linalg.norm(direction_2d)
    direction_2d = direction_2d / length  # Normalize

    # Extend the 2D direction vector to 3D by adding a zero Z component
    direction = np.append(direction_2d, 0)

    # Create a box with the desired dimensions
    beam = box(extents=[width, length, height])

    # Align the beam with the start-end direction
    # Calculate rotation between beam's current direction (y-axis) and desired direction
    current_direction_y_vector = [0, 1, 0]  # Beam's length is along y-axis
    rotation_axis = np.cross(current_direction_y_vector, direction)
    rotation_angle = np.arccos(np.dot(current_direction_y_vector, direction))
    beam.apply_transform(trimesh.transformations.rotation_matrix(rotation_angle, rotation_axis, point=(0, 0, 0)))

    # Adjust the beam's position
    midpoint = (start_point + end_point) / 2
    midpoint_3d = np.append(midpoint, height / 2)  # Adjust Z to place the beam correctly
    beam.apply_translation(midpoint_3d - beam.center_mass)

    return beam


def write_stl(graph,point_cloud):
    """Create beams for each edge in the graph"""
    beams = []
    for edge in graph.edges():
        start_index, end_index = edge
        # print(point_cloud[start_idx], point_cloud[end_idx])
        # Access coordinates directly from the point_cloud array
        start_point = point_cloud[start_index]
        end_point = point_cloud[end_index]
        beam = create_beam(start_point, end_point, width=30, height=30)
        beams.append(beam)  # Adjust width and height as needed, it should be proportional to the spread of the points.

    # Combine all beams into a single mesh
    mesh = trimesh.util.concatenate(beams)
    mesh.process(validate=True)
    mesh.fill_holes()
    print("Is watertight:", mesh.is_watertight)

    # Export the mesh to an STL file for 3D printing
    mesh.export('network_3d_model.stl')

# csv_file_path = "./net101.csv"
# Get clarification on num_points,area

def find_csv_files(directory='.'):
    """Find CSV files in the specified directory"""
    csv_files = [filename for filename in os.listdir(directory) if filename.endswith('.csv')]
    return csv_files

def create_graph_from_point_cloud(point_cloud):
    """Generate a graph from point cloud using Delaunay triangulation"""
    delaunay = Delaunay(point_cloud)
    graph = nx.Graph()
    for triangle in delaunay.simplices:
        for i in range(len(triangle)):
            for j in range(i + 1, len(triangle)):
                graph.add_edge(triangle[i], triangle[j])
    return graph

def main():
    csv_files = find_csv_files()

    if not csv_files:
        print("No CSV files found. Generating random point cloud.")
        # generate_csv()
        # Generating random point cloud if CSV does not exist
        num_points = 100
        point_cloud = np.random.rand(num_points, 2) * 1000  # points within a 1000x1000 area
        graph = create_graph_from_point_cloud(point_cloud)
        # Create Delaunay triangulation from the points
        # delaunay = Delaunay(point_cloud)
        # # print("\nIndices of points forming the Delaunay triangles (simplices):")
        # # print(delaunay.simplices)
        # # Convert Delaunay edges into a NetworkX graph for beam creation
        # graph = nx.Graph()
        # for triangle in delaunay.simplices:
        #     for i in range(len(triangle)):
        #         for j in range(i + 1, len(triangle)):
        #             graph.add_edge(triangle[i], triangle[j])
        # print(graph)
        write_stl(graph, point_cloud)
    else :   
        print("Found CSV files:", csv_files)
        csv_file_path = csv_files[0]  # Use the first found CSV file
        # Load the point cloud data
        point_cloud = np.loadtxt(open(csv_file_path, "rb"), delimiter=",")
        # Generate Voronoi diagram (simulating Delaunay-like edges for the purpose of 3D modeling)
        voronoi = Voronoi(point_cloud, criterion='rook', clip=sh.box(0, 0, 2000, 2000))
        graph = voronoi.to_networkx()
        write_stl(graph,point_cloud)

if __name__ == "__main__":
    main()
