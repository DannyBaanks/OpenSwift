# OpenSwift

## El comando

Desde la carpeta del proyecto en el que quieres trabajar, no desde OpenSwift:

```bash
PYTHONPATH="/home/danny/Development/ISyCo Git/OpenSwift" \
  python3 -m openswift focus "/home/danny/Development/ISyCo Git/OpenSwift/examples/hello.swift" \
  --allow Theme.swift --allow ModelPicker.swift \
  --intent "hacer el panel menos apretado"
```

Salida real:

```text
/tmp/openswift-demo/.ui-session
```

Esa ruta era la carpeta donde se corrió. En tu proyecto el archivo queda en `./.ui-session`.

## La regla

Durante esa sesión se toca el archivo de `target.json` y los de `allowed`. El resto se lee y no se edita. El dibujo no es el iPhone: es un bosquejo. Si una vista no se conoce, sale una caja con su nombre.

## Los otros comandos

```bash
PYTHONPATH="/home/danny/Development/ISyCo Git/OpenSwift" python3 -m openswift status
```

```text
target: /home/danny/Development/ISyCo Git/OpenSwift/examples/hello.swift
provider: approximate-web
allowed: Theme.swift, ModelPicker.swift
read only: everything except target and allowed
iteration: 0
session: /tmp/openswift-demo/.ui-session
intent: hacer el panel menos apretado
```

```bash
PYTHONPATH="/home/danny/Development/ISyCo Git/OpenSwift" python3 -m openswift render
```

La primera vez imprime `.../iterations/001.png`. La segunda, `002.png`. El mismo dibujo también queda en `.ui-session/preview.png`, con su sha256 al lado.

## Cómo leerlo

| Campo | Qué es |
|---|---|
| `target` | La única pantalla de esta mesa |
| `allowed` | Los archivos que sí se pueden cambiar junto con ella |
| `iteration` | Cuántos dibujos se han guardado |
| `001.png`, `002.png` | Cada intento, para poder decir "esa, pero con el botón de la otra" |
| `provider: approximate-web` | El bosquejo local. `miniswift` y `xcode-preview` están nombrados y todavía no dibujan |

## Trampas

- Sin `focus` previo, `render` dice `no .ui-session here`.
- Pedir `--provider miniswift` se niega. No hay compilador detrás.
- El PNG es un mapa de píxeles del bosquejo, no una captura de Xcode.
