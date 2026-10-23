#!/usr/bin/env bash
# Refuse to run from a unit definition that no longer matches the reviewed one.
#
# `git pull` updates /opt/aca; it does not touch /etc/systemd/system. Until
# `make install` runs, systemd keeps executing the unit it loaded earlier --
# with the old sandbox, the old environment files, the old ExecStart. A backup
# failed three times in a row against fixes that were already on disk, and
# nothing in the journal connected the two.
set -euo pipefail

UNIT="${1:?usage: check_unit_current.sh <unit name>}"
[[ "$UNIT" =~ ^[a-z0-9@.-]+\.(service|timer)$ ]] || { echo "gx10 invalid unit name" >&2; exit 64; }
ROOT_DIR="${GX10_ROOT_DIR:-/opt/aca}"
UNIT_DIR="${GX10_UNIT_DIR:-/etc/systemd/system}"

reviewed="$ROOT_DIR/deploy/gx10/systemd/$UNIT"
installed="$UNIT_DIR/$UNIT"

[[ -f "$reviewed" ]] || { echo "gx10 reviewed unit $UNIT is missing from $ROOT_DIR" >&2; exit 1; }
[[ -f "$installed" ]] || { echo "gx10 unit $UNIT is not installed; run: make -C $ROOT_DIR/deploy/gx10 install" >&2; exit 1; }

if ! cmp -s "$reviewed" "$installed"; then
  echo "gx10 $UNIT is running an older installed definition; run: make -C $ROOT_DIR/deploy/gx10 install" >&2
  exit 1
fi
