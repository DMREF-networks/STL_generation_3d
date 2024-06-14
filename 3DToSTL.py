import numpy as np
import trimesh
from trimesh.creation import cylinder, icosphere
import math
from scipy.io import loadmat
import matplotlib.pyplot as plt
"""
3DToSTL.py

This script processes "3D positional and force data from LAMMPS simulations" or "adjacency and positional data from MATLAB .mat" files to generate
STL files. These STL files model the connections and positions in a 3D structure as beams based on provided
data. This can be useful for visualizing complex networks or for simulations where mechanical interactions
are studied.

How to use:
- Specify the input type ('lammps' for LAMMPS data or 'mat' for MATLAB data).
- Provide the required file paths:
  For LAMMPS: position file and force file.
  For MATLAB: .mat file containing the adjacency matrix and positions.
- Set the desired beam diameter and output file name.
- Run the script to generate the STL file.

Eg for LAMMPS:  process_data('lammps', position_file=position_file, force_file=force_file, beam_diameter=beam_diameter, output_file="lammps_to_stl.stl")
Eg for Matlab:  process_data("mat", mat_file=mat_file, beam_diameter=beam_diameter, output_file="mat_to_stl.stl")

Requirements:
- numpy
- trimesh
- scipy

Ensure you have the above Python packages installed before running the script.
"""

def plot_3D(positions):
    """Plots the 3D scatter plot for the positions given, make sure that positions is (n x 3)"""
    # Unpack the positions data into separate lists for x, y, and z coordinates
    xs, ys, zs = zip(*positions)

    # Create a new matplotlib figure and its axes
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # Plot the data as a 3D scatter plot
    ax.scatter(xs, ys, zs)

    # Set labels for each axis
    ax.set_xlabel('X Coordinate')
    ax.set_ylabel('Y Coordinate')
    ax.set_zlabel('Z Coordinate')

    # Set the title of your plot
    plt.title('3D Plot of Positions')

    # Finally, display the plot
    plt.show()

def read_position_file(filename):
    """Reads positions from a LAMMPS dump file; each line should contain ID, x, y, z, and radius."""
    positions = {}
    try:
        with open(filename, 'r') as file:
            for line in file:
                parts = line.strip().split()
                if parts:
                    id, x, y, z, radius = map(float, parts)
                    positions[int(id)] = (x, y, z, radius)
    except Exception as e:
        print(f"Error reading position file: {e}")
    return positions


def read_force_file(filename):
    """Reads force data from a LAMMPS dump file; each line should include ID1, ID2, fx, fy, and fz."""
    forces = []
    try:
        with open(filename, 'r') as file:
            for line in file:
                parts = line.strip().split()
                if parts:
                    id1, id2 = int(parts[1]), int(parts[2])
                    fx, fy, fz = map(float, parts[3:6])
                    # To find the force bw 2 points 
                    magnitude = math.sqrt(fx ** 2 + fy ** 2 + fz ** 2)
                    if magnitude > 0:
                        forces.append((id1, id2, magnitude))
    except Exception as e:
        print(f"Error reading force file: {e}")
    return forces


def create_adjacency_matrix(positions, forces):
    """Generates a matrix showing the connection strength between points based on forces."""
    size = len(positions)
    matrix = np.zeros((size + 1, size + 1))
    # Assuming particle IDs are 1-indexed and sequential.
    for id1, id2, magnitude in forces:
        matrix[id1, id2] = magnitude
    return matrix


def read_adjacency_matrix_from_mat(filename):
    """Extracts adjacency matrix and positions from a MATLAB .mat file."""
    try:
        data = loadmat(filename)
        print(data)
        # Assuming the adjacency matrix is stored under the key 'adjacency'
        # You may need to adjust this key based on the actual content of your .mat file
        adjacency_matrix = data.get('adjacency', None)
        positions = data.get('newItr', None)
        # print(positions)
        if adjacency_matrix is None or positions is None:
            raise ValueError("MAT file does not contain 'adjacency' or 'positions'.")
    except Exception as e:
        print(f"Error reading MAT file: {e}")
        return None, None
    return adjacency_matrix, positions

# def create_triangle(radius):
#     # Triangle vertices based on radius
#     triangle_height = radius * np.sqrt(3)  # Equilateral triangle height
#     triangle_vertices = np.array([
#         [0, -radius, 0],  # Vertex at the middle of base
#         [triangle_height, 0, 0],  # Vertex at the top of the triangle
#         [0, radius, 0]  # Vertex at the other end of the base
#     ])
    
