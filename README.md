# OpenSwift

OpenSwift draws a picture of a small SwiftUI sketch. It does not compile Swift, it does not run a preview, and it is not [MiniSwift](https://miniswift.run/).

MiniSwift is an in-browser Swift compiler: lexer, parser, type checker, WebAssembly, and a real SwiftUI canvas. OpenSwift is the thing you can run on this machine when you only need to *see the shape* of a screen before anyone has Xcode. An agent can point it at a `.swift` file and open the SVG.

## What it draws

`VStack`, `HStack`, `ZStack`, `Text`, `Button`, `Spacer`, `Divider`, `TextField`, `SecureField`, plus `font`, `foregroundColor`, `background`, `padding`, `frame`, and `cornerRadius`.

Anything else is drawn as a labeled box with its type name, so a missing view is visible instead of silently dropped.

## Run

From this directory:

```bash
python3 -m openswift examples/hello.swift -o /tmp/hello.svg
```

The command prints the SVG path. Open that file. The picture is a phone frame with the sketch inside, and a footer that says it was not compiled.

```bash
python3 -m unittest tests/test_preview.py
```
