"""Generate one STL per material from a JSON configuration.

The core design is intentionally conservative:

* adjacency values stay numeric and mean connectivity / thickness
* material assignments live beside the adjacency data or in explicit edge-list
  material-code columns
* every material group is exported as a separate STL in the same coordinate
  frame, so slicers can import them together and assign extruders/materials

For adjacency matrices, use a same-shape material matrix or an edge-material
table. For edge lists, use edge_list_interpretation to define whether extra
columns are thickness, material codes, or both.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import pickle
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import numpy as np
import trimesh
from trimesh.creation import cylinder, icosphere


PALETTE = [
    "#2563eb",  # blue
    "#dc2626",  # red
    "#059669",  # green
    "#d97706",  # amber
    "#7c3aed",  # violet
    "#0891b2",  # cyan
    "#be123c",  # rose
    "#4b5563",  # gray
]


@dataclass(frozen=True)
class Edge:
    source: int
    target: int
    weight: float
    material: str


@dataclass(frozen=True)
class BeamRecord:
    mesh: trimesh.Trimesh
    source: int
    target: int
    diameter: float


@dataclass(frozen=True)
class EdgeListColumnConfig:
    source_col: int
    target_col: int
    thickness_col: Optional[int]
    material_col: Optional[int]
    use_thickness: bool
    explicit_material: bool
    allow_ambiguous_text_thickness: bool
    allow_material_heuristic: bool


@dataclass(frozen=True)
class NodeReservation:
    mesh: trimesh.Trimesh
    radius: float
    center: Tuple[float, float, float]


def generate_from_config_file(config_path: str) -> Dict[str, Any]:
    """Load a JSON config file and generate its configured STL outputs."""
    path = Path(config_path).expanduser().resolve()
    with path.open("r", encoding="utf-8") as f:
        config = json.load(f)
    return generate_from_config_data(config, base_dir=path.parent)


def generate_from_config_text(config_text: str, base_dir: Optional[str] = None) -> Dict[str, Any]:
    """Generate STL outputs from a JSON config string."""
    root = Path(base_dir).expanduser().resolve() if base_dir else Path.cwd()
    return generate_from_config_data(json.loads(config_text), base_dir=root)


def generate_from_config_data(config: Mapping[str, Any], base_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Generate all jobs in a parsed config dictionary."""
    root = Path(base_dir).resolve() if base_dir else Path.cwd()
    jobs = config.get("jobs")
    if jobs is None:
        jobs = [config]
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("Config must contain a job object or a non-empty 'jobs' list.")

    results = []
    for index, job in enumerate(jobs):
        if not isinstance(job, Mapping):
            raise ValueError(f"Job {index} must be an object.")
        results.append(_generate_job(config, job, root, index))

    return {"jobs": results}


