ins__": __builtins__}, local_vars)
                messagebox.showinfo("Success", "Code executed successfully")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Execution failed: {e}")
        
        ttk.Button(dialog, text="Execute", command=run_code).pack(pady=10)
    
    def show_shortcuts(self):
        """Show keyboard shortcuts"""
        shortcuts = """
Keyboard Shortcuts:
==================
Ctrl+N          - New File
Ctrl+O          - Open File
Ctrl+S          - Save File
Ctrl+Z          - Undo
Ctrl+Y          - Redo
Ctrl+C          - Copy Selection
Ctrl+V          - Paste
Delete          - Delete Selection
Ctrl+A          - Select All
Escape          - Deselect

Tools:
B               - Brush
E               - Eraser
P               - Pencil
L               - Line
R               - Rectangle
C               - Ellipse (Circle)
T               - Text
F               - Fill
I               - Eyedropper
S               - Spray
V               - Select

Mouse:
Left Click      - Draw/Select
Drag            - Draw shape/Select area
Double Click    - Add text (Text tool)
"""
        messagebox.showinfo("Keyboard Shortcuts", shortcuts)
    
    def show_about(self):
        """Show about dialog"""
        about_text = """AgentCore Paint v1.0
=====================
A Paint-like application with A2A and Tools integration

Features:
• 11 Drawing Tools (Brush, Eraser, Pencil, Line, Rectangle, Ellipse, Text, Fill, Eyedropper, Spray, Select)
• Undo/Redo History (50 steps)
• Color Picker & Palette
• Canvas Resize, Rotate, Flip
• Layer-like Selection (Copy/Paste/Delete)
• A2A Agent Communication
• Memory Storage/Recall
• Web Search Integration
• Python Code Execution
• Image Analysis (Colors, Histogram, Dimensions)

Built for the Orchestrator-Planner-Executor-Reviewer Swarm

Dependencies: tkinter, Pillow (PIL), requests"""
        messagebox.showinfo("About AgentCore Paint", about_text)


class StatusBar:
    """Status bar at bottom of window"""
    
    def __init__(self, parent, canvas: PaintCanvas):
        self.parent = parent
        self.canvas = canvas
        
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)
        
        # Coordinates
        self.coord_var = tk.StringVar(value="X: 0, Y: 0")
        ttk.Label(self.frame, textvariable=self.coord_var).pack(side=tk.LEFT, padx=10)
        
        # Tool info
        self.tool_var = tk.StringVar(value="Tool: Brush")
        ttk.Label(self.frame, textvariable=self.tool_var).pack(side=tk.LEFT, padx=10)
        
        # Canvas size
        self.size_var = tk.StringVar(value=f"Canvas: {canvas.width}x{canvas.height}")
        ttk.Label(self.frame, textvariable=self.size_var).pack(side=tk.LEFT, padx=10)
        
        # Zoom
        self.zoom_var = tk.StringVar(value="Zoom: 100%")
        ttk.Label(self.frame, textvariable=self.zoom_var).pack(side=tk.RIGHT, padx=10)
        
        # Bind motion event
        canvas.canvas.bind("<Motion>", self.on_motion)
    
    def on_motion(self, event):
        """Update coordinates on mouse move"""
        self.coord_var.set(f"X: {event.x}, Y: {event.y}")
    
    def update_tool(self, tool_name: str):
        """Update current tool display"""
        tool_info = self.canvas.tool_manager.get_tool(tool_name)
        self.tool_var.set(f"Tool: {tool_info['name']}")
    
    def update_size(self, width: int, height: int):
        """Update canvas size display"""
        self.size_var.set(f"Canvas: {width}x{height}")


class AgentCorePaint:
    """Main application class"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("🎨 AgentCore Paint - A2A Enabled")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # Set icon (if available)
        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass
        
        # Create main layout
        self.create_layout()
        
        # Initialize components
        self.canvas = PaintCanvas(self.center_frame, width=800, height=600)
        self.tool_panel = ToolPanel(self.left_frame, self.canvas)
        self.a2a_panel = A2APanel(self.right_frame, self.canvas)
        self.menu_bar = MenuBar(self.root, self.canvas)
        self.status_bar = StatusBar(self.root, self.canvas)
        
        # Bind tool selection to status bar
        self.bind_tool_updates()
        
        # Set default tool
        self.canvas.tool_manager.set_tool("brush")
        self.tool_panel.select_tool("brush")
        
        # Center window
        self.center_window()
    
    def create_layout(self):
        """Create main application layout"""
        # Main container
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - Tools
        self.left_frame = ttk.Frame(main_container, width=250)
        main_container.add(self.left_frame, weight=0)
        
        # Center - Canvas
        self.center_frame = ttk.Frame(main_container)
        main_container.add(self.center_frame, weight=1)
        
        # Right panel - A2A & Tools
        self.right_frame = ttk.Frame(main_container, width=400)
        main_container.add(self.right_frame, weight=0)
    
    def bind_tool_updates(self):
        """Bind tool selection to update status bar"""
        original_select = self.tool_panel.select_tool
        
        def wrapped_select(tool_id):
            original_select(tool_id)
            self.status_bar.update_tool(tool_id)
        
        self.tool_panel.select_tool = wrapped_select
    
    def center_window(self):
        """Center window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")


def main():
    """Main entry point"""
    root = tk.Tk()
    
    # Set theme
    style = ttk.Style()
    style.theme_use('clam')  # Modern theme
    
    # Configure colors
    style.configure('TFrame', background='#f0f0f0')
    style.configure('TLabel', background='#f0f0f0')
    style.configure('TButton', padding=5)
    style.configure('TLabelframe', background='#f0f0f0')
    style.configure('TLabelframe.Label', background='#f0f0f0', font=('Segoe UI', 10, 'bold'))
    
    app = AgentCorePaint(root)
    
    # Handle window close
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit AgentCore Paint?"):
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Start main loop
    root.mainloop()


if __name__ == "__main__":
    main()