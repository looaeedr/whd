#!/bin/sh
set -eu

URL="https://raw.githubusercontent.com/looaeedr/whd/ops/bill-manager-upgrade-20260918/tools/upgrade_bill_manager_db.py"
DST="/storage/upgrade_bill_manager_db.py"

echo "Downloading upgrade script..."
curl -fL "$URL" -o "$DST"
chmod 700 "$DST"

echo "Running upgrade..."
python3 "$DST"
