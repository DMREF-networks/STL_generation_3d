import tempfile
import unittest
from pathlib import Path

from config_to_stl import generate_from_config_data
from config_to_stl import _load_edges


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


if __name__ == "__main__":
    unittest.main()
