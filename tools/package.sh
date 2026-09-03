#!/usr/bin/env bash
# Build the card and roll the integration into one tarball to copy to /config.
#
#   tools/package.sh
#   scp dayline-integration.tar.gz root@ha:/config/custom_components/
#   # on the instance:  tar xzf dayline-integration.tar.gz && rm dayline-integration.tar.gz
set -euo pipefail
cd "$(dirname "$0")/.."
npm run build
tar --exclude='__pycache__' --exclude='*.pyc' \
    -czf dayline-integration.tar.gz -C custom_components day_spine
echo "wrote dayline-integration.tar.gz ($(du -h dayline-integration.tar.gz | cut -f1))"
tar tzf dayline-integration.tar.gz
