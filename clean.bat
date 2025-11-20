@echo off
setlocal enabledelayedexpansion

REM List the files and directories to remove (relative to current directory)
set FILES_TO_REMOVE=__pycache__ csvFiles output.txt

REM Get the current directory
set CURRENT_DIR=%cd%

echo Cleaning up the following files and directories in %CURRENT_DIR%:

REM Loop through each item and remove it
for %%F in (%FILES_TO_REMOVE%) do (
    if exist "%CURRENT_DIR%\%%F" (
        echo Removing %%F...
        rmdir /s /q "%CURRENT_DIR%\%%F" 2>nul
        del /f /q "%CURRENT_DIR%\%%F" 2>nul
    ) else (
        echo Warning: %%F not found in %CURRENT_DIR%.
    )
)

echo Cleanup complete.
endlocal
