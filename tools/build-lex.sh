#!/bin/sh
# msf's Makefile splits on spaces, so the library is built from a copy in /tmp.
set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
SRC="$ROOT/third_party/msf"
if [ ! -f "$SRC/include/msf.h" ]; then
  git clone --depth 1 https://github.com/toprakdeviren/msf.git "$SRC"
fi
rm -rf /tmp/msf-build
cp -a "$SRC" /tmp/msf-build
make -C /tmp/msf-build -j"$(nproc)"
mkdir -p "$ROOT/bin"
cc -O2 -I/tmp/msf-build/include "$ROOT/tools/openswift-lex.c" /tmp/msf-build/build/native/libMiniSwiftFrontend.a -o "$ROOT/bin/openswift-lex"
echo "$ROOT/bin/openswift-lex"
