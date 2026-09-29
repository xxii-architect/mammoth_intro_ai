#!/usr/bin/env python
"""
Verification script for Team Workflows implementation
Run: python verify_team_workflows.py
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

def verify_module_imports():
    """Verify all required modules can be imported"""
    print("Verifying module imports...")
    try:
        from mammoth_os.team_workflows import (
            TeamWorkflowManager,
            WorkflowTemplate,
            ApprovalPolicy,
            Runbook,
            RunbookStep,
        )
        print("  OK: All team_workflows classes imported")
        return True
    except ImportError as e:
        print(f"  ERROR: Failed to import team_workflows: {e}")
        return False


def verify_api_server():
    """Verify API server can be imported with new endpoints"""
    print("\nVerifying API server integration...")
    try:
        os.environ['SKIP_SUPABASE'] = '1'
        from api_server import app
        
        # Count team endpoints
        team_routes = [r.path for r in app.routes if '/team/' in r.path]
        
        if len(team_routes) >= 22:
            print(f"  OK: API server imported with {len(team_routes)} team endpoints")
            return True
        else:
            print(f"  ERROR: Expected 22+ team endpoints, found {len(team_routes)}")
            return False
    except Exception as e:
        print(f"  ERROR: Failed to import API server: {e}")
        return False


def verify_ui_component():
    """Verify UI component file exists"""
    print("\nVerifying UI components...")
    ui_page = Path(__file__).parent / "ui" / "mad-architecht-command-center" / "src" / "pages" / "TeamWorkflowsPage.jsx"
    ui_css = Path(__file__).parent / "ui" / "mad-architecht-command-center" / "src" / "pages" / "TeamWorkflowsPage.css"
    
    page_ok = ui_page.exists()
    css_ok = ui_css.exists()
    
    if page_ok:
        print(f"  OK: TeamWorkflowsPage.jsx exists ({ui_page.stat().st_size} bytes)")
    else:
        print(f"  ERROR: TeamWorkflowsPage.jsx not found at {ui_page}")
    
    if css_ok:
        print(f"  OK: TeamWorkflowsPage.css exists ({ui_css.stat().st_size} bytes)")
    else:
        print(f"  ERROR: TeamWorkflowsPage.css not found at {ui_css}")
    
    return page_ok and css_ok


def verify_documentation():
    """Verify documentation files exist"""
    print("\nVerifying documentation...")
    docs = [
        Path(__file__).parent / "docs" / "TEAM_WORKFLOWS.md",
        Path(__file__).parent / "TEAM_WORKFLOWS_IMPLEMENTATION.md",
    ]
    
    all_ok = True
    for doc in docs:
        if doc.exists():
            print(f"  OK: {doc.name} exists ({doc.stat().st_size} bytes)")
        else:
            print(f"  ERROR: {doc.name} not found at {doc}")
            all_ok = False
    
    return all_ok


def verify_tests():
    """Run test suite"""
    print("\nVerifying test suite...")
    import subprocess
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "src/mammoth_os/test_team_workflows.py", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path(__file__).parent
        )
        
        if result.returncode == 0:
            # Extract passed count from output
            if "passed" in result.stdout:
                print("  OK: All tests passed")
                print(f"  {[line for line in result.stdout.split(chr(10)) if 'passed' in line][-1]}")
                return True
        else:
            print("  ERROR: Tests failed")
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            return False
    except Exception as e:
        print(f"  ERROR: Failed to run tests: {e}")
        return False


def verify_storage_structure():
    """Verify storage structure is set up correctly"""
    print("\nVerifying storage structure...")
    
    mammoth_dir = Path(__file__).parent / ".mammoth"
    if mammoth_dir.exists():
        print(f"  OK: .mammoth directory exists")
        return True
    else:
        print(f"  INFO: .mammoth directory will be created on first use")
        return True


def main():
    """Run all verifications"""
    print("=" * 70)
    print("TEAM WORKFLOWS IMPLEMENTATION VERIFICATION")
    print("=" * 70)
    
    results = {
        "Module Imports": verify_module_imports(),
        "API Server Integration": verify_api_server(),
        "UI Components": verify_ui_component(),
        "Documentation": verify_documentation(),
        "Storage Structure": verify_storage_structure(),
        "Test Suite": verify_tests(),
    }
    
    print("\n" + "=" * 70)
    print("VERIFICATION RESULTS")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for check, result in results.items():
        status = "PASS" if result else "FAIL"
        symbol = "[OK]" if result else "[!]"
        print(f"{symbol} {check}: {status}")
    
    print("\n" + "=" * 70)
    print(f"TOTAL: {passed}/{total} checks passed")
    print("=" * 70)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
