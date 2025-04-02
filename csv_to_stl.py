
def csv_process(inputPath): 
    import os
    import sys
    
    original_stdout = sys.stdout  # Save original stdout
    with open('output.txt', 'w') as f:
        sys.stdout = f  # Redirect stdout to output.txt
        for root, _, files in os.walk(inputPath):  
            csv_files = [file for file in files if file.endswith('.csv')]  # Filter only .csv files
            for csv_file in csv_files:
                print(os.path.join(root, csv_file))  # Print full path of each CSV file
    
    sys.stdout = original_stdout


def csv_to_stl(inputPath, beam_diameter_in_mm, cube_side_length):
    csv_process(inputPath)

    import numpy as np
    import trimesh
    from trimesh.creation import cylinder, icosphere
    import math
    from scipy.io import loadmat
    from matplotlib import pyplot as plt

    def plot_3D(positions):
        """Plots the 3D scatter plot for the positions given, make sure that positions is (n x 3)"""
        xs, ys, zs = zip(*positions)
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.scatter(xs, ys, zs)
        ax.set_xlabel('X Coordinate')
        ax.set_ylabel('Y Coordinate')
        ax.set_zlabel('Z Coordinate')
        plt.title('3D Plot of Positions')
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
        for id1, id2, magnitude in forces:
            matrix[id1, id2] = magnitude
        return matrix

    def read_adjacency_matrix_from_mat(filename):
        """Extracts adjacency matrix and positions from a MATLAB .mat file."""
        try:
            data = loadmat(filename)
            adjacency_matrix = data.get('adjacency', None)
            positions = data.get('newItr', None)
            if adjacency_matrix is None or positions is None:
                raise ValueError("MAT file does not contain 'adjacency' or 'positions'.")
        except Exception as e:
            print(f"Error reading MAT file: {e}")
            return None, None
        return adjacency_matrix, positions

    def normalize_positions(positions, cube_side_length):
        """Normalize and scale positions to fit inside a cube with a specified side length."""
        min_coords = np.min(positions, axis=0)
        max_coords = np.max(positions, axis=0)
        scale_factor = cube_side_length / np.max(max_coords - min_coords)
        normalized_positions = (positions - min_coords) * scale_factor
        return normalized_positions

    def create_beam(start_point, end_point, beam_diameter):
        """Creates a cylinder mesh between two points to represent a beam."""
        vector = np.array(end_point) - np.array(start_point)
        length = np.linalg.norm(vector)
        direction = vector / length
        
        # Create a cylinder with a fixed height
        beam = cylinder(radius=beam_diameter / 2, height=length, sections=32)
        beam.apply_translation(-beam.centroid)

        z_vector = np.array([0, 0, 1])
        axis = np.cross(z_vector, direction)
        if np.allclose(axis, [0, 0, 0]):
            axis = [0, 1, 0]
        angle = np.arccos(np.dot(z_vector, direction))
        beam.apply_transform(trimesh.transformations.rotation_matrix(angle, axis, point=beam.centroid))
        
        midpoint = (np.array(start_point) + np.array(end_point)) / 2
        beam.apply_translation(midpoint)
        
        return beam

    def write_stl(positions, adjacency_matrix, beam_diameter, output_file="output.stl", is_one_indexed=True):
        """Generates an STL file from given positions and their adjacency matrix."""
        beams = []
        spheres = []
        start_index = 1 if is_one_indexed else 0

        # Add beams
        for i in range(start_index, len(adjacency_matrix)):
            for j in range(i + 1, len(adjacency_matrix[i])):
                if adjacency_matrix[i, j] > 0:
                    start_point = positions[i][:3]
                    end_point = positions[j][:3]
                    beam = create_beam(start_point, end_point, beam_diameter)
                    beams.append(beam)

        # Add spheres at the junctions
        if isinstance(positions, dict):
            position_values = positions.values()
        else:
            position_values = positions
        
        for pos in position_values:
            sphere = icosphere(radius=beam_diameter / 2)
            # sphere = icosphere( radius=beam_diameter * 2 ) # OVERSIZED SPHERES
            sphere.apply_translation(pos[:3])
            spheres.append(sphere)

        # combined_mesh = trimesh.util.concatenate(beams + spheres) # CONCATENATE - original meshing method
        combined_mesh = trimesh.boolean.union( beams + spheres ) # UNION - requires pip install manifold3d
        # CONCATENATE + REPAIR HOLES 
        # combined_mesh = trimesh.util.concatenate(beams + spheres)
        # trimesh.repair.fill_holes(combined_mesh)

        combined_mesh.export(output_file)

    def process_data(input_type, position_file=None, force_file=None, mat_file=None, beam_diameter=0.05, cube_side_length=1.0, output_file="output.stl", adjacency_array=None, position_array=None):
        """Determines processing strategy based on input type."""
        if input_type == 'lammps':
            positions = read_position_file(position_file)
            forces = read_force_file(force_file)
            adjacency_matrix = create_adjacency_matrix(positions, forces)
            positions_array = np.array([positions[key][:3] for key in sorted(positions.keys())])
            normalized_positions = normalize_positions(positions_array, cube_side_length)
            write_stl(normalized_positions, adjacency_matrix, beam_diameter, output_file, is_one_indexed=True)
        elif input_type == 'mat':
            adjacency_matrix, positions = read_adjacency_matrix_from_mat(mat_file)
            if adjacency_matrix is not None and positions is not None:
                normalized_positions = normalize_positions(positions, cube_side_length)
                write_stl(normalized_positions, adjacency_matrix, beam_diameter, output_file, is_one_indexed=False)
        elif input_type == 'csv':
            adjacency_matrix = np.genfromtxt(adjacency_array, delimiter=',')
            positions = np.genfromtxt(position_array, delimiter=',')
            if adjacency_matrix is not None and positions is not None:
                normalized_positions = normalize_positions(positions, cube_side_length)
                write_stl(normalized_positions, adjacency_matrix, beam_diameter, output_file, is_one_indexed=False)
        else:
            print("Invalid input type. Specify 'lammps' or 'mat'.")

    adjFiles = []
    xyFiles = []
    file = open('output.txt','r')
    for i in file.readlines():
        if ("adj" in i):
            adjFiles.append(i.strip("\n"))
        if ("xy" in i):
            xyFiles.append(i.strip("\n"))

    for i in range(len(xyFiles)):
        adjacency_file = adjFiles[i]
        position_file = xyFiles[i]
        process_data("csv", beam_diameter=beam_diameter_in_mm, cube_side_length=cube_side_length, output_file=f"STLFile{i}.stl", adjacency_array=adjacency_file, position_array=position_file)
