# Build script for AgentCore Paint executable
import PyInstaller.__main__
import os
import sys

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))
main_script = os.path.join(script_dir, "main.py")

# PyInstaller arguments
args = [
    main_script,
    "--name=AgentCorePaint",
    "--onefile",
    "--windowed",  # No console window
    "--icon=icon.ico" if os.path.exists(os.path.join(script_dir, "icon.ico")) else "",
    "--add-data=requirements.txt;.",
    "--hidden-import=PIL",
    "--hidden-import=PIL.Image",
    "--hidden-import=PIL.ImageDraw",
    "--hidden-import=PIL.ImageTk",
    "--hidden-import=PIL.ImageFilter",
    "--hidden-import=PIL.ImageEnhance",
    "--hidden-import=requests",
    "--hidden-import=tkinter",
    "--hidden-import=tkinter.ttk",
    "--hidden-import=tkinter.filedialog",
    "--hidden-import=tkinter.colorchooser",
    "--hidden-import=tkinter.messagebox",
    "--hidden-import=tkinter.simpledialog",
    "--clean",
    "--noconfirm",
]

# Filter out empty strings
args = [arg for arg in args if arg]

print("Building AgentCore Paint executable...")
print(f"Main script: {main_script}")
print(f"Arguments: {args}")

PyInstaller.__main__.run(args)

print("\nBuild complete!")
print(f"Executable location: {os.path.join(script_dir, 'dist', 'AgentCorePaint.exe')}")