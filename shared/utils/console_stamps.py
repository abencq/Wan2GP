"""Console stamps: a wall-clock stamp at the start of every line the app prints.

Console only: nothing is written to a file and no folder is created. The stamps ride on stdout, so
``python wgp.py ... 2>&1 | tee job.log`` stores them, and ``> job.log`` sends them to a file.

Progress bars stay intact. The app produces three kinds of console traffic: plain print lines,
carriage-return status lines that overwrite themselves in a terminal (the CLI queue loop,
``process_tasks_cli``) and bar redraws (``tqdm`` in ``shared/utils/phase_progress.py`` and the
download bars in ``shared/utils/download.py``). A line is stamped once, at its start, and every
byte of a bar's redraws is echoed untouched -- colour codes included, a terminal is what reads
this output.

Output written straight to the descriptors -- ffmpeg's own stderr, a C library warning -- never
reaches the wrapper, so it keeps the console's own shape: no stamp, no reordering.

The default format is the fixed-width wall clock (``2026-10-12 15:06:41``) followed by a
pipe, because WanGP already uses square brackets for its own tags (``[50/50]``, ``[ERROR]``,
``[INFO]``, tqdm's ``[00:41<00:00, 1.21it/s]``) and syslog reads a bracketed number as a
process id. The frame is just text: the format string is rendered literally, so brackets are
available by writing them.

Off by default, in every mode: a run without the flag prints exactly what it printed before, with
no header line, no stamps and no file. ``--log-timestamp=on`` turns the stamps on for that run,
``WAN2GP_LOG_TIMESTAMP=1`` turns them on for every run; ``--log-timestamp=off`` /
``WAN2GP_LOG_TIMESTAMP=0`` puts the original streams back, byte for byte. The one mode that
refuses them is the MCP server over stdio: its stdout carries JSON-RPC frames, so the feature is
simply not installed there.
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time

_LOCK = threading.RLock()

FORMAT_PRESETS = {
    "full": "%Y-%m-%d %H:%M:%S",
    "clock": "%H:%M:%S",
    "date": "%Y-%m-%d",
    "ms": "%H:%M:%S.{ms}",
    "uptime": "+{uptime}",
    "clock+uptime": "{time} +{uptime}",
}
SEPARATOR_PRESETS = {"pipe": " | ", "space": " ", "dash": " - ", "none": " "}

_TOKEN_RE = re.compile(r"\{(uptime|elapsed|time|date|ms|pid)\}")

DEFAULT_FORMAT = "full"
DEFAULT_SEPARATOR = "pipe"

_STATE = {
    "installed": False,
    "enabled": False,
    "format": DEFAULT_FORMAT,
    "separator": DEFAULT_SEPARATOR,
    "separator_resolved": " | ",
    "stdout": None,
    "stderr": None,
    "streams": [],
    "started": 0.0,
}

def _safe_write(stream, text):
    if stream is None or not text:
        return None
    try:
        return stream.write(text)
    except Exception:
        return None

def _safe_flush(stream):
    if stream is None:
        return
    try:
        stream.flush()
    except Exception:
        return

def _format_duration(seconds):
    """The same human-readable duration shape as the app's own ``format_time``."""
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if seconds >= 60:
        return f"{minutes}m {secs:02d}s"
    return f"{seconds:.1f}s"

def _uptime_text():
    started = _STATE.get("started") or 0.0
    if started <= 0:
        return "0:00:00"
    return _format_duration(time.time() - started).replace(" ", "")

def resolve_format(value):
    fmt = str(value if value is not None else DEFAULT_FORMAT).strip()
    if len(fmt) == 0:
        fmt = DEFAULT_FORMAT
    return FORMAT_PRESETS.get(fmt, fmt)

def resolve_separator(value):
    raw = str(value if value is not None else DEFAULT_SEPARATOR)
    preset = SEPARATOR_PRESETS.get(raw.strip().lower())
    if preset is not None:
        return preset                                        # presets are exact: 'none' means a single space
    separator = raw.strip()
    if not separator.endswith(" "):
        separator = f"{separator} "
    return separator

_STAMP_CACHE = [-1, "", ""]

def render_stamp(fmt=None):
    """One rendered stamp, cached per wall-clock second (bars write many lines per second)."""
    fmt = resolve_format(fmt) if fmt is not None else _STATE["format"]
    fmt = resolve_format(fmt)
    if fmt in ("off", "none", "none", ""):
        return ""
    now = int(time.time())
    if _STAMP_CACHE[0] == now and _STAMP_CACHE[1] == fmt:
        return _STAMP_CACHE[2]
    values = {
        "time": time.strftime("%H:%M:%S"),
        "date": time.strftime("%Y-%m-%d"),
        "ms": f"{int((time.time() % 1) * 1000):03d}",
        "uptime": _uptime_text(),
        "elapsed": _uptime_text(),
        "pid": str(os.getpid()),
    }
    text = time.strftime(fmt)
    if "{" in fmt:
        text = _TOKEN_RE.sub(lambda match: values[match.group(1)], text)   # a token mix is strftime'd first
    _STAMP_CACHE[0], _STAMP_CACHE[1], _STAMP_CACHE[2] = now, fmt, text
    return text


