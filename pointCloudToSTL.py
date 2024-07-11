import numpy as np
from libpysal.weights import Voronoi
import shapely.geometry as sh
import trimesh
from trimesh.creation import box, cylinder
import warnings
import networkx as nx

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

def create_cylinder(junction, radius=0.05, height=1.0):
    # Create a vertical cylinder
    cyl = cylinder(radius=radius, height=height)

    # Position the cylinder at the junction point
    junction_3d = np.append(junction, height / 2)  # Adjust Z to place the cylinder correctly
    cyl.apply_translation(junction_3d - cyl.center_mass)

    return cyl

# Variables to define in the code
adjacency_file = "./PC11t004_216_2D-box_Triangular-lattice_Gabriel_URL_adj_100.csv"
point_cloud_file = "./PC11t004_216_2D-box_Triangular-lattice_Gabriel_URL_xy_100.csv"
output_file = "PC11t004_216_100_80mm.stl"
beam_width = 1.5
beam_height = 1.5
cylinder_radius = 0.5*beam_width
cylinder_height = 1.0

def main(adjacency_file, point_cloud_file, output_file, beam_width, beam_height, cylinder_radius, cylinder_height):
    # Load the point cloud data from CSV into a NumPy array
    point_cloud = np.loadtxt(point_cloud_file, delimiter=',')

    xmin = np.min(point_cloud[:, 1])
    xmax = np.max(point_cloud[:, 1])

    scale = 80 / (xmax - xmin) 

    point_cloud = point_cloud * scale

    # Load adjacency matrix from CSV
    adj_matrix = np.loadtxt(adjacency_file, delimiter=',').astype(np.int64)

    # Create a graph from the adjacency matrix
    graph = nx.from_numpy_array(adj_matrix)

    # Create beams for each edge in the graph
    beams = []
    junctions = {}
    for edge in graph.edges():
        start_idx, end_idx = edge
        # Access coordinates directly from the point_cloud array
        start_point = point_cloud[int(start_idx)]
        end_point = point_cloud[int(end_idx)]
        beams.append(create_beam(start_point, end_point, width=beam_width, height=beam_height))

        # Track junctions
        for point in [start_point, end_point]:
            point_key = tuple(point)
            if point_key not in junctions:
                junctions[point_key] = 0
            junctions[point_key] += 1

    # Create cylinders at junctions where beams meet
    cylinders = []
    for junction, count in junctions.items():
        if count > 1:
            cylinders.append(create_cylinder(np.array(junction), radius=cylinder_radius, height=cylinder_height))

    # Combine all beams and cylinders into a single mesh
    all_meshes = beams + cylinders
    mesh = trimesh.util.concatenate(all_meshes)
    mesh.process(validate=True)
    mesh.fill_holes()
    print("Is watertight:", mesh.is_watertight)

    # Export the mesh to an STL file for 3D printing
    mesh.export(output_file)
    print(f"3D model saved as {output_file}")

# Call main function with defined variables
main(adjacency_file, point_cloud_file, output_file, beam_width, beam_height, cylinder_radius, cylinder_height)

