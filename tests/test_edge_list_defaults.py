import pickle
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

import numpy as np
import trimesh

from config_to_stl import generate_from_config_data
from config_to_stl import _add_junction_spheres
from config_to_stl import _load_edges
from config_to_stl import _load_node_diameters


class EdgeListDefaultsTest(unittest.TestCase):
    def test_two_column_edge_list_uses_default_weight_and_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edges_path = root / "edges.csv"
            edges_path.write_text("source,target\n0,1\n1,2\n", encoding="utf-8")

            edges = _load_edges(
                edges_path,
                {"adjacency_format": "edge_list"},
                variable_thickness=False,
                default_material="rigid",
                material_lookup={},
                base_dir=root,
            )

        self.assertEqual([(edge.source, edge.target, edge.weight, edge.material) for edge in edges], [
            (0, 1, 1.0, "rigid"),
            (1, 2, 1.0, "rigid"),
        ])

    def test_three_column_numeric_edge_list_uses_thickness_only_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edges_path = root / "edges.csv"
            edges_path.write_text("0,1,0.5\n1,2,2.0\n", encoding="utf-8")

            fixed_edges = _load_edges(
                edges_path,
                {"adjacency_format": "edge_list"},
                variable_thickness=False,
                default_material="rigid",
                material_lookup={},
                base_dir=root,
            )
            variable_edges = _load_edges(
                edges_path,
                {"adjacency_format": "edge_list"},
                variable_thickness=True,
                default_material="rigid",
                material_lookup={},
                base_dir=root,
            )

        self.assertEqual([edge.weight for edge in fixed_edges], [1.0, 1.0])
        self.assertEqual([edge.weight for edge in variable_edges], [0.5, 2.0])
        self.assertEqual([edge.material for edge in variable_edges], ["rigid", "rigid"])

    def test_explicit_legacy_edge_list_ignores_third_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edges_path = root / "edges.npy"
            np.save(edges_path, np.array([
                [0, 1, 99],
                [1, 2, 42],
            ]))

            edges = _load_edges(
                edges_path,
                {
                    "adjacency_format": "edge_list",
                    "edge_list_interpretation": "legacy",
                },
                variable_thickness=True,
                default_material="rigid",
                material_lookup={},
                base_dir=root,
            )

        self.assertEqual([(edge.weight, edge.material) for edge in edges], [
            (1.0, "rigid"),
            (1.0, "rigid"),
        ])

    def test_explicit_material_code_edge_list_uses_configured_material_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edges_path = root / "edges.npy"
            np.save(edges_path, np.array([
                [0, 1, 0],
                [1, 2, 1],
                [2, 3, 0],
            ]))

            edges = _load_edges(
                edges_path,
                {
                    "adjacency_format": "edge_list",
                    "edge_list_interpretation": "material",
                    "edge_material_map": {
                        "0": "material_a",
                        "1": "material_b",
                    },
                },
                variable_thickness=True,
                default_material="default",
                material_lookup={},
                base_dir=root,
            )

        self.assertEqual([edge.weight for edge in edges], [1.0, 1.0, 1.0])
        self.assertEqual([edge.material for edge in edges], ["material_a", "material_b", "material_a"])

    def test_explicit_thickness_material_edge_list_uses_both_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edges_path = root / "edges.npy"
            np.save(edges_path, np.array([
                [0, 1, 0.5, 0],
                [1, 2, 2.0, 1],
            ]))

            edges = _load_edges(
                edges_path,
                {
                    "adjacency_format": "edge_list",
                    "edge_list_interpretation": "thickness_material",
                    "edge_material_map": {
                        "0": "soft",
                        "1": "stiff",
                    },
                },
                variable_thickness=False,
                default_material="default",
                material_lookup={},
                base_dir=root,
            )

        self.assertEqual([(edge.weight, edge.material) for edge in edges], [
            (0.5, "soft"),
            (2.0, "stiff"),
        ])

    def test_explicit_thickness_edge_list_rejects_material_text_in_third_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edges_path = root / "edges.csv"
            edges_path.write_text("0,1,soft\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Invalid edge thickness"):
                _load_edges(
                    edges_path,
                    {
                        "adjacency_format": "edge_list",
                        "edge_list_interpretation": "thickness",
                    },
                    variable_thickness=False,
                    default_material="rigid",
                    material_lookup={},
                    base_dir=root,
                )

    def test_three_column_material_edge_list_can_omit_thickness_with_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edges_path = root / "edges.csv"
            edges_path.write_text("source,target,material\n0,1,flexible\n1,2,rigid\n", encoding="utf-8")

            edges = _load_edges(
                edges_path,
                {"adjacency_format": "edge_list"},
                variable_thickness=True,
                default_material="default",
                material_lookup={},
                base_dir=root,
            )

        self.assertEqual([edge.weight for edge in edges], [1.0, 1.0])
        self.assertEqual([edge.material for edge in edges], ["flexible", "rigid"])

    def test_pickle_edge_list_with_columns_disambiguates_material_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edges_path = root / "edges.pkl"
            with edges_path.open("wb") as f:
                pickle.dump({
                    "columns": ["source", "target", "material"],
                    "edges": [
                        [0, 1, "flexible"],
                        [1, 2, "rigid"],
                    ],
                }, f)

            edges = _load_edges(
                edges_path,
                {"adjacency_format": "edge_list"},
                variable_thickness=True,
                default_material="rigid",
                material_lookup={},
                base_dir=root,
            )

        self.assertEqual([edge.weight for edge in edges], [1.0, 1.0])
        self.assertEqual([edge.material for edge in edges], ["flexible", "rigid"])

    def test_pickle_edge_list_with_columns_preserves_thickness_and_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edges_path = root / "edges.pkl"
            with edges_path.open("wb") as f:
                pickle.dump({
                    "columns": ["source", "target", "thickness", "material"],
                    "edges": [
                        [0, 1, 0.5, "flexible"],
                        [1, 2, 2.0, "rigid"],
                    ],
                }, f)

            edges = _load_edges(
                edges_path,
                {"adjacency_format": "edge_list"},
                variable_thickness=True,
                default_material="default",
                material_lookup={},
                base_dir=root,
            )

        self.assertEqual([edge.weight for edge in edges], [0.5, 2.0])
        self.assertEqual([edge.material for edge in edges], ["flexible", "rigid"])

    def test_pickle_edge_list_accepts_mapping_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edges_path = root / "edges.pkl"
            with edges_path.open("wb") as f:
                pickle.dump([
                    {"source": 0, "target": 1, "thickness": 0.5, "material": "flexible"},
                    {"source": 1, "target": 2, "thickness": 2.0, "material": "rigid"},
                ], f)

            edges = _load_edges(
                edges_path,
                {"adjacency_format": "edge_list"},
                variable_thickness=True,
                default_material="default",
                material_lookup={},
                base_dir=root,
            )

        self.assertEqual([(edge.weight, edge.material) for edge in edges], [
            (0.5, "flexible"),
            (2.0, "rigid"),
        ])

    def test_configured_node_material_is_used_when_nodes_have_no_material_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "xy.csv").write_text("0,0\n1,0\n1,1\n", encoding="utf-8")
            (root / "edges.csv").write_text("source,target\n0,1\n1,2\n", encoding="utf-8")
            config = {
                "output_dir": "out",
                "default_material": "edge_default",
                "geometry": {
                    "beam_diameter_mm": 0.1,
                    "cube_side_length_mm": 1,
                    "variable_thickness": False,
                    "node_material": "node_default",
                    "boolean_union": False,
                    "sections": 8,
                    "sphere_subdivisions": 0,
                },
                "jobs": [{
                    "name": "defaults",
                    "positions": "xy.csv",
                    "adjacency": "edges.csv",
                    "adjacency_format": "edge_list",
                }],
            }

            result = generate_from_config_data(config, base_dir=root)

        materials = {output["material"] for output in result["jobs"][0]["outputs"]}
        self.assertEqual(materials, {"edge_default", "node_default"})

    def test_node_diameters_file_must_match_node_count_and_be_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid_path = root / "node_diameters.npy"
            np.save(valid_path, np.array([[0.1], [0.2], [0.3]]))
            bad_length_path = root / "bad_length.npy"
            np.save(bad_length_path, np.array([0.1, 0.2]))
            bad_value_path = root / "bad_value.npy"
            np.save(bad_value_path, np.array([0.1, 0.0, 0.3]))

            diameters = _load_node_diameters(valid_path, 3)

            with self.assertRaisesRegex(ValueError, "must match node count"):
                _load_node_diameters(bad_length_path, 3)
            with self.assertRaisesRegex(ValueError, "finite positive"):
                _load_node_diameters(bad_value_path, 3)

        np.testing.assert_allclose(diameters, [0.1, 0.2, 0.3])

    def test_explicit_node_diameters_override_automatic_node_radius_scale(self):
        positions = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
        ])
        meshes_by_material = defaultdict(list)

        reservations = _add_junction_spheres(
            positions,
            {
                0: [("beam", 1.0)],
                1: [("beam", 3.0)],
            },
            meshes_by_material,
            beam_diameter=10.0,
            junction_policy="separate",
            mixed_junction_material="mixed",
            node_material="node",
            sphere_subdivisions=0,
            node_radius_scale=99.0,
            node_diameters=np.array([0.4, 0.8]),
        )

        self.assertEqual(sorted(reservations), [0, 1])
        self.assertAlmostEqual(reservations[0].radius, 0.2)
        self.assertAlmostEqual(reservations[1].radius, 0.4)

    def test_per_material_junction_policy_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "geometry": {"junction_policy": "per_material"},
                "jobs": [{
                    "positions": "xy.csv",
                    "adjacency": "edges.csv",
                }],
            }

            with self.assertRaisesRegex(ValueError, "junction_policy"):
                generate_from_config_data(config, base_dir=root)

    def test_node_material_priority_subtracts_node_volume_from_beams(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "xy.csv").write_text("0,0\n1,0\n", encoding="utf-8")
            (root / "edges.csv").write_text("source,target,material\n0,1,beam\n", encoding="utf-8")
            base_config = {
                "default_material": "beam",
                "geometry": {
                    "beam_diameter_mm": 0.25,
                    "cube_side_length_mm": 1,
                    "variable_thickness": False,
                    "node_material": "node",
                    "boolean_union": False,
                    "sections": 16,
                    "sphere_subdivisions": 1,
                },
                "jobs": [{
                    "positions": "xy.csv",
                    "adjacency": "edges.csv",
                    "adjacency_format": "edge_list",
                }],
            }

            legacy_config = dict(base_config)
            legacy_config["output_dir"] = "legacy"
            legacy_config["geometry"] = dict(base_config["geometry"], node_material_priority=False)
            legacy_config["jobs"] = [dict(base_config["jobs"][0], name="legacy")]
            priority_config = dict(base_config)
            priority_config["output_dir"] = "priority"
            priority_config["geometry"] = dict(base_config["geometry"], node_material_priority=True)
            priority_config["jobs"] = [dict(base_config["jobs"][0], name="priority")]

            legacy = generate_from_config_data(legacy_config, base_dir=root)["jobs"][0]
            priority = generate_from_config_data(priority_config, base_dir=root)["jobs"][0]

            legacy_outputs = {output["material"]: output for output in legacy["outputs"]}
            priority_outputs = {output["material"]: output for output in priority["outputs"]}
            legacy_beam = trimesh.load_mesh(legacy_outputs["beam"]["path"])
            priority_beam = trimesh.load_mesh(priority_outputs["beam"]["path"])
            priority_node = trimesh.load_mesh(priority_outputs["node"]["path"])

            self.assertLess(priority_beam.volume, legacy_beam.volume * 0.9)
            self.assertTrue(priority_beam.is_watertight)
            self.assertTrue(priority_beam.is_volume)
            self.assertTrue(priority_node.is_watertight)
            self.assertTrue(priority_node.is_volume)


if __name__ == "__main__":
    unittest.main()
