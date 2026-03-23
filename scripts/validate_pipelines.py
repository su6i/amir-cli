#!/usr/bin/env python3
"""
Integration validation script for refactored translation pipelines
Validates that all extracted pipelines can be imported and have correct signatures
"""

import sys
import inspect
from pathlib import Path

# Add lib/python to path so we can import subtitle module
sys.path.insert(0, str(Path(__file__).parent.parent / "lib" / "python"))

def validate_imports():
    """Verify all pipeline functions can be imported"""
    print("\n✓ Checking pipeline imports...")
    try:
        from subtitle.translation import (
            run_deepseek_translation_pipeline,
            run_gemini_translation_pipeline,
            run_litellm_translation_pipeline,
            run_minimax_translation_pipeline,
        )
        print("  ✅ All pipeline functions imported successfully")
        return True
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False

def validate_signatures():
    """Verify all pipelines have correct function signatures"""
    print("\n✓ Checking pipeline function signatures...")
    
    from subtitle.translation import (
        run_deepseek_translation_pipeline,
        run_gemini_translation_pipeline,
        run_litellm_translation_pipeline,
        run_minimax_translation_pipeline,
    )
    
    expected_params = {
        'processor', 'texts', 'target_lang', 'source_lang',
        'batch_size', 'original_entries', 'output_srt',
        'existing_translations'
    }
    
    all_ok = True
    for func_name, func in [
        ('DeepSeek', run_deepseek_translation_pipeline),
        ('Gemini', run_gemini_translation_pipeline),
        ('LiteLLM', run_litellm_translation_pipeline),
        ('MiniMax', run_minimax_translation_pipeline),
    ]:
        sig = inspect.signature(func)
        params = set(sig.parameters.keys())
        
        if expected_params.issubset(params):
            print(f"  ✅ {func_name:12} pipeline signature OK")
        else:
            missing = expected_params - params
            print(f"  ❌ {func_name:12} pipeline missing: {missing}")
            all_ok = False
    
    return all_ok

def validate_processor_methods():
    """Verify processor still has all translation methods"""
    print("\n✓ Checking processor translation methods...")
    
    from subtitle.processor import SubtitleProcessor
    
    expected_methods = [
        'translate_with_deepseek',
        'translate_with_gemini',
        'translate_with_litellm',
        'translate_with_minimax',
    ]
    
    all_ok = True
    for method_name in expected_methods:
        if hasattr(SubtitleProcessor, method_name):
            method = getattr(SubtitleProcessor, method_name)
            sig = inspect.signature(method)
            params = list(sig.parameters.keys())
            
            # Should have self + 7 parameters
            if len(params) == 8:
                print(f"  ✅ {method_name:30} (signature OK)")
            else:
                print(f"  ⚠️  {method_name:30} (got {len(params)} params, expected 8)")
        else:
            print(f"  ❌ {method_name:30} NOT FOUND")
            all_ok = False
    
    return all_ok

def validate_method_delegation():
    """Verify processor methods delegate to pipelines"""
    print("\n✓ Checking processor method delegation...")
    
    from subtitle.processor import SubtitleProcessor
    
    methods_to_check = [
        ('translate_with_deepseek', 'run_deepseek_translation_pipeline'),
        ('translate_with_gemini', 'run_gemini_translation_pipeline'),
        ('translate_with_litellm', 'run_litellm_translation_pipeline'),
        ('translate_with_minimax', 'run_minimax_translation_pipeline'),
    ]
    
    all_ok = True
    for method_name, pipeline_name in methods_to_check:
        method = getattr(SubtitleProcessor, method_name)
        source = inspect.getsource(method)
        
        if pipeline_name in source:
            # Count lines - should be thin (< 20 lines)
            lines = len([l for l in source.split('\n') if l.strip()])
            if lines < 20:
                print(f"  ✅ {method_name:30} delegates to {pipeline_name}")
            else:
                print(f"  ⚠️  {method_name:30} longer than expected ({lines} lines)")
        else:
            print(f"  ❌ {method_name:30} does NOT delegate to {pipeline_name}")
            all_ok = False
    
    return all_ok

def validate_exports():
    """Verify all pipelines are properly exported"""
    print("\n✓ Checking module exports...")
    
    from subtitle import translation
    
    expected_exports = [
        'run_deepseek_translation_pipeline',
        'run_gemini_translation_pipeline',
        'run_litellm_translation_pipeline',
        'run_minimax_translation_pipeline',
    ]
    
    all_ok = True
    for export_name in expected_exports:
        if hasattr(translation, export_name):
            print(f"  ✅ {export_name:40} exported")
        else:
            print(f"  ❌ {export_name:40} NOT exported")
            all_ok = False
    
    return all_ok

def main():
    """Run all validations"""
    print("\n" + "="*70)
    print("  TRANSLATION PIPELINE REFACTORING VALIDATION")
    print("="*70)
    
    results = []
    
    try:
        results.append(("Imports", validate_imports()))
        results.append(("Function Signatures", validate_signatures()))
        results.append(("Processor Methods", validate_processor_methods()))
        results.append(("Method Delegation", validate_method_delegation()))
        results.append(("Module Exports", validate_exports()))
    except Exception as e:
        print(f"\n❌ Validation error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Summary
    print("\n" + "="*70)
    print("  VALIDATION SUMMARY")
    print("="*70)
    
    for check_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}  {check_name}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "="*70)
    if all_passed:
        print("🎉 ALL VALIDATIONS PASSED!")
        print("="*70)
        return 0
    else:
        print("⚠️  SOME VALIDATIONS FAILED")
        print("="*70)
        return 1

if __name__ == '__main__':
    sys.exit(main())