def _generate_job(
    root_config: Mapping[str, Any],
    job: Mapping[str, Any],
    base_dir: Path,
    index: int,
) -> Dict[str, Any]:
    geometry = _merged_object(root_config.get("geometry"), job.get("geometry"))
    material_defs = _merged_object(root_config.get("materials"), job.get("materials"))

    positions_path = _required_path(job, "positions", "xy")
    adjacency_path = _required_path(job, "adjacency", "adj")
    output_dir = _resolve_path(base_dir, job.get("output_dir", root_config.get("output_dir", ".")))
    output_dir.mkdir(parents=True, exist_ok=True)

    name = str(job.get("name") or _default_job_name(adjacency_path))
    beam_diameter = float(geometry.get("beam_diameter_mm", geometry.get("beam_diameter", 1.0)))
    cube_side = float(geometry.get("cube_side_length_mm", geometry.get("cube_side_length", 1.0)))
    variable_thickness = bool(geometry.get("variable_thickness", False))
    adjacency_format = str(job.get("adjacency_format", "auto")).strip().lower().replace("-", "_")
    edge_interpretation = None if adjacency_format == "matrix" else _edge_list_interpretation(job)
    if edge_interpretation in {"legacy", "material"}:
        variable_thickness = False
    elif edge_interpretation in {"thickness", "thickness_material"}:
        variable_thickness = True
    sections = int(geometry.get("sections", 32))
    sphere_subdivisions = int(geometry.get("sphere_subdivisions", 2))
    boolean_union = bool(geometry.get("boolean_union", True))
    junction_policy = str(geometry.get("junction_policy", "separate")).strip().lower()
    default_material = str(job.get("default_material", root_config.get("default_material", "default")))
    mixed_junction_material = str(geometry.get("mixed_junction_material", default_material))
    node_radius_scale = float(geometry.get("node_radius_scale", geometry.get("junction_radius_scale", 1.0)))
    node_material = geometry.get("node_material")
    node_material = str(node_material).strip() if node_material is not None else None
    if not node_material:
        node_material = None
    node_material_priority = bool(geometry.get("node_material_priority", node_material is not None))

    if beam_diameter <= 0:
        raise ValueError("geometry.beam_diameter_mm must be greater than zero.")
    if cube_side <= 0:
        raise ValueError("geometry.cube_side_length_mm must be greater than zero.")
    if sections < 3:
        raise ValueError("geometry.sections must be at least 3.")
    if sphere_subdivisions < 0:
        raise ValueError("geometry.sphere_subdivisions must be non-negative.")
    if node_radius_scale <= 0:
        raise ValueError("geometry.node_radius_scale must be greater than zero.")
    if junction_policy not in {"separate", "dominant"}:
        raise ValueError("geometry.junction_policy must be one of: separate, dominant.")

    positions = _load_positions(_resolve_path(base_dir, positions_path))
    positions = _normalize_positions(positions, cube_side)

    material_lookup = _load_material_lookup(job, base_dir)
    edges = _load_edges(
        _resolve_path(base_dir, adjacency_path),
        job,
        variable_thickness=variable_thickness,
        default_material=default_material,
        material_lookup=material_lookup,
        base_dir=base_dir,
    )
    _validate_edges(edges, len(positions))

    meshes_by_material: Dict[str, List[trimesh.Trimesh]] = defaultdict(list)
    beam_records_by_material: Dict[str, List[BeamRecord]] = defaultdict(list)
    preview_records = []
    incident: Dict[int, List[Tuple[str, float]]] = defaultdict(list)

    for edge in edges:
        start = positions[edge.source][:3]
        end = positions[edge.target][:3]
        diameter = beam_diameter * edge.weight
        if diameter <= 0:
            continue
        beam = _create_beam(start, end, diameter, sections=sections)
        if beam is None:
            continue
        meshes_by_material[edge.material].append(beam)
        beam_records_by_material[edge.material].append(BeamRecord(beam, edge.source, edge.target, diameter))
        preview_records.append((edge.material, start, end, diameter))
        incident[edge.source].append((edge.material, edge.weight))
        incident[edge.target].append((edge.material, edge.weight))

    node_reservations = _add_junction_spheres(
        positions,
        incident,
        meshes_by_material,
        beam_diameter,
        junction_policy=junction_policy,
        mixed_junction_material=mixed_junction_material,
        node_material=node_material,
        sphere_subdivisions=sphere_subdivisions,
        node_radius_scale=node_radius_scale,
    )

    outputs = []
    combined_for_preview: Dict[str, trimesh.Trimesh] = {}
    for material in sorted(meshes_by_material):
        meshes = meshes_by_material[material]
        if node_material_priority and node_reservations and material != node_material:
            meshes = _apply_node_material_priority(
                meshes,
                beam_records_by_material.get(material, []),
                positions,
                node_reservations,
                sections,
            )
        if not meshes:
            continue
        material_boolean_union = boolean_union and material != node_material
        combined = _combine_meshes(meshes, boolean_union=material_boolean_union)
        if combined is None or combined.is_empty:
            continue
        filename = f"{_slug(name)}_{_slug(material)}.stl"
        output_path = output_dir / filename
        combined.export(output_path)
        combined_for_preview[material] = combined
        outputs.append(_mesh_result(material, output_path, combined))

    preview_path = output_dir / f"{_slug(name)}_preview.html"
    preview_result = _write_preview_html(
        combined_for_preview,
        material_defs,
        preview_path,
        node_material=node_material,
    )

    return {
        "name": name,
        "positions": str(_resolve_path(base_dir, positions_path)),
        "adjacency": str(_resolve_path(base_dir, adjacency_path)),
        "output_dir": str(output_dir),
        "edge_count": len(edges),
        "material_count": len(outputs),
        "outputs": outputs,
        "preview": preview_result,
        "geometry": {
            "beam_diameter_mm": beam_diameter,
            "cube_side_length_mm": cube_side,
            "variable_thickness": variable_thickness,
            "junction_policy": junction_policy,
            "node_material": node_material,
            "node_material_priority": node_material_priority,
            "node_radius_scale": node_radius_scale,
            "boolean_union": boolean_union,
        },
    }


def _load_edges(
    adjacency_path: Path,
    job: Mapping[str, Any],
    variable_thickness: bool,
    default_material: str,
    material_lookup: Mapping[Tuple[int, int], str],
    base_dir: Path,
) -> List[Edge]:
    adjacency_format = str(job.get("adjacency_format", "auto")).strip().lower().replace("-", "_")
    if adjacency_format in {"edge_list", "edgelist", "edges", "edge_list_with_material"}:
        return _load_edge_list(adjacency_path, job, variable_thickness, default_material, material_lookup)
    if adjacency_format == "matrix":
        matrix = _load_numeric_array(adjacency_path)
        return _edges_from_matrix(matrix, job, base_dir, variable_thickness, default_material, material_lookup)
    if adjacency_format != "auto":
        raise ValueError("adjacency_format must be one of: auto, matrix, edge_list.")

    try:
        matrix = _load_numeric_array(adjacency_path)
    except ValueError:
        return _load_edge_list(adjacency_path, job, variable_thickness, default_material, material_lookup)

    if matrix.ndim == 2 and matrix.shape[0] == matrix.shape[1]:
        return _edges_from_matrix(matrix, job, base_dir, variable_thickness, default_material, material_lookup)
    return _edges_from_numeric_edge_list(matrix, job, variable_thickness, default_material, material_lookup)


def _edges_from_matrix(
    matrix: np.ndarray,
    job: Mapping[str, Any],
    base_dir: Path,
    variable_thickness: bool,
    default_material: str,
    material_lookup: Mapping[Tuple[int, int], str],
) -> List[Edge]:
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Matrix adjacency input must be a square 2D array.")

    material_matrix = None
    material_matrix_path = job.get("material_matrix") or job.get("materials_matrix")
    if material_matrix_path:
        material_matrix = _load_material_matrix(_resolve_path(base_dir, material_matrix_path))
        if material_matrix.shape != matrix.shape:
            raise ValueError(
                f"material_matrix shape {material_matrix.shape} must match adjacency shape {matrix.shape}."
            )

    edges = []
    n = matrix.shape[0]
    for i in range(n):
        for j in range(i + 1, n):
            value = float(matrix[i, j])
            if value <= 0:
                continue
            weight = value if variable_thickness else 1.0
            material = default_material
            if material_matrix is not None:
                material = _material_from_matrix(material_matrix, i, j, default_material)
            material = material_lookup.get(_edge_key(i, j), material)
            edges.append(Edge(i, j, weight, material))
    return edges


