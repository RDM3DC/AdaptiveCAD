"""
Simple test to verify shape display functionality.
"""
import sys
sys.path.insert(0, r'd:\SuperCAD\AdaptiveCAD')

from PySide6.QtWidgets import QApplication
from adaptivecad.gui.playground import MainWindow
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from adaptivecad.command_defs import Feature, DOCUMENT

print("🧪 Testing basic shape display...")

app = QApplication([])
mw = MainWindow()
mw.win.show()

# Create a simple test box
print("Creating test box...")
box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()

# Add it to the document
print("Adding to document...")
feature = Feature("Test Box", {}, box)
DOCUMENT.append(feature)

# Display it
print("Displaying shape...")
mw.view._display.EraseAll()
mw.view._display.DisplayShape(box, update=True)
mw.view._display.FitAll()

print("✓ Test box should now be visible in the 3D view")
print("📋 If you can see the box, the display system works fine.")
print("📋 If not, there's an issue with the display system itself.")

app.exec()
