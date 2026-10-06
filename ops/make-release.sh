#!/usr/bin/env bash
# Build the files of a release into dist/:
#
#   ezyspeech-<version>.tar.gz          the code, from the commit checked out
#   ezyspeech-cockpit-<version>.tar.gz  the Cockpit module (with COCKPIT_DIR)
#   install.sh                          the installer
#   SHA256SUMS                          what install.sh and ezyspeech check
#
#   ops/make-release.sh                 (COCKPIT_DIR=path/to/ezy_speech_cockpit)
#
# The version is VERSION's. The release workflow runs this; running it by hand
# gives the same files to test with.
#
# Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu)
# This file is part of EzySpeech, and is free software under the GNU Affero
# General Public License, version 3 or later. See LICENSE and TRADEMARK.md.
set -euo pipefail
cd "$(dirname "$0")/.."
version="$(cat VERSION)"
out="${DIST:-dist}"
rm -rf "$out" && mkdir -p "$out"

# The code as committed; files marked export-ignore in .gitattributes stay out.
git archive --format=tar.gz --prefix="ezyspeech-$version/" -o "$out/ezyspeech-$version.tar.gz" HEAD

if [ -n "${COCKPIT_DIR:-}" ]; then
    # Its Makefile fetches the parts of Cockpit it builds against (pkg/lib);
    # production is minified and compressed, without source maps.
    (cd "$COCKPIT_DIR" \
        && { [ -d node_modules ] || env -u NODE_ENV npm install --ignore-scripts --no-audit --no-fund; } \
        && rm -rf dist runtime-npm-modules.txt && make NODE_ENV=production >/dev/null)
    # dist/ goes in as ezyspeech/, the directory Cockpit looks for it in.
    stage="$(mktemp -d)"
    cp -R "$COCKPIT_DIR/dist" "$stage/ezyspeech"
    tar -czf "$out/ezyspeech-cockpit-$version.tar.gz" -C "$stage" ezyspeech
    rm -rf "$stage"
fi

cp install.sh "$out/install.sh"
(cd "$out" && if command -v sha256sum >/dev/null; then sha256sum -- *; else shasum -a 256 -- *; fi | grep -v SHA256SUMS > SHA256SUMS)
echo "Built $version in $out/:"; ls -l "$out"