def _load_edge_list(
    path: Path,
    job: Mapping[str, Any],
    variable_thickness: bool,
    default_material: str,
    material_lookup: Mapping[Tuple[int, int], str],
) -> List[Edge]:
    if path.suffix.lower() == ".npy":
        data = np.load(path, allow_pickle=True)
        if data.dtype.kind in {"U", "S", "O"}:
            return _edges_from_string_edge_rows(data.tolist(), job, variable_thickness, default_material, material_lookup)
        return _edges_from_numeric_edge_list(data, job, variable_thickness, default_material, material_lookup)

    if path.suffix.lower() in {".pkl", ".pickle"}:
        return _edges_from_pickle_edge_list(_load_pickle(path), job, variable_thickness, default_material, material_lookup)

    rows = _read_csv_rows(path)
    header = _header_map(rows[0]) if rows and _looks_like_header(rows[0]) else None
    data_rows = rows[1:] if header else rows
    columns = _edge_list_column_config(
        job,
        header,
        variable_thickness,
    )
    material_map = _edge_material_map(job)

    edges = []
    for line_number, row in enumerate(data_rows, start=2 if header else 1):
        if not row:
            continue
        try:
            source = int(float(row[columns.source_col]))
            target = int(float(row[columns.target_col]))
        except (IndexError, ValueError) as exc:
            raise ValueError(f"Invalid edge endpoints in {path} line {line_number}: {row}") from exc

        weight = _edge_weight_from_row(
            row,
            columns.thickness_col,
            columns.use_thickness,
            has_header=header is not None,
            source=f"{path} line {line_number}",
            allow_ambiguous_text_thickness=columns.allow_ambiguous_text_thickness,
        )
        material = _edge_material_from_row(
            row,
            columns.material_col,
            default_material,
            has_header=header is not None,
            material_map=material_map,
            explicit_material=columns.explicit_material,
            allow_heuristic=columns.allow_material_heuristic,
        )
        material = material_lookup.get(_edge_key(source, target), material)
        if weight > 0:
            edges.append(Edge(source, target, weight, material))
    return edges


def _edge_list_column_config(
    job: Mapping[str, Any],
    header: Optional[Mapping[str, int]],
    variable_thickness: bool,
) -> EdgeListColumnConfig:
    columns = job.get("edge_columns") or {}
    interpretation = _edge_list_interpretation(job)

    source_col = _column_index(columns.get("source", columns.get("from")), header, 0)
    target_col = _column_index(columns.get("target", columns.get("to")), header, 1)

    if interpretation == "legacy":
        return EdgeListColumnConfig(source_col, target_col, None, None, False, False, False, False)
    if interpretation == "thickness":
        return EdgeListColumnConfig(
            source_col,
            target_col,
            _column_index(columns.get("thickness", columns.get("weight")), header, 2),
            None,
            True,
            False,
            False,
            False,
        )
    if interpretation == "material":
        return EdgeListColumnConfig(
            source_col,
            target_col,
            None,
            _column_index(columns.get("material"), header, 2),
            False,
            True,
            False,
            False,
        )
    if interpretation == "thickness_material":
        return EdgeListColumnConfig(
            source_col,
            target_col,
            _column_index(columns.get("thickness", columns.get("weight")), header, 2),
            _column_index(columns.get("material"), header, 3),
            True,
            True,
            False,
            False,
        )

    thickness_col = _column_index(columns.get("thickness", columns.get("weight")), header, 2)
    material_col = _column_index(columns.get("material"), header, 3)
    return EdgeListColumnConfig(
        source_col,
        target_col,
        thickness_col,
        material_col,
        variable_thickness,
        False,
        True,
        True,
    )


def _edge_list_interpretation(job: Mapping[str, Any]) -> Optional[str]:
    value = job.get("edge_list_interpretation") or job.get("edge_interpretation")
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "uniform": "legacy",
        "ignore_extra_columns": "legacy",
        "ignore_extra": "legacy",
        "legacy_edges": "legacy",
        "thickness_column": "thickness",
        "edge_thickness": "thickness",
        "material_column": "material",
        "material_type": "material",
        "beam_type": "material",
        "thickness_and_material": "thickness_material",
        "thickness_material_column": "thickness_material",
    }
    normalized = aliases.get(normalized, normalized)
    valid = {"legacy", "thickness", "material", "thickness_material"}
    if normalized not in valid:
        raise ValueError(f"edge_list_interpretation must be one of: {', '.join(sorted(valid))}.")
    return normalized


def _edge_material_map(job: Mapping[str, Any]) -> Dict[str, str]:
    value = job.get("edge_material_map") or job.get("material_code_map") or {}
    if not value:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("edge_material_map must be an object.")
    return {_material_code_key(code): str(material) for code, material in value.items()}


def _edges_from_numeric_edge_list(
    data: np.ndarray,
    job: Mapping[str, Any],
    variable_thickness: bool,
    default_material: str,
    material_lookup: Mapping[Tuple[int, int], str],
) -> List[Edge]:
    data = np.asarray(data)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.ndim != 2 or data.shape[1] < 2:
        raise ValueError("Edge-list adjacency input must have at least two columns.")
    columns = _edge_list_column_config(
        job,
        header=None,
        variable_thickness=variable_thickness,
    )
    material_map = _edge_material_map(job)

    edges = []
    for row_index, row in enumerate(data, start=1):
        try:
            source = int(row[columns.source_col])
            target = int(row[columns.target_col])
        except (IndexError, ValueError) as exc:
            raise ValueError(f"Invalid edge endpoints in row {row_index}: {row}") from exc
        weight = _edge_weight_from_row(
            row,
            columns.thickness_col,
            columns.use_thickness,
            has_header=False,
            source=f"edge row {row_index}",
            allow_ambiguous_text_thickness=columns.allow_ambiguous_text_thickness,
        )
        material = _edge_material_from_row(
            row,
            columns.material_col,
            default_material,
            has_header=False,
            material_map=material_map,
            explicit_material=columns.explicit_material,
            allow_heuristic=columns.allow_material_heuristic,
        )
        material = material_lookup.get(_edge_key(source, target), material)
        if weight > 0:
            edges.append(Edge(source, target, weight, material))
    return edges


