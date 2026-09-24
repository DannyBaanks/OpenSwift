# Third-party notice

## msf — Mini Swift Frontend

| | |
|---|---|
| Project | msf (Mini Swift Frontend) |
| Author | Toprakdeviren |
| Source | https://github.com/toprakdeviren/msf |
| License | MIT, Copyright (c) 2026 Toprakdeviren |
| Pinned commit | `a060d55bd60ae0c31acc30fbade23e550817e40e` (2026-06-29) |
| What OpenSwift uses | the lexer only, to color Swift in the studio editor |

**How it gets in.** None of msf's code is committed to this repository. `tools/build-lex.sh` fetches the pinned commit into `third_party/msf/` and builds it. It then links msf's static library with `tools/openswift-lex.c`, a small token-dump program written for OpenSwift, and writes the result to `bin/openswift-lex`. `third_party/` and `bin/` are git-ignored. The script refuses to build if `third_party/msf` is at any other commit.

**What ships.** The `.deb` built by Tauri does not include `bin/openswift-lex` or any msf code. A package that did include that binary would have to include msf's `LICENSE` file, because the binary contains msf.

**Without it.** OpenSwift works without msf: the editor is shown without colors, and parsing and drawing are OpenSwift's own code (`openswift/parse.py`, `openswift/render.py`).

## Related, not included

[MiniSwift](https://miniswift.run/) compiles Swift in the browser. It inspired the idea of a Swift preview with no Xcode. OpenSwift includes no code from miniswift.run, and `miniswift` is only a provider name that is not wired yet. This notice does not claim that msf and miniswift.run are the same project.
