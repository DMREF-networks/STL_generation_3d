from npy_to_stl import *
from csv_to_stl import *


file_type = input("Are the files csv or npy? ").lower()
while not(file_type == "csv") and not(file_type == "npy"):
    file_type = input("Enter file type again: ")

inputPath = input("Enter input path here: ")  # Example: /Users/sarayukondaveeti/NetworkModels
diameter = float(input("Enter beam diameter in millimeters: ")) # Example: 2.8
side = float(input("Enter matrix side length in millimeters: ")) # Example: 80

# Method selection. "cylinders" = original 3D cylinder + junction-sphere
# approach (works for any network). "planar" = merge 2D rectangles + discs
# with shapely and extrude (flat networks only; robust to thin beams and
# avoids the junction-gap problem). Press Enter to keep the default.
method = input("Method [cylinders/planar] (default cylinders): ").strip().lower()
if method not in ("cylinders", "planar", ""):
    print(f"Unknown method '{method}', falling back to cylinders.")
    method = "cylinders"
if method == "":
    method = "cylinders"

extrusion_depth = None
if method == "planar":
    resp = input(f"Extrusion depth in millimeters (default = beam diameter = {diameter}): ").strip()
    extrusion_depth = float(resp) if resp else None

if (file_type == "csv"):
    csv_to_stl(inputPath, diameter, side, method=method, extrusion_depth=extrusion_depth)
elif (file_type == "npy"):
    npy_to_stl(inputPath, diameter, side, method=method, extrusion_depth=extrusion_depth)