def _edges_from_string_edge_rows(
    rows: Iterable[Iterable[Any]],
    job: Mapping[str, Any],
    variable_thickness: bool,
    default_material: str,
    material_lookup: Mapping[Tuple[int, int], str],
) -> List[Edge]:
    rows = [[str(cell).strip() for cell in row] for row in rows if len(row) >= 2]
    if not rows:
        return []
    header = _header_map(rows[0]) if _looks_like_header(rows[0]) else None
    data_rows = rows[1:] if header else rows
    columns = _edge_list_column_config(
        job,
        header,
        variable_thickness,
    )
    material_map = _edge_material_map(job)
    edges = []
    for line_number, row in enumerate(data_rows, start=2 if header else 1):
        source = int(float(row[columns.source_col]))
        target = int(float(row[columns.target_col]))
        weight = _edge_weight_from_row(
            row,
            columns.thickness_col,
            columns.use_thickness,
            has_header=header is not None,
            source=f"edge row {line_number}",
            allow_ambiguous_text_thickness=columns.allow_ambiguous_text_thickness,
        )
        material = _edge_material_from_row(
            row,
            columns.material_col,
            default_material,
            has_header=header is not None,
            material_map=material_map,
            explicit_material=columns.explicit_material,
            allow_heuristic=columns.allow_material_heuristic,
        )
        material = material_lookup.get(_edge_key(source, target), material)
        if weight > 0:
            edges.append(Edge(source, target, weight, material))
    return edges


def _edges_from_pickle_edge_list(
    data: Any,
    job: Mapping[str, Any],
    variable_thickness: bool,
    default_material: str,
    material_lookup: Mapping[Tuple[int, int], str],
) -> List[Edge]:
    rows, header = _pickle_edge_rows_and_header(data)
    if header:
        return _edges_from_string_edge_rows([header] + rows, job, variable_thickness, default_material, material_lookup)

    if _looks_like_mapping_records(rows):
        return _edges_from_mapping_edge_records(rows, job, variable_thickness, default_material, material_lookup)

    array = np.asarray(rows)
    if array.dtype.kind in {"U", "S", "O"}:
        return _edges_from_string_edge_rows(array.tolist(), job, variable_thickness, default_material, material_lookup)
    return _edges_from_numeric_edge_list(array, job, variable_thickness, default_material, material_lookup)


def _load_material_lookup(job: Mapping[str, Any], base_dir: Path) -> Dict[Tuple[int, int], str]:
    lookup: Dict[Tuple[int, int], str] = {}

    edge_materials = job.get("edge_materials")
    if edge_materials:
        for source, target, material in _read_edge_material_records(_resolve_path(base_dir, edge_materials)):
            lookup[_edge_key(source, target)] = material

    inline = job.get("material_assignments") or job.get("edge_material_assignments")
    if inline:
        lookup.update(_parse_inline_material_assignments(inline))

    return lookup


def _read_edge_material_records(path: Path) -> List[Tuple[int, int, str]]:
    rows = _read_csv_rows(path)
    if not rows:
        return []
    header = _header_map(rows[0]) if _looks_like_header(rows[0]) else None
    data_rows = rows[1:] if header else rows
    source_col = _column_index("source", header, 0)
    target_col = _column_index("target", header, 1)
    material_col = _column_index("material", header, 2)
    records = []
    for line_number, row in enumerate(data_rows, start=2 if header else 1):
        try:
            source = int(float(row[source_col]))
            target = int(float(row[target_col]))
            material = _clean_material(row[material_col], "default")
        except (IndexError, ValueError) as exc:
            raise ValueError(f"Invalid edge material record in {path} line {line_number}: {row}") from exc
        records.append((source, target, material))
    return records


def _parse_inline_material_assignments(value: Any) -> Dict[Tuple[int, int], str]:
    lookup: Dict[Tuple[int, int], str] = {}
    if isinstance(value, Mapping):
        for key, material in value.items():
            source, target = _parse_edge_key(str(key))
            lookup[_edge_key(source, target)] = str(material)
        return lookup

    if isinstance(value, list):
        for entry in value:
            if not isinstance(entry, Mapping):
                raise ValueError("material_assignments entries must be objects.")
            source = int(entry.get("source", entry.get("from")))
            target = int(entry.get("target", entry.get("to")))
            material = str(entry["material"])
            lookup[_edge_key(source, target)] = material
        return lookup

    raise ValueError("material_assignments must be an object or list.")


def _load_positions(path: Path) -> np.ndarray:
    data = _load_numeric_array(path)
    data = np.asarray(data, dtype=float)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.ndim != 2 or data.shape[1] < 2:
        raise ValueError("positions must be a 2D array with at least x and y columns.")
    if data.shape[1] == 2:
        data = np.hstack([data, np.zeros((data.shape[0], 1))])
    return data[:, :3]


