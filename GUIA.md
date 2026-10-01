# OpenSwift — guía de uso

OpenSwift está pensado para trabajar **una pantalla a la vez** sin fingir que existe un runtime Swift donde no lo hay.

La idea es simple:

```text
elige una vista
      ↓
define qué archivos pertenecen a la tarea
      ↓
escribe la intención humana
      ↓
renderiza un sketch
      ↓
guarda cada iteración
```

## 1. Crear una sesión

Ejecuta `focus` desde la carpeta del proyecto donde quieras trabajar:

```bash
PYTHONPATH="/path/to/OpenSwift" \
  python3 -m openswift focus path/to/View.swift \
  --allow Theme.swift \
  --allow ModelPicker.swift \
  --intent "hacer el panel menos apretado"
```

OpenSwift crea `./.ui-session/` en el directorio actual.

La sesión registra:

- `target`: la pantalla en la que estás trabajando
- `allowed`: archivos relacionados declarados para esa tarea
- `intent`: qué quieres mejorar
- `provider`: cómo se genera el sketch
- `iteration`: cuántas previews se han guardado

## 2. Ver el estado

```bash
PYTHONPATH="/path/to/OpenSwift" python3 -m openswift status
```

Ejemplo:

```text
target: /project/Sources/ProfileView.swift
provider: approximate-web
allowed: Theme.swift, ModelPicker.swift
read only: everything except target and allowed
iteration: 0
session: /project/.ui-session
intent: hacer el panel menos apretado
```

`read only` describe la frontera de trabajo de la sesión: el target y los archivos `allowed` son los que pertenecen al cambio; el resto del proyecto queda fuera de alcance.

## 3. Renderizar

```bash
PYTHONPATH="/path/to/OpenSwift" \
  python3 -m openswift render --device iphone-16-pro
```

La primera ejecución crea:

```text
.ui-session/
├── preview.svg
├── preview.png
├── preview.sha256
└── iterations/
    ├── 001.png
    └── 001.sha256
```

La segunda añade `002.png`, luego `003.png`, etc.

Eso permite feedback concreto como:

> usa el layout de la 003, pero conserva el botón de la 002

sin depender de memoria visual o descripciones ambiguas.

## 4. Entender el sketch

El provider actual es `approximate-web`.

No ejecuta Swift, no evalúa bindings y no reemplaza Xcode Preview. Lee un subconjunto útil de SwiftUI y lo convierte en un árbol visual aproximado.

| Resultado | Significado |
|---|---|
| vista conocida | OpenSwift intenta dibujarla |
| vista custom/desconocida | aparece como una caja con su nombre |
| modificador no soportado | aparece en `Problems` |
| preview PNG/SVG | evidencia visual del sketch, no captura de Xcode |

Providers actuales:

| Provider | Estado |
|---|---|
| `approximate-web` | activo |
| `miniswift` | nombrado, todavía no cableado |
| `xcode-preview` | nombrado, todavía no cableado |

Si pides un provider no cableado, OpenSwift se niega en lugar de simular que funcionó.

## 5. Studio de escritorio

La app Tauri junta todo en una sola superficie:

- navegador de archivos Swift
- editor
- syntax highlighting
- selector de dispositivo
- preview del iPhone
- panel inferior de diagnóstico

```bash
cd /path/to/OpenSwift/app
npm install
npm run tauri dev
```

Atajos:

| Atajo | Acción |
|---|---|
| `Ctrl+Enter` | renderizar |
| `Ctrl+S` | guardar |

Paneles inferiores:

- **Debugger** — árbol del sketch, no call stack de Swift
- **Output** — salida del render
- **Problems** — vistas/modificadores no representados
- **Console** — eventos del Studio

## 6. Studio web local

También existe una superficie web local:

```bash
PYTHONPATH="/path/to/OpenSwift" \
  python3 -m openswift studio /path/to/project --port 8765
```

Ábrela en:

```text
http://127.0.0.1:8765
```

El servidor restringe `Host` a localhost, rechaza `Origin` cruzados y exige `Content-Type: application/json` para POST.

Esto es intencional: Studio puede guardar archivos, así que una página web ajena no debe poder manejarlo como un endpoint local genérico.

## 7. Render directo sin sesión

Para generar sólo un SVG:

```bash
PYTHONPATH="/path/to/OpenSwift" \
  python3 -m openswift draw examples/hello.swift \
  -o /tmp/hello.svg \
  --device iphone-15
```

Para obtener el árbol y el sketch como JSON:

```bash
PYTHONPATH="/path/to/OpenSwift" \
  python3 -m openswift sketch examples/hello.swift --device iphone-12
```

## 8. Dispositivos soportados

```text
iphone-11
iphone-12
iphone-13
iphone-14
iphone-14-plus
iphone-14-pro
iphone-15
iphone-16
iphone-16-pro
```

Los frames modelan diferencias visibles como notch clásico, notch reducido, Dynamic Island, home indicator y controles laterales.

## 9. Trampas comunes

**`no .ui-session here`**  
No ejecutaste `focus` desde ese directorio o estás ejecutando `render` desde otra carpeta.

**`miniswift is named, not wired`**  
Correcto. El provider existe en el contrato, pero todavía no tiene implementación.

**El preview no coincide 1:1 con Xcode**  
También es correcto. `approximate-web` produce un sketch útil, no una compilación SwiftUI real.

**Una vista aparece como caja**  
OpenSwift todavía no conoce esa vista. Revisa `Problems` para ver qué quedó fuera de la representación.

## 10. Qué conservar como evidencia

Para una iteración reproducible, conserva la carpeta `.ui-session` completa o al menos:

```text
target.json
intent.md
preview.png
preview.sha256
iterations/
```

Así la conversación humana, la tarea del agente y la evidencia visual siguen apuntando al mismo estado.
