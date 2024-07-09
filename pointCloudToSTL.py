import numpy as np
from libpysal.weights import Voronoi
import shapely.geometry as sh
import trimesh
from trimesh.creation import box
import warnings
import networkx as nx
import argparse
import os

# Ignore future warnings
warnings.filterwarnings("ignore", category=FutureWarning)

def create_beam(start, end, width=0.05, height=1.0):
    direction_2d = end - start
    length = np.linalg.norm(direction_2d)
    direction_2d = direction_2d / length  # Normalize

    # Extend the 2D direction vector to 3D by adding a zero Z component
    direction = np.append(direction_2d, 0)

    # Create a box with the desired dimensions
    beam = box(extents=[width, length, height])

    # Align the beam with the start-end direction
    # Calculate rotation between beam's current direction (y-axis) and desired direction
    current_direction = [0, 1, 0]  # Beam's length is along y-axis
    rotation_axis = np.cross(current_direction, direction)
    rotation_angle = np.arccos(np.dot(current_direction, direction))
    beam.apply_transform(trimesh.transformations.rotation_matrix(rotation_angle, rotation_axis, point=(0, 0, 0)))

    # Adjust the beam's position
    midpoint = (start + end) / 2
    midpoint_3d = np.append(midpoint, height / 2)  # Adjust Z to place the beam correctly
    beam.apply_translation(midpoint_3d - beam.center_mass)

    return beam

def main(adjacency_file, point_cloud_file, output_file, beam_width, beam_height):
    # Load the point cloud data from CSV into a NumPy array
    point_cloud = np.loadtxt(point_cloud_file, delimiter=',')

    xmin = np.min(point_cloud[:, 1])
    xmax = np.max(point_cloud[:, 1])

    scale = 2000 / (xmax - xmin) 

    point_cloud = point_cloud * scale

    # Load adjacency matrix from CSV
    adj_matrix = np.loadtxt(adjacency_file, delimiter=',').astype(np.int64)

    # Create a graph from the adjacency matrix
    graph = nx.from_numpy_array(adj_matrix)

    # Create beams for each edge in the graph
    beams = []
    for edge in graph.edges():
        start_idx, end_idx = edge
        # Access coordinates directly from the point_cloud array
        start_point = point_cloud[int(start_idx)]
        end_point = point_cloud[int(end_idx)]
        beams.append(create_beam(start_point, end_point, width=beam_width, height=beam_height))

    # Combine all beams into a single mesh
    mesh = trimesh.util.concatenate(beams)
    mesh.process(validate=True)
    mesh.fill_holes()
    print("Is watertight:", mesh.is_watertight)

    # Export the mesh to an STL file for 3D printing
    mesh.export(output_file)
    print(f"3D model saved as {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate 3D STL file from adjacency data and point cloud")
    parser.add_argument("adjacency_file", help="Path to the adjacency matrix CSV file")
    parser.add_argument("point_cloud_file", help="Path to the point cloud CSV file")
    parser.add_argument("-o", "--output_file", help="Path for the output STL file (default: based on adjacency filename)")
    parser.add_argument("--beam_width", type=float, default=30, help="Width of the beams (default: 30)")
    parser.add_argument("--beam_height", type=float, default=30, help="Height of the beams (default: 30)")

    args = parser.parse_args()

    # Set default output file name if not provided
    if args.output_file is None:
        base_name = os.path.splitext(os.path.basename(args.adjacency_file))[0]
        args.output_file = f"{base_name}_3d_model.stl"

    main(args.adjacency_file, args.point_cloud_file, args.output_file, args.beam_width, args.beam_height)