def _load_numeric_array(path: Path) -> np.ndarray:
    if not path.exists():
        raise ValueError(f"File not found: {path}")
    if path.suffix.lower() == ".npy":
        return np.load(path, allow_pickle=True)
    if path.suffix.lower() in {".pkl", ".pickle"}:
        data = _load_pickle(path)
        if isinstance(data, Mapping):
            raise ValueError(f"Pickle numeric array must be an array-like object, not a mapping: {path}")
        try:
            return np.asarray(data, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Could not read numeric data from {path}") from exc
    try:
        data = np.genfromtxt(path, delimiter=",", dtype=float)
    except Exception as exc:
        raise ValueError(f"Could not read numeric data from {path}") from exc
    if np.asarray(data).size == 0:
        raise ValueError(f"Numeric data file is empty: {path}")
    if np.any(np.isnan(data)):
        raise ValueError(f"Numeric data file contains non-numeric values: {path}")
    return data


def _load_material_matrix(path: Path) -> np.ndarray:
    if not path.exists():
        raise ValueError(f"File not found: {path}")
    if path.suffix.lower() == ".npy":
        data = np.load(path, allow_pickle=True)
    elif path.suffix.lower() in {".pkl", ".pickle"}:
        data = _load_pickle(path)
    else:
        data = np.genfromtxt(path, delimiter=",", dtype=str, comments=None, autostrip=True)
    data = np.asarray(data, dtype=str)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    return data


def _normalize_positions(positions: np.ndarray, cube_side_length: float) -> np.ndarray:
    min_coords = np.min(positions, axis=0)
    max_coords = np.max(positions, axis=0)
    spans = max_coords - min_coords
    max_span = float(np.max(spans))
    if max_span <= 0:
        raise ValueError("positions must span a non-zero distance.")
    return (positions - min_coords) * (cube_side_length / max_span)


def _create_beam(start_point: np.ndarray, end_point: np.ndarray, beam_diameter: float, sections: int) -> Optional[trimesh.Trimesh]:
    vector = np.asarray(end_point, dtype=float) - np.asarray(start_point, dtype=float)
    length = float(np.linalg.norm(vector))
    if length < 1e-12:
        return None
    direction = vector / length

    beam = cylinder(radius=beam_diameter / 2.0, height=length, sections=sections)
    beam.apply_translation(-beam.centroid)

    z_vector = np.array([0.0, 0.0, 1.0])
    axis = np.cross(z_vector, direction)
    axis_length = float(np.linalg.norm(axis))
    if axis_length < 1e-12:
        if float(np.dot(z_vector, direction)) < 0:
            beam.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [0, 1, 0], point=beam.centroid))
    else:
        axis = axis / axis_length
        angle = math.acos(float(np.clip(np.dot(z_vector, direction), -1.0, 1.0)))
        beam.apply_transform(trimesh.transformations.rotation_matrix(angle, axis, point=beam.centroid))

    beam.apply_translation((np.asarray(start_point, dtype=float) + np.asarray(end_point, dtype=float)) / 2.0)
    return beam


def _add_junction_spheres(
    positions: np.ndarray,
    incident: Mapping[int, List[Tuple[str, float]]],
    meshes_by_material: Dict[str, List[trimesh.Trimesh]],
    beam_diameter: float,
    junction_policy: str,
    mixed_junction_material: str,
    node_material: Optional[str],
    sphere_subdivisions: int,
    node_radius_scale: float,
) -> Dict[int, NodeReservation]:
    node_reservations = {}
    for idx, material_weights in incident.items():
        if not material_weights:
            continue
        max_weight = max(weight for _, weight in material_weights)
        radius = beam_diameter / 2.0 * max_weight * node_radius_scale
        if radius <= 0:
            continue

        unique_materials = sorted({material for material, _ in material_weights})
        if node_material:
            target_materials = [node_material]
        elif len(unique_materials) == 1:
            target_materials = unique_materials
        elif junction_policy == "separate":
            target_materials = [mixed_junction_material]
        else:
            target_materials = [_dominant_material(material_weights)]

        for material in target_materials:
            sphere = icosphere(radius=radius, subdivisions=sphere_subdivisions)
            center = tuple(float(value) for value in positions[idx][:3])
            sphere.apply_translation(center)
            meshes_by_material[material].append(sphere)
            if node_material and material == node_material:
                node_reservations[idx] = NodeReservation(sphere, radius, center)
    return node_reservations


def _apply_node_material_priority(
    meshes: List[trimesh.Trimesh],
    beam_records: List[BeamRecord],
    positions: np.ndarray,
    node_reservations: Mapping[int, NodeReservation],
    sections: int,
) -> List[trimesh.Trimesh]:
    if not beam_records:
        return meshes

    protected = []
    beam_count = min(len(meshes), len(beam_records))
    for record in beam_records[:beam_count]:
        source_reservation = node_reservations.get(record.source)
        target_reservation = node_reservations.get(record.target)
        if source_reservation is None or target_reservation is None:
            protected.append(record.mesh)
            continue
        cut_mesh = _create_node_cut_beam(
            positions[record.source][:3],
            positions[record.target][:3],
            record.diameter,
            source_reservation.radius,
            target_reservation.radius,
            sections=sections,
        )
        if cut_mesh is not None and not cut_mesh.is_empty:
            protected.append(cut_mesh)
    protected.extend(meshes[beam_count:])
    return protected


