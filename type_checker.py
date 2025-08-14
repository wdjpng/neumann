import os
import inspect
import importlib
from pathlib import Path
from typing import get_type_hints, get_origin, get_args, Annotated
from pydantic import validate_call, ConfigDict, BeforeValidator

# Optional imports for complex type validation
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    
try:
    import pymupdf
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Custom validators for complex types (only if libraries are available)
if PIL_AVAILABLE:
    def validate_pil_image(v):
        """Validate PIL Image - just check if it's an Image instance"""
        if isinstance(v, Image.Image):
            return v
        raise ValueError(f"Expected PIL Image, got {type(v)}")
    
    PILImage = Annotated[Image.Image, BeforeValidator(validate_pil_image)]

if PYMUPDF_AVAILABLE:
    def validate_pymupdf_document(v):
        """Validate pymupdf Document - just check if it's a Document instance"""
        if isinstance(v, pymupdf.Document):
            return v
        raise ValueError(f"Expected pymupdf Document, got {type(v)}")
    
    PyMuPDFDocument = Annotated[pymupdf.Document, BeforeValidator(validate_pymupdf_document)]

def patch_function_annotations(func):
    """Replace complex type annotations with Pydantic-friendly ones"""
    sig = inspect.signature(func)
    new_params = []
    
    for param in sig.parameters.values():
        new_annotation = param.annotation
        
        # Replace PIL.Image.Image with our custom type (if PIL is available)
        if PIL_AVAILABLE and param.annotation == Image.Image:
            new_annotation = PILImage
        # Replace pymupdf.Document with our custom type (if pymupdf is available)
        elif PYMUPDF_AVAILABLE and param.annotation == pymupdf.Document:
            new_annotation = PyMuPDFDocument
            
        new_param = param.replace(annotation=new_annotation)
        new_params.append(new_param)
    
    # Handle return annotation
    new_return = sig.return_annotation
    if PIL_AVAILABLE and sig.return_annotation == Image.Image:
        new_return = PILImage
    elif PYMUPDF_AVAILABLE and sig.return_annotation == pymupdf.Document:
        new_return = PyMuPDFDocument
        
    # Create new signature
    new_sig = sig.replace(parameters=new_params, return_annotation=new_return)
    
    # Create wrapper function with new signature
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    
    wrapper.__signature__ = new_sig
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    
    return wrapper

def has_type_hints(func) -> bool:
    """Check if function has any type annotations"""
    try:
        hints = get_type_hints(func)
        sig = inspect.signature(func)
        
        # Check if it has return annotation or parameter annotations
        return (
            sig.return_annotation != inspect.Signature.empty or
            len(hints) > 0
        )
    except (NameError, AttributeError, TypeError):
        # get_type_hints can fail for various reasons
        return False

def auto_validate_module(module):
    """Add validation to all functions with type hints in a module"""
    validated_count = 0
    
    for name, obj in inspect.getmembers(module):
        if (inspect.isfunction(obj) and 
            not name.startswith('_') and  # Skip private functions
            has_type_hints(obj)):
            
            try:
                # Try direct validation first with more permissive config
                validated_func = validate_call(
                    obj, 
                    config=ConfigDict(
                        arbitrary_types_allowed=True,
                        validate_assignment=False,
                        validate_default=False,
                        validate_return=False
                    )
                )
                setattr(module, name, validated_func)
                validated_count += 1
                print(f"✓ Added validation to {module.__name__}.{name}")
                
            except Exception as e:
                # Check if it's specifically a PIL.Image schema error
                if "PIL.Image.Image" in str(e) and "pydantic-core schema" in str(e):
                    # Try with patched annotations for PIL.Image issues
                    try:
                        patched_func = patch_function_annotations(obj)
                        validated_func = validate_call(
                            patched_func, 
                            config=ConfigDict(
                                arbitrary_types_allowed=True,
                                validate_assignment=False,
                                validate_default=False,
                                validate_return=False
                            )
                        )
                        setattr(module, name, validated_func)
                        validated_count += 1
                        print(f"✓ Added validation to {module.__name__}.{name} (with patched PIL.Image)")
                    except Exception as e2:
                        print(f"⚠ Skipping validation for {module.__name__}.{name} (PIL.Image schema issues)")
                else:
                    print(f"⚠ Skipping validation for {module.__name__}.{name}: {str(e)[:100]}...")
    
    print(f"Auto-validated {validated_count} functions in {module.__name__}")

def auto_validate_package(*module_names):
    """Auto-validate multiple modules"""
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            auto_validate_module(module)
        except ImportError as e:
            print(f"Could not import {module_name}: {e}")
            
def auto_validate_project():
    """Auto-validate all .py files in current directory"""
    current_dir = Path('.')
    
    for py_file in current_dir.glob('*.py'):
        if py_file.name in ('__init__.py', 'auto_validate.py', 'type_checker.py'):
            continue
            
        module_name = py_file.stem
        try:
            module = importlib.import_module(module_name)
            auto_validate_module(module)
        except ImportError as e:
            print(f"Skipped {module_name}: Import error - {e}")
        except Exception as e:
            print(f"Skipped {module_name}: {e}")
            # Don't let one module's errors stop processing others
            continue 