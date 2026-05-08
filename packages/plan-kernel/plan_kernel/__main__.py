"""``python -m plan_kernel`` entry point.

With no args (or with ``-f <connection_file>`` supplied by Jupyter) this
launches the kernel. With the ``install`` subcommand it registers the
kernelspec.
"""

import sys

from .kernel import _cli_main


if __name__ == "__main__":
    sys.exit(_cli_main(sys.argv))
