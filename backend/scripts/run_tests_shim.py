"""
Runs the tests/ suite using scripts/_pytest_shim.py because real pytest is
not installed and this environment has no network access to fetch it.
Explicitly NOT a claim that real pytest passed - see final report.

Skips test_m5_reasoning.py entirely (it requires `pydantic`, also not
installed) rather than faking a result for it.
"""
import importlib.util
import inspect
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts._pytest_shim as pytest_shim  # noqa: E402
sys.modules["pytest"] = pytest_shim

TEST_DIR = ROOT / "tests"
SKIP_FILES = {"test_m5_reasoning.py"}  # requires pydantic - not installed


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def resolve_fixture(name, fixtures, cache, module):
    if name in cache:
        return cache[name]
    ff = fixtures[name]
    sig = inspect.signature(ff.func)
    kwargs = {}
    teardown_gens = []
    for pname in sig.parameters:
        val, gens = resolve_fixture(pname, fixtures, cache, module)
        kwargs[pname] = val
        teardown_gens.extend(gens)
    result = ff.func(**kwargs)
    gens_here = []
    if inspect.isgenerator(result):
        value = next(result)
        gens_here = [result]
    else:
        value = result
    cache[name] = (value, teardown_gens + gens_here)
    return cache[name]


def run_file(path: Path):
    mod = load_module(path)
    fixtures = {
        name: obj for name, obj in vars(mod).items()
        if isinstance(obj, pytest_shim.FixtureFunc)
    }
    tests = [
        (name, obj) for name, obj in vars(mod).items()
        if name.startswith("test_") and inspect.isfunction(obj)
    ]
    passed, failed = 0, []
    for name, fn in tests:
        cache = {}
        try:
            sig = inspect.signature(fn)
            kwargs = {}
            all_gens = []
            for pname in sig.parameters:
                if pname in fixtures:
                    val, gens = resolve_fixture(pname, fixtures, cache, mod)
                    kwargs[pname] = val
                    all_gens.extend(gens)
            fn(**kwargs)
            passed += 1
        except Exception as e:
            failed.append((name, "".join(traceback.format_exception_only(type(e), e)).strip()))
        finally:
            for g in reversed(all_gens if 'all_gens' in dir() else []):
                pass
            for cache_entry in cache.values():
                for g in cache_entry[1]:
                    try:
                        next(g)
                    except StopIteration:
                        pass
    return passed, failed


def main():
    total_passed = 0
    total_failed = []
    ran_files = []
    for path in sorted(TEST_DIR.glob("test_*.py")):
        if path.name in SKIP_FILES:
            print(f"SKIPPED {path.name} (requires pydantic, not installed in this environment)")
            continue
        passed, failed = run_file(path)
        ran_files.append(path.name)
        total_passed += passed
        total_failed.extend((path.name, n, msg) for n, msg in failed)
        print(f"{path.name}: {passed} passed, {len(failed)} failed")
        for n, msg in failed:
            print(f"    FAILED {n}: {msg}")

    print()
    print(f"[pytest-compatible shim] {total_passed} passed, {len(total_failed)} failed "
          f"across {len(ran_files)} files ({', '.join(ran_files)})")
    return 0 if not total_failed else 1


if __name__ == "__main__":
    sys.exit(main())