def _create_node_cut_beam(
    start_point: np.ndarray,
    end_point: np.ndarray,
    beam_diameter: float,
    source_radius: float,
    target_radius: float,
    sections: int,
) -> Optional[trimesh.Trimesh]:
    vector = np.asarray(end_point, dtype=float) - np.asarray(start_point, dtype=float)
    length = float(np.linalg.norm(vector))
    if length < 1e-12:
        return None
    direction = vector / length
    radius = beam_diameter / 2.0
    source_radius = max(float(source_radius), radius)
    target_radius = max(float(target_radius), radius)
    source_offset = math.sqrt(max(source_radius * source_radius - radius * radius, 0.0))
    target_offset = math.sqrt(max(target_radius * target_radius - radius * radius, 0.0))
    if source_offset + target_offset >= length:
        return None

    cap_steps = max(4, min(16, sections // 4))
    vertices: List[List[float]] = []
    faces: List[List[int]] = []

    def add_vertex(x: float, y: float, z: float) -> int:
        vertices.append([x, y, z])
        return len(vertices) - 1

    def add_ring(ring_radius: float, z: float) -> List[int]:
        ring = []
        for k in range(sections):
            angle = 2.0 * math.pi * k / sections
            ring.append(add_vertex(ring_radius * math.cos(angle), ring_radius * math.sin(angle), z))
        return ring

    def connect_rings(lower: List[int], upper: List[int]) -> None:
        for k in range(sections):
            k_next = (k + 1) % sections
            faces.append([lower[k], lower[k_next], upper[k]])
            faces.append([lower[k_next], upper[k_next], upper[k]])

    def add_center_fan(center: int, ring: List[int], reverse: bool = False) -> None:
        for k in range(sections):
            k_next = (k + 1) % sections
            if reverse:
                faces.append([center, ring[k_next], ring[k]])
            else:
                faces.append([center, ring[k], ring[k_next]])

    source_center = add_vertex(0.0, 0.0, source_radius)
    source_theta = math.asin(min(1.0, radius / source_radius))
    previous_ring = None
    source_rim = None
    for step in range(1, cap_steps + 1):
        theta = source_theta * step / cap_steps
        ring = add_ring(source_radius * math.sin(theta), source_radius * math.cos(theta))
        if previous_ring is None:
            add_center_fan(source_center, ring, reverse=True)
        else:
            connect_rings(ring, previous_ring)
        previous_ring = ring
        source_rim = ring

    target_theta = math.asin(min(1.0, radius / target_radius))
    target_rim = add_ring(radius, length - target_offset)
    if source_rim is not None:
        connect_rings(source_rim, target_rim)

    previous_ring = target_rim
    for step in range(cap_steps - 1, 0, -1):
        theta = target_theta * step / cap_steps
        ring = add_ring(target_radius * math.sin(theta), length - target_radius * math.cos(theta))
        connect_rings(previous_ring, ring)
        previous_ring = ring
    target_center = add_vertex(0.0, 0.0, length - target_radius)
    add_center_fan(target_center, previous_ring, reverse=False)

    mesh = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=False)
    z_vector = np.array([0.0, 0.0, 1.0])
    axis = np.cross(z_vector, direction)
    axis_length = float(np.linalg.norm(axis))
    if axis_length < 1e-12:
        if float(np.dot(z_vector, direction)) < 0:
            mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [0, 1, 0], point=[0, 0, 0]))
    else:
        axis = axis / axis_length
        angle = math.acos(float(np.clip(np.dot(z_vector, direction), -1.0, 1.0)))
        mesh.apply_transform(trimesh.transformations.rotation_matrix(angle, axis, point=[0, 0, 0]))
    mesh.apply_translation(np.asarray(start_point, dtype=float))
    mesh.merge_vertices()
    return mesh


def _combine_meshes(meshes: List[trimesh.Trimesh], boolean_union: bool) -> Optional[trimesh.Trimesh]:
    if not meshes:
        return None
    if boolean_union:
        prepared = [_repair_mesh(mesh.copy()) for mesh in meshes if mesh is not None and not mesh.is_empty]
        if not prepared:
            return None
        if len(prepared) == 1:
            mesh = prepared[0]
        else:
            mesh = trimesh.boolean.union(prepared)
    elif len(meshes) == 1:
        mesh = meshes[0].copy()
    else:
        mesh = trimesh.util.concatenate(meshes)
    return _repair_mesh(mesh)


def _repair_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    if mesh is None or mesh.is_empty:
        return mesh
    try:
        mesh.update_faces(mesh.nondegenerate_faces())
    except Exception:
        mesh.remove_degenerate_faces()
    try:
        mesh.update_faces(mesh.unique_faces())
    except Exception:
        try:
            mesh.remove_duplicate_faces()
        except Exception:
            pass
    mesh.remove_unreferenced_vertices()
    try:
        trimesh.repair.fix_normals(mesh)
    except Exception:
        pass
    try:
        trimesh.repair.fill_holes(mesh)
    except Exception:
        pass
    return mesh


