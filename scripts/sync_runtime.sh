#!/usr/bin/env bash
# Sync vendored PLAN runtime files from a Gallowglass checkout into
# marduk/runtime/. Updates VENDOR.md's commit SHA and per-file blob SHAs.
#
# Usage:
#   GALLOWGLASS_HOME=/path/to/gallowglass scripts/sync_runtime.sh
#
# Defaults to $GALLOWGLASS_HOME, falling back to ../../.. if Marduk lives
# at gallowglass/vendor/marduk/ (the canonical dev layout).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARDUK_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNTIME_DIR="${MARDUK_ROOT}/marduk/runtime"
VENDOR_MD="${RUNTIME_DIR}/VENDOR.md"

GALLOWGLASS="${GALLOWGLASS_HOME:-${MARDUK_ROOT}/../..}"
GALLOWGLASS="$(cd "${GALLOWGLASS}" && pwd)"

if [ ! -f "${GALLOWGLASS}/dev/harness/plan.py" ]; then
    echo "error: ${GALLOWGLASS} does not look like a gallowglass checkout"
    echo "       (missing dev/harness/plan.py)"
    echo "       set GALLOWGLASS_HOME to override"
    exit 1
fi

echo "Syncing from: ${GALLOWGLASS}"
echo "Into:         ${RUNTIME_DIR}"

cp "${GALLOWGLASS}/dev/harness/plan.py"        "${RUNTIME_DIR}/plan.py"
cp "${GALLOWGLASS}/dev/harness/bplan.py"       "${RUNTIME_DIR}/bplan.py"
cp "${GALLOWGLASS}/bootstrap/bplan_deps.py"    "${RUNTIME_DIR}/bplan_deps.py"

# Rewrite bplan.py imports to be relative within marduk.runtime.
# Two occurrences: top-level and lazy import inside _bexec.
python3 - "${RUNTIME_DIR}/bplan.py" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
text = p.read_text()
text = text.replace("from dev.harness.plan import", "from .plan import")
p.write_text(text)
PY

# Capture upstream commit + blob SHAs for VENDOR.md.
COMMIT="$(git -C "${GALLOWGLASS}" rev-parse HEAD)"
SHA_PLAN="$(git -C "${GALLOWGLASS}" hash-object dev/harness/plan.py)"
SHA_BPLAN="$(git -C "${GALLOWGLASS}" hash-object dev/harness/bplan.py)"
SHA_DEPS="$(git -C "${GALLOWGLASS}" hash-object bootstrap/bplan_deps.py)"
TODAY="$(date +%Y-%m-%d)"

python3 - "${VENDOR_MD}" "${COMMIT}" "${TODAY}" "${SHA_PLAN}" "${SHA_BPLAN}" "${SHA_DEPS}" <<'PY'
import sys, re, pathlib
path, commit, today, sha_plan, sha_bplan, sha_deps = sys.argv[1:7]
p = pathlib.Path(path)
text = p.read_text()
text = re.sub(r"(\*\*Commit:\*\*\s+`)[0-9a-f]+(`)", rf"\g<1>{commit}\g<2>", text)
text = re.sub(r"(\*\*Sync date:\*\*\s+)\S+", rf"\g<1>{today}", text)
text = re.sub(r"(\*\*Sync method:\*\*\s+).*", r"\g<1>scripts/sync_runtime.sh", text)
text = re.sub(r"(`marduk/runtime/plan\.py`\s*\|\s*`dev/harness/plan\.py`\s*\|\s*`)[0-9a-f]+(`)",
              rf"\g<1>{sha_plan}\g<2>", text)
text = re.sub(r"(`marduk/runtime/bplan\.py`\s*\|\s*`dev/harness/bplan\.py`\s*\|\s*`)[0-9a-f]+(`)",
              rf"\g<1>{sha_bplan}\g<2>", text)
text = re.sub(r"(`marduk/runtime/bplan_deps\.py`\s*\|\s*`bootstrap/bplan_deps\.py`\s*\|\s*`)[0-9a-f]+(`)",
              rf"\g<1>{sha_deps}\g<2>", text)
p.write_text(text)
PY

echo
echo "Synced. Updated VENDOR.md to commit ${COMMIT}."
echo "Run pytest to confirm no shape-drift broke the runtime."
