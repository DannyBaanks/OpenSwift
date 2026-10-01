# Guía práctica de OpenSwift

OpenSwift dibuja un bosquejo de SwiftUI para revisar una pantalla y conversar sobre su composición. No compila Swift, no ejecuta la app y no reemplaza la preview de Xcode.

## Requisitos

- Python 3.10 o posterior para el CLI y el Studio web local.
- Bun, Rust y las dependencias nativas de Tauri para desarrollar la app de escritorio.

Los comandos siguientes se ejecutan desde la carpeta del proyecto que vas a editar. Define la ruta al clon de OpenSwift una vez:

```bash
export OPENSWIFT_DIR="/ruta/al/clon/OpenSwift"
export PYTHONPATH="$OPENSWIFT_DIR"
```

Por ejemplo, si estás dentro del mismo clon:

```bash
export OPENSWIFT_DIR="$PWD"
export PYTHONPATH="$OPENSWIFT_DIR"
```

## 1. Abrir una sesión

Elige el archivo principal de la vista. Usa `--allow` para indicar dependencias que también se pueden guardar durante esta sesión:

```bash
python3 -m openswift focus Sources/ContentView.swift \
  --allow Sources/Theme.swift \
  --intent "darle más aire al panel"
```

Esto crea `.ui-session/` en el directorio actual. `target` es la vista elegida; `allowed` contiene los otros archivos autorizados.

## 2. Dibujar y revisar

```bash
python3 -m openswift render --device iphone-16-pro
python3 -m openswift status
```

La primera preview aparece como `.ui-session/iterations/001.png`. Los renders posteriores crean `002.png`, `003.png` y así sucesivamente. La imagen actual, el SVG y los hashes quedan también en `.ui-session/`.

Para inspeccionar un archivo sin abrir una sesión:

```bash
python3 -m openswift draw Sources/ContentView.swift \
  --device iphone-14 --output /tmp/content-view.svg
```

## 3. Editar en Studio

### App de escritorio

Desde la raíz del clon de OpenSwift:

```bash
cd "$OPENSWIFT_DIR/app"
bun install
bun run tauri dev
```

Pulsa **Open** para elegir el proyecto y selecciona un archivo Swift. **Run** dibuja el sketch, **Save** guarda el archivo abierto, `Ctrl+Enter` vuelve a dibujar y `Ctrl+S` guarda.

Los paneles de abajo muestran el árbol del sketch, el resultado, los avisos y los eventos. “Debugger” es el nombre del panel: no hay ejecución de Swift ni call stack.

Para compilar la app, ejecuta `bun run tauri build` desde `app/`. Linux genera AppImage y paquetes como `.deb`/`.rpm`; en Windows el icono se integra al `.exe` mediante `icon.ico`.

### Studio web local

Desde cualquier directorio:

```bash
PYTHONPATH="$OPENSWIFT_DIR" python3 -m openswift studio \
  "/ruta/al/proyecto" --port 8765
```

Abre `http://127.0.0.1:8765` o `http://localhost:8765`. El Studio web se restringe a la máquina local. No lo expongas mediante un proxy o una interfaz de red.

## Qué significa el límite de edición

Mientras exista `.ui-session/target.json`, Studio permite guardar únicamente `target` y las rutas incluidas en `allowed`. El resto del proyecto sigue disponible para lectura.

Ese límite protege los guardados realizados desde Studio. No es un sandbox del sistema operativo: un agente o proceso con acceso directo al disco puede editar cualquier archivo. Si ya no quieres que Studio aplique la sesión, mueve o elimina `target.json`; los renders y hashes restantes se conservan.

## Leer `status`

| Campo | Significado |
|---|---|
| `target` | Archivo principal de esta sesión |
| `allowed` | Archivos adicionales permitidos al guardar desde Studio |
| `provider` | Motor usado para producir la preview |
| `iteration` | Número de previews guardadas |
| `intent` | Cambio que quieres explorar |

`approximate-web` es el único provider conectado. `miniswift` y `xcode-preview` están reservados para una integración futura.

## Qué esperar del bosquejo

El parser reconoce un subconjunto de SwiftUI: stacks, texto, botones, algunos controles, contenedores y modificadores sencillos. No interpreta el programa Swift completo. Vistas propias o APIs no compatibles pueden salir como cajas etiquetadas o aparecer en **Problems**.

Usa la imagen para hablar de estructura y proporciones. Confirma el comportamiento real en el entorno SwiftUI de destino.

## Problemas comunes

- **`no .ui-session here`**: ejecuta `focus` primero desde la carpeta del proyecto.
- **Un guardado responde `file is read-only in active .ui-session`**: el archivo no es el `target` ni está en `allowed`; cierra la sesión o crea otra con el archivo autorizado.
- **No aparecen colores de sintaxis**: el lexer es opcional. Para compilarlo, ejecuta `./tools/build-lex.sh` desde la raíz de OpenSwift.
- **La preview se ve distinta de iOS**: es una aproximación estática, no el renderer de Apple.
- **No se conecta Studio desde otra computadora**: el servidor sólo acepta el origen local por diseño.

## Referencias

- [README](README.md)
- [Aviso de terceros](NOTICE.md)
- [Licencia](LICENSE)