class _LineStamper:
    """Write a stamp at the start of every line of one console stream.

    ``write`` chunks are echoed verbatim, so a bar keeps redrawing exactly as it does today, its
    ``ljust`` padding intact, and the terminal receives every byte it expects -- colour codes
    included. One stamp is written per line, at its start: a carriage return continues the same
    line, so a bar is stamped once, and a closing newline is what asks for the next stamp.
    """

    def __init__(self, console):
        self._console = console
        self._need_stamp = True

    def feed(self, text):
        if not text:
            return
        position = 0
        while position < len(text):
            if self._need_stamp:
                self._need_stamp = False
                stamp = render_stamp()
                if stamp:
                    _safe_write(self._console, f"{stamp}{_STATE['separator_resolved']}")
            index = text.find("\n", position)
            if index < 0:
                _safe_write(self._console, text[position:])
                return
            _safe_write(self._console, text[position:index + 1])
            position = index + 1
            self._need_stamp = True

    def flush(self):
        _safe_flush(self._console)



class ConsoleStampStream:
    """A ``sys.stdout`` / ``sys.stderr`` replacement: the console, stamped at line starts.

    The stream contract the app relies on is preserved: ``encoding``, ``errors``, ``isatty``,
    ``fileno``, ``buffer`` and friends pass through to the wrapped stream (``shared/deepy/
    engine.py`` and ``shared/prompt_enhancer/qwen35_text.py`` probe ``encoding``, and tqdm
    decides how to redraw from ``isatty``). ``fileno`` keeps returning the *real* descriptor,
    so a subprocess started without redirection still writes to the real console.
    """

    def __init__(self, console):
        self._stamper = _LineStamper(console)

    def write(self, data):
        if not data:
            return 0
        text = data.decode("utf-8", "replace") if isinstance(data, (bytes, bytearray)) else str(data)
        with _LOCK:
            self._stamper.feed(text)
        return len(text)

    def flush(self):
        with _LOCK:
            self._stamper.flush()

    @property
    def encoding(self):
        return getattr(self._stamper._console, "encoding", "utf-8")

    @property
    def errors(self):
        return getattr(self._stamper._console, "errors", "strict")

    def isatty(self):
        return bool(getattr(self._stamper._console, "isatty", lambda: False)())

    def writable(self):
        return True

    def fileno(self):
        return getattr(self._stamper._console, "fileno")()

    def __getattr__(self, name):
        return getattr(self._stamper._console, name)


def _argv_value(argv, name):
    argv = [str(one) for one in (argv or [])]
    prefix = f"{name}="
    for index, one in enumerate(argv):
        if one == name and index + 1 < len(argv):
            return argv[index + 1]
        if one.startswith(prefix):
            return one[len(prefix):]
    return None


ON_OFF_TRUE = ("on", "yes", "true", "1")
ON_OFF_FALSE = ("off", "no", "false", "0")


def _on_off_value(raw):
    value = str(raw).strip().lower()
    if value in ON_OFF_TRUE:
        return True
    if value in ON_OFF_FALSE:
        return False
    return None


def _argv_on_off(argv, name):
    """True or False when the command line sets the option, None when it is left out.

    The flag on its own means on; the value form (--name=off, or --name with the value next to
    it) decides both ways.
    """
    argv = [str(one) for one in (argv or [])]
    prefix = f"{name}="
    for index, one in enumerate(argv):
        text = one.strip()
        if text.startswith(prefix):
            return _on_off_value(text[len(prefix):])
        if text == name:
            following = argv[index + 1].strip() if index + 1 < len(argv) else ""
            value = _on_off_value(following)
            return True if value is None else value                  # a flag on its own is an on
    return None


def _uses_stdio_protocol(argv):
    """MCP stdio carries JSON-RPC on stdout: that stream must never be stamped."""
    argv = [str(one) for one in (argv or [])]
    if not any(one == "--mcp" for one in argv):
        return False
    transport = _argv_value(argv, "--mcp-transport") or "stdio"
    return transport.strip().lower() == "stdio"


def console_stamps_enabled():
    return bool(_STATE["installed"] and _STATE["enabled"])


