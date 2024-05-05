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

# Ignore future warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Load the point cloud data
point_cloud = np.loadtxt(open("./net100.csv", "rb"), delimiter=",")

# Generate Voronoi diagram (simulating Delaunay-like edges for the purpose of 3D modeling)
voronoi = Voronoi(point_cloud, criterion='rook', clip=sh.box(0, 0, 2000, 2000))
graph = voronoi.to_networkx()

# Function to create a 3D beam between two points
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

# Create beams for each edge in the graph
beams = []
for edge in graph.edges():
    start_idx, end_idx = edge
    # print(point_cloud[start_idx], point_cloud[end_idx])
    # Access coordinates directly from the point_cloud array
    start_point = point_cloud[start_idx]
    end_point = point_cloud[end_idx]
    beams.append(create_beam(start_point, end_point, width=30, height=30))  # Adjust width and height as needed, it should be proportional to the spread of the points.

# Combine all beams into a single mesh
mesh = trimesh.util.concatenate(beams)
mesh.process(validate=True)
mesh.fill_holes()
print("Is watertight:", mesh.is_watertight)

# Export the mesh to an STL file for 3D printing
mesh.export('network_3d_model.stl')
