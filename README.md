<p align="center">
  <img src="docs/img/iphone16pro.png" alt="OpenSwift render on iPhone 16 Pro" width="100%">
</p>

<h1 align="center">OpenSwift</h1>

<p align="center">
  <strong>Una mesa compartida para una pantalla.</strong><br>
  Tú nombras la vista. OpenSwift bloquea la sesión en ese archivo, lista los pocos archivos que un agente puede editar, y dibuja un bosquejo del teléfono. El siguiente comentario ("menos apretado", "ese botón es enorme") va sobre ese dibujo, no sobre el resto del repo.
</p>

<p align="center">
  <a href="#-pruébalo-en-30-segundos"><strong>▶ Pruébalo en 30 segundos</strong></a>
  &nbsp;·&nbsp;
  <a href="#-comandos"><strong>Comandos</strong></a>
  &nbsp;·&nbsp;
  <a href="#-providers"><strong>Providers</strong></a>
  &nbsp;·&nbsp;
  <a href="#-studio"><strong>Studio</strong></a>
</p>

---

## ¿Qué es?

No compila Swift. Dibuja un **bosquejo** de stacks, texto y botones dentro de un marco de iPhone realista (notch clásico, notch reducido, Dynamic Island, home indicator, botones laterales). La sesión alrededor del dibujo es el producto: una carpeta `.ui-session` con `target.json`, `intent.md`, `source.swift`, `preview.svg`, `preview.png` y `iterations/` con hashes SHA-256. Un agente y una persona miran lo mismo.

<p align="center">
  <img src="docs/img/iphone11.png" alt="iPhone 11 classic notch" width="30%">
  &nbsp;
  <img src="docs/img/iphone14.png" alt="iPhone 14 reduced notch" width="30%">
  &nbsp;
  <img src="docs/img/iphone16pro.png" alt="iPhone 16 Pro Dynamic Island" width="30%">
</p>

<p align="center">
  <em>iPhone 11 (notch clásico) · iPhone 14 (notch reducido) · iPhone 16 Pro (Dynamic Island)</em>
</p>

## Providers

| name | qué hace hoy |
|---|---|
| `approximate-web` | el único que dibuja. SVG + PNG, sin compilador |
| `miniswift` | nombrado, no cableado |
| `xcode-preview` | nombrado, no cableado |

## Pruébalo en 30 segundos

```bash
# 1. Clona y entra
cd OpenSwift

# 2. Bloquea una vista (crea .ui-session/)
PYTHONPATH="." python3 -m openswift focus examples/hello.swift \
  --allow Theme.swift --allow ModelPicker.swift \
  --intent "hacer el panel menos apretado"

# 3. Dibuja la primera iteración
PYTHONPATH="." python3 -m openswift render --device iphone-16-pro

# 4. Ve el estado
PYTHONPATH="." python3 -m openswift status
```

Salida de `status`:

```
target: /home/danny/.../OpenSwift/examples/hello.swift
provider: approximate-web
allowed: Theme.swift, ModelPicker.swift
read only: everything except target and allowed
iteration: 1
session: /home/danny/.../.ui-session
intent: hacer el panel menos apretado
```

Cada `render` añade `iterations/002.png`, `003.png`… para poder decir "esa, pero con el botón de la otra".

## Comandos

```bash
# Dibuja un SVG directo (sin sesión)
PYTHONPATH="." python3 -m openswift draw examples/hello.swift -o /tmp/hello.svg --device iphone-15

# Bloquea la mesa a una vista
PYTHONPATH="." python3 -m openswift focus ruta/a/Vista.swift \
  --allow Dep1.swift --allow Dep2.swift \
  --intent "tu intención" \
  --provider approximate-web

# Renderiza la vista bloqueada (usa .ui-session del cwd)
PYTHONPATH="." python3 -m openswift render --device iphone-14

# Estado de la sesión actual
PYTHONPATH="." python3 -m openswift status

# Sketch como JSON (para tooling)
PYTHONPATH="." python3 -m openswift sketch examples/hello.swift --device iphone-12
```

