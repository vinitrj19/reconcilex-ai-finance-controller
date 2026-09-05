"""
Minimal pytest-compatible shim.

This is NOT pytest. It exists only because pytest is not installed in this
environment (no network access to fetch it) and the milestone instructions
require running whatever test suite exists rather than skipping tests
silently. It supports the small subset of pytest features the tests in
this repo actually use: @pytest.fixture (including generator/teardown
fixtures), fixture-as-test-argument dependency injection, pytest.approx,
and pytest.raises. Nothing about test result reporting here should be
confused with a real pytest run - the final report explicitly labels
results produced by this shim.
"""
import inspect


class ApproxValue:
    def __init__(self, expected, rel=1e-6, abs_tol=1e-9):
        self.expected = expected
        self.rel = rel
        self.abs_tol = abs_tol

    def __eq__(self, other):
        try:
            return abs(other - self.expected) <= max(self.rel * abs(self.expected), self.abs_tol)
        except TypeError:
            return NotImplemented

    def __repr__(self):
        return f"approx({self.expected!r})"


class RaisesContext:
    def __init__(self, exc_type):
        self.exc_type = exc_type
        self.raised = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            raise AssertionError(f"DID NOT RAISE {self.exc_type}")
        self.raised = exc_val
        return issubclass(exc_type, self.exc_type)


class FixtureFunc:
    def __init__(self, func):
        self.func = func
        self.__name__ = func.__name__


def fixture(func=None, **kwargs):
    if func is None:
        def deco(f):
            return FixtureFunc(f)
        return deco
    return FixtureFunc(func)


def approx(expected, rel=1e-6, abs=1e-9):
    return ApproxValue(expected, rel, abs)


def raises(exc_type):
    return RaisesContext(exc_type)


class _Mark:
    def parametrize(self, *a, **k):
        def deco(f):
            return f
        return deco

    def skip(self, *a, **k):
        def deco(f):
            f.__skip__ = True
            return f
        return deco


mark = _Mark()


class Fail(Exception):
    pass


def fail(msg=""):
    raise Fail(msg)
