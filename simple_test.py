import sys
import os
sys.path.append('.')

try:
    from src.core.plugins import get_role_plugin_manager
    print("SUCCESS: Plugin import working")
    
    # Test basic functionality
    manager = get_role_plugin_manager("./workspace")
    print("SUCCESS: Plugin manager created")
    
    # Test status without asyncio
    status = manager.get_status()
    print("SUCCESS: Status retrieved without asyncio error")
    print(f"Profile available: {status['profile_plugin']['available']}")
    print(f"KB available: {status['knowledge_base_plugin']['available']}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc() 