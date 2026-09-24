# OpenSwift

A shared table for one screen.

You name a view. OpenSwift locks the session to that file, lists the few files an agent may edit, and draws a picture of the sketch. The next remark ("less cramped", "that button is huge") is about that picture, not about the rest of the repo.

This is not [MiniSwift](https://miniswift.run/). MiniSwift compiles Swift in the browser. OpenSwift does not compile anything. The picture is an approximation of stacks, text, and buttons. The session around the picture is the product. A later provider can swap in MiniSwift or an Xcode preview without changing the folder.

## Providers

| name | what it does today |
|---|---|
| `approximate-web` | the only one that draws. SVG plus PNG, no compiler |
| `miniswift` | named, not wired |
| `xcode-preview` | named, not wired |

## The folder

```text
.ui-session/
├── target.json
├── intent.md
├── source.swift
├── preview.svg
├── preview.png
├── preview.sha256
└── iterations/
    ├── 001.png
    └── 002.png
```

`target.json` says which file is in play, which dependencies may be edited, and that everything else is read only.

## Commands

```bash
python3 -m openswift focus SettingsView.swift \
  --allow Theme.swift --allow ModelPicker.swift \
  --intent "hacer el panel menos apretado"

python3 -m openswift render
python3 -m openswift status
python3 -m openswift draw examples/hello.swift -o /tmp/hello.svg
```

`render` reads the locked file again, writes `preview.png`, and copies it to the next `iterations/NNN.png`.

## Credits

The studio colors Swift with the lexer from [msf](https://github.com/toprakdeviren/msf) (MIT, by Toprakdeviren), pinned to one commit and built by `tools/build-lex.sh`. None of its code is in this repository. [NOTICE.md](NOTICE.md) has the commit, what ships and what does not.
