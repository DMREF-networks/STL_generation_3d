"""Generate a random-material edge-list demo config.

The primary demo source is the SR centerline-network generator from the
neighboring sr_huppi_project repository. If that repository is unavailable,
the script falls back to a small self-contained k-nearest-neighbor network so
the example still works from a fresh clone of this repository.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np


DEFAULT_OUTPUT_DIR = Path("sample_configs/random_edge_material_demo")


def generate_demo(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    source: str = "auto",
    sr_repo: str | Path | None = None,
    size: int = 35,
    alpha: float = 0.5,
    seed: int = 7,
    material_a: str = "edge_material_a",
    material_b: str = "edge_material_b",
    node_material: str = "node_material",
) -> Dict[str, Any]:
    """Create demo CSV files plus a config JSON, returning output paths."""
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if source not in {"auto", "sr", "synthetic"}:
        raise ValueError("source must be one of: auto, sr, synthetic")

    rng = np.random.default_rng(seed)
    actual_source = source
    if source in {"auto", "sr"}:
        try:
            positions, edges = _generate_sr_network(size=size, alpha=alpha, seed=seed, sr_repo=sr_repo)
            actual_source = "sr_huppi_project"
        except Exception:
            if source == "sr":
                raise
            positions, edges = _generate_synthetic_network(node_count=max(18, size), seed=seed)
            actual_source = "synthetic_k_nearest"
    else:
        positions, edges = _generate_synthetic_network(node_count=max(18, size), seed=seed)
        actual_source = "synthetic_k_nearest"

    xy_path = output_dir / "edge_material_demo_xy.csv"
    edge_path = output_dir / "edge_material_demo_edges.csv"
    node_path = output_dir / "edge_material_demo_node_materials.csv"
    config_path = output_dir / "edge_material_demo.json"
    repo_root = Path(__file__).resolve().parent.parent
    stl_output_dir = repo_root / "samples_output" / "random_edge_material_demo"

    _write_positions(xy_path, positions)
    _write_edges(edge_path, edges, rng, material_a, material_b)
    _write_node_materials(node_path, len(positions), node_material)

    config = {
        "output_dir": os.path.relpath(stl_output_dir, output_dir),
        "default_material": material_a,
        "geometry": {
            "beam_diameter_mm": 0.25,
            "cube_side_length_mm": 35,
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
                "name": "random_edge_material_demo",
                "positions": "edge_material_demo_xy.csv",
                "adjacency": "edge_material_demo_edges.csv",
                "adjacency_format": "edge_list",
            }
        ],
    }
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    return {
        "source": actual_source,
        "config_path": str(config_path),
        "positions_path": str(xy_path),
        "edge_list_path": str(edge_path),
        "node_materials_path": str(node_path),
        "node_count": int(len(positions)),
        "edge_count": int(len(edges)),
        "materials": [material_a, material_b],
        "node_material": node_material,
    }


def _generate_sr_network(
    size: int,
    alpha: float,
    seed: int,
    sr_repo: str | Path | None,
) -> Tuple[np.ndarray, np.ndarray]:
    repo = Path(sr_repo or os.environ.get("SR_HUPPI_PROJECT", "/home/james/sr_huppi_project")).expanduser()
    if not repo.exists():
        raise FileNotFoundError(f"SR repo not found: {repo}")

    sys.path.insert(0, str(repo.resolve()))
    try:
        from src.sr_code.generate_line_segments_dynamic_thickness import (
            generate_line_segments_dynamic_thickness,
        )
        from src.centerline_network import sr_to_centerline_network
    finally:
        try:
            sys.path.remove(str(repo.resolve()))
        except ValueError:
            pass

    np.random.seed(seed)
    t_steps = np.arange(1, size + 1)
    thickness_arr = 0.05 * np.power(t_steps, -alpha)
    with contextlib.redirect_stdout(io.StringIO()):
        segments_dict, _polygon_arr, segment_thickness_dict, _config = generate_line_segments_dynamic_thickness(
            size=size,
            thickness_arr=thickness_arr,
            angles="uniform",
            epsilon=0.001,
            box_size=1.0,
        )
        edge_list, _num_nodes, node_info = sr_to_centerline_network(segment_thickness_dict, segments_dict)
    if len(edge_list) == 0:
        raise ValueError("SR generator returned no edges.")

    node_ids = sorted(nid for nid in node_info if isinstance(nid, int))
    node_map = {old: new for new, old in enumerate(node_ids)}
    positions = []
    for old in node_ids:
        coord = np.asarray(node_info[old]["coord"], dtype=float)
        positions.append([coord[0], coord[1], 0.0])

    edges = []
    for row in np.asarray(edge_list):
        u_old, v_old = int(row[0]), int(row[1])
        if u_old in node_map and v_old in node_map:
            edges.append([node_map[u_old], node_map[v_old], 1.0])
    if not edges:
        raise ValueError("SR generator returned no mappable edges.")
    return np.asarray(positions, dtype=float), np.asarray(edges, dtype=float)


def _generate_synthetic_network(node_count: int, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    positions_2d = rng.uniform(0.0, 1.0, size=(node_count, 2))
    positions = np.hstack([positions_2d, np.zeros((node_count, 1))])

    edges = set()
    k = min(3, max(1, node_count - 1))
    for i in range(node_count):
        deltas = positions_2d - positions_2d[i]
        dist2 = np.einsum("ij,ij->i", deltas, deltas)
        neighbors = np.argsort(dist2)[1 : k + 1]
        for j in neighbors:
            edges.add(tuple(sorted((int(i), int(j)))))

    edge_rows = [[u, v, 1.0] for u, v in sorted(edges)]
    return positions, np.asarray(edge_rows, dtype=float)


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
    parser = argparse.ArgumentParser(description="Generate a random two-material edge-list STL demo config.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--source", choices=["auto", "sr", "synthetic"], default="auto")
    parser.add_argument("--sr-repo", default=None)
    parser.add_argument("--size", type=int, default=35)
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--material-a", default="edge_material_a")
    parser.add_argument("--material-b", default="edge_material_b")
    parser.add_argument("--node-material", default="node_material")
    args = parser.parse_args()

    result = generate_demo(
        output_dir=args.output_dir,
        source=args.source,
        sr_repo=args.sr_repo,
        size=args.size,
        alpha=args.alpha,
        seed=args.seed,
        material_a=args.material_a,
        material_b=args.material_b,
        node_material=args.node_material,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
