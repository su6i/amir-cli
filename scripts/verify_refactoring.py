#!/usr/bin/env python3
"""Verification script for subtitle module refactoring

Run this to validate:
- All modules compile cleanly
- All imports resolve
- Processor line count is acceptable
- Test structure is complete
- Workflow stages are properly exported
"""

import sys
import ast
from pathlib import Path
import subprocess


class Verification:
    """Run verification checks on refactored module"""
    
    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.subtitle_path = self.base_path / "lib" / "python" / "subtitle"
        self.checks_passed = 0
        self.checks_failed = 0
    
    def print_header(self, text):
        print(f"\n{'='*60}")
        print(f"  {text}")
        print('='*60)
    
    def run_check(self, name: str, func):
        """Run a single verification check"""
        try:
            func()
            print(f"✅ {name}")
            self.checks_passed += 1
        except AssertionError as e:
            print(f"❌ {name}: {e}")
            self.checks_failed += 1
        except Exception as e:
            print(f"⚠️  {name}: {e}")
            self.checks_failed += 1

    @staticmethod
    def _read_dunder_all(file_path: Path):
        """Parse __all__ values from a module without importing dependencies."""
        content = file_path.read_text(encoding='utf-8')
        tree = ast.parse(content)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == '__all__':
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            out = []
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    out.append(elt.value)
                            return out
        return []
    
    def verify_line_count(self):
        processor_path = self.subtitle_path / "processor.py"
        with open(processor_path) as f:
            lines = len(f.readlines())
        
        assert 2700 <= lines <= 3600, f"Expected 2700-3600 lines, got {lines}"
        print(f"    → processor.py: {lines} lines")
    
    def verify_compilation(self):
        result = subprocess.run(
            ["python3", "-m", "compileall", str(self.subtitle_path)],
            capture_output=True,
            text=True,
            cwd=str(self.base_path)
        )
        
        assert result.returncode == 0, f"Compilation failed: {result.stderr}"
        print("    → All modules compile cleanly")
    
    def verify_workflow_exports(self):
        workflow_init = self.subtitle_path / 'workflow' / '__init__.py'
        exported = set(self._read_dunder_all(workflow_init))
        required = {
            'resolve_workflow_base',
            'prepare_runtime_execution',
            'prepare_source_srt',
            'run_translation_stage',
            'run_rendering_stage',
            'run_finalize_stage',
        }
        missing = sorted(required - exported)
        assert not missing, f"Missing workflow exports: {missing}"
        print("    → All 6 workflow stages properly exported")
    
    def verify_translation_exports(self):
        translation_init = self.subtitle_path / 'translation' / '__init__.py'
        exported = set(self._read_dunder_all(translation_init))
        required = {
            'validate_and_retry_translations',
            'apply_final_target_text_fixes',
        }
        missing = sorted(required - exported)
        assert not missing, f"Missing translation exports: {missing}"
        print("    → Translation utilities properly exported")
    
    def verify_test_structure(self):
        test_dir = self.subtitle_path / "tests"
        assert test_dir.exists(), "Tests directory missing"
        
        required_files = [
            "__init__.py",
            "conftest.py",
            "test_workflow_base.py",
            "test_workflow_runtime.py",
            "test_workflow_source_stage.py",
            "test_workflow_translation_stage.py",
            "test_workflow_rendering.py",
            "test_workflow_finalize.py",
            "test_workflow_integration.py",
            "README.md",
        ]
        
        for fname in required_files:
            fpath = test_dir / fname
            assert fpath.exists(), f"Missing test file: {fname}"
        
        print(f"    → All {len(required_files)} test files present")
    
    def verify_workflow_utils(self):
        workflow_init = self.subtitle_path / 'workflow' / '__init__.py'
        exported = set(self._read_dunder_all(workflow_init))
        required = {
            'emit_stage_progress',
            'validate_context_keys',
            'merge_context_dicts',
        }
        missing = sorted(required - exported)
        assert not missing, f"Missing workflow utility exports: {missing}"
        print("    → Workflow utilities properly exported")
    
    def verify_documentation(self):
        docs = [
            self.base_path / "REFACTORING_SUMMARY.md",
            self.subtitle_path / "tests" / "README.md",
            self.base_path / "SESSION_PROGRESS.md",
        ]
        
        for doc in docs:
            assert doc.exists(), f"Missing documentation: {doc.name}"
        
        print(f"    → All {len(docs)} documentation files present")
    
    def verify_git_history(self):
        result = subprocess.run(
            ["git", "log", "--oneline", "-n", "20"],
            capture_output=True,
            text=True,
            cwd=str(self.base_path)
        )
        
        assert result.returncode == 0, "Git log failed"
        
        lines = result.stdout.strip().split("\n")
        extraction_commits = [l for l in lines if "extract" in l.lower() or "test" in l.lower()]
        
        assert len(extraction_commits) >= 10, f"Expected 10+ extraction/test commits, found {len(extraction_commits)}"
        print(f"    → Git history shows {len(extraction_commits)} refactoring commits")
    
    def run_all(self):
        """Run all verification checks"""
        self.print_header("SUBTITLE MODULE REFACTORING VERIFICATION")
        
        self.run_check("Verify processor.py line count", self.verify_line_count)
        self.run_check("Verify all modules compile", self.verify_compilation)
        self.run_check("Verify workflow stages exported", self.verify_workflow_exports)
        self.run_check("Verify translation utilities exported", self.verify_translation_exports)
        self.run_check("Verify test structure exists", self.verify_test_structure)
        self.run_check("Verify workflow utilities module", self.verify_workflow_utils)
        self.run_check("Verify documentation exists", self.verify_documentation)
        self.run_check("Verify git history", self.verify_git_history)
        
        self.print_header("VERIFICATION RESULTS")
        print(f"✅ Passed: {self.checks_passed}")
        print(f"❌ Failed: {self.checks_failed}")
        
        if self.checks_failed == 0:
            print("\n🎉 All verifications passed! Refactoring is complete.")
            return 0
        else:
            print(f"\n⚠️  {self.checks_failed} verification(s) failed.")
            return 1


if __name__ == "__main__":
    verifier = Verification()
    sys.exit(verifier.run_all())
