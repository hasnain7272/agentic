# AgentCore Paint - A2A Enabled Paint Application

A feature-rich Paint-like desktop application built with Python tkinter, featuring A2A (Agent-to-Agent) communication and tools integration for the Orchestrator-Planner-Executor-Reviewer swarm.

## Features

### Drawing Tools (11 Tools)
- **Brush** - Freehand drawing with adjustable size
- **Eraser** - Erase with adjustable size
- **Pencil** - Thin precise lines (1px)
- **Line** - Straight lines
- **Rectangle** - Rectangles (outline)
- **Ellipse** - Circles and ellipses (outline)
- **Text** - Add text annotations
- **Fill** - Flood fill (bucket tool)
- **Eyedropper** - Pick colors from canvas
- **Spray** - Spray paint effect
- **Select** - Rectangular selection with copy/paste/delete

### Core Features
- **Undo/Redo** - 50-step history
- **Color Picker** - Full color dialog + quick palette
- **Canvas Operations** - Resize, Rotate 90°, Flip Horizontal/Vertical
- **File Operations** - New, Open, Save (PNG, JPG, BMP, GIF)
- **Keyboard Shortcuts** - Full hotkey support

### A2A & Tools Integration
- **Agent Communication** - Send messages to other swarm agents
- **Memory Storage** - Store/recall key-value memories
- **Web Search** - Search the web from within the app
- **Code Execution** - Run Python code snippets
- **Image Analysis** - Analyze canvas (colors, histogram, dimensions)

## Installation

### From Source
```bash
cd paint_app
pip install -r requirements.txt
python main.py
```

### Build Executable (.exe)
```bash
cd paint_app
pip install pyinstaller
python build_exe.py
```

The executable will be at `dist/AgentCorePaint.exe`

## Usage

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| Ctrl+N | New File |
| Ctrl+O | Open File |
| Ctrl+S | Save File |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl+C | Copy Selection |
| Ctrl+V | Paste |
| Delete | Delete Selection |
| Ctrl+A | Select All |
| Escape | Deselect |

### Tool Shortcuts
| Key | Tool |
|-----|------|
| B | Brush |
| E | Eraser |
| P | Pencil |
| L | Line |
| R | Rectangle |
| C | Ellipse |
| T | Text |
| F | Fill |
| I | Eyedropper |
| S | Spray |
| V | Select |

### A2A Panel
The right panel provides integration with the AgentCore swarm:
1. **Configure Agent** - Set target session ID and API endpoint
2. **Send Messages** - Communicate with other agents
3. **Memory** - Store/recall persistent memories
4. **Web Search** - Search and fetch web content
5. **Code Execution** - Run Python code
6. **Image Analysis** - Analyze current canvas

## Architecture

```
paint_app/
├── main.py           # Main application entry point
├── requirements.txt  # Python dependencies
├── setup.py         # Package setup
├── build_exe.py     # PyInstaller build script
└── README.md        # This file
```

### Key Classes
- **PaintCanvas** - Core drawing surface with tool management
- **ToolManager** - Handles 11 drawing tools
- **HistoryManager** - Undo/redo functionality
- **ToolPanel** - Left sidebar with tool buttons and settings
- **A2APanel** - Right sidebar with agent integration
- **MenuBar** - Top menu with file/edit/view/help
- **StatusBar** - Bottom status with coordinates, tool, canvas size

## Requirements
- Python 3.8+
- tkinter (standard library)
- Pillow (PIL) >= 10.0.0
- requests >= 2.31.0

## License
MIT License - Built for the AgentCore Orchestrator-Planner-Executor-Reviewer Swarm