"""
Zero-code instrumentation CLI for monocle_apptrace.

Usage:
    python -m monocle_apptrace deploy_app.py
    python -m monocle_apptrace --config okahu.yaml deploy_app.py
    python -m monocle_apptrace --config okahu.yaml deploy_app.py --arg1 val1
"""
import importlib
import inspect
import json
import os
import runpy
import sys
from pathlib import Path

from monocle_apptrace import setup_monocle_telemetry


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
        return json.dumps(input_data)[:1000]

    def get_output_result(arguments):
        result = arguments.get('result')
        if result is None:
            return "None"
        try:
            if hasattr(result, '__dict__') and not isinstance(result, (str, int, float, bool, list, dict)):
                return f"<{type(result).__name__}>: {str(result)[:200]}"
            return json.dumps(result)[:500]
        except Exception:
            return str(result)[:500]

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

    if config_path:
        if not Path(config_path).exists():
            print(f"[monocle] ERROR: Config not found: {config_path}")
            sys.exit(1)

        config = _load_yaml_config(config_path)
        workflow_name = config.get('workflow_name', Path(script).stem)
        wrapper_methods = _build_wrapper_methods(config)

        setup_monocle_telemetry(
            workflow_name=workflow_name,
            wrapper_methods=wrapper_methods,
            union_with_default_methods=True,
        )

        packages = list({item['package'] for item in config.get('instrument', []) if 'package' in item})
    else:
        workflow_name = Path(script).stem
        setup_monocle_telemetry(workflow_name=workflow_name)
        packages = []

    script_dir = os.path.dirname(os.path.abspath(script))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    for pkg in packages:
        try:
            importlib.import_module(pkg)
        except Exception:
            pass

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
        try:
            from monocle_apptrace.instrumentation.common.instrumentor import get_tracer_provider
            provider = get_tracer_provider()
            if provider and hasattr(provider, 'force_flush'):
                provider.force_flush(timeout_millis=5000)
        except Exception:
            pass

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
