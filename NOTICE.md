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

## iLoader — sideloading engine

| | |
|---|---|
| Project | iLoader |
| Author | nab138 |
| Source | https://github.com/nab138/iloader |
| License | MIT, Copyright (c) 2025 nab138 (its name and logo are licensed separately; OpenSwift uses neither) |
| What OpenSwift uses | the approach and parts of its Rust backend (Apple sign-in, certificate and App ID management, installing an `.ipa`, pairing files, SideStore install), adapted in `app/src-tauri/src/sideload.rs` |

It builds on the crates [`isideload`](https://crates.io/crates/isideload) and [`idevice`](https://crates.io/crates/idevice) (both MIT), which are regular Cargo dependencies, not copied code.

**Licenses that come with those crates.** `isideload` depends on `apple-codesign-quick`, which is **LGPL-2.1-or-later**. It is linked into the desktop app. Anyone who distributes a build of the desktop app must keep that notice, make the corresponding source of that crate available (it is public on crates.io and pinned in `app/src-tauri/Cargo.lock`) and not stop users from relinking the app with a modified version. The repository itself stays MIT.

The iLoader license text, as required by the MIT license:

```text
MIT License

Copyright (c) 2025 nab138

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## xtool — not included

[xtool](https://github.com/xtool-org/xtool) (MIT, Copyright (c) 2024 Kabir Oberai) is **not** part of OpenSwift. The desktop app only runs the `xtool` program if the user installed it, as a separate process.

## Related, not included

[MiniSwift](https://miniswift.run/) compiles Swift in the browser. It inspired the idea of a Swift preview with no Xcode. OpenSwift includes no code from miniswift.run, and `miniswift` is only a provider name that is not wired yet. This notice does not claim that msf and miniswift.run are the same project.