def _write_preview_html(
    meshes_by_material: Mapping[str, trimesh.Trimesh],
    material_defs: Mapping[str, Any],
    output_path: Path,
    node_material: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not meshes_by_material:
        return None
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None

    traces = []
    materials = sorted(meshes_by_material)
    if node_material in materials:
        materials = [material for material in materials if material != node_material] + [str(node_material)]
    for idx, material in enumerate(materials):
        mesh = meshes_by_material[material]
        if mesh.is_empty or len(mesh.faces) == 0:
            continue
        color = _material_color(material, material_defs, idx)
        opacity = 0.68 if node_material in meshes_by_material and material != node_material else 1.0
        vertices = np.asarray(mesh.vertices)
        faces = np.asarray(mesh.faces)
        traces.append(
            go.Mesh3d(
                x=vertices[:, 0],
                y=vertices[:, 1],
                z=vertices[:, 2],
                i=faces[:, 0],
                j=faces[:, 1],
                k=faces[:, 2],
                name=str(material),
                color=color,
                opacity=opacity,
                flatshading=True,
                showlegend=True,
            )
        )

    if not traces:
        return None

    fig = go.Figure(data=traces)
    fig.update_layout(
        scene=dict(
            aspectmode="data",
            xaxis_title="x",
            yaxis_title="y",
            zaxis_title="z",
            camera=dict(eye=dict(x=2.4, y=2.4, z=2.4)),
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        title=output_path.stem,
        legend=dict(itemsizing="constant"),
    )
    fig.write_html(output_path, include_plotlyjs="cdn", full_html=True)
    return {"path": str(output_path), "trace_count": len(traces)}


def _mesh_result(material: str, output_path: Path, mesh: trimesh.Trimesh) -> Dict[str, Any]:
    return {
        "material": str(material),
        "path": str(output_path),
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "is_volume": bool(mesh.is_volume),
    }


def _validate_edges(edges: List[Edge], node_count: int) -> None:
    for edge in edges:
        if edge.source < 0 or edge.target < 0:
            raise ValueError(f"Edge has negative node index: {edge}")
        if edge.source >= node_count or edge.target >= node_count:
            raise ValueError(
                f"Edge ({edge.source}, {edge.target}) references a node outside positions count {node_count}."
            )


def _read_csv_rows(path: Path) -> List[List[str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        return [
            [cell.strip() for cell in row]
            for row in reader
            if row and not str(row[0]).strip().startswith("#")
        ]


def _looks_like_header(row: List[str]) -> bool:
    normalized = {cell.strip().lower() for cell in row}
    return bool(
        normalized
        & {
            "source",
            "from",
            "target",
            "to",
            "material",
            "material_id",
            "material_name",
            "material_type",
            "beam_type",
            "thickness",
            "weight",
        }
    )


def _header_map(row: List[str]) -> Dict[str, int]:
    aliases = {
        "from": "source",
        "i": "source",
        "node1": "source",
        "target": "target",
        "to": "target",
        "j": "target",
        "node2": "target",
        "weight": "thickness",
        "diameter": "thickness",
        "material_id": "material",
        "material_name": "material",
        "material_type": "material",
        "beam_type": "material",
    }
    mapping: Dict[str, int] = {}
    for idx, name in enumerate(row):
        key = name.strip().lower()
        key = aliases.get(key, key)
        mapping[key] = idx
    return mapping


def _column_index(value: Any, header: Optional[Mapping[str, int]], fallback: Optional[int]) -> Optional[int]:
    if value is None:
        if header is None:
            return fallback
        if fallback == 0:
            return header.get("source", fallback)
        if fallback == 1:
            return header.get("target", fallback)
        if fallback == 2:
            return header.get("thickness")
        if fallback == 3:
            return header.get("material")
        return fallback
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if value.isdigit():
            return int(value)
        if header is None:
            raise ValueError(f"Column name '{value}' requires a header row.")
        key = _header_map([value]).keys()
        canonical = next(iter(key))
        if canonical not in header:
            raise ValueError(f"Column '{value}' was not found in the header.")
        return header[canonical]
    raise ValueError(f"Invalid column selector: {value!r}")


def _edge_weight_from_row(
    row: List[str],
    thickness_col: Optional[int],
    variable_thickness: bool,
    has_header: bool,
    source: str,
    allow_ambiguous_text_thickness: bool,
) -> float:
    if not variable_thickness or thickness_col is None or thickness_col >= len(row):
        return 1.0

    value = _float_or_none(row[thickness_col])
    if value is not None:
        return value

    # Headerless three-column files are ambiguous: source,target,thickness
    # and source,target,material are both common. Text in the third column is
    # treated as material, with default thickness.
    if allow_ambiguous_text_thickness and not has_header and len(row) == 3 and thickness_col == 2:
        return 1.0

    raise ValueError(f"Invalid edge thickness in {source}: {row[thickness_col]!r}")


def _edge_material_from_row(
    row: List[str],
    material_col: Optional[int],
    default_material: str,
    has_header: bool,
    material_map: Optional[Mapping[str, str]] = None,
    explicit_material: bool = False,
    allow_heuristic: bool = True,
) -> str:
    material_map = material_map or {}
    if material_col is not None and material_col < len(row):
        return _material_from_code(row[material_col], default_material, material_map, explicit_material)
    if allow_heuristic and not has_header and len(row) == 3 and _float_or_none(row[2]) is None:
        return _material_from_code(row[2], default_material, material_map, explicit_material)
    return default_material


def _float_or_none(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _material_from_code(
    value: Any,
    default_material: str,
    material_map: Mapping[str, str],
    explicit_material: bool,
) -> str:
    text = "" if value is None else str(value).strip()
    if text == "" or text.lower() in {"none", "nan", "null"}:
        return default_material
    key = _material_code_key(value)
    if key in material_map:
        return material_map[key]
    if explicit_material and _float_or_none(text) is not None:
        return f"material_{key}"
    return _clean_material(value, default_material)


def _material_code_key(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    number = _float_or_none(text)
    if number is not None and math.isfinite(number) and number.is_integer():
        return str(int(number))
    return text


def _load_pickle(path: Path) -> Any:
    try:
        with path.open("rb") as f:
            return pickle.load(f)
    except Exception as exc:
        raise ValueError(f"Could not read pickle data from {path}") from exc


def _pickle_edge_rows_and_header(data: Any) -> Tuple[List[Any], Optional[List[str]]]:
    if hasattr(data, "columns") and hasattr(data, "to_numpy"):
        return data.to_numpy().tolist(), [str(column) for column in data.columns]

    if isinstance(data, Mapping):
        columns = data.get("columns") or data.get("header")
        rows = data.get("edges")
        if rows is None:
            rows = data.get("edge_list")
        if rows is None:
            rows = data.get("rows")
        if rows is None:
            rows = data.get("data")
        if rows is not None:
            return _rows_from_any(rows), [str(column) for column in columns] if columns else None
        if _mapping_has_edge_columns(data):
            return _records_from_column_mapping(data), None
        return [data], None

    if isinstance(data, tuple) and len(data) == 2:
        first, second = data
        if _looks_like_column_sequence(first):
            return _rows_from_any(second), [str(column) for column in first]
        if _looks_like_column_sequence(second):
            return _rows_from_any(first), [str(column) for column in second]

    return _rows_from_any(data), None


def _rows_from_any(value: Any) -> List[Any]:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    raise ValueError("Pickle edge-list data must contain rows, records, or an edge array.")


def _looks_like_column_sequence(value: Any) -> bool:
    if not isinstance(value, (list, tuple)):
        return False
    return bool(value) and all(isinstance(item, str) for item in value)


def _looks_like_mapping_records(rows: Iterable[Any]) -> bool:
    return all(isinstance(row, Mapping) for row in rows)


def _mapping_has_edge_columns(mapping: Mapping[str, Any]) -> bool:
    lower_keys = {str(key).strip().lower() for key in mapping}
    return bool(lower_keys & {"source", "from", "i", "node1"}) and bool(
        lower_keys & {"target", "to", "j", "node2"}
    )


def _records_from_column_mapping(mapping: Mapping[str, Any]) -> List[Dict[str, Any]]:
    lengths = {
        len(value)
        for value in mapping.values()
        if isinstance(value, (list, tuple, np.ndarray))
    }
    if len(lengths) != 1:
        raise ValueError("Column-oriented pickle edge data must have same-length columns.")
    length = lengths.pop()
    records = []
    for index in range(length):
        records.append({
            str(key): value[index] if isinstance(value, (list, tuple, np.ndarray)) else value
            for key, value in mapping.items()
        })
    return records


def _edges_from_mapping_edge_records(
    rows: Iterable[Mapping[str, Any]],
    job: Mapping[str, Any],
    variable_thickness: bool,
    default_material: str,
    material_lookup: Mapping[Tuple[int, int], str],
) -> List[Edge]:
    material_map = _edge_material_map(job)
    interpretation = _edge_list_interpretation(job)
    use_thickness = variable_thickness
    use_material = True
    if interpretation == "legacy":
        use_thickness = False
        use_material = False
    elif interpretation == "thickness":
        use_thickness = True
        use_material = False
    elif interpretation == "material":
        use_thickness = False
        use_material = True
    elif interpretation == "thickness_material":
        use_thickness = True
        use_material = True

    edges = []
    for row_index, row in enumerate(rows, start=1):
        try:
            source = int(float(_mapping_column_value(row, "source")))
            target = int(float(_mapping_column_value(row, "target")))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid edge endpoints in pickle record {row_index}: {row}") from exc

        thickness_value = _mapping_column_value(row, "thickness", default=None)
        weight = float(thickness_value) if use_thickness and thickness_value is not None else 1.0
        material = default_material
        if use_material:
            material_value = _mapping_column_value(row, "material", default=None)
            material = _material_from_code(
                material_value,
                default_material,
                material_map,
                explicit_material=material_value is not None,
            )
        material = material_lookup.get(_edge_key(source, target), material)
        if weight > 0:
            edges.append(Edge(source, target, weight, material))
    return edges


def _mapping_column_value(row: Mapping[str, Any], canonical: str, default: Any = None) -> Any:
    aliases = {
        "source": ["source", "from", "i", "node1"],
        "target": ["target", "to", "j", "node2"],
        "thickness": ["thickness", "weight", "diameter"],
        "material": ["material", "material_id", "material_name", "material_type", "beam_type"],
    }
    lower = {str(key).strip().lower(): value for key, value in row.items()}
    for key in aliases[canonical]:
        if key in lower:
            return lower[key]
    return default


def _merged_object(parent: Any, child: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    if isinstance(parent, Mapping):
        result.update(parent)
    if isinstance(child, Mapping):
        result.update(child)
    return result


def _required_path(job: Mapping[str, Any], primary: str, fallback: str) -> str:
    value = job.get(primary) or job.get(fallback)
    if not value:
        raise ValueError(f"Job must define '{primary}'.")
    return str(value)


def _resolve_path(base_dir: Path, value: Any) -> Path:
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _default_job_name(path_value: Any) -> str:
    stem = Path(str(path_value)).stem
    return stem.replace("_adj", "").replace("-adj", "")


def _edge_key(source: int, target: int) -> Tuple[int, int]:
    return (source, target) if source <= target else (target, source)


def _parse_edge_key(value: str) -> Tuple[int, int]:
    parts = re.split(r"[\s,;:\-]+", value.strip())
    parts = [part for part in parts if part]
    if len(parts) != 2:
        raise ValueError(f"Edge key must contain exactly two node indices: {value!r}")
    return int(parts[0]), int(parts[1])


def _material_from_matrix(
    matrix: np.ndarray,
    source: int,
    target: int,
    default_material: str,
) -> str:
    material = _clean_material(matrix[source, target], "")
    if not material:
        material = _clean_material(matrix[target, source], "")
    return material or default_material


def _clean_material(value: Any, default_material: str) -> str:
    text = "" if value is None else str(value).strip()
    if text == "" or text.lower() in {"0", "none", "nan", "null"}:
        return default_material
    return text


def _dominant_material(material_weights: List[Tuple[str, float]]) -> str:
    totals: Dict[str, float] = defaultdict(float)
    for material, weight in material_weights:
        totals[material] += float(weight)
    return max(totals.items(), key=lambda item: item[1])[0]


def _material_color(material: str, material_defs: Mapping[str, Any], index: int) -> str:
    definition = material_defs.get(material)
    if isinstance(definition, Mapping):
        color = definition.get("color")
        if color:
            return str(color)
    return PALETTE[index % len(PALETTE)]


def _slug(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip())
    text = text.strip("._")
    return text or "output"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate one STL per material from a JSON config.")
    parser.add_argument("config", help="Path to a JSON configuration file.")
    args = parser.parse_args()
    result = generate_from_config_file(args.config)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
