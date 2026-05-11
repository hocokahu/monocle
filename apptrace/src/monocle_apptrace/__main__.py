"""
Zero-code instrumentation CLI for monocle_apptrace.

Usage:
    python -m monocle_apptrace deploy_app.py
    python -m monocle_apptrace --config okahu.yaml deploy_app.py
    python -m monocle_apptrace --config okahu.yaml deploy_app.py --arg1 val1
"""
import importlib
import inspect
import io
import json
import os
import runpy
import sys
import threading
from functools import wraps
from pathlib import Path

from monocle_apptrace import setup_monocle_telemetry

_captured_stdout = threading.local()


def _load_yaml_config(config_path):
    try:
        import yaml
    except ImportError:
        print("[monocle] ERROR: PyYAML required for --config. Run: pip install pyyaml")
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def _build_input_output_processor(span_name, package=None, class_name=None, method=None):
    _param_cache = {}

    def _get_param_names(instance):
        cache_key = (package, class_name, method)
        if cache_key in _param_cache:
            return _param_cache[cache_key]
        param_names = []
        try:
            if instance is not None and method:
                func = getattr(instance, method, None)
                if func:
                    param_names = list(inspect.signature(func).parameters.keys())
            elif package and method:
                mod = importlib.import_module(package)
                target = getattr(mod, class_name, None) if class_name else mod
                func = getattr(target, method, None) if target else None
                if func:
                    param_names = list(inspect.signature(func).parameters.keys())
                    if param_names and param_names[0] == 'self':
                        param_names = param_names[1:]
        except Exception:
            pass
        _param_cache[cache_key] = param_names
        return param_names

    def get_input_args(arguments):
        args = arguments.get('args', ())
        kwargs = arguments.get('kwargs', {})
        param_names = _get_param_names(arguments.get('instance'))
        input_data = {}
        for i, arg in enumerate(args):
            key = param_names[i] if i < len(param_names) else f"arg_{i}"
            try:
                if hasattr(arg, '__dict__') and not isinstance(arg, (str, int, float, bool, list, dict)):
                    input_data[key] = f"<{type(arg).__name__}>"
                else:
                    input_data[key] = arg
            except Exception:
                input_data[key] = str(arg)[:200]
        for k, v in kwargs.items():
            try:
                if hasattr(v, '__dict__') and not isinstance(v, (str, int, float, bool, list, dict)):
                    input_data[k] = f"<{type(v).__name__}>"
                else:
                    input_data[k] = v
            except Exception:
                input_data[k] = str(v)[:200]
        return json.dumps(input_data)

    def get_output_result(arguments):
        result = arguments.get('result')
        captured = getattr(_captured_stdout, 'value', '')
        if result is None:
            ex = arguments.get('exception')
            parts = []
            if captured:
                parts.append(captured)
            if ex is not None:
                parts.append(f"{type(ex).__name__}: {ex}")
            return "\n".join(parts) if parts else ""
        try:
            if hasattr(result, '__dict__') and not isinstance(result, (str, int, float, bool, list, dict)):
                output = f"<{type(result).__name__}>: {str(result)}"
            else:
                output = json.dumps(result)
        except Exception:
            output = str(result)
        if captured:
            output = captured + "\n" + output
        return output

    return {
        "type": "custom",
        "attributes": [
            [
                {"attribute": "name", "accessor": lambda args, sn=span_name: sn},
                {"attribute": "type", "accessor": lambda args: "function.custom"},
            ],
        ],
        "events": [
            {
                "name": "data.input",
                "attributes": [
                    {"attribute": "input", "accessor": get_input_args},
                ]
            },
            {
                "name": "data.output",
                "attributes": [
                    {"attribute": "output", "accessor": get_output_result, "phase": "post_execution"},
                ]
            }
        ]
    }


