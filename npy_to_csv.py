def npy_to_csv(inputPath):
    import subprocess 
    import os
    currentPath = str(os.getcwd())
    outputPath = currentPath + "/csvFiles"
    subprocess.Popen("python3 convert.py " + inputPath + " " + outputPath, shell=True)