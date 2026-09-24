#!/bin/sh
# msf's Makefile splits on spaces, so the library is built from a copy in /tmp.
# msf is pinned to one commit (see NOTICE.md); bump MSF_COMMIT on purpose, never by accident.
set -e
MSF_URL=https://github.com/toprakdeviren/msf.git
MSF_COMMIT=a060d55bd60ae0c31acc30fbade23e550817e40e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
SRC="$ROOT/third_party/msf"
if [ ! -f "$SRC/include/msf.h" ]; then
  git init -q "$SRC"
  git -C "$SRC" remote add origin "$MSF_URL"
  git -C "$SRC" fetch -q --depth 1 origin "$MSF_COMMIT"
  git -C "$SRC" checkout -q FETCH_HEAD
fi
HAVE=$(git -C "$SRC" rev-parse HEAD)
if [ "$HAVE" != "$MSF_COMMIT" ]; then
  echo "third_party/msf is at $HAVE, expected $MSF_COMMIT (NOTICE.md)." >&2
  echo "Move that folder aside and run this again to fetch the pinned commit." >&2
  exit 1
fi
rm -rf /tmp/msf-build
cp -a "$SRC" /tmp/msf-build
make -C /tmp/msf-build -j"$(nproc)"
mkdir -p "$ROOT/bin"
cc -O2 -I/tmp/msf-build/include "$ROOT/tools/openswift-lex.c" /tmp/msf-build/build/native/libMiniSwiftFrontend.a -o "$ROOT/bin/openswift-lex"
echo "$ROOT/bin/openswift-lex (msf $MSF_COMMIT)"
