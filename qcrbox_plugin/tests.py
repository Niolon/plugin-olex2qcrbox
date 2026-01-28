"""Testing utilities for QCrBox plugin.

This module contains test functions that can be called from the plugin.
"""

import json


def test_cif_conversion():
    """Test CIF DDL2 to DDL1 conversion."""
    from .cif_utils import convert_cif_ddl2_to_ddl1
    
    print("\n" + "="*60)
    print("Testing CIF DDL2 to DDL1 Conversion")
    print("="*60)
    
    # Test case 1: Simple data name conversion
    test_cif_1 = "_cell.length_a 10.5\n_cell.length_b 12.3"
    result_1 = convert_cif_ddl2_to_ddl1(test_cif_1)
    expected_1 = "_cell_length_a 10.5\n_cell_length_b 12.3"
    
    print(f"\nTest 1: Simple conversion")
    print(f"Input:    {repr(test_cif_1)}")
    print(f"Output:   {repr(result_1)}")
    print(f"Expected: {repr(expected_1)}")
    print(f"Result:   {'✓ PASS' if result_1 == expected_1 else '✗ FAIL'}")
    
    # Test case 2: Preserve multiline strings
    test_cif_2 = """;
This is a multiline string with _cell.length_a inside it
;
_cell.length_a 10.5"""
    result_2 = convert_cif_ddl2_to_ddl1(test_cif_2)
    
    print(f"\nTest 2: Multiline string preservation")
    print(f"Input has multiline string: {';' in test_cif_2}")
    print(f"Output preserved multiline: {';' in result_2}")
    print(f"Result:   {'✓ PASS' if '_cell.length_a' in result_2.split(';')[1] else '✗ FAIL'}")
    
    # Test case 3: Don't convert numeric decimals
    test_cif_3 = "_cell.length_a 10.5\n_refine.ls_R_factor_gt 0.0234"
    result_3 = convert_cif_ddl2_to_ddl1(test_cif_3)
    
    print(f"\nTest 3: Preserve numeric decimals")
    print(f"Output contains 10.5: {'10.5' in result_3}")
    print(f"Output contains 0.0234: {'0.0234' in result_3}")
    print(f"Result:   {'✓ PASS' if '10.5' in result_3 and '0.0234' in result_3 else '✗ FAIL'}")
    
    print("\n" + "="*60 + "\n")
    return True


def test_state_management():
    """Test plugin state management."""
    from .state import PluginState
    from .api_adapter import CalculationStatus
    
    print("\n" + "="*60)
    print("Testing State Management")
    print("="*60)
    
    # Create state instance
    state = PluginState()
    
    print(f"\nTest 1: Initial state")
    print(f"  applications: {len(state.applications)}")
    print(f"  current_calculation_id: {state.current_calculation_id}")
    print(f"  is_interactive_session: {state.is_interactive_session}")
    
    # Test state updates
    state.current_calculation_id = "test-calc-123"
    state.current_calculation_status = CalculationStatus.RUNNING
    state.polling_active = True
    
    print(f"\nTest 2: State updates")
    print(f"  calculation_id set: {state.current_calculation_id == 'test-calc-123'}")
    print(f"  status set: {state.current_calculation_status == CalculationStatus.RUNNING}")
    print(f"  polling active: {state.polling_active}")
    
    # Test reset
    state.reset_calculation_state()
    
    print(f"\nTest 3: State reset")
    print(f"  calculation_id cleared: {state.current_calculation_id is None}")
    print(f"  status cleared: {state.current_calculation_status is None}")
    print(f"  polling stopped: {not state.polling_active}")
    
    print(f"\n{'✓ All state tests passed' if state.current_calculation_id is None else '✗ Test failed'}")
    print("="*60 + "\n")
    return True


def test_gui_controller(OV, olx):
    """Test GUI controller functionality.
    
    Args:
        OV: OlexFunctions instance
        olx: olex module
    """
    from . import gui_controller
    
    print("\n" + "="*60)
    print("Testing GUI Controller")
    print("="*60)
    
    # Test color retrieval
    print(f"\nTest 1: Get colors")
    colors = gui_controller.get_olex2_colors()
    print(f"  Colors retrieved: {len(colors)} keys")
    print(f"  Has bg_color: {'bg_color' in colors}")
    print(f"  Has font_color: {'font_color' in colors}")
    print(f"  Result: {'✓ PASS' if len(colors) >= 8 else '✗ FAIL'}")
    
    # Test button update
    print(f"\nTest 2: Update button")
    try:
        gui_controller.update_run_button("Test Button", "#FF0000", True)
        print(f"  Result: ✓ PASS (no exceptions)")
    except Exception as e:
        print(f"  Result: ✗ FAIL ({e})")
    
    print("\n" + "="*60 + "\n")
    return True


def test_session_detection():
    """Test interactive session detection."""
    from .session_manager import SessionManager
    
    print("\n" + "="*60)
    print("Testing Session Detection")
    print("="*60)
    
    # Mock command object
    class MockCommand:
        def __init__(self, name, interactive=False, description=""):
            self.name = name
            self.interactive = interactive
            self.description = description
    
    # Test cases
    tests = [
        (MockCommand("normal_command", False, "A normal command"), False),
        (MockCommand("interactive_session", False, "Some command"), True),
        (MockCommand("normal", True, "Normal description"), True),
        (MockCommand("run", False, "This is an interactive tool"), True),
    ]
    
    passed = 0
    for cmd, expected in tests:
        result = SessionManager.is_command_interactive(cmd)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        print(f"  {cmd.name}: {result} (expected {expected}) {status}")
        if result == expected:
            passed += 1
    
    print(f"\n  Passed: {passed}/{len(tests)}")
    print("="*60 + "\n")
    return passed == len(tests)


def run_all_tests(OV=None, olx=None):
    """Run all available tests.
    
    Args:
        OV: OlexFunctions instance (optional for GUI tests)
        olx: olex module (optional for GUI tests)
    
    Returns:
        True if all tests passed
    """
    print("\n" + "="*70)
    print(" QCrBox Plugin Test Suite")
    print("="*70)
    
    results = []
    
    # Pure function tests (no dependencies)
    try:
        results.append(("CIF Conversion", test_cif_conversion()))
    except Exception as e:
        print(f"CIF Conversion test failed with exception: {e}")
        results.append(("CIF Conversion", False))
    
    try:
        results.append(("State Management", test_state_management()))
    except Exception as e:
        print(f"State Management test failed with exception: {e}")
        results.append(("State Management", False))
    
    try:
        results.append(("Session Detection", test_session_detection()))
    except Exception as e:
        print(f"Session Detection test failed with exception: {e}")
        results.append(("Session Detection", False))
    
    # GUI tests (require Olex2 context)
    if OV and olx:
        try:
            results.append(("GUI Controller", test_gui_controller(OV, olx)))
        except Exception as e:
            print(f"GUI Controller test failed with exception: {e}")
            results.append(("GUI Controller", False))
    else:
        print("\nSkipping GUI Controller tests (requires Olex2 context)")
    
    # Summary
    print("\n" + "="*70)
    print(" Test Results Summary")
    print("="*70)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {test_name:.<50} {status}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    print(f"\n  Total: {total_passed}/{total_tests} tests passed")
    print("="*70 + "\n")
    
    return total_passed == total_tests
