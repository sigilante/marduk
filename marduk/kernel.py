"""Jupyter kernel and CLI entry points.

Two surface areas:

- :func:`_kernel_main` — invoked via ``python -m marduk`` (i.e.
  ``marduk/__main__.py``). Lazy-imports ``ipykernel`` and launches the
  kernel via ``IPKernelApp.launch_instance``.

- :func:`_install_kernelspec` — registers ``Marduk (PLAN)`` with Jupyter's
  ``KernelSpecManager`` so the kernel picker shows it. The kernel.json's
  ``argv`` is ``[sys.executable, '-m', 'marduk', '-f', '{connection_file}']``,
  so launching the kernel reuses the Python interpreter that ran ``install``.

The ``MardukKernel`` class is defined inside :func:`_kernel_main` so that
importing this module doesn't pull in ``ipykernel`` — that keeps test
environments without ``ipykernel`` (and the kernel-startup path itself)
fast and importable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import traceback


__all__ = [
    "_install_kernelspec",
    "_kernel_main",
    "_cli_main",
]


_KERNEL_NAME = "marduk"
_DISPLAY_NAME = "Marduk (PLAN)"
_IMPLEMENTATION = "Marduk"


def _kernel_main() -> None:
    """Launch the kernel under ``ipykernel.IPKernelApp.launch_instance``."""
    from ipykernel.kernelapp import IPKernelApp
    from ipykernel.kernelbase import Kernel

    from . import __version__
    from .evaluator import MardukEvaluator

    class MardukKernel(Kernel):
        implementation = _IMPLEMENTATION
        implementation_version = __version__
        language_info = {
            "name": "plan",
            "mimetype": "text/x-plan",
            "file_extension": ".plan",
            "pygments_lexer": "lisp",
        }
        banner = (
            "Marduk PLAN kernel — type Plan Asm in a cell, see the reduced "
            "PLAN value back. The BPLAN op prelude is auto-loaded; %backend, "
            "%reset, %env are available as cell magics."
        )

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._evaluator = MardukEvaluator()

        def do_execute(self, code, silent, store_history=True,
                       user_expressions=None, allow_stdin=False, *,
                       cell_id=None):
            try:
                result = self._evaluator.eval_cell(code)
            except Exception as e:    # noqa: BLE001 — last-resort guard
                tb = traceback.format_exception(type(e), e, e.__traceback__)
                if not silent:
                    self.send_response(self.iopub_socket, "stream", {
                        "name": "stderr",
                        "text": "".join(tb),
                    })
                return {
                    "status": "error",
                    "execution_count": self.execution_count,
                    "ename": type(e).__name__,
                    "evalue": str(e),
                    "traceback": tb,
                }

            if result.error is not None:
                error_text = _format_error(result.error)
                if not silent:
                    self.send_response(self.iopub_socket, "stream", {
                        "name": "stderr",
                        "text": error_text,
                    })
                return {
                    "status": "error",
                    "execution_count": self.execution_count,
                    "ename": result.error.get("type", "Error"),
                    "evalue": result.error.get("message", ""),
                    "traceback": [error_text],
                }

            if result.value_text is not None and not silent:
                data = {"text/plain": result.value_text}
                if result.value_html is not None:
                    data["text/html"] = result.value_html
                self.send_response(self.iopub_socket, "execute_result", {
                    "execution_count": self.execution_count,
                    "data": data,
                    "metadata": {},
                })

            return {
                "status": "ok",
                "execution_count": self.execution_count,
                "payload": [],
                "user_expressions": {},
            }

    IPKernelApp.launch_instance(kernel_class=MardukKernel)


def _format_error(envelope: dict) -> str:
    """Render an error envelope for the Jupyter ``stream`` channel.

    Format: ``[file:line:col: ]<stage> error: <message>``. The location
    block is dropped when no ``loc`` is present (most expand/runtime
    errors).
    """
    stage = envelope.get("stage", "error")
    msg = envelope.get("message", "")
    loc = envelope.get("loc")
    if loc is not None:
        file_part = loc.get("file") or "<cell>"
        prefix = f"{file_part}:{loc['line']}:{loc['col']}: "
    else:
        prefix = ""
    return f"{prefix}{stage} error: {msg}\n"


def _install_kernelspec(user: bool = True, prefix: str | None = None) -> str:
    """Register the Marduk kernelspec with Jupyter.

    Returns the install path (the directory containing ``kernel.json``).

    Parameters
    ----------
    user
        Install to the per-user kernels directory (default). Set to
        ``False`` together with a ``prefix`` for an isolated install.
    prefix
        Optional prefix path. When set, the kernelspec is written under
        ``<prefix>/share/jupyter/kernels/marduk/``. Useful for venv-scoped
        installs (``--prefix .venv``).
    """
    from jupyter_client.kernelspec import KernelSpecManager

    spec = {
        "argv": [
            sys.executable,
            "-m",
            "marduk",
            "-f",
            "{connection_file}",
        ],
        "display_name": _DISPLAY_NAME,
        "language": "plan",
        "metadata": {
            "description": "Marduk — Jupyter kernel for the PLAN virtual machine",
        },
    }

    with tempfile.TemporaryDirectory() as td:
        spec_path = os.path.join(td, "kernel.json")
        with open(spec_path, "w") as f:
            json.dump(spec, f, indent=2)
        ksm = KernelSpecManager()
        installed = ksm.install_kernel_spec(
            td,
            kernel_name=_KERNEL_NAME,
            user=user,
            prefix=prefix,
        )
    return installed


def _cli_main(argv: list[str]) -> int:
    """CLI entry point. Returns process exit code.

    Subcommands:
    - ``marduk install [--prefix DIR] [--system]`` registers the
      kernelspec and prints the install path.
    - Any other invocation (typically ``-f <connection_file>`` from
      Jupyter) falls through to :func:`_kernel_main`.
    """
    if len(argv) >= 2 and argv[1] == "install":
        parser = argparse.ArgumentParser(
            prog="marduk install",
            description="Register the Marduk kernelspec with Jupyter.",
        )
        parser.add_argument(
            "--prefix",
            default=None,
            help="install under PREFIX/share/jupyter/kernels/marduk (overrides --user)",
        )
        parser.add_argument(
            "--system",
            action="store_true",
            help="install system-wide instead of per-user (the default)",
        )
        args = parser.parse_args(argv[2:])
        user = not args.system and args.prefix is None
        installed = _install_kernelspec(user=user, prefix=args.prefix)
        print(f"Installed Marduk kernelspec at {installed}")
        return 0

    _kernel_main()
    return 0