Dispositivos soportados: `iphone-11`, `iphone-12`, `iphone-13`, `iphone-14`, `iphone-14-plus`, `iphone-14-pro`, `iphone-15`, `iphone-16`, `iphone-16-pro`.

## Studio

Editor web local + previsualización del teléfono. No compila Swift.

```bash
# Desde tu proyecto (no desde OpenSwift)
PYTHONPATH="/home/danny/Development/ISyCo Git/OpenSwift" python3 -m openswift studio /ruta/a/tu/proyecto --port 8765
```

Abre `http://127.0.0.1:8765`. Elige un `.swift` a la izquierda, pulsa **Run** y verás el bosquejo a la derecha.

- **Debugger**: árbol del bosquejo (no call stack)
- **Output**: logs de render
- **Problems**: vistas/modificadores no dibujados
- **Console**: eventos

Seguridad: el servidor solo responde a `Host: 127.0.0.1` o `localhost`, rechaza `Origin` cruzados y exige `Content-Type: application/json` en POST. Probado contra DNS rebinding y formularios `text/plain`.

<p align="center">
  <img src="docs/img/iphone16pro.png" alt="Studio preview on iPhone 16 Pro" width="60%">
</p>

## App de escritorio (Tauri)

```bash
cd app
npm install
npm run tauri dev      # desarrollo
npm run tauri build    # .deb en src-tauri/target/release/bundle/deb/
```

La app incluye selector de dispositivo, árbol de archivos, editor con syntax highlighting (via `msf` lexer), y el mismo motor de bosquejo.

## La carpeta `.ui-session`

```text
.ui-session/
├── target.json      # target, allowed, provider, read_only, created, iteration, preview_sha256
├── intent.md        # tu intención en texto
├── source.swift     # copia del archivo bloqueado
├── preview.svg      # último SVG
├── preview.png      # último PNG
├── preview.sha256   # hash del PNG
└── iterations/
    ├── 001.png
    ├── 001.sha256
    ├── 002.png
    └── 002.sha256
```

`target.json` es la verdad única: qué archivo está en juego, qué dependencias puede tocar el agente, y que todo lo demás es **read only**.

## Qué dibuja (y qué no)

| SwiftUI | Dibuja |
|---|---|
| `VStack` / `HStack` / `ZStack` | ✅ layout real |
| `Text` / `Button` | ✅ con texto, fuente, color, peso |
| `Spacer` / `Divider` | ✅ |
| `TextField` / `SecureField` / `Label` / `Image` | ✅ como caja etiquetada |
| `Form` / `Section` / `List` / `ScrollView` | ✅ contenedores verticales |
| `NavigationStack` / `Group` / `GroupBox` | ✅ |
| `.font(.system(size:weight:))` | ✅ size + bold |
| `.foregroundColor/.foregroundStyle` | ✅ color + opacity |
| `.background` | ✅ color |
| `.padding` (todos los edges) | ✅ |
| `.cornerRadius` | ✅ |
| `.frame(height: / maxWidth: .infinity)` | ✅ |
| `.sheet`, `.overlay`, bindings, animaciones | ❌ sale en `problems` como `.sheet is ignored` |
| Vistas custom / librerías externas | ❌ caja con su nombre |

## Tests

```bash
PYTHONPATH="." python3 -m unittest discover -s tests
# 13 tests OK (preview, session, studio, security)
```

## Créditos

El studio colorea Swift con el lexer de [msf](https://github.com/toprakdeviren/msf) (MIT, Toprakdeviren), pinedo a un commit y compilado por `tools/build-lex.sh`. Ningún código de msf está en este repo. Ver [NOTICE.md](NOTICE.md) para el commit exacto, qué se distribuye y qué no.

---

<p align="center">
  <img src="docs/img/iphone11.png" alt="iPhone 11" width="24%">
  <img src="docs/img/iphone14.png" alt="iPhone 14" width="24%">
  <img src="docs/img/iphone16pro.png" alt="iPhone 16 Pro" width="24%">
</p>

<p align="center">
  Hecho para coordinar humanos y agentes en maquetado UI.<br>
  Licencia MIT.
</p>