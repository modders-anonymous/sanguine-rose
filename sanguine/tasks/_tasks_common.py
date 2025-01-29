from sanguine.common import *

_proc_num: int = -1  # number of child process
_parallel_count: int = 0


def current_proc_num() -> int:
    global _proc_num
    return _proc_num


def set_current_proc_num(proc_num: int) -> None:
    global _proc_num
    _proc_num = proc_num


def increment_parallel_count() -> None:
    global _parallel_count
    _parallel_count += 1


def decrement_parallel_count() -> None:
    global _parallel_count
    _parallel_count -= 1


def _abort_if_parallel_running() -> None:
    global _parallel_count
    raise_if_not(_parallel_count == 0)


def is_lambda(func: Callable) -> bool:
    return callable(func) and func.__name__ == '<lambda>'


class LambdaReplacement:
    f: Callable[[Any, Any], Any]
    capture: Any

    def __init__(self, f: Callable[[Any, Any], Any], capture: Any) -> None:
        self.f = f
        self.capture = capture

    def call(self, param: Any) -> Any:
        return self.f(self.capture, param)


_global_process_initializers: list[LambdaReplacement] = []


def add_global_process_initializer(init: LambdaReplacement) -> None:
    _abort_if_parallel_running()
    _global_process_initializers.append(init)


def get_global_process_initializers() -> list[LambdaReplacement]:
    return _global_process_initializers


def run_global_process_initializers(inits: list[LambdaReplacement]) -> None:
    for init in inits:
        init.call(None)


class TaskDataDependencies:
    required_tags: list[str]
    required_not_tags: list[str]
    provided_tags: list[str]

    def __init__(self, reqtags: list[str], reqnottags: list[str], provtags: list[str]) -> None:
        self.required_tags = reqtags
        self.required_not_tags = reqnottags
        self.provided_tags = provtags


class Task:
    name: str
    f: Callable[[Any, ...], Any] | None  # variable # of params depending on len(dependencies)
    param: Any
    dependencies: list[str]
    w: float | None
    data_dependencies: TaskDataDependencies

    def __init__(self, name: str, f: Callable, param: Any, dependencies: list[str], w: float | None = None,
                 datadeps: TaskDataDependencies = None) -> None:
        self.name = name
        self.f = f
        self.param = param
        self.dependencies = dependencies
        self.w: float = w
        self.data_dependencies = datadeps


class OwnTask(Task):
    pass


class TaskPlaceholder(Task):
    def __init__(self, name: str) -> None:
        super().__init__(name, lambda: None, None, [])


type TaskStatsOfInterest = list[str]


class ProcessStarted:
    def __init__(self, proc_num: int) -> None:
        self.proc_num = proc_num
