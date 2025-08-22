#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Image Recognition Workflow Runner
This script serves as a simple entry point to run the image recognition workflow.
"""

import sys
import os

# Add the project root and src directory to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, project_root)
sys.path.insert(0, src_path)

try:
    # Import and run the main workflow
    from src.workflow.image_recognition_workflow import cli_main
    import asyncio
    
    if __name__ == "__main__":
        asyncio.run(cli_main())
        
except ImportError as e:
    print(f"Import error: {e}")
    print("Please make sure all dependencies are installed and the project structure is correct.")
    sys.exit(1)
except Exception as e:
    print(f"Error running image recognition workflow: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)