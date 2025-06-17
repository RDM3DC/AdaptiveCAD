# This is a fix for the Superellipse reference error
# It removes the problematic line that references NewSuperellipseCmd 

import os
import re

def fix_superellipse_error():
    # Path to playground.py
    playground_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                  'gui', 'playground.py')
    
    print(f"Reading {playground_path}...")
    
    # Read the file content
    with open(playground_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Find the problematic line
    problematic_line = 'add_shape_action(procedural_menu, "Superellipse", "draw-bezier", NewSuperellipseCmd)'
    
    if problematic_line not in content:
        print("Could not find the problematic line. No changes made.")
        return
        
    # Remove the problematic line
    new_content = content.replace(problematic_line, '# Line removed to fix the NameError')
    
    # Write back to the file
    with open(playground_path, 'w', encoding='utf-8') as file:
        file.write(new_content)
    
    print("Successfully fixed the Superellipse reference error.")
    print("You can now run the playground with 'python run_playground.py'")

if __name__ == "__main__":
    fix_superellipse_error()
