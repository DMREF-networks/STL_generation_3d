#!/bin/bash

# List the files and directories to remove (relative to the current directory)
FILES_TO_REMOVE=(
    "__pycache__"
    "csvFiles"
    "output.txt"
)

# Get the current directory where the script is being executed
CURRENT_DIR="$(pwd)"

echo "Cleaning up the following files and directories in $CURRENT_DIR:"

# Loop through each file/directory and remove it
for FILE in "${FILES_TO_REMOVE[@]}"; do
    # Check if the file/directory exists
    if [ -e "$CURRENT_DIR/$FILE" ]; then
        echo "Removing $FILE..."
        rm -rf "$CURRENT_DIR/$FILE"
    else
        echo "Warning: $FILE not found in $CURRENT_DIR."
    fi
done

echo "Cleanup complete."