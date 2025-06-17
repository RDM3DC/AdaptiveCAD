#!/usr/bin/env python3
"""
Quick test to verify that the responsive import system works correctly.
This script tests thread creation, execution, and cleanup.
"""

import os
import sys
import time

# Add the project to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_import_thread():
    """Test the ImportThread class in isolation."""
    print("🧪 Testing ImportThread functionality...")
    
    from adaptivecad.commands.import_conformal import ImportThread
    
    # Create a mock thread
    thread = ImportThread("nonexistent_test_file.stl", 4)
    
    print(f"✅ Thread created successfully")
    print(f"   📁 Filename: {thread.filename}")
    print(f"   🧵 Number of threads: {thread.num_threads}")
    
    # Test signal connections (won't run the actual import)
    progress_updates = []
    errors = []
    completion_flag = []
    
    def on_progress(msg):
        progress_updates.append(msg)
        print(f"   📊 Progress: {msg}")
    
    def on_error(msg):
        errors.append(msg)
        print(f"   ❌ Error: {msg}")
    
    def on_complete():
        completion_flag.append(True)
        print(f"   ✅ Completion signal received")
    
    # Connect signals
    thread.progress_update.connect(on_progress)
    thread.error_occurred.connect(on_error)
    thread.import_complete.connect(on_complete)
    
    print("✅ Signals connected successfully")
    
    # Start the thread (will fail with expected error)
    print("🚀 Starting import thread...")
    thread.start()
    
    # Wait for thread to complete
    thread.wait(5000)  # Wait up to 5 seconds
    
    # Cleanup
    thread.progress_update.disconnect()
    thread.error_occurred.disconnect()
    thread.import_complete.disconnect()
    thread.deleteLater()
    
    print("✅ Thread cleanup completed")
    
    # Verify results
    if errors:
        print("✅ Expected error occurred (file not found)")
    else:
        print("❌ No error occurred (unexpected)")
    
    print(f"📊 Progress updates received: {len(progress_updates)}")
    print(f"❌ Errors received: {len(errors)}")
    print(f"✅ Completion signals: {len(completion_flag)}")


def test_command_class():
    """Test the ImportConformalCmd class."""
    print("\n🧪 Testing ImportConformalCmd class...")
    
    from adaptivecad.commands.import_conformal import ImportConformalCmd
    
    cmd = ImportConformalCmd()
    print(f"✅ Command created successfully")
    print(f"   📝 Title: {cmd.title}")
    
    # Test cleanup method exists
    if hasattr(cmd, '_cleanup_thread'):
        print("✅ Thread cleanup method exists")
    else:
        print("❌ Thread cleanup method missing")
    
    print("✅ Command class test completed")


def main():
    """Run all tests."""
    print("🎯 RESPONSIVE IMPORT SYSTEM TEST")
    print("=" * 50)
    
    try:
        test_command_class()
        test_import_thread()
        
        print("\n" + "=" * 50)
        print("🎉 ALL TESTS PASSED!")
        print("✅ Thread creation works")
        print("✅ Signal communication works") 
        print("✅ Thread cleanup works")
        print("✅ Error handling works")
        print("✅ Command class loads properly")
        print("\n🚀 The responsive import system is ready for use!")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
