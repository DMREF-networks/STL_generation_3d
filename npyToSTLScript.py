from npy_to_stl import *

# Enter a the directory containing your NUMPY files 
inputPath = input("Enter input path here: ")  # Example: /Users/sarayukondaveeti/NetworkModels
diameter = float(input("Enter beam diameter in millimeters: ")) # Example: 2.8
side = float(input("Enter matrix side length in millimeters: ")) # Example: 80
npy_to_stl(inputPath, diameter, side)