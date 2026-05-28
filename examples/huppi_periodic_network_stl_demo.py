"""Generate periodic HuPPI network STL examples.

This demo uses the neighboring HuPPI-Network-Analysis repository to build one
disordered lattice point pattern and four periodic, box-clipped network types:
Gabriel, Delaunay, Delaunay-centroidal, and Voronoi.

For each network type it writes three STL-generation configurations:

* uniform thickness, one beam material
* random variable thickness, one beam material
* two random beam materials plus a separate node material
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import types
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config_to_stl import generate_from_config_file


DEFAULT_OUTPUT_DIR = Path("sample_configs/huppi_periodic_a05_demo")
DEFAULT_HUPPI_REPO = Path("/home/james/HuPPI-Network-Analysis")
GRAPH_TYPES = {
    "gabriel": "clipped_gabriel_graph",
    "delaunay": "clipped_delaunay_tessellation",
    "delaunay_centroidal": "clipped_delaunay_centroidal",
    "voronoi": "clipped_voronoi_tessellation",
}
MATERIALS = {
    "beam_default": {"color": "#2563eb"},
    "beam_material_a": {"color": "#2563eb"},
    "beam_material_b": {"color": "#dc2626"},
    "node_material": {"color": "#f59e0b"},
}


def generate_demo(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    huppi_repo: str | Path = DEFAULT_HUPPI_REPO,
    lattice_size: int = 12,
    alpha: float = 0.5,
    seed: int = 20260528,
    beam_diameter_mm: float = 0.25,
    cube_side_length_mm: float = 30.0,
    generate_stls: bool = True,
) -> Dict[str, Any]:
    """Generate input files, configs, and optionally STL files."""
    output_dir = Path(output_dir).expanduser().resolve()
    stl_root = REPO_ROOT / "samples_output" / output_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "points").mkdir(parents=True, exist_ok=True)

    LatticeGenerator, GraphGenerator = _load_huppi_generators(huppi_repo)
    points, box_size = _generate_huppi_points(LatticeGenerator, lattice_size, alpha, seed)
    _write_positions(output_dir / "points" / "underlying_points.csv", _to_3d(points))

    rng = np.random.default_rng(seed)
    summary: Dict[str, Any] = {
        "source": "HuPPI-Network-Analysis",
        "huppi_repo": str(Path(huppi_repo).expanduser().resolve()),
        "output_dir": _repo_path(output_dir),
        "stl_output_dir": _repo_path(stl_root),
        "lattice_size": int(lattice_size),
        "point_count": int(len(points)),
        "alpha": float(alpha),
        "seed": int(seed),
        "box_size": np.asarray(box_size, dtype=float).tolist(),
        "graph_types": {},
    }

    graph_generator = GraphGenerator(points, box_size)
    for graph_type, method_name in GRAPH_TYPES.items():
        network_dir = output_dir / graph_type
        network_dir.mkdir(parents=True, exist_ok=True)
        nodes, edges = _generate_graph(graph_generator, method_name)
        nodes = _to_3d(nodes)
        edges = _dedupe_edges(edges)

        _write_positions(network_dir / "nodes.csv", nodes)
        _write_uniform_edges(network_dir / "edges_uniform.csv", edges)
        variable_edges = _with_random_thickness(edges, rng)
        _write_weighted_edges(network_dir / "edges_variable_thickness.csv", variable_edges)
        material_edges = _with_random_materials(edges, rng)
        _write_material_edges(network_dir / "edges_two_materials.csv", material_edges)
        _write_node_materials(network_dir / "node_materials.csv", len(nodes), "node_material")

        configs = []
        configs.append(
            _write_config(
                network_dir,
                stl_root,
                graph_type,
                variant="uniform_thickness",
                edge_file="edges_uniform.csv",
                default_material="beam_default",
                materials={"beam_default": MATERIALS["beam_default"]},
                variable_thickness=False,
                node_material=None,
                beam_diameter_mm=beam_diameter_mm,
                cube_side_length_mm=cube_side_length_mm,
            )
        )
        configs.append(
            _write_config(
                network_dir,
                stl_root,
                graph_type,
                variant="variable_thickness",
                edge_file="edges_variable_thickness.csv",
                default_material="beam_default",
                materials={"beam_default": MATERIALS["beam_default"]},
                variable_thickness=True,
                node_material=None,
                beam_diameter_mm=beam_diameter_mm,
                cube_side_length_mm=cube_side_length_mm,
            )
        )
        configs.append(
            _write_config(
                network_dir,
                stl_root,
                graph_type,
                variant="two_materials",
                edge_file="edges_two_materials.csv",
                default_material="beam_material_a",
                materials={
                    "beam_material_a": MATERIALS["beam_material_a"],
                    "beam_material_b": MATERIALS["beam_material_b"],
                    "node_material": MATERIALS["node_material"],
                },
                variable_thickness=False,
                node_material="node_material",
                beam_diameter_mm=beam_diameter_mm,
                cube_side_length_mm=cube_side_length_mm,
            )
        )

        stl_results = []
        if generate_stls:
            for config_path in configs:
                stl_results.append(_compact_stl_result(generate_from_config_file(str(config_path))))

        summary["graph_types"][graph_type] = {
            "node_count": int(len(nodes)),
            "edge_count": int(len(edges)),
            "configs": [_repo_path(path) for path in configs],
            "stl_results": stl_results,
            "thickness_range": [0.5, 2.0],
            "materials": ["beam_material_a", "beam_material_b", "node_material"],
        }

    manifest_path = output_dir / "manifest.json"
    summary["manifest_path"] = _repo_path(manifest_path)
    manifest_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _load_huppi_generators(huppi_repo: str | Path) -> Tuple[Any, Any]:
    repo = Path(huppi_repo).expanduser().resolve()
    if not repo.exists():
        raise FileNotFoundError(f"HuPPI-Network-Analysis repo not found: {repo}")

    # The top-level utils package imports analysis tools that may depend on
    # GraphRicciCurvature. The generators do not need that package, so a small
    # stub keeps this teaching example lightweight.
    stub = types.ModuleType("GraphRicciCurvature")
    stub.OllivierRicci = types.ModuleType("OllivierRicci")
    stub.OllivierRicci.OllivierRicci = None
    sys.modules.setdefault("GraphRicciCurvature", stub)
    sys.modules.setdefault("GraphRicciCurvature.OllivierRicci", stub.OllivierRicci)

    sys.path.insert(0, str(repo))
    try:
        from utils.network.generators import GraphGenerator, LatticeGenerator
    finally:
        try:
            sys.path.remove(str(repo))
        except ValueError:
            pass
    return LatticeGenerator, GraphGenerator


def _generate_huppi_points(
    LatticeGenerator: Any,
    lattice_size: int,
    alpha: float,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray]:
    np.random.seed(seed)
    generator = LatticeGenerator(lattice_size, dimensions=2, C=1)
    generator.generate_lattice()
    generator.perturb_lattice(alpha)
    return np.asarray(generator.points, dtype=float), np.asarray(generator.box_size, dtype=float)


def _generate_graph(graph_generator: Any, method_name: str) -> Tuple[np.ndarray, np.ndarray]:
    method = getattr(graph_generator, method_name)
    result = method()
    nodes = np.asarray(result[0], dtype=float)
    edges = np.asarray(result[1], dtype=float)
    if edges.size == 0:
        raise ValueError(f"{method_name} returned no edges.")
    return nodes, edges


def _to_3d(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] not in {2, 3}:
        raise ValueError("Point array must have shape (N, 2) or (N, 3).")
    if points.shape[1] == 3:
        return points
    return np.column_stack([points, np.zeros(len(points))])


def _dedupe_edges(edges: np.ndarray) -> np.ndarray:
    edge_pairs = edges[:, :2].astype(int)
    edge_pairs.sort(axis=1)
    unique = sorted(set(map(tuple, edge_pairs.tolist())))
    return np.asarray(unique, dtype=int)


def _with_random_thickness(edges: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    thickness = rng.uniform(0.5, 2.0, size=len(edges))
    return np.column_stack([edges, thickness])


def _with_random_materials(edges: np.ndarray, rng: np.random.Generator) -> List[Tuple[int, int, float, str]]:
    rows = []
    for source, target in edges:
        material = rng.choice(["beam_material_a", "beam_material_b"])
        rows.append((int(source), int(target), 1.0, str(material)))
    return rows


def _write_positions(path: Path, positions: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerows(np.asarray(positions, dtype=float).tolist())


def _write_uniform_edges(path: Path, edges: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["source", "target"])
        writer.writerows(edges.astype(int).tolist())


def _write_weighted_edges(path: Path, edges: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["source", "target", "thickness"])
        for source, target, thickness in edges:
            writer.writerow([int(source), int(target), f"{float(thickness):.8f}"])


def _write_material_edges(path: Path, rows: Iterable[Tuple[int, int, float, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["source", "target", "thickness", "material"])
        for source, target, thickness, material in rows:
            writer.writerow([int(source), int(target), f"{float(thickness):.8f}", material])


def _write_node_materials(path: Path, node_count: int, node_material: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["node", "material"])
        for node in range(node_count):
            writer.writerow([node, node_material])


def _write_config(
    network_dir: Path,
    stl_root: Path,
    graph_type: str,
    variant: str,
    edge_file: str,
    default_material: str,
    materials: Dict[str, Dict[str, str]],
    variable_thickness: bool,
    node_material: str | None,
    beam_diameter_mm: float,
    cube_side_length_mm: float,
) -> Path:
    output_dir = stl_root / graph_type / variant
    geometry: Dict[str, Any] = {
        "beam_diameter_mm": beam_diameter_mm,
        "cube_side_length_mm": cube_side_length_mm,
        "variable_thickness": variable_thickness,
        "junction_policy": "separate",
        "mixed_junction_material": "node_material",
        "boolean_union": False,
    }
    if node_material:
        geometry["node_material"] = node_material
        geometry["node_material_priority"] = True
        geometry["node_radius_scale"] = 1.35

    config = {
        "output_dir": os.path.relpath(output_dir, network_dir),
        "default_material": default_material,
        "geometry": geometry,
        "materials": materials,
        "jobs": [
            {
                "name": f"{graph_type}_{variant}",
                "positions": "nodes.csv",
                "adjacency": edge_file,
                "adjacency_format": "edge_list",
            }
        ],
    }
    config_path = network_dir / f"{variant}.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config_path


def _compact_stl_result(result: Dict[str, Any]) -> Dict[str, Any]:
    compact_jobs = []
    for job in result.get("jobs", []):
        preview = job.get("preview") or {}
        compact_jobs.append(
            {
                "name": job.get("name"),
                "edge_count": job.get("edge_count"),
                "material_count": job.get("material_count"),
                "outputs": [
                    {
                        "material": output.get("material"),
                        "path": _repo_path(output.get("path")),
                        "faces": output.get("faces"),
                        "watertight": output.get("watertight"),
                        "is_volume": output.get("is_volume"),
                    }
                    for output in job.get("outputs", [])
                ],
                "preview": _repo_path(preview.get("path")) if preview.get("path") else None,
            }
        )
    return {"jobs": compact_jobs}


def _repo_path(path: Any) -> str:
    path = Path(str(path)).expanduser().resolve()
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate periodic HuPPI STL demo networks.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--huppi-repo", default=str(DEFAULT_HUPPI_REPO))
    parser.add_argument("--lattice-size", type=int, default=12)
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=20260528)
    parser.add_argument("--beam-diameter-mm", type=float, default=0.25)
    parser.add_argument("--cube-side-length-mm", type=float, default=30.0)
    parser.add_argument("--skip-stl", action="store_true", help="Only write CSV/config files.")
    args = parser.parse_args()

    result = generate_demo(
        output_dir=args.output_dir,
        huppi_repo=args.huppi_repo,
        lattice_size=args.lattice_size,
        alpha=args.alpha,
        seed=args.seed,
        beam_diameter_mm=args.beam_diameter_mm,
        cube_side_length_mm=args.cube_side_length_mm,
        generate_stls=not args.skip_stl,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
