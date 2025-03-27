from csv_to_stl import *

import numpy as np
import trimesh
from trimesh.creation import cylinder, icosphere
import math
from scipy.io import loadmat
from matplotlib import pyplot as plt

import os 

def convert_npy_to_csv(src_directory, dst_directory):
    
    """
    Convert all numpy arrays in the source directory to CSV files in the destination directory.

    Parameters:
    src_directory (str): The source directory containing numpy arrays.
    dst_directory (str): The destination directory to save CSV files.
    """
    import sys
    original_stdout = sys.stdout
    with open('output.txt', 'w') as f:
        sys.stdout = f

        for root, _, files in os.walk(src_directory):
            relative_path = os.path.relpath(root, src_directory)
            dst_subdir = os.path.join(dst_directory, "")
            os.makedirs(dst_subdir, exist_ok=True)

            for file in files:
                if file.endswith('.npy'):
                    npy_path = os.path.join(root, file)

                    if 'adj' in file:
                        # Convert edge list to CSV and adjacency matrix
                        edges = np.load(npy_path)
                        '''
                        csv_path = os.path.join(dst_subdir, file[:-4] + '.csv')
                        np.savetxt(csv_path, edges, delimiter=',')
                        print(f"Converted {npy_path} to {csv_path}")
                        '''
                        adjacency_matrix = edges_to_adjacency_matrix(edges)
                        adj_matrix_csv_path = os.path.join(dst_subdir, file[:-4] + '.csv')
                        np.savetxt(adj_matrix_csv_path, adjacency_matrix, delimiter=',')
                        # print(f"Converted {npy_path} to {adj_matrix_csv_path}")
                        print(adj_matrix_csv_path)

                    elif 'xy' in file:
                        # Convert positions to CSV
                        csv_path = os.path.join(dst_subdir, file[:-4] + '.csv')
                        array = np.load(npy_path)
                        np.savetxt(csv_path, array, delimiter=',')
                        # print(f"Converted {npy_path} to {csv_path}")
                        print(csv_path)

def edges_to_adjacency_matrix(edges):
    """
    Convert a list of edges with lengths to an adjacency matrix.

    Parameters:
    edges (list of tuples): List of tuples (node1, node2, length) representing the edges and their lengths.

    Returns:
    numpy.ndarray: An adjacency matrix.
    """
    # Determine the number of nodes from the edges
    num_nodes = int(max(max(edge[0], edge[1]) for edge in edges) + 1)
    # num_nodes = int(np.max(edges[:, :2])) + 1

    # Initialize the adjacency matrix with zeros
    adjacency_matrix = np.zeros((num_nodes, num_nodes))

    # Iterate over the edges and populate the adjacency matrix
    for edge in edges:
        node1 = int(edge[0])
        node2 = int(edge[1])
        # edge_length = edge[2]
        adjacency_matrix[node1, node2] = 1
        adjacency_matrix[node2, node1] = 1 

    return adjacency_matrix

def npy_to_stl(inputPath, beam_diameter_in_mm, cube_side_length):
    currentPath = str(os.getcwd())
    outputPath = currentPath + "/csvFiles"
    convert_npy_to_csv(inputPath, outputPath)

    csv_to_stl(outputPath, beam_diameter_in_mm, cube_side_length)