def _stdout_capturing_wrapper(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = _TeeWriter(old_stdout, buf)
        try:
            return func(*args, **kwargs)
        finally:
            sys.stdout = old_stdout
            _captured_stdout.value = buf.getvalue().rstrip()
    return wrapper


class _TeeWriter:
    """Write to both the original stdout and a capture buffer."""
    def __init__(self, original, capture):
        self._original = original
        self._capture = capture

    def write(self, s):
        self._original.write(s)
        self._capture.write(s)

    def flush(self):
        self._original.flush()
        self._capture.flush()

    def __getattr__(self, name):
        return getattr(self._original, name)


def _patch_methods_for_capture(config):
    for item in config.get('instrument', []):
        package = item.get('package')
        class_name = item.get('class')
        method_name = item.get('method')
        try:
            mod = importlib.import_module(package)
            if class_name:
                cls = getattr(mod, class_name, None)
                if cls and hasattr(cls, method_name):
                    setattr(cls, method_name, _stdout_capturing_wrapper(getattr(cls, method_name)))
            else:
                func = getattr(mod, method_name, None)
                if func:
                    setattr(mod, method_name, _stdout_capturing_wrapper(func))
        except Exception:
            pass


def _build_wrapper_methods(config):
    from monocle_apptrace.instrumentation.common.wrapper_method import WrapperMethod
    from monocle_apptrace.instrumentation.common.wrapper import task_wrapper, atask_wrapper

    wrapper_methods = []
    for item in config.get('instrument', []):
        package = item.get('package')
        class_name = item.get('class')
        method = item.get('method')
        span_name = item.get('span_name',
            f"{package}.{class_name}.{method}" if class_name else f"{package}.{method}")
        is_async = item.get('async', False)
        wrapper_methods.append(
            WrapperMethod(
                package=package,
                object_name=class_name,
                method=method,
                span_name=span_name,
                wrapper_method=atask_wrapper if is_async else task_wrapper,
                output_processor=_build_input_output_processor(span_name, package, class_name, method)
            )
        )
    return wrapper_methods


def _set_ci_scopes():
    """Register CI environment metadata as monocle scopes for fact-based trace lookup."""
    from monocle_apptrace.instrumentation.common.utils import set_scopes
    scopes = {}
    github_run_id = os.environ.get("GITHUB_RUN_ID")
    if github_run_id:
        scopes["git.run.id"] = f"github_{github_run_id}"
    github_sha = os.environ.get("GITHUB_SHA")
    if github_sha:
        scopes["git.commit.hash"] = github_sha
    github_workflow = os.environ.get("GITHUB_WORKFLOW")
    if github_workflow:
        scopes["git.workflow.name"] = github_workflow
    if scopes:
        set_scopes(scopes)


def main():
    args = sys.argv[1:]

    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)

    config_path = None
    if '--config' in args:
        idx = args.index('--config')
        if idx + 1 < len(args):
            config_path = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            print("[monocle] ERROR: --config requires a path")
            sys.exit(1)

    if not args or not args[0].endswith(".py"):
        print("Usage: python -m monocle_apptrace [--config FILE] <script.py> [args...]")
        sys.exit(1)

    script = args[0]
    script_args = args[1:]

    script_dir = os.path.dirname(os.path.abspath(script))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    if config_path:
        if not Path(config_path).exists():
            print(f"[monocle] ERROR: Config not found: {config_path}")
            sys.exit(1)

        config = _load_yaml_config(config_path)
        workflow_name = config.get('workflow_name', Path(script).stem)
        packages = list({item['package'] for item in config.get('instrument', []) if 'package' in item})

        for pkg in packages:
            try:
                importlib.import_module(pkg)
            except Exception:
                pass

        _patch_methods_for_capture(config)

        wrapper_methods = _build_wrapper_methods(config)
        setup_monocle_telemetry(
            workflow_name=workflow_name,
            wrapper_methods=wrapper_methods,
            union_with_default_methods=True,
        )
    else:
        workflow_name = Path(script).stem
        setup_monocle_telemetry(workflow_name=workflow_name)
        packages = []

    _set_ci_scopes()

    from monocle_apptrace.instrumentation.common.instrumentor import get_tracer_provider
    _provider = get_tracer_provider()

    module_name = os.path.splitext(os.path.basename(script))[0]
    sys.argv = [os.path.abspath(script)] + script_args

    exit_code = 0
    try:
        target_module = sys.modules.get(module_name)
        if target_module and hasattr(target_module, 'main'):
            target_module.main()
        else:
            runpy.run_path(path_name=script, run_name="__main__")
    except SystemExit as e:
        exit_code = e.code if e.code else 0
    except Exception as e:
        print(f"[monocle] Error: {e}")
        exit_code = 1
    finally:
        if _provider and hasattr(_provider, 'force_flush'):
            _provider.force_flush(timeout_millis=5000)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
