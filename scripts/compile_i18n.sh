#!/usr/bin/env bash
# Compile gettext catalogs for deploy. Requires GNU gettext (msgfmt).
set -euo pipefail
cd "$(dirname "$0")/.."
python manage.py compilemessages
