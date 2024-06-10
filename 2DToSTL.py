# --------------------------------------------------------------------------------
# Author: Harikrishnan Venkatesh
# Year: 2024
# Description: Code that generates a 3D STL file with a configurable width and height option from a 2D Point Cloud file
# --------------------------------------------------------------------------------

import numpy as np
from libpysal.weights import Voronoi # type: ignore
import shapely.geometry as sh # type: ignore
import trimesh # type: ignore
from trimesh.creation import box # type: ignore
import warnings
import os
from scipy.spatial import Delaunay
import networkx as nx # type: ignore
import pandas as pd


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


# csv_file_path = "./net101.csv"
# Get clarification on num_points,area

def find_csv_files():
    """Find CSV files in the specified directory"""
    print("Inside find_csv_files function")
    csv_files = [filename for filename in os.listdir(os.getcwd()) if filename.endswith('.csv')]
    return csv_files

def load_csv_file(csv_file) :
    """Loads the CSV file to dataframe and later converts to numpy array"""
    print("Inside Load CSV file")
    df = pd.read_csv(csv_file,header=None)
    # Converting dataframe to numpy array
    csv_file_arr = df.values
    return csv_file_arr

def create_adjacency_matrix(point_cloud):
    """Create adjacency matrix from Delaunay triangulation of given points."""
    # # Compute Delaunay triangulation
    # delaunay = Delaunay(point_cloud)

    # # Number of points
    n_points = point_cloud.shape[0]
    # print(n_points)

    # Initialize adjacency matrix with zeros
    adjacency_matrix = np.zeros((n_points, n_points), dtype=int)
    # print(delaunay.simplices)
    # # Iterate over each Delaunay triangle
    # for simplex in delaunay.simplices:
    #     # Each simplex is a triangle with vertices indexed by points
    #     for i in range(len(simplex)):
    #         for j in range(i + 1, len(simplex)):
    #             adjacency_matrix[simplex[i], simplex[j]] = 1
    #             adjacency_matrix[simplex[j], simplex[i]] = 1  # Since it's an undirected graph
    # # print(type(adjacency_matrix))
    # return adjacency_matrix
    voronoi = Voronoi(point_cloud, criterion='rook', clip=sh.box(0, 0, 2000, 2000))
    # voronoi.neighbours will have information on what all nodes is a paticular node connected to.
    # ex: {0: [184, 194], 1: [96, 60, 15, 151], ...}
    # print(voronoi.neighbors.items())
    for node, connected_nodes in voronoi.neighbors.items():
        for neighbor in connected_nodes:
            adjacency_matrix[node, neighbor] = 1
            adjacency_matrix[neighbor, node] = 1  # Since it's an undirected graph
    return adjacency_matrix

def write_matrix_to_file(matrix, file_path):
    """Writes the adjacency matrix to a CSV file and saves the file in current working directory"""
    # print(file_path)
    with open(file_path, 'w') as file:
        for row in matrix:
            file.write(','.join(map(str, row)) + '\n')

def create_graph_from_adjacency_matrix(adjacency_matrix):
    """Generate a graph from adjacency matrix using Delaunay triangulation"""
    graph = nx.Graph()
    # Number of nodes is equal to the number of rows in the adjacency matrix
    n = adjacency_matrix.shape[0]
    # Add edges based on the adjacency matrix
    for i in range(n):
        for j in range(i+1, n):  # Start from i+1 to avoid duplicate edges (assuming to be undirected graph)
            if adjacency_matrix[i, j] != 0:
                graph.add_edge(i, j)
    return graph


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
    rotation_angle = np.arccos(np.clip(np.dot(current_direction_y_vector, direction),-1.0,1.0))
    beam.apply_transform(trimesh.transformations.rotation_matrix(rotation_angle, rotation_axis, point=(0, 0, 0)))

    # Adjust the beam's position
    midpoint = (start_point + end_point) / 2
    midpoint_3d = np.append(midpoint, height / 2)  # Adjust Z to place the beam correctly
    beam.apply_translation(midpoint_3d - beam.center_mass)

    return beam

