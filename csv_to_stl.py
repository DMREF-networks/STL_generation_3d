
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


def csv_to_stl(inputPath, beam_diameter_in_mm, cube_side_length,
               method="cylinders", extrusion_depth=None):
    """Build STL files from adjacency/xy CSVs in ``inputPath``.

    method : "cylinders" (default) uses the 3D cylinder + junction-sphere
        approach. "planar" merges 2D rectangles (one per edge) and discs
        (one per node) with shapely's ``unary_union``, then extrudes the
        merged polygon to 3D. The planar method is robust for flat 2D
        networks and avoids the junction-gap problem entirely, since
        crossing rectangles in the plane union cleanly. Requires shapely.
    extrusion_depth : only used when ``method == "planar"``. Z-thickness
        of the extruded slab in mm. Defaults to ``beam_diameter_in_mm``
        (thinnest beam gets a square cross-section).
    """
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
        """Generates an STL file from given positions and their adjacency matrix.

        Adjacency values act as per-edge weights on the base beam_diameter:
        the beam diameter between nodes i and j is ``beam_diameter *
        adjacency_matrix[i, j]``. Binary matrices (entries = 1) therefore
        reproduce the original uniform-thickness behaviour. Non-binary
        matrices produce variable-thickness beams. An HTML viewer is
        written alongside the STL so the network can be inspected in a
        browser.
        """
        # Promote 2D positions (N, 2) to 3D by laying beams on z=0.
        if not isinstance(positions, dict):
            positions = np.asarray(positions, dtype=float)
            if positions.ndim == 2 and positions.shape[1] == 2:
                positions = np.hstack([positions, np.zeros((positions.shape[0], 1))])

        beams = []
        spheres = []
        edge_records = []  # (start, end, diameter) used by the HTML viewer
        start_index = 1 if is_one_indexed else 0

        # Compute the max incident weight per node so junction spheres match
        # the thickest beam they meet. Endpoint nodes thus get a sphere
        # sized to their (single) beam rather than a fixed floor, and
        # isolated nodes get no sphere at all.
        n = len(adjacency_matrix)
        node_max_weight = np.zeros(n)
        for i in range(start_index, n):
            for j in range(i + 1, len(adjacency_matrix[i])):
                w = adjacency_matrix[i, j]
                if w > 0:
                    if w > node_max_weight[i]:
                        node_max_weight[i] = w
                    if w > node_max_weight[j]:
                        node_max_weight[j] = w

        # Add beams
        for i in range(start_index, n):
            for j in range(i + 1, len(adjacency_matrix[i])):
                w = adjacency_matrix[i, j]
                if w > 0:
                    diameter = beam_diameter * w
                    start_point = positions[i][:3]
                    end_point = positions[j][:3]
                    beam = create_beam(start_point, end_point, diameter)
                    beams.append(beam)
                    edge_records.append((np.asarray(start_point, dtype=float),
                                         np.asarray(end_point, dtype=float),
                                         diameter))

        # Add spheres at the junctions
        if isinstance(positions, dict):
            position_values = list(positions.values())
        else:
            position_values = positions

        for idx, pos in enumerate(position_values):
            weight = node_max_weight[idx] if idx < n else 0.0
            if weight <= 0:
                continue  # isolated node → no junction sphere
            sphere = icosphere(radius=beam_diameter / 2 * weight)
            # sphere = icosphere( radius=beam_diameter * 2 ) # OVERSIZED SPHERES
            sphere.apply_translation(pos[:3])
            spheres.append(sphere)

        # combined_mesh = trimesh.util.concatenate(beams + spheres) # CONCATENATE - original meshing method
        combined_mesh = trimesh.boolean.union( beams + spheres ) # UNION - requires pip install manifold3d
        trimesh.repair.fill_holes(combined_mesh)

        combined_mesh.export(output_file)

        # Accompany every STL with an interactive HTML viewer.
        html_file = output_file[:-4] + ".html" if output_file.lower().endswith(".stl") else output_file + ".html"
        write_html(edge_records, position_values, node_max_weight, beam_diameter, html_file)

    def write_html(edge_records, position_values, node_max_weight, beam_diameter, output_file):
        """Write an interactive 3D HTML viewer that mirrors the STL geometry.

        Uses the same cylinder/sphere tessellation as the STL so the file is
        a faithful visual preview. Beams are coloured by diameter.
        """
        try:
            import plotly.graph_objects as go
        except ImportError:
            print("plotly not installed; skipping HTML viewer. Install with: pip install plotly")
            return

        V_parts, F_parts, I_parts = [], [], []
        offset = 0
        sections = 12  # lighter tessellation than the STL; good enough for preview
        for start, end, diameter in edge_records:
            beam = cylinder(radius=diameter / 2, height=float(np.linalg.norm(end - start)), sections=sections)
            beam.apply_translation(-beam.centroid)
            direction = (end - start) / np.linalg.norm(end - start)
            z_vec = np.array([0, 0, 1])
            axis = np.cross(z_vec, direction)
            if np.linalg.norm(axis) < 1e-12:
                if np.dot(z_vec, direction) < 0:
                    beam.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [0, 1, 0]))
            else:
                angle = float(np.arccos(np.clip(np.dot(z_vec, direction), -1.0, 1.0)))
                beam.apply_transform(trimesh.transformations.rotation_matrix(angle, axis, point=[0, 0, 0]))
            beam.apply_translation((start + end) / 2.0)
            v = np.asarray(beam.vertices)
            f = np.asarray(beam.faces) + offset
            V_parts.append(v); F_parts.append(f)
            I_parts.append(np.full(len(v), diameter))
            offset += len(v)

        for idx, pos in enumerate(position_values):
            weight = node_max_weight[idx] if idx < len(node_max_weight) else 0.0
            r = beam_diameter / 2 * weight
            if r <= 0:
                continue  # isolated node → no junction sphere
            s = icosphere(radius=r, subdivisions=1)
            v = np.asarray(s.vertices) + np.asarray(pos[:3], dtype=float)
            f = np.asarray(s.faces) + offset
            V_parts.append(v); F_parts.append(f)
            I_parts.append(np.full(len(v), 2 * r))  # colour junctions by their diameter
            offset += len(v)

        if not V_parts:
            return
        V = np.vstack(V_parts); F = np.vstack(F_parts); I = np.concatenate(I_parts)
        mesh = go.Mesh3d(
            x=V[:, 0], y=V[:, 1], z=V[:, 2],
            i=F[:, 0], j=F[:, 1], k=F[:, 2],
            intensity=I, colorscale="Viridis",
            colorbar=dict(title="diameter"),
            flatshading=True, showscale=True,
        )
        fig = go.Figure(data=[mesh])
        fig.update_layout(
            scene=dict(aspectmode="data", xaxis_title="x", yaxis_title="y", zaxis_title="z"),
            margin=dict(l=0, r=0, t=30, b=0),
            title=output_file,
        )
        fig.write_html(output_file, include_plotlyjs="cdn", full_html=True)

    def write_stl_planar(positions, adjacency_matrix, beam_diameter, extrude_depth,
                         output_file="output.stl", is_one_indexed=True):
        """Planar STL: merge 2D rectangles (per edge) + discs (per node) with
        shapely, then extrude. Requires 2D / coplanar positions."""
        try:
            from shapely.geometry import Polygon as _ShPoly
            from shapely.ops import unary_union as _sh_union
        except ImportError:
            raise ImportError("planar method requires shapely. Install with: pip install shapely")

        # Extract 2D coordinates; allow 3D input only if z is constant.
        if isinstance(positions, dict):
            positions = np.array([list(v)[:3] for v in positions.values()], dtype=float)
        positions = np.asarray(positions, dtype=float)
        if positions.shape[1] >= 3 and not np.allclose(positions[:, 2], positions[0, 2]):
            raise ValueError("planar method requires a flat network (constant z)")
        pts2d = positions[:, :2]

        n = len(adjacency_matrix)
        start_index = 1 if is_one_indexed else 0

        # Max incident weight per node. Endpoint nodes get a disc sized to
        # their (single) beam, and isolated nodes get no disc at all.
        node_max_weight = np.zeros(n)
        for i in range(start_index, n):
            for j in range(i + 1, len(adjacency_matrix[i])):
                w = adjacency_matrix[i, j]
                if w > 0:
                    if w > node_max_weight[i]:
                        node_max_weight[i] = w
                    if w > node_max_weight[j]:
                        node_max_weight[j] = w

        polys = []

        # Rectangle per edge: width = beam_diameter * weight.
        for i in range(start_index, n):
            for j in range(i + 1, len(adjacency_matrix[i])):
                w = adjacency_matrix[i, j]
                if w <= 0:
                    continue
                p1 = pts2d[i]
                p2 = pts2d[j]
                d = p2 - p1
                length = float(np.linalg.norm(d))
                if length < 1e-12:
                    continue
                normal = np.array([-d[1], d[0]]) / length
                half_w = beam_diameter * w / 2.0
                corners = [p1 + half_w * normal,
                           p1 - half_w * normal,
                           p2 - half_w * normal,
                           p2 + half_w * normal]
                polys.append(_ShPoly(corners))

        # Disc per node: radius = beam_diameter/2 * max_incident_weight.
        disc_resolution = 24
        thetas = np.linspace(0.0, 2.0 * math.pi, disc_resolution, endpoint=False)
        for idx, p in enumerate(pts2d):
            weight = node_max_weight[idx] if idx < n else 0.0
            r = beam_diameter / 2.0 * weight
            if r <= 0:
                continue
            ring = [(p[0] + r * math.cos(t), p[1] + r * math.sin(t)) for t in thetas]
            polys.append(_ShPoly(ring))

        if not polys:
            return

        merged = _sh_union(polys)

        # Extrude to 3D. MultiPolygon -> concatenate per-component extrusions.
        if merged.geom_type == "MultiPolygon":
            pieces = [trimesh.creation.extrude_polygon(g, height=extrude_depth)
                      for g in merged.geoms]
            mesh = trimesh.util.concatenate(pieces)
        else:
            mesh = trimesh.creation.extrude_polygon(merged, height=extrude_depth)

        # Drop tiny degenerate fragments sometimes emitted by extrude_polygon
        # on near-zero-area shapely slivers (3-4 vertex triangles, etc.).
        parts = mesh.split(only_watertight=False)
        if len(parts) > 1:
            parts = [p for p in parts if len(p.vertices) >= 8]
            if parts:
                mesh = trimesh.util.concatenate(parts)

        # Ensure outward-facing normals (extrude_polygon can leave volume<0).
        if mesh.is_watertight and mesh.volume < 0:
            mesh.invert()

        mesh.export(output_file)

        # Extract exterior + hole rings from the shapely geometry; drawing
        # them on top in the HTML viewer makes missing chunks obvious.
        outline_rings = []
        geoms = list(merged.geoms) if merged.geom_type == "MultiPolygon" else [merged]
        for geom in geoms:
            outline_rings.append(np.asarray(geom.exterior.coords))
            for hole in geom.interiors:
                outline_rings.append(np.asarray(hole.coords))

        html_file = output_file[:-4] + ".html" if output_file.lower().endswith(".stl") else output_file + ".html"
        write_html_mesh(mesh, html_file, outline_rings=outline_rings, outline_z=extrude_depth)

    def write_html_mesh(mesh, output_file, outline_rings=None, outline_z=None):
        """HTML viewer for a prebuilt mesh (used by planar path).

        outline_rings : optional list of (N, 2) arrays drawn as dark lines at
            z = outline_z. Surfacing the planar boundary on top makes
            missing chunks / holes obvious even under flat shading.
        """
        try:
            import plotly.graph_objects as go
        except ImportError:
            print("plotly not installed; skipping HTML viewer. Install with: pip install plotly")
            return
        V = np.asarray(mesh.vertices); F = np.asarray(mesh.faces)
        if len(V) == 0 or len(F) == 0:
            return
        mesh_trace = go.Mesh3d(
            x=V[:, 0], y=V[:, 1], z=V[:, 2],
            i=F[:, 0], j=F[:, 1], k=F[:, 2],
            color="lightsteelblue", flatshading=True,
            lighting=dict(ambient=0.55, diffuse=0.85, specular=0.25,
                          roughness=0.6, fresnel=0.15),
            lightposition=dict(x=1000, y=1000, z=2000),
        )
        traces = [mesh_trace]
        if outline_rings:
            z_top = float(outline_z) if outline_z is not None else float(mesh.bounds[1][2])
            for ring in outline_rings:
                ring = np.asarray(ring)
                traces.append(go.Scatter3d(
                    x=ring[:, 0], y=ring[:, 1],
                    z=np.full(len(ring), z_top),
                    mode="lines",
                    line=dict(color="black", width=2),
                    showlegend=False, hoverinfo="skip",
                ))
        fig = go.Figure(data=traces)
        fig.update_layout(
            scene=dict(aspectmode="data", xaxis_title="x", yaxis_title="y", zaxis_title="z"),
            margin=dict(l=0, r=0, t=30, b=0),
            title=output_file,
        )
        fig.write_html(output_file, include_plotlyjs="cdn", full_html=True)

    def _emit(normalized_positions, adjacency_matrix, is_one_indexed, output_file):
        """Dispatch to the selected writer (cylinders / planar)."""
        if method == "planar":
            depth = extrusion_depth if extrusion_depth is not None else beam_diameter_in_mm
            write_stl_planar(normalized_positions, adjacency_matrix,
                             beam_diameter_in_mm, depth, output_file,
                             is_one_indexed=is_one_indexed)
        else:
            write_stl(normalized_positions, adjacency_matrix,
                      beam_diameter_in_mm, output_file,
                      is_one_indexed=is_one_indexed)

    def process_data(input_type, position_file=None, force_file=None, mat_file=None, beam_diameter=0.05, cube_side_length=1.0, output_file="output.stl", adjacency_array=None, position_array=None):
        """Determines processing strategy based on input type."""
        if input_type == 'lammps':
            positions = read_position_file(position_file)
            forces = read_force_file(force_file)
            adjacency_matrix = create_adjacency_matrix(positions, forces)
            positions_array = np.array([positions[key][:3] for key in sorted(positions.keys())])
            normalized_positions = normalize_positions(positions_array, cube_side_length)
            _emit(normalized_positions, adjacency_matrix, True, output_file)
        elif input_type == 'mat':
            adjacency_matrix, positions = read_adjacency_matrix_from_mat(mat_file)
            if adjacency_matrix is not None and positions is not None:
                normalized_positions = normalize_positions(positions, cube_side_length)
                _emit(normalized_positions, adjacency_matrix, False, output_file)
        elif input_type == 'csv':
            adjacency_matrix = np.genfromtxt(adjacency_array, delimiter=',')
            positions = np.genfromtxt(position_array, delimiter=',')
            if adjacency_matrix is not None and positions is not None:
                normalized_positions = normalize_positions(positions, cube_side_length)
                _emit(normalized_positions, adjacency_matrix, False, output_file)
        else:
            print("Invalid input type. Specify 'lammps' or 'mat'.")

    adjFiles = []
    xyFiles = []
    match_strings = []

    with open('output.txt', 'r') as file:
        readlines = file.readlines()

    disorder = "" # currently not being added
    for line in readlines:
        if "adj" in line:
            line = line.strip()
            match_string = line[:line.index("adj") - 1]
            adjFiles.append(line)

            # matching xy file
            for xy_line in readlines:
                if "xy" in xy_line and match_string in xy_line:
                    xyFiles.append(xy_line.strip())
                    # try:
                    #     disorder = xy_line[xy_line.index("xy") + 2 : line.index("csv") - 2]
                    # except:
                    #     print("No disorder found")
                    break  # stop after the first match

            # match string
            try:
                match_base = match_string[match_string.rindex("/") + 1:]
            except ValueError:
                match_base = match_string
            match_base += disorder
            match_strings.append(match_base)

        for i in range(len(xyFiles)):
            adjacency_file = adjFiles[i]
            position_file = xyFiles[i]
            process_data("csv", beam_diameter=beam_diameter_in_mm, cube_side_length=cube_side_length, output_file=f"{match_strings[i]}.stl", adjacency_array=adjacency_file, position_array=position_file)