#     # Create the triangle mesh
#     return trimesh.Trimesh(vertices=triangle_vertices, faces=[[0, 1, 2]])


def create_beam(start_point, end_point, beam_diameter):
    """Creates a cylinder mesh between two points to represent a beam."""
    direction_3d = np.array(end_point) - np.array(start_point)
    length = np.linalg.norm(direction_3d)  # Calculate the length of the vector
    direction_3d = direction_3d / length  # Normalize vector to get the direction

    # Create cylinder along z-axis with specified diameter and length
    beam = cylinder(radius=beam_diameter / 2, height=length, sections=64, capped=True)

    # Create triangles
    # triangle = create_triangle(beam_diameter / 2)

    # Translate to center the cylinder at the origin
    beam.apply_translation(-beam.centroid)

    # Position triangles at both ends of the cylinder
    # triangle_top = triangle.copy()
    # triangle_bottom = triangle.copy()

    # Position the top triangle
    # triangle_top.apply_translation([0, 0, length / 2])
    # rotation_matrix = trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0], point=triangle_top.centroid)
    # triangle_top.apply_transform(rotation_matrix)

    # # Position the bottom triangle
    # triangle_bottom.apply_translation([0, 0, -length / 2])

    # Combine cylinder and triangles
    beam = trimesh.util.concatenate(beam)
    # beam = trimesh.util.concatenate([beam, triangle_top, triangle_bottom])

    current_direction_z_vector = np.array([0, 0, 1])  # Reference vector along the cylinder's axis
    rotation_axis = np.cross(current_direction_z_vector, direction_3d)  # Axis for rotation
    if np.allclose(rotation_axis, [0, 0, 0]):  # If parallel, use an arbitrary axis
        rotation_axis = [0, 1, 0]
    rotation_angle = np.arccos(np.dot(current_direction_z_vector, direction_3d))  # Angle for rotation

    # Apply rotation and translation to align cylinder
    beam.apply_transform(trimesh.transformations.rotation_matrix(rotation_angle, rotation_axis, point=beam.centroid))

    midpoint_3d = (np.array(start_point) + np.array(end_point)) / 2
    beam.apply_translation(midpoint_3d)
    return beam


def write_stl(positions, adjacency_matrix, beam_diameter=0.06, output_file="output.stl", is_one_indexed=True):
    """Generates an STL file from given positions and their adjacency matrix."""
    beams = []
    start_index = 1 if is_one_indexed else 0
    for i in range(start_index, len(adjacency_matrix)):
        for j in range(i + 1, len(adjacency_matrix[i])):
            if adjacency_matrix[i, j] > 0:
                start_point = positions[i][:3]
                end_point = positions[j][:3]
                beam = create_beam(start_point, end_point, beam_diameter)
                beams.append(beam)

    # Normal Beam Concatenation
    mesh = trimesh.util.concatenate(beams)
    mesh.fill_holes()
    # print(combined_mesh)
    mesh.export(output_file)

def process_data(input_type, position_file=None, force_file=None, mat_file=None, beam_diameter=0.05, output_file="output.stl"):
    """Determines processing strategy based on input type."""
    '''lammps data is 1-indexed while matlab data is 0-indexed'''

    if input_type == 'lammps':
        positions = read_position_file(position_file)
        forces = read_force_file(force_file)
        adjacency_matrix = create_adjacency_matrix(positions, forces)
        write_stl(positions, adjacency_matrix, beam_diameter, output_file, is_one_indexed=True)
    elif input_type == 'mat':
        adjacency_matrix, positions = read_adjacency_matrix_from_mat(mat_file)
        # plot_3D(positions)
        if adjacency_matrix is not None and positions is not None:
            write_stl(positions, adjacency_matrix, beam_diameter, output_file, is_one_indexed=False)
    else:
        print("Invalid input type. Specify 'lammps' or 'mat'.")


# LAMMPS DATA
# position_path = './dump.position4'
# force_path = './dump.force4'
# beam_diameter = 0.25  # Modify as needed, this should be based on the spead of the points.
# process_data('lammps', position_file=position_path, force_file=force_path, beam_diameter=beam_diameter, output_file="lammps_to_stl.stl")

# MATLAB DATA
mat_file ="./Adjacency_Lattice1_240408.mat"
beam_diameter = 0.0004
process_data("mat", mat_file=mat_file, beam_diameter=beam_diameter, output_file="mat_to_stl.stl")