def write_stl(graph,point_cloud,output_filename):
    """Create beams for each edge in the graph"""
    beams = []
    # print(graph.edges())
    # print(point_cloud)
    for edge in graph.edges():
        start_index, end_index = edge
        # print(point_cloud[start_idx], point_cloud[end_idx])
        # Access coordinates directly from the point_cloud array
        # print("end_index :", end_index)
        start_point = point_cloud[start_index]
        end_point = point_cloud[end_index]
        beam = create_beam(start_point, end_point, width=30, height=30)
        beams.append(beam)  # Adjust width and height as needed, it should be proportional to the spread of the points.

    # Combine all beams into a single mesh
    mesh = trimesh.util.concatenate(beams)
    boundary_edges = mesh.edges_boundary
    print(boundary_edges)
    # mesh = mesh.convex_hull
    mesh.process(validate=True)
    mesh.fill_holes()
    print("Is watertight:", mesh.is_watertight)

    # Export the mesh to an STL file for 3D printing
    mesh.export(f"{output_filename}_1.stl")

    # Tried to fetch the points from adjacency matrix but felt fetching from graphs is easier 
    # beams = []
    # start_index=0
    # for i in range(start_index, len(adjacency_matrix)):
    #     for j in range(i + 1, len(adjacency_matrix[i])):
    #         if adjacency_matrix[i, j] > 0:
    #             print('point_cloud[i] ', point_cloud[i] )
    #             start_point = point_cloud[i]
    #             end_point = point_cloud[j]
    #             beam = create_beam(start_point, end_point,width=30, height=30)
    #             beams.append(beam)

    # # Normal Beam Concatenation
    # mesh = trimesh.util.concatenate(beams)
    # mesh.process(validate=True)
    # mesh.fill_holes()
    # # print(combined_mesh)
    # mesh.export('network_3d_model.stl')


def main():
    csv_files = find_csv_files()
    if len(csv_files) == 1 :
        print("Should Create CSV file")
        point_cloud = csv_files[0]
        filename = csv_files[0].split('.')
        # print(filename)
        point_cloud_arr = load_csv_file(point_cloud)
        # print(type(point_cloud_arr))
        adjacency_matrix = create_adjacency_matrix(point_cloud_arr)
        write_matrix_to_file(adjacency_matrix,f"{filename[0]}_adjacency_matrix.csv")
        graph = create_graph_from_adjacency_matrix (adjacency_matrix)
        write_stl(graph,point_cloud_arr,f"{filename[0]}_3d_model_output")

        # Hari's Code
        # print(len(graph))
        # point_cloud = np.loadtxt(open("./net100.csv", "rb"), delimiter=",")
        # voronoi = Voronoi(point_cloud_arr, criterion='rook', clip=sh.box(0, 0, 2000, 2000))
        # # voronoi.neighbours will have information on what all nodes is a paticular node connected to.
        # # ex: {0: [184, 194], 1: [96, 60, 15, 151], ...}
        # # print(voronoi.neighbors.items())
        # graph = voronoi.to_networkx()
        # write_stl(graph,point_cloud_arr)
    
    elif len(csv_files) == 2 :
        print("CSV file exists")
        # print(csv_files)
        temp = load_csv_file(csv_files[0])
        # Checking if number of rows = number of columns (This would be the case for adjacency matrix)
        if len(temp[0]) == len(temp) :
            adjacency_matrix_arr = temp
            point_cloud = csv_files[1]
            filename = csv_files[1].split('.')
            point_cloud_arr = load_csv_file(point_cloud)
        else :
            point_cloud_arr = temp
            filename = csv_files[0].split('.')
            adjacency_matrix = csv_files[1]
            adjacency_matrix_arr = load_csv_file(adjacency_matrix)       
        # print(adjacency_matrix_arr)
        graph = create_graph_from_adjacency_matrix (adjacency_matrix_arr)
        write_stl(graph,point_cloud_arr,f"{filename[0]}_3d_model_output")
    else:
        print("Please give 2 files")






















#     # if adjacency matrix is not given and point_cloud is providded create adjaceny matrix from the point_cloud
#     csv_files = find_csv_files()
#     # csv_files = "./net100.csv"
#     if not csv_files:
#         print("No CSV files found. Generating random point cloud.")
#         # generate_csv()
#         # Generating random point cloud if CSV does not exist
#         num_points = 100
#         point_cloud = np.random.rand(num_points, 2) * 1000  # points within a 1000x1000 area
#         graph = create_graph_from_point_cloud(point_cloud)
#         # # Create Delaunay triangulation from the points
#         # delaunay = Delaunay(point_cloud)
#         # # print("\nIndices of points forming the Delaunay triangles (simplices):")
#         # # print(delaunay.simplices)
#         # # Convert Delaunay edges into a NetworkX graph for beam creation
#         # graph = nx.Graph()
#         # for triangle in delaunay.simplices:
#         #     for i in range(len(triangle)):
#         #         for j in range(i + 1, len(triangle)):
#         #             graph.add_edge(triangle[i], triangle[j])
#         # print(graph)
#         write_stl(graph, point_cloud)
#     else :   
#         print("Found CSV files:", csv_files)

#         # csv_file_path = csv_files[0]  # Use the first found CSV file
#         # Load the point cloud data
#         # point_cloud = np.loadtxt(open(csv_file_path, "rb"), delimiter=",")
#         point_cloud = np.loadtxt(csv_files, delimiter=",")
#         # Generate Voronoi diagram (simulating Delaunay-like edges for the purpose of 3D modeling)
#         voronoi = Voronoi(point_cloud, criterion='rook', clip=sh.box(0, 0, 2000, 2000))
#         graph = voronoi.to_networkx()
#         write_stl(graph,point_cloud)

if __name__ == "__main__":
    main()