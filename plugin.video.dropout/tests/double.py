import inspect
import logging
import sys
from collections import OrderedDict
from collections.abc import Callable
from functools import partial
from types import ModuleType
from typing import TYPE_CHECKING, Any, ClassVar, Generic, ParamSpec, Protocol, Self, TypeVar, cast
from unittest import mock

import pytest

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")
P = ParamSpec("P")


class Double(Generic[T]):
    class POD:
        _real: ClassVar[type]
        _data: dict[str, Any]

        def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
            bound = inspect.signature(self._real).bind(*args, **kwargs)
            bound.apply_defaults()
            object.__setattr__(self, "_data", dict(bound.arguments))

        @classmethod
        def expected(cls, **kwargs: Any) -> "Double.POD":  # noqa: ANN401
            this = cls()
            for k, v in kwargs.items():
                this._data[k] = v
            return this

        def __getattr__(self, name: str) -> Any:  # noqa: ANN401
            if name in self._data:
                return self._data[name]
            method = getattr(self._real, name, None)
            if name.startswith("_") or not inspect.isfunction(method):
                msg = f"Unknown attribute {name!r} for {self.__class__.__name__}"
                raise AttributeError(msg)
            return lambda *args, **kwargs: self._call(name, method, *args, **kwargs)

        def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN401
            self._data[name] = value

        def _call(self, name: str, method: Any, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            bound = inspect.signature(method).bind(self, *args, **kwargs)
            values = list(bound.arguments.values())[1:]
            verb, key = name[:3], name[3:]
            key = key[0].lower() + key[1:]
            match verb, values:
                case "set", [value]:
                    self._data[key] = value
                case "set", [key, value]:
                    self._data[f"prop_{key}"] = value
                case "get", []:
                    return self._data.get(key)
                case "get", [key]:
                    return self._data.get(f"prop_{key}")
                case _:
                    self._data.setdefault(f"call_{name}", []).append(
                        {k: v for k, v in bound.arguments.items() if k != "self"}
                    )
            return None

        def __repr__(self) -> str:
            kv = [f"{k}={v!r}" for k, v in self._data.items()]
            return f"{self.__class__.__name__}({', '.join(kv)})"

        def __hash__(self) -> int:
            return hash(self._data)

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, Double.POD):
                return NotImplemented
            return self._data == other._data

    Handler = tuple[bool, R, bool]

    class _Register(Protocol):
        def __call__(self, produce: Callable[[], R], *, many: bool = False) -> None: ...

    class Returning(Generic[R]):
        def __init__(self, register: "Double._Register") -> None:
            self._register = register

        def returns(self, value: R, *, many: bool = False) -> Self:
            self._register(lambda: value, many=many)
            return self

        def raises(self, error: BaseException | type[BaseException]) -> Self:
            def fail() -> R:
                raise error

            self._register(fail)
            return self

    _pending: ClassVar[list["Double[Any]"]] = []

    @classmethod
    def reset(cls) -> None:
        cls._pending.clear()

    @classmethod
    def ensure(cls) -> None:
        for dbl in cls._pending:
            dbl.verify()
        cls._pending.clear()

    def __init__(self, cls: type[T] | ModuleType) -> None:
        self.cls = cls
        self.mock = mock.create_autospec(cls, instance=True, spec_set=True)
        self._answers: dict[Any, list[tuple[inspect.BoundArguments, Callable[[], Any], bool]]] = {}
        self._overrides: dict[Any, list[Callable[[inspect.BoundArguments], self.Handler]]] = {}
        for name in self.get_methods(cls):
            method = getattr(self.mock, name)
            self._answers[method] = []
            method.side_effect = partial(self._answer, method, name)
        for name, value in vars(cls).items():
            if isinstance(value, int | str) and not name.startswith("_"):
                setattr(self.mock, name, value)
        self._ = cast("T", self.mock)
        self._instances = []
        self._pending.append(self)

    if not TYPE_CHECKING:

        def __getattr__(self, name: str) -> Any:  # noqa: ANN401
            return getattr(self.mock, name)

    @property
    def real(self) -> T:
        if self._instances:
            return self._instances[-1]
        msg = "No instance of the double has been created yet"
        raise ValueError(msg)

    def handle(self, method: Callable[P, R], handle: Callable[P, tuple[bool, R]], *, quiet: bool = False) -> None:
        def _wrapper(given: inspect.BoundArguments) -> self.Handler:
            return (*handle(*given.args, **given.kwargs), quiet)

        self._overrides.setdefault(method, []).append(_wrapper)

    def expect(self, method: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> Returning:
        double = cast("Any", method)
        expected = inspect.signature(double).bind(*args, **kwargs)

        def register(produce: Callable[[], R], *, many: bool = False) -> None:
            if double not in self._answers:
                pytest.fail(f"method {double} is not a mock")
            self._answers[double].append((expected, produce, many))

        return self.Returning(register)

    def _find_match(self, method: Any, given: inspect.BoundArguments) -> Handler:  # noqa: ANN401
        for handle in self._overrides.get(method, []):
            handled, returns, quiet = handle(given)
            if handled:
                return (True, returns, quiet)
        for expected, produce, many in self._answers[method]:
            if expected.arguments == given.arguments:
                if not many:
                    self._answers[method].remove((expected, produce, many))
                return (True, produce(), False)
        return (False, None, False)

    def _fqdn(self, name: str) -> str:
        if inspect.ismodule(self.cls):
            return f"{self.cls.__name__}.{name}"
        return f"{self.cls.__module__}.{self.cls.__name__}.{name}"

    def _answer(self, method: Any, name: str, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        given = inspect.signature(method).bind(*args, **kwargs)
        found, res, quiet = self._find_match(method, given)
        if found and quiet:
            return res
        fname = self._fqdn(name)
        sig = self._fmt_call(fname, args, kwargs)
        if found:
            logger.info("[%-7s] %s -> %s", "double", sig, repr(res))
            return res
        indent = " • "
        expected = "\n".join(
            f"+{indent}{self._fmt_call(fname, exp.args, exp.kwargs)}" for exp, *_ in self._answers[method]
        )
        expected_list = f"\n{expected}" if expected else " <none>"
        logger.error("%s", f"unexpected call: {fname}\n-{indent}{sig}\nexpected:{expected_list}")
        assert given.arguments in [exp.arguments for exp, *_ in self._answers[method]]
        return None

    def _fmt_call(self, name: str, args: Any, kwargs: Any) -> str:  # noqa: ANN401
        sig = ""
        if args:
            sig += ", ".join(repr(arg) for arg in args)
        if kwargs:
            if args:
                sig += ", "
            sig += ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        return f"{name}({sig})"

    def verify(self) -> None:
        issues = []
        for method, answers in self._answers.items():
            for expected, *_ in answers:
                fn = self._fmt_call(self._fqdn(method.__name__), expected.args, expected.kwargs)
                issues.append(f"expected call not made: {fn}")
        if issues:
            pytest.fail("\n".join(issues))

    @classmethod
    def get_methods(cls, obj: type[T] | ModuleType) -> OrderedDict[str, Any]:
        if isinstance(obj, type):
            return OrderedDict(
                (name, value) for name, value in inspect.getmembers(obj, inspect.isroutine) if not name.startswith("_")
            )
        return OrderedDict((name, getattr(obj, name)) for name in dir(obj) if inspect.isfunction(getattr(obj, name)))

    def sub_double(self, cls: type[T]) -> "Double[T]":
        dbl = Double(cls)
        self.__subtype(
            cls.__name__,
            parents=(cls.__base__,),
            __init__=lambda self, *_args, **_kwargs: dbl._instances.append(self),
            __getattr__=lambda _self, name: getattr(dbl.mock, name),
        )
        return dbl

    def sub_pod(self, cls: type[T]) -> type[T]:
        return cast("type[T]", self.__subtype(cls.__name__, parents=(Double.POD,), _real=cls))

    def __subtype(self, name: str, *, parents: tuple[type | None, ...] | None = None, **kwargs: Any) -> type:  # noqa: ANN401
        pars = (*(p for p in parents if p is not None),) if parents is not None else ()
        typ = type(name, pars, kwargs)
        setattr(self.mock, name, typ)
        return typ


class Module(Double):
    def __init__(self, module: ModuleType) -> None:
        super().__init__(module)
        sys.modules[module.__name__] = self.mock
