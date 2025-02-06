from npy_to_stl import *
from csv_to_stl import *


file_type = input("Are the files csv or npy? ").lower()
while not(file_type == "csv") and not(file_type == "npy"):
    file_type = input("Enter file type again: ")

inputPath = input("Enter input path here: ")  # Example: /Users/sarayukondaveeti/NetworkModels
diameter = float(input("Enter beam diameter in millimeters: ")) # Example: 2.8
side = float(input("Enter matrix side length in millimeters: ")) # Example: 80


if (file_type == "csv"):
    csv_to_stl(inputPath, diameter, side)
elif (file_type == "npy"):
    npy_to_stl(inputPath, diameter, side)