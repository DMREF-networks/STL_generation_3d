import math
from pathlib import Path

from csv_to_stl import csv_to_stl
from npy_to_stl import npy_to_stl


def prompt_positive_number(prompt, default=None):
    while True:
        response = input(prompt).strip()
        if response == "" and default is not None:
            return float(default)
        try:
            value = float(response)
        except ValueError:
            print("Please enter a number greater than zero.")
            continue
        if math.isfinite(value) and value > 0:
            return value
        print("Please enter a number greater than zero.")


def run(method=None):
    file_type = input("Are the files csv or npy? ").strip().lower()
    while file_type not in ("csv", "npy"):
        file_type = input("Enter file type again: ").strip().lower()

    input_path = Path(
        input("Enter the directory containing paired *_xy and *_adj files: ").strip()
    ).expanduser()
    if not input_path.is_dir():
        if input_path.is_file():
            print(
                "Error: the input must be a directory, not an individual file. "
                f"Try: {input_path.parent}"
            )
        else:
            print(f"Error: input directory does not exist: {input_path}")
        return 2

    diameter = prompt_positive_number("Enter beam diameter in millimeters: ")
    side = prompt_positive_number("Enter desired model side length in millimeters: ")

    variable_thickness_resp = input(
        "Use variable beam thickness from adjacency values? [y/N]: "
    ).strip().lower()
    variable_thickness = variable_thickness_resp in ("y", "yes", "true", "1")

    if method is None:
        method = input("Choose method [cylinders/planar]: ").strip().lower()
        while method not in ("cylinders", "planar"):
            method = input("Please enter either cylinders or planar: ").strip().lower()

    extrusion_depth = None
    if method == "planar":
        extrusion_depth = prompt_positive_number(
            f"Extrusion depth in millimeters (default = beam diameter = {diameter}): ",
            default=diameter,
        )

    converter = csv_to_stl if file_type == "csv" else npy_to_stl
    outputs = converter(
        str(input_path),
        diameter,
        side,
        method=method,
        extrusion_depth=extrusion_depth,
        variable_thickness=variable_thickness,
    )
    if not outputs:
        print(
            f"Error: no matching *_xy.{file_type} and *_adj.{file_type} pairs "
            f"were found in {input_path.resolve()}."
        )
        return 1

    print("Generated files:")
    for output in outputs:
        print(f"  {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
