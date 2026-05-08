"""Protocol-free smoke tests for the kernel + CLI surface.

The :class:`PlanKernel` class itself is defined inside :func:`_kernel_main`
to keep ``ipykernel`` lazy-imported, so we don't instantiate it here. The
checks below cover module import, kernelspec construction, and CLI
dispatch — enough to catch regressions in the install path without
spinning up a kernel process.
"""

import json
import os
import subprocess
import sys

import pytest


def test_module_imports_without_launching_kernel():
    """Importing ``plan_kernel.kernel`` must not pull in ``ipykernel`` (which
    is lazy-imported inside ``_kernel_main``)."""
    import plan_kernel.kernel as kernel
    assert hasattr(kernel, "_install_kernelspec")
    assert hasattr(kernel, "_kernel_main")
    assert hasattr(kernel, "_cli_main")


def test_main_module_imports():
    import plan_kernel.__main__   # noqa: F401


def test_install_kernelspec_writes_kernel_json(tmp_path):
    pytest.importorskip("jupyter_client")
    from plan_kernel.kernel import _install_kernelspec

    installed = _install_kernelspec(user=False, prefix=str(tmp_path))
    spec_path = os.path.join(installed, "kernel.json")
    assert os.path.isfile(spec_path), f"kernel.json not at {spec_path}"

    with open(spec_path) as f:
        spec = json.load(f)

    # Identity
    assert spec["display_name"] == "PLAN"
    assert spec["language"] == "plan"

    # argv launches the kernel via `python -m plan_kernel` with the connection file.
    argv = spec["argv"]
    assert argv[0] == sys.executable
    assert "-m" in argv and "plan_kernel" in argv
    assert "{connection_file}" in argv

    # Metadata describes Marduk for the kernelspec listing.
    assert "metadata" in spec
    assert "description" in spec["metadata"]
    assert "PLAN" in spec["metadata"]["description"]


def test_install_kernelspec_install_path_contains_plan_kernel(tmp_path):
    pytest.importorskip("jupyter_client")
    from plan_kernel.kernel import _install_kernelspec

    installed = _install_kernelspec(user=False, prefix=str(tmp_path))
    # KernelSpecManager preserves the registered kernel name; jupyter
    # accepts either form so we tolerate both in case of normalization.
    assert (installed.endswith(os.sep + "plan-kernel")
            or installed.endswith(os.sep + "plan_kernel"))


def test_cli_install_subcommand(tmp_path, capsys):
    pytest.importorskip("jupyter_client")
    from plan_kernel.kernel import _cli_main

    rc = _cli_main(["__main__", "install", "--prefix", str(tmp_path)])
    assert rc == 0

    captured = capsys.readouterr()
    assert "Installed plan-kernel kernelspec at" in captured.out


def test_cli_install_creates_loadable_kernel_json(tmp_path):
    """End-to-end: run install with a tempdir prefix, then read back the
    kernel.json the way Jupyter would."""
    pytest.importorskip("jupyter_client")
    from plan_kernel.kernel import _cli_main

    _cli_main(["__main__", "install", "--prefix", str(tmp_path)])
    # Spec lives at <prefix>/share/jupyter/kernels/<kernel-name>/kernel.json.
    # jupyter accepts both hyphen and underscore forms; pick whichever exists.
    base = tmp_path / "share" / "jupyter" / "kernels"
    spec_path = next(p / "kernel.json" for p in (base / "plan-kernel",
                                                  base / "plan_kernel")
                     if (p / "kernel.json").is_file())
    assert spec_path.is_file()
    spec = json.loads(spec_path.read_text())
    assert spec["display_name"] == "PLAN"


def test_module_can_be_invoked_via_python_dash_m(tmp_path):
    """``python -m plan-kernel install --prefix tmp`` must succeed end-to-end."""
    pytest.importorskip("jupyter_client")
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    result = subprocess.run(
        [sys.executable, "-m", "plan_kernel", "install", "--prefix", str(tmp_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "Installed plan-kernel kernelspec at" in result.stdout


def test_format_error_with_loc():
    from plan_kernel.kernel import _format_error
    envelope = {
        "stage": "parse",
        "message": "unterminated string",
        "type": "ParseError",
        "loc": {"file": "<cell>", "line": 3, "col": 7},
    }
    out = _format_error(envelope)
    assert "<cell>:3:7" in out
    assert "parse error" in out
    assert "unterminated string" in out


def test_format_error_without_loc():
    from plan_kernel.kernel import _format_error
    envelope = {
        "stage": "expand",
        "message": "unbound: foo",
        "type": "MacroError",
        "loc": None,
    }
    out = _format_error(envelope)
    # No file: prefix when loc is None.
    assert not out.startswith("<")
    assert "expand error" in out
    assert "unbound: foo" in out
