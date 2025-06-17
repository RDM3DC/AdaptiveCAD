# AdaptiveCAD Display Bug Fix Summary

## Problem Description
After performing a **Cut** operation followed by a **Move** operation, the old geometry (before the cut) would remain visible in the display, and a new geometry would appear at the moved location without the cut applied. This resulted in duplicate or incorrect geometry being displayed.

## Root Cause Analysis

The issue was caused by inconsistent feature consumption marking between different modeling operations:

1. **CutCmd** properly marked the target shape as consumed using `DOCUMENT[i1].params['consumed'] = True`
2. **MoveCmd** only relied on the automatic consumption detection in `rebuild_scene()` but didn't explicitly mark the source feature as consumed
3. **UnionCmd** and **IntersectCmd** had similar inconsistencies
4. **IntersectCmd** used different parameter names ("a", "b") instead of standard ("target", "tool")

## Fixes Applied

### 1. Fixed MoveCmd (Primary Fix)
**File:** `adaptivecad/command_defs.py` - Lines ~655-658

Added explicit consumption marking to MoveCmd:
```python
# Mark the source shape as consumed (hidden)
if hasattr(DOCUMENT[shape_idx], 'params'):
    DOCUMENT[shape_idx].params['consumed'] = True
    print(f"[MoveCmd] Feature '{DOCUMENT[shape_idx].name}' (index {shape_idx}) marked as consumed: {DOCUMENT[shape_idx].params}") # DEBUG
```

### 2. Fixed IntersectCmd Parameter Names
**File:** `adaptivecad/command_defs.py` - Line ~1007

Changed parameter names for consistency:
```python
# Before: Feature("Intersect", {"a": i1, "b": i2}, common)
# After:  Feature("Intersect", {"target": i1, "tool": i2}, common)
```

### 3. Added Explicit Consumption Marking to UnionCmd
**File:** `adaptivecad/command_defs.py` - Lines ~704-707

Added explicit consumption marking for consistency:
```python
# Mark the target and tool as consumed (hidden)
if hasattr(DOCUMENT[i1], 'params'):
    DOCUMENT[i1].params['consumed'] = True
if hasattr(DOCUMENT[i2], 'params'):
    DOCUMENT[i2].params['consumed'] = True
```

### 4. Added Explicit Consumption Marking to IntersectCmd
**File:** `adaptivecad/command_defs.py` - Lines ~1012-1015

Added explicit consumption marking for consistency:
```python
# Mark the target and tool as consumed (hidden)
if hasattr(DOCUMENT[i1], 'params'):
    DOCUMENT[i1].params['consumed'] = True
if hasattr(DOCUMENT[i2], 'params'):
    DOCUMENT[i2].params['consumed'] = True
```

## How the Fix Works

The display system uses two mechanisms to hide consumed features:

1. **Automatic Detection:** `rebuild_scene()` automatically detects features that are consumed by looking at "target" and "tool" parameters in Move/Boolean operations
2. **Explicit Marking:** Features can be explicitly marked as consumed using `params['consumed'] = True`

The fix ensures both mechanisms work together consistently:

- When a **Move** operation is performed, the source feature is explicitly marked as consumed
- When **Boolean** operations (Union, Cut, Intersect) are performed, both operands are explicitly marked as consumed
- The `rebuild_scene()` function displays only features that are not consumed by either mechanism

## Testing

Created comprehensive test (`test_display_bug_fix.py`) that verifies:

1. Creation of two box features
2. Cut operation consuming original boxes
3. Move operation consuming cut result
4. Final state: only the moved result is visible

**Test Result:** ✅ SUCCESS - Only the correct, updated geometry is displayed

## Workflow Verification

The fix ensures the following workflow works correctly:

1. **Create Box A** → Box A visible
2. **Create Box B** → Box A, Box B visible  
3. **Cut A with B** → Only Cut result visible (A, B hidden)
4. **Move Cut result** → Only Moved Cut result visible (Cut result hidden)

## Impact

- ✅ **Fixed:** Cut + Move operations now display correctly
- ✅ **Improved:** All Boolean operations (Union, Cut, Intersect) are now consistent
- ✅ **Enhanced:** Feature consumption marking is now robust and predictable
- ✅ **Maintained:** Backward compatibility with existing project files
- ✅ **Added:** Debug logging for troubleshooting consumption issues

## Files Modified

1. `adaptivecad/command_defs.py` - Primary fixes for MoveCmd, UnionCmd, CutCmd, IntersectCmd
2. `test_display_bug_fix.py` - Comprehensive test to verify the fix

The display bug has been completely resolved and the modeling workflow now behaves correctly.
