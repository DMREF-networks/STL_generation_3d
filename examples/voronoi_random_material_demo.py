"""Generate a bounded Voronoi network with random edge materials.

The generated files are intended as a teaching example:

* around 150 graph nodes from a 2D Voronoi tessellation
* edges randomly assigned to one of two material labels
* all node junctions assigned to one shared node material
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, box


DEFAULT_OUTPUT_DIR = Path("sample_configs/voronoi_random_material_demo")


def generate_demo(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    seed_count: int = 75,
    seed: int = 23,
    material_a: str = "material_a",
    material_b: str = "material_b",
    node_material: str = "node_material",
) -> Dict[str, Any]:
    """Write Voronoi demo CSV/config files and return a summary."""
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    positions, edges = _bounded_voronoi_graph(seed_count=seed_count, seed=seed)
    rng = np.random.default_rng(seed)

    xy_path = output_dir / "voronoi_material_demo_xy.csv"
    edge_path = output_dir / "voronoi_material_demo_edges.csv"
    node_path = output_dir / "voronoi_material_demo_node_materials.csv"
    config_path = output_dir / "voronoi_material_demo.json"

    repo_root = Path(__file__).resolve().parent.parent
    stl_output_dir = repo_root / "samples_output" / "voronoi_random_material_demo"

    _write_positions(xy_path, positions)
    _write_edges(edge_path, edges, rng, material_a, material_b)
    _write_node_materials(node_path, len(positions), node_material)

    config = {
        "output_dir": os.path.relpath(stl_output_dir, output_dir),
        "default_material": material_a,
        "geometry": {
            "beam_diameter_mm": 0.18,
            "cube_side_length_mm": 50,
            "variable_thickness": True,
            "node_material": node_material,
            "junction_policy": "separate",
            "mixed_junction_material": node_material,
            "boolean_union": False,
        },
        "materials": {
            material_a: {"color": "#2563eb"},
            material_b: {"color": "#dc2626"},
            node_material: {"color": "#4b5563"},
        },
        "jobs": [
            {
                "name": "voronoi_random_material_demo",
                "positions": "voronoi_material_demo_xy.csv",
                "adjacency": "voronoi_material_demo_edges.csv",
                "adjacency_format": "edge_list",
            }
        ],
    }
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    return {
        "source": "bounded_voronoi",
        "seed_count": int(seed_count),
        "seed": int(seed),
        "config_path": str(config_path),
        "positions_path": str(xy_path),
        "edge_list_path": str(edge_path),
        "node_materials_path": str(node_path),
        "node_count": int(len(positions)),
        "edge_count": int(len(edges)),
        "materials": [material_a, material_b],
        "node_material": node_material,
    }


def _bounded_voronoi_graph(seed_count: int, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    """Build a clipped Voronoi graph inside the unit square."""
    if seed_count < 4:
        raise ValueError("seed_count must be at least 4.")

    rng = np.random.default_rng(seed)
    points = rng.uniform(0.0, 1.0, size=(seed_count, 2))

    # Guard points outside the box make boundary cells well behaved.
    guard_points = np.array(
        [
            [-0.2, -0.2],
            [-0.2, 0.5],
            [-0.2, 1.2],
            [0.5, -0.2],
            [0.5, 1.2],
            [1.2, -0.2],
            [1.2, 0.5],
            [1.2, 1.2],
        ],
        dtype=float,
    )
    vor = Voronoi(np.vstack([points, guard_points]))
    regions, vertices = _finite_voronoi_polygons_2d(vor, radius=3.0)
    bounding_box = box(0.0, 0.0, 1.0, 1.0)

    vertex_lookup: Dict[Tuple[float, float], int] = {}
    graph_vertices: List[List[float]] = []
    graph_edges = set()

    def vertex_id(coord: Tuple[float, float]) -> int:
        key = (round(float(coord[0]), 8), round(float(coord[1]), 8))
        if key not in vertex_lookup:
            vertex_lookup[key] = len(graph_vertices)
            graph_vertices.append([key[0], key[1], 0.0])
        return vertex_lookup[key]

    for region in regions[:seed_count]:
        polygon = Polygon(vertices[region])
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        clipped = polygon.intersection(bounding_box)
        if clipped.is_empty:
            continue
        geoms = list(clipped.geoms) if clipped.geom_type == "MultiPolygon" else [clipped]
        for geom in geoms:
            coords = list(geom.exterior.coords)
            for a, b in zip(coords, coords[1:]):
                if np.linalg.norm(np.asarray(a) - np.asarray(b)) < 1e-10:
                    continue
                ia = vertex_id(a)
                ib = vertex_id(b)
                if ia != ib:
                    graph_edges.add(tuple(sorted((ia, ib))))

    positions = np.asarray(graph_vertices, dtype=float)
    edge_rows = [[u, v, 1.0] for u, v in sorted(graph_edges)]
    return positions, np.asarray(edge_rows, dtype=float)


def _finite_voronoi_polygons_2d(vor: Voronoi, radius: float) -> Tuple[List[List[int]], np.ndarray]:
    """Reconstruct infinite Voronoi regions as finite polygons."""
    if vor.points.shape[1] != 2:
        raise ValueError("Only 2D Voronoi diagrams are supported.")

    new_regions: List[List[int]] = []
    new_vertices = vor.vertices.tolist()
    center = vor.points.mean(axis=0)

    all_ridges: Dict[int, List[Tuple[int, int, int]]] = {}
    for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
        all_ridges.setdefault(p1, []).append((p2, v1, v2))
        all_ridges.setdefault(p2, []).append((p1, v1, v2))

    for p1, region_idx in enumerate(vor.point_region):
        vertices = vor.regions[region_idx]
        if all(v >= 0 for v in vertices):
            new_regions.append(vertices)
            continue

        new_region = [v for v in vertices if v >= 0]
        for p2, v1, v2 in all_ridges[p1]:
            if v2 < 0:
                v1, v2 = v2, v1
            if v1 >= 0:
                continue

            tangent = vor.points[p2] - vor.points[p1]
            tangent = tangent / np.linalg.norm(tangent)
            normal = np.array([-tangent[1], tangent[0]])
            midpoint = vor.points[[p1, p2]].mean(axis=0)
            direction = np.sign(np.dot(midpoint - center, normal)) * normal
            far_point = vor.vertices[v2] + direction * radius

            new_region.append(len(new_vertices))
            new_vertices.append(far_point.tolist())

        region_points = np.asarray([new_vertices[v] for v in new_region])
        centroid = region_points.mean(axis=0)
        angles = np.arctan2(region_points[:, 1] - centroid[1], region_points[:, 0] - centroid[0])
        new_region = np.asarray(new_region)[np.argsort(angles)].tolist()
        new_regions.append(new_region)

    return new_regions, np.asarray(new_vertices)


def _write_positions(path: Path, positions: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(positions.tolist())


def _write_edges(path: Path, edges: np.ndarray, rng: np.random.Generator, material_a: str, material_b: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "target", "thickness", "material"])
        for source, target, thickness in edges:
            material = rng.choice([material_a, material_b])
            writer.writerow([int(source), int(target), float(thickness), material])


def _write_node_materials(path: Path, node_count: int, node_material: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["node", "material"])
        for node in range(node_count):
            writer.writerow([node, node_material])


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Voronoi random-material STL demo config.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--seed-count", type=int, default=75)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--material-a", default="material_a")
    parser.add_argument("--material-b", default="material_b")
    parser.add_argument("--node-material", default="node_material")
    args = parser.parse_args()

    result = generate_demo(
        output_dir=args.output_dir,
        seed_count=args.seed_count,
        seed=args.seed,
        material_a=args.material_a,
        material_b=args.material_b,
        node_material=args.node_material,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
