#!/usr/bin/env bash
set -euo pipefail
vault_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$vault_source/deploy.sh" test "$@"
