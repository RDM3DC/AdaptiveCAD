"""Build a Benchy-like boat from scratch using modeling tools!

Demonstrates the complete workflow:
- Sketch 2D profiles
- Extrude to 3D
- Boolean operations
- Edge modification
"""

from adaptivecad.aacore.sdf import KIND_BOX, KIND_CAPSULE, Prim, Scene, Xform


def create_prim(kind, size, position, color=(0.2, 0.6, 0.8), op='solid', beta=0.0):
    """Helper to create primitives with proper constructor."""
    prim = Prim(
        kind=kind,
        params=list(size),  # Size as params
        xform=Xform(),
        op=op,
        color=color,
        beta=beta  # Rounded edges
    )
    prim.set_transform(pos=position)
    return prim

def build_benchy_boat():
    """Build a simplified benchy-like boat."""
    
    scene = Scene()
    
    print("🚢 Building Benchy from scratch...")
    print("=" * 50)
    
    # === STEP 1: Hull Base ===
    print("\n1️⃣ Creating hull base...")
    hull_base = create_prim(
        KIND_BOX,
        [30.0, 15.0, 10.0],
        [0.0, 0.0, 5.0],
        color=(0.2, 0.6, 0.8),
        beta=1.5  # Soften the hull
    )
    scene.prims.append(hull_base)
    print("   ✓ Hull base: 30×15×10mm")
    
    # === STEP 2: Hull Bow (Front Taper) ===
    print("\n2️⃣ Creating bow (front taper)...")
    bow = create_prim(KIND_BOX, [8.0, 12.0, 10.0], [19.0, 0.0, 5.0], beta=2.0)
    scene.prims.append(bow)
    print("   ✓ Bow section: 8×12×10mm")
    
    # === STEP 3: Deck ===
    print("\n3️⃣ Creating deck...")
    deck = create_prim(KIND_BOX, [28.0, 13.0, 2.0], [0.0, 0.0, 11.0], color=(0.25, 0.65, 0.85), beta=0.2)
    scene.prims.append(deck)
    print("   ✓ Deck: 28×13×2mm")
    
    # === STEP 4: Cabin Base ===
    print("\n4️⃣ Creating cabin...")
    cabin = create_prim(KIND_BOX, [12.0, 8.0, 8.0], [-3.0, 0.0, 16.0], color=(0.3, 0.7, 0.9), beta=0.5)
    scene.prims.append(cabin)
    print("   ✓ Cabin: 12×8×8mm")
    
    # === STEP 5: Cabin Roof ===
    print("\n5️⃣ Creating cabin roof...")
    roof = create_prim(KIND_BOX, [13.0, 9.0, 1.5], [-3.0, 0.0, 20.75], color=(0.35, 0.75, 0.95), beta=0.3)
    scene.prims.append(roof)
    print("   ✓ Roof: 13×9×1.5mm")
    
    # === STEP 6: Smokestack ===
    print("\n6️⃣ Creating smokestack...")
    smokestack = create_prim(KIND_CAPSULE, [1.5, 1.5, 6.0], [-3.0, 0.0, 24.5], color=(0.15, 0.5, 0.7))
    scene.prims.append(smokestack)
    print("   ✓ Smokestack: ø1.5×6mm")
    
    # === STEP 7: Smokestack Top ===
    print("\n7️⃣ Creating smokestack top...")
    stack_top = create_prim(KIND_CAPSULE, [2.2, 2.2, 1.0], [-3.0, 0.0, 28.0], color=(0.15, 0.5, 0.7))
    scene.prims.append(stack_top)
    print("   ✓ Stack top: ø2.2×1mm")
    
    # === STEP 8: Bridge/Wheelhouse ===
    print("\n8️⃣ Creating wheelhouse...")
    wheelhouse = create_prim(KIND_BOX, [6.0, 6.0, 4.0], [5.0, 0.0, 14.0], color=(0.3, 0.7, 0.9), beta=0.4)
    scene.prims.append(wheelhouse)
    print("   ✓ Wheelhouse: 6×6×4mm")
    
    # === STEP 9: Windows (subtract) ===
    print("\n9️⃣ Creating windows...")
    window_front = create_prim(KIND_CAPSULE, [1.2, 1.2, 4.0], [9.0, 0.0, 15.5], color=(0.0, 0.0, 0.0), op='subtract')
    window_front.set_transform(euler=[0, 90, 0], pos=[9.0, 0.0, 15.5])
    scene.prims.append(window_front)
    
    window_left = create_prim(KIND_CAPSULE, [1.0, 1.0, 2.0], [5.0, -3.5, 15.5], color=(0.0, 0.0, 0.0), op='subtract')
    scene.prims.append(window_left)
    
    window_right = create_prim(KIND_CAPSULE, [1.0, 1.0, 2.0], [5.0, 3.5, 15.5], color=(0.0, 0.0, 0.0), op='subtract')
    scene.prims.append(window_right)
    print("   ✓ Front and side windows")
    
    # === STEP 10: Door ===
    print("\n🔟 Creating door...")
    door = create_prim(KIND_BOX, [2.0, 3.5, 1.0], [-3.0, -4.5, 14.0], color=(0.0, 0.0, 0.0), op='subtract', beta=0.1)
    scene.prims.append(door)
    print("   ✓ Door: 2×3.5mm")
    
    # === STEP 11: Propeller shaft hole ===
    print("\n1️⃣1️⃣ Creating propeller shaft hole...")
    shaft_hole = create_prim(KIND_CAPSULE, [1.0, 1.0, 12.0], [-12.0, 0.0, 3.0], color=(0.0, 0.0, 0.0), op='subtract')
    shaft_hole.set_transform(euler=[0, 90, 0], pos=[-12.0, 0.0, 3.0])
    scene.prims.append(shaft_hole)
    print("   ✓ Shaft hole: ø1.0×12mm")
    
    # === STEP 12: Done! ===
    print("\n1️⃣2️⃣ Boat structure complete!")
    print("\n" + "=" * 50)
    print("✅ Benchy-like boat completed!")
    
    return scene


if __name__ == "__main__":
    import sys
    
    # Option 1: Save to file
    print("\n" + "=" * 50)
    print("Building boat and saving scene...")
    print("=" * 50)
    
    boat_scene = build_benchy_boat()
    
    # Save scene
    import pickle
    from pathlib import Path
    
    output_path = Path(__file__).parent / "benchy_from_scratch.scene"
    
    # Simple pickle save
    with open(output_path, 'wb') as f:
        pickle.dump(boat_scene, f)
    
    print(f"\n💾 Scene saved to: {output_path}")
    print("\n📖 To view:")
    print("   1. Open AdaptiveCAD")
    print("   2. File → Open")
    print("   3. Select benchy_from_scratch.scene")
    print("\nOR run: python -c \"from build_benchy_from_scratch import build_benchy_boat; build_benchy_boat()\"")
    
    # Option 2: Launch viewer
    try:
        from PySide6.QtWidgets import QApplication
        
        print("\n🚀 Launching AdaptiveCAD with boat scene...")
        
        app = QApplication.instance() or QApplication(sys.argv)
        
        from adaptivecad.app.main_window import AdaptiveCADApp
        window = AdaptiveCADApp()
        window.scene = boat_scene
        window._update_scene_display()
        window.show()
        
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"\n⚠️ Could not launch viewer: {e}")
        print("Scene saved to file - open manually in AdaptiveCAD")
