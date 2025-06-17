"""Fix the MainWindow class structure in playground.py"""

import os
import sys
import re

# Use the absolute path directly
playground_path = r"d:\SuperCAD\AdaptiveCAD\adaptivecad\gui\playground.py"
backup_path = playground_path + '.bak2'

print(f"Creating backup at {backup_path}...")
with open(playground_path, 'r', encoding='utf-8') as f:
    original = f.read()

with open(backup_path, 'w', encoding='utf-8') as f:
    f.write(original)

# Find where 'if not HAS_GUI:' is defined and fix the class structure
if "class MainWindow" in original:
    fixed_content = re.sub(
        r'if not HAS_GUI:(\s+)class MainWindow:',
        '# Ensure MainWindow is always defined, but with different implementation based on HAS_GUI\n'
        'if not HAS_GUI:\n'
        '    class MainWindow:\n'
        '        """Placeholder MainWindow implementation when GUI dependencies are not available."""\n'
        '        def __init__(self):\n'
        '            print("GUI dependencies not available. Can\'t create MainWindow.")\n'
        '        \n'
        '        def run(self):\n'
        '            print("Error: Cannot run GUI without PySide6 and OCC.Display dependencies.")\n'
        '            return 1\n'
        'else:\n'
        '    class MainWindow:',
        original
    )

    print("Writing updated content to file...")
    with open(playground_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print(f"Successfully patched {playground_path}")
else:
    print("Could not find MainWindow class definition in the file.")