def _wrap_streams():
    """Wrap the live ``sys.stdout`` / ``sys.stderr`` with the stamping streams."""
    streams = [one for one in (_STATE.get("streams") or []) if isinstance(one, ConsoleStampStream)]
    for name in ("stdout", "stderr"):
        original = getattr(sys, name)
        if original is None or isinstance(original, ConsoleStampStream):
            continue
        if _STATE.get(name) is None:
            _STATE[name] = original
        wrapped = ConsoleStampStream(original)
        setattr(sys, name, wrapped)
        streams.append(wrapped)
    _STATE["streams"] = streams
    return streams


def _restore_streams():
    for name in ("stdout", "stderr"):
        original = _STATE.get(name)
        if original is not None:
            setattr(sys, name, original)
    _STATE["streams"] = []


def _apply_environment(argv):
    env_stamp = _on_off_value(os.environ.get("WAN2GP_LOG_TIMESTAMP", ""))
    return {
        "enabled": env_stamp is True,
        "env_stamp_set": env_stamp is not None,
        "format": os.environ.get("WAN2GP_LOG_TIMESTAMP_FORMAT") or DEFAULT_FORMAT,
        "separator": os.environ.get("WAN2GP_LOG_TIMESTAMP_SEP") or DEFAULT_SEPARATOR,
    }


def install_console_stamps(argv=None, *, fmt=None, separator=None, quiet=False):
    """Wrap sys.stdout / sys.stderr so every line the app prints starts with a stamp.

    No file is opened and no folder is created: the stamps go to the console and nowhere else.
    Called from ``wgp.py`` before the heavy imports, so model loading output is stamped too --
    the options are read from the raw command line and the environment here, and the parsed
    ``argparse`` values are applied afterwards by :func:`configure_console_stamps`.
    Stamping is off unless ``--log-timestamp=on`` (or ``WAN2GP_LOG_TIMESTAMP=1``) asks for it, so a
    plain run keeps the legacy output. Returns True when the streams are stamped.
    """
    if _STATE["installed"]:
        return console_stamps_enabled()
    argv = list(sys.argv[1:] if argv is None else argv)
    env = _apply_environment(argv)
    # A flag given on the command line takes effect from the very first printed line: this runs
    # before the heavy imports, while the parsed argparse values land later, in
    # configure_console_stamps. Explicit keyword arguments still win over the flags.
    if fmt is None:
        fmt = _argv_value(argv, "--log-timestamp-format")
    if separator is None:
        separator = _argv_value(argv, "--log-timestamp-sep")
    requested = _argv_on_off(argv, "--log-timestamp")
    if requested is not None:
        enabled = requested                                             # the flag wins over everything
    elif env["env_stamp_set"]:
        enabled = env["enabled"]                                        # WAN2GP_LOG_TIMESTAMP sets the default
    else:
        enabled = False                                                 # the default is the legacy plain output
    enabled = bool(enabled) and not _uses_stdio_protocol(argv)
    fmt = fmt if fmt is not None else env["format"]
    separator = separator if separator is not None else env["separator"]
    _STATE.update(
        enabled=enabled,
        format=resolve_format(fmt),
        separator=resolve_separator(separator),
        separator_resolved=resolve_separator(separator),
        started=time.time(),
    )
    _STATE["installed"] = True
    if not enabled:
        return False

    _wrap_streams()
    if not quiet:
        mode = str(_STATE.get("format") or DEFAULT_FORMAT)
        detail = ("time of day" if "uptime" not in mode
                  else "time of day + uptime")
        print(f"WanGP console log start: PID {os.getpid()}, python {sys.version.split()[0]}, "
              f"stamps {detail} at the start of every line, format '{mode}'")
    return True


def configure_console_stamps(args, argv=None):
    """Apply the parsed command-line options (called right after ``parse_wgp_args``).

    A flag left out keeps the value coming from the environment and the defaults, so
    ``WAN2GP_LOG_TIMESTAMP``, ``WAN2GP_LOG_TIMESTAMP_FORMAT`` & co. work without a flag.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    get = (lambda key, default=None: getattr(args, key, default))
    stamps = _argv_on_off(argv, "--log-timestamp")
    if stamps is False:
        return disable_console_stamps()
    if stamps is True and not console_stamps_enabled():
        install_console_stamps(argv)
    if not console_stamps_enabled():
        return ""                                # the modes that print as before: nothing to apply

    fmt = get("log_timestamp_format", None)
    separator = get("log_timestamp_sep", None)

    with _LOCK:
        if fmt is not None:
            _STATE["format"] = resolve_format(fmt)
        if separator is not None:
            _STATE["separator_resolved"] = resolve_separator(separator)
            _STATE["separator"] = _STATE["separator_resolved"]
    return ""


def disable_console_stamps():
    """``--log-timestamp=off``: put the original streams back, output is byte-identical to a plain run."""
    _STATE["enabled"] = False
    _restore_streams()
    return ""


def console_stamp_state():
    return {
        "enabled": console_stamps_enabled(),
        "format": _STATE.get("format"),
        "separator": _STATE.get("separator_resolved"),
    }
