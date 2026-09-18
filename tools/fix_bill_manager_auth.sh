#!/bin/sh
set -eu
URL="https://raw.githubusercontent.com/looaeedr/whd/ops/bill-manager-upgrade-20260918/tools/fix_bill_manager_auth.py"
DST="/storage/fix_bill_manager_auth.py"
curl -fL "$URL" -o "$DST"
chmod 700 "$DST"
python3 "$DST"
