import math
from typing import List, Dict, Tuple, Union, Optional
import os

class Point3D:
    """Represents a 3D point."""
    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z
    
    def __str__(self):
        return f"({self.x:.2f}, {self.y:.2f}, {self.z:.2f})"
    
    def distance_to(self, other: 'Point3D') -> float:
        """Calculate Euclidean distance to another point."""
        return math.sqrt(
            (self.x - other.x)**2 + 
            (self.y - other.y)**2 + 
            (self.z - other.z)**2
        )

class GCodeCommand:
    """Base class for G-code commands."""
    def __init__(self, comment=None):
        self.comment = comment
    
    def to_string(self) -> str:
        """Generate G-code string for this command."""
        raise NotImplementedError("Subclasses must implement to_string()")

class GCodeRapidMove(GCodeCommand):
    """G0: Rapid positioning."""
    def __init__(self, x=None, y=None, z=None, comment=None):
        super().__init__(comment)
        self.x = x
        self.y = y
        self.z = z
    
    def to_string(self) -> str:
        parts = ["G0"]
        if self.x is not None:
            parts.append(f"X{self.x:.3f}")
        if self.y is not None:
            parts.append(f"Y{self.y:.3f}")
        if self.z is not None:
            parts.append(f"Z{self.z:.3f}")
        
        code = " ".join(parts)
        if self.comment:
            code += f" ; {self.comment}"
        return code

class GCodeLinearMove(GCodeCommand):
    """G1: Linear move."""
    def __init__(self, x=None, y=None, z=None, f=None, comment=None):
        super().__init__(comment)
        self.x = x
        self.y = y
        self.z = z
        self.f = f  # Feed rate
    
    def to_string(self) -> str:
        parts = ["G1"]
        if self.x is not None:
            parts.append(f"X{self.x:.3f}")
        if self.y is not None:
            parts.append(f"Y{self.y:.3f}")
        if self.z is not None:
            parts.append(f"Z{self.z:.3f}")
        if self.f is not None:
            parts.append(f"F{self.f:.1f}")
        
        code = " ".join(parts)
        if self.comment:
            code += f" ; {self.comment}"
        return code

class GCodeArcMove(GCodeCommand):
    """G2/G3: Arc movement."""
    def __init__(self, clockwise=True, x=None, y=None, z=None, i=None, j=None, k=None, f=None, comment=None):
        super().__init__(comment)
        self.clockwise = clockwise  # G2 = clockwise, G3 = counter-clockwise
        self.x = x  # End X
        self.y = y  # End Y
        self.z = z  # End Z
        self.i = i  # X offset from start to center
        self.j = j  # Y offset from start to center
        self.k = k  # Z offset from start to center
        self.f = f  # Feed rate
    
    def to_string(self) -> str:
        parts = ["G2" if self.clockwise else "G3"]
        if self.x is not None:
            parts.append(f"X{self.x:.3f}")
        if self.y is not None:
            parts.append(f"Y{self.y:.3f}")
        if self.z is not None:
            parts.append(f"Z{self.z:.3f}")
        if self.i is not None:
            parts.append(f"I{self.i:.3f}")
        if self.j is not None:
            parts.append(f"J{self.j:.3f}")
        if self.k is not None:
            parts.append(f"K{self.k:.3f}")
        if self.f is not None:
            parts.append(f"F{self.f:.1f}")
        
        code = " ".join(parts)
        if self.comment:
            code += f" ; {self.comment}"
        return code

class GCodeComment(GCodeCommand):
    """Comment only."""
    def __init__(self, comment):
        super().__init__(comment)
    
    def to_string(self) -> str:
        return f"; {self.comment}"

class GCodeSetUnits(GCodeCommand):
    """G20/G21: Set units to inches or mm."""
    def __init__(self, use_mm=True, comment=None):
        super().__init__(comment)
        self.use_mm = use_mm
    
    def to_string(self) -> str:
        code = "G21" if self.use_mm else "G20"
        if self.comment:
            code += f" ; {self.comment}"
        else:
            comment_text = "Set units to mm" if self.use_mm else "Set units to inches"
            code += f" ; {comment_text}"
        return code

class GCodeHomePosition(GCodeCommand):
    """G28: Move to home position."""
    def __init__(self, comment=None):
        super().__init__(comment)
    
    def to_string(self) -> str:
        code = "G28"
        if self.comment:
            code += f" ; {self.comment}"
        else:
            code += " ; Home all axes"
        return code

