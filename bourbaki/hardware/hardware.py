#coding:utf-8
from typing import Callable, Tuple, Dict, Any, Optional as Opt, Union, Iterable
from itertools import repeat
from functools import partial
import time
import sys
from threading import Thread, Event
from warnings import warn
import psutil

DEFAULT_WARN_MEM_THRESHOLD = 1e9
DEFAULT_CPU_BAR_SIZE = 10
DEFAULT_REPORT_INTERVAL = 0.2

print_to_stderr = partial(print, file=sys.stderr)
print_to_stdout = partial(print, file=sys.stdout)

mem_unit_conversions = {"B": 1, "KB": 10**3, "MB": 10**6, "GB": 10**9, "TB": 10**12}


def to_bytes(size):
    err_msg = "memory sizes must be numeric for bytes, or strings like '64 kB' or '12 MB' (with a space); got {}"
    if isinstance(size, int):
        return size
    if isinstance(size, float):
        return int(round(size, 0))
    elif not isinstance(size, str):
        raise TypeError(err_msg.format(type(size)))
    else:
        try:
            number, unit = [s.strip() for s in size.upper().strip().split()]
        except ValueError:
            raise ValueError(err_msg.format(size))
    try:
        b = int(round(float(number) * mem_unit_conversions[unit], 0))
    except KeyError:
        raise KeyError("Unknown memory units: {}".format(unit))

    return b


def _bars(p, width, char='\u2588'):
    return (char * int(round(p * width / 100.0))).ljust(width, ' ')


def report_cpu_load(end='\r', bars=DEFAULT_CPU_BAR_SIZE, print_func=print_to_stderr):
    if bars:
        sep = '\u2592'
        msg = "cpu load: %s{}%s" % (sep, sep)
        fmt = partial(_bars, width=bars)
        # sort = lambda x: x
    else:
        sep = ', '
        msg = "cpu load: {}"
        fmt = '{:2.2f}'.format
        # sort = partial(sorted, reverse=True)
    loads = psutil.cpu_percent(percpu=True)
    print_func(msg.format(sep.join(map(fmt, loads))), end=end)

    return loads


def report_free_mem(warn_mem_threshold=DEFAULT_WARN_MEM_THRESHOLD,
                    end='\r',
                    print_func=print_to_stderr):
    """warn_threshold is in Mb units"""
    warn_mem_threshold = to_bytes(warn_mem_threshold)
    free = psutil.virtual_memory().available
    print_func("free mem: {:2.2}Gb".format(free / 1e9), end=end)
    if free < warn_mem_threshold:
        warn("LOW MEMORY!!! {:.2f}Mb".format(free / 1e6))

    return free


def report_hardware_status(warn_mem_threshold=DEFAULT_WARN_MEM_THRESHOLD, 
                           cpu_bar_size=DEFAULT_CPU_BAR_SIZE, 
                           print_func=print_to_stderr):
    warn_mem_threshold = to_bytes(warn_mem_threshold)
    report_free_mem(end=' | ', warn_mem_threshold=warn_mem_threshold, print_func=print_func)
    report_cpu_load(end='\r', bars=cpu_bar_size, print_func=print_func)


def repeat_at_intervals(f: Callable, flag: Event, interval: float=0.25,
                        args: Union[Tuple, Iterable[Tuple]]=(),
                        kwargs: Opt[Union[Dict[str, Any], Iterable[Dict[str, Any]]]]=None):
    if not isinstance(args, tuple):
        iterargs = iter(args)
    else:
        iterargs = iter(repeat(args))
    if kwargs is not None and not isinstance(kwargs, dict):
        iterkwargs = iter(kwargs)
    else:
        iterkwargs = iter(repeat(kwargs))

    while not flag.is_set():
        kwargs = next(iterkwargs)
        f(*next(iterargs), **kwargs) if kwargs else f(*args)
        time.sleep(interval)


def with_hardware_report(f, interval=DEFAULT_REPORT_INTERVAL, 
                         warn_mem_threshold=DEFAULT_WARN_MEM_THRESHOLD, 
                         cpu_bar_size=DEFAULT_CPU_BAR_SIZE, 
                         print_func=print_to_stderr):
    def call_f(*a, **kw):
        with hardware_report(interval, warn_mem_threshold,
                             cpu_bar_size=cpu_bar_size, print_func=print_func):
            result = f(*a, **kw)
        return result
    return call_f


class hardware_report:
    def __init__(self, interval=DEFAULT_REPORT_INTERVAL, 
                 warn_mem_threshold=DEFAULT_WARN_MEM_THRESHOLD, 
                 cpu_bar_size=DEFAULT_CPU_BAR_SIZE, 
                 print_func=print_to_stderr):
        self.interval = interval
        self.warn_mem_threshold = to_bytes(warn_mem_threshold)
        self.report_thread = None
        self.exit_flag = None
        self.print_func = print_func
        self.cpu_bar_size = cpu_bar_size

    def __enter__(self):
        self.exit_flag = Event()
        report = Thread(target=repeat_at_intervals,
                        args=(report_hardware_status,
                              self.exit_flag, self.interval,
                              (self.warn_mem_threshold,),
                              dict(cpu_bar_size=self.cpu_bar_size, print_func=self.print_func),
                              ),
                        )

        report.start()
        self.report_thread = report

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.exit_flag.set()
        self.report_thread.join()

        if exc_type is not None:
            raise exc_val
