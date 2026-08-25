#!/usr/bin/env python3
"""
Type Sync Check - Compare TypeScript interfaces against Pydantic models.

This script helps catch drift between frontend TypeScript types and backend
Pydantic models. Run it as part of CI to prevent type mismatches.

Usage:
    python scripts/type_sync_check.py [--fail-on-drift]
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


# Configuration
BACKEND_MODELS_DIR = Path(__file__).parent.parent / "backend" / "models"
FRONTEND_TYPES_FILE = Path(__file__).parent.parent / "frontend" / "src" / "lib" / "types.ts"
FAIL_ON_DRIFT = "--fail-on-drift" in sys.argv


def get_pydantic_models() -> Dict[str, Dict[str, str]]:
    """Extract Pydantic model fields from backend models."""
    models: Dict[str, Dict[str, str]] = {}
    
    for model_file in BACKEND_MODELS_DIR.glob("*.py"):
        if model_file.name.startswith("_"):
            continue
            
        try:
            source = model_file.read_text()
            tree = ast.parse(source)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if it's a BaseModel subclass
                    is_model = False
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id in ("BaseModel",):
                            is_model = True
                            break
                        if isinstance(base, ast.Attribute) and base.attr in ("BaseModel",):
                            is_model = True
                            break
                    
                    if is_model:
                        fields = extract_fields(node)
                        if fields:
                            models[node.name] = fields
        except SyntaxError:
            continue
    
    return models


def extract_fields(class_node: ast.ClassDef) -> Dict[str, str]:
    """Extract field definitions from a Pydantic model class."""
    fields: Dict[str, str] = {}
    
    for node in class_node.body:
        # Look for variable annotations
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                field_name = node.target.id
                field_type = infer_type(node.annotation)
                fields[field_name] = field_type
    
    return fields


def infer_type(annotation: ast.expr) -> str:
    """Infer the TypeScript type from an AST annotation."""
    if isinstance(annotation, ast.Name):
        type_map = {
            "str": "string",
            "int": "number",
            "float": "number",
            "bool": "boolean",
            "List": "array",
            "Optional": "nullable",
        }
        return type_map.get(annotation.id, "any")
    
    if isinstance(annotation, ast.Subscript):
        if isinstance(annotation.value, ast.Name):
            if annotation.value.id == "List":
                inner = infer_type(annotation.slice)
                return f"{inner}[]"
            if annotation.value.id == "Optional":
                inner = infer_type(annotation.slice)
                return f"{inner} | null"
    
    return "any"


def get_ts_interfaces() -> Dict[str, Set[str]]:
    """Extract TypeScript interface field names from types.ts."""
    interfaces: Dict[str, Set[str]] = {}
    
    if not FRONTEND_TYPES_FILE.exists():
        return interfaces
    
    source = FRONTEND_TYPES_FILE.read_text()
    
    # Match interface declarations
    interface_pattern = r"export interface\s+(\w+)\s*\{([^}]+)\}"
    matches = re.findall(interface_pattern, source, re.DOTALL)
    
    for interface_name, body in matches:
        fields = set()
        # Extract field names (handle various formats)
        for line in body.split("\n"):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            # Match: fieldName: type; or fieldName?: type;
            field_match = re.match(r"(\w+)[?:]", line)
            if field_match:
                fields.add(field_match.group(1))
        
        if fields:
            interfaces[interface_name] = fields
    
    return interfaces


def compare_types() -> Tuple[List[str], List[str]]:
    """Compare Pydantic models against TypeScript interfaces."""
    pydantic_models = get_pydantic_models()
    ts_interfaces = get_ts_interfaces()
    
    missing_in_ts: List[str] = []
    missing_in_py: List[str] = []
    
    # Check each Pydantic model against TypeScript interface
    for model_name, fields in pydantic_models.items():
        if model_name not in ts_interfaces:
            # Check for common naming variations
            alternatives = [
                model_name,
                model_name.rstrip("s"),
                model_name + "Response",
                model_name + "Create",
                model_name + "Update",
            ]
            found = False
            for alt in alternatives:
                if alt in ts_interfaces:
                    found = True
                    break
            if not found:
                missing_in_ts.append(f"{model_name}: No matching TypeScript interface found")
                continue
        
        ts_fields = ts_interfaces.get(model_name, set())
        py_fields = set(fields.keys())
        
        # Find missing fields
        missing = py_fields - ts_fields
        for field in sorted(missing):
            missing_in_ts.append(f"{model_name}.{field}: Missing in TypeScript")
        
        # Find extra fields in TS
        extra = ts_fields - py_fields
        for field in sorted(extra):
            missing_in_py.append(f"{model_name}.{field}: Extra in TypeScript (not in Pydantic)")
    
    return missing_in_ts, missing_in_py


def main() -> int:
    """Run the type sync check."""
    print("=" * 60)
    print("Type Sync Check - Pydantic vs TypeScript")
    print("=" * 60)
    
    missing_in_ts, missing_in_py = compare_types()
    
    all_issues = missing_in_ts + missing_in_py
    
    if all_issues:
        print("\n❌ DRIFT DETECTED\n")
        for issue in all_issues:
            print(f"  • {issue}")
        return 1
    else:
        print("\n✅ Types are in sync!\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