class GCodeProgram:
    """A complete G-code program."""
    def __init__(self, name="program"):
        self.name = name
        self.commands: List[GCodeCommand] = []
        self.current_position = Point3D(0, 0, 0)
        self.current_feed_rate = None
    
    def add_command(self, command: GCodeCommand):
        """Add a command to the program."""
        self.commands.append(command)
        
        # Update current position if it's a movement command
        if isinstance(command, (GCodeRapidMove, GCodeLinearMove, GCodeArcMove)):
            if command.x is not None:
                self.current_position.x = command.x
            if command.y is not None:
                self.current_position.y = command.y
            if command.z is not None:
                self.current_position.z = command.z
            if hasattr(command, 'f') and command.f is not None:
                self.current_feed_rate = command.f
    
    def add_comment(self, comment: str):
        """Add a comment line to the program."""
        self.add_command(GCodeComment(comment))
    
    def add_header(self):
        """Add standard header with machine setup."""
        self.add_comment(f"G-code generated for {self.name}")
        self.add_comment("Generated by AdaptiveCAD G-code Generator")
        self.add_comment(f"Date: {import_time()}")
        self.add_comment("------------------------------------------")
        self.add_command(GCodeSetUnits(use_mm=True))
        self.add_command(GCodeHomePosition("Home all axes"))
        self.add_comment("------------------------------------------")
    
    def add_footer(self):
        """Add standard footer to end the program."""
        self.add_comment("------------------------------------------")
        self.add_comment("End of program")
        self.add_command(GCodeHomePosition("Return to home position"))
        self.add_comment(f"Program {self.name} completed")
    
    def to_string(self) -> str:
        """Generate complete G-code program as a string."""
        return '\n'.join(cmd.to_string() for cmd in self.commands)
    
    def save(self, filepath: str):
        """Save G-code program to file."""
        with open(filepath, 'w') as f:
            f.write(self.to_string())
        print(f"G-code program saved to {filepath}")

def import_time():
    """Get the current time as a string for G-code comments."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class GCodeGenerator:
    """Base class for G-code generation strategies."""
    def generate(self, part_data) -> GCodeProgram:
        """Generate G-code from part data."""
        raise NotImplementedError("Subclasses must implement generate()")

class SimpleMilling(GCodeGenerator):
    """A simple milling strategy that follows the shape contours."""
    def __init__(
        self, 
        safe_height: float = 10.0, 
        cut_depth: float = 1.0,
        feed_rate: float = 100.0,
        rapid_feed_rate: float = 500.0,
        tool_diameter: float = 3.0
    ):
        self.safe_height = safe_height
        self.cut_depth = cut_depth
        self.feed_rate = feed_rate
        self.rapid_feed_rate = rapid_feed_rate
        self.tool_diameter = tool_diameter
    
    def generate(self, part_data) -> GCodeProgram:
        """Generate G-code for simple milling operation."""
        program = GCodeProgram(name=f"mill_{part_data.get('name', 'part')}")
        program.add_header()
        program.add_comment("Simple milling operation")
        program.add_comment(f"Tool diameter: {self.tool_diameter}mm")
        
        # Basic movement sequence (this would be more complex with real geometry)
        # Move to safe height
        program.add_command(GCodeRapidMove(z=self.safe_height, comment="Move to safe height"))
        
        # Move to start position
        program.add_command(GCodeRapidMove(x=0, y=0, comment="Move to start position"))
        
        # Start cutting
        program.add_comment("Begin cutting operation")
        
        # Move down to cutting depth
        program.add_command(GCodeLinearMove(z=-self.cut_depth, f=self.feed_rate/2, comment="Move to cutting depth"))
        
        # Example: Simple square path (would actually use geometry from the AMA file)
        # This is just a placeholder for demonstration
        size = 50  # mm
        program.add_command(GCodeLinearMove(x=size, f=self.feed_rate, comment="Cut along X"))
        program.add_command(GCodeLinearMove(y=size, comment="Cut along Y"))
        program.add_command(GCodeLinearMove(x=0, comment="Cut back along X"))
        program.add_command(GCodeLinearMove(y=0, comment="Cut back along Y"))
        
        # Return to safe height
        program.add_command(GCodeRapidMove(z=self.safe_height, comment="Move to safe height"))
        
        program.add_footer()
        return program

def ama_to_gcode(ama_file_path: str, output_path: str = None, strategy: GCodeGenerator = None) -> str:
    """
    Convert an AMA file to G-code.
    
    Args:
        ama_file_path (str): Path to the AMA file
        output_path (str, optional): Path where G-code file should be saved
        strategy (GCodeGenerator, optional): Strategy to use for G-code generation
    
    Returns:
        str: Path to the generated G-code file
    """
    from adaptivecad.io.ama_reader import read_ama
    
    # Use simple strategy as default
    if strategy is None:
        strategy = SimpleMilling()
    
    # Read AMA file
    ama_content = read_ama(ama_file_path)
    if not ama_content:
        raise ValueError(f"Could not read AMA file {ama_file_path}")
    
    # If no output path, create one based on the input filename
    if output_path is None:
        base_name = os.path.splitext(os.path.basename(ama_file_path))[0]
        output_path = os.path.join(os.path.dirname(ama_file_path), f"{base_name}.gcode")
    
    # If multiple parts are present, we should generate separate G-code files
    # For now, we'll just use the first part (or create a merged G-code)
    if not ama_content.parts:
        raise ValueError(f"No parts found in AMA file {ama_file_path}")
    
    # For simple example, we'll just create G-code for the first part
    part = ama_content.parts[0]
    
    # Form a data structure with part info that the strategy can use
    part_data = {
        "name": part.name,
        "metadata": part.metadata,
        # In a real implementation, we'd parse the BREP data here
        # and generate a representation suitable for G-code generation
    }
    
    # Generate G-code using the chosen strategy
    program = strategy.generate(part_data)
    
    # Save G-code to file
    program.save(output_path)
    
    return output_path

if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) > 1:
        ama_file_path = sys.argv[1]
        try:
            output_path = ama_to_gcode(ama_file_path)
            print(f"G-code generated and saved to {output_path}")
        except Exception as e:
            print(f"Error generating G-code: {e}")
    else:
        print("Please provide a path to an AMA file")
