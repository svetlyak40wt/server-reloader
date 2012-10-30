# Autoreloading launcher.
# Borrowed from Peter Hunt and the CherryPy project (http://www.cherrypy.org).
# Some taken from Ian Bicking's Paste (http://pythonpaste.org/).
# Then "stolen" from Django project and slightly modified by Artemenko Alexander.
#
# Portions copyright (c) 2004, CherryPy Team (team@cherrypy.org)
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#     * Neither the name of the CherryPy Team nor the names of its contributors
#       may be used to endorse or promote products derived from this software
#       without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os, sys, time, signal

import threading

try:
    import termios
except ImportError:
    termios = None


_reload_event = threading.Event()


class CodeWatcher(object):
    def __init__(self):
        self._mtimes = {}
        self._win = (sys.platform == "win32")

    def is_code_changed(self):
        filenames = [getattr(m, "__file__", None) for m in sys.modules.values()]
        for filename in filter(None, filenames):
            if filename.endswith(".pyc") or filename.endswith(".pyo"):
                filename = filename[:-1]
            if filename.endswith("$py.class"):
                filename = filename[:-9] + ".py"
            if not os.path.exists(filename):
                continue # File might be in an egg, so it can't be reloaded.
            stat = os.stat(filename)
            mtime = stat.st_mtime
            if self._win:
                mtime -= stat.st_ctime
            if filename not in self._mtimes:
                self._mtimes[filename] = mtime
                continue
            if mtime != self._mtimes[filename]:
                self._mtimes = {}
                return True
        return False


def _ensure_echo_on():
    if termios:
        fd = sys.stdin
        if fd.isatty():
            attr_list = termios.tcgetattr(fd)
            if not attr_list[3] & termios.ECHO:
                attr_list[3] |= termios.ECHO
                if hasattr(signal, 'SIGTTOU'):
                    old_handler = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
                else:
                    old_handler = None
                termios.tcsetattr(fd, termios.TCSANOW, attr_list)
                if old_handler is not None:
                    signal.signal(signal.SIGTTOU, old_handler)


def trigger_reload():
    _reload_event.set()


def trigger_on_code_changes():
    def worker():
        watcher = CodeWatcher()
        while True:
            if watcher.is_code_changed():
                trigger_reload()
            time.sleep(1)

    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()


def _restart_with_reloader():
    while True:
        args = [sys.executable] + ['-W%s' % o for o in sys.warnoptions] + sys.argv
        if sys.platform == "win32":
            args = ['"%s"' % arg for arg in args]
        new_environ = os.environ.copy()
        new_environ["RUN_MAIN"] = 'true'
        exit_code = os.spawnve(os.P_WAIT, sys.executable, args, new_environ)
        if exit_code != 3:
            return exit_code


def _reloader(main_func, args, kwargs, before_reload, before_exit, watch_on_files):
    if os.environ.get("RUN_MAIN") == "true":

        exit_code = [0]

        def sys_exit_catcher():
            """A special handler of SystemExit exception.
            This exception can be processed only if thrown
            from the main thread, so we'll pull this from
            a worker into the main thread.
            """
            try:
                main_func(*args, **kwargs)
            except SystemExit as e:
                exit_code[0] = e.code
                # we set event to speedup exit, not for real reloading
                _reload_event.set()

        thread = threading.Thread(target=sys_exit_catcher)
        thread.daemon = True
        thread.start()

        if watch_on_files:
            trigger_on_code_changes()

        _ensure_echo_on()
        try:

            while True:
                # we can't block on event forever because in this case
                # this child process will never be interrupted
                # by Ctrl-C
                _reload_event.wait(timeout=1.0)

                if not thread.is_alive():
                    # if main_func exited, then we should terminate reloader too
                    sys.exit(exit_code[0])

                if _reload_event.is_set():
                    before_reload()
                    sys.exit(3) # force reload

        except KeyboardInterrupt:
            before_exit()
    else:
        try:
            exit_code = _restart_with_reloader()
            if exit_code < 0:
                os.kill(os.getpid(), -exit_code)
            else:
                sys.exit(exit_code)
        except KeyboardInterrupt:
            pass


def main(
        main_func,
        args=None,
        kwargs=None,
        before_reload=lambda: None,
        before_exit=lambda: None,
        watch_on_files=True,
    ):
    """Starts a 'main_func' under code reloader.

    @param args - function's positional arguments.
    @param kargs - function's keyword arguments.
    @param before_reload - a function to call before code will be reloaded.
    @param before_exit - a function to call if a programm was interrupted by Ctrl+C.
           This is really needed, because the main_func is executed in a child thread,
           but KeyboardInterrupt exception is sent to the main thread.
    @param watch_on_files - if True (default), then a separate thread will be
           started to watch on changes in loaded modules' sources.
    """
    _reloader(main_func, args or (), kwargs or {}, before_reload, before_exit, watch_on_files)

