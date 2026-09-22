# OpenSwift

## El comando

```bash
cd "/home/danny/Development/ISyCo Git/OpenSwift"
python3 -m openswift examples/hello.swift -o /tmp/hello.svg
```

Salida real:

```text
/tmp/hello.svg
```

Abre ese archivo. Es un dibujo del teléfono, no una app compilada.

## La regla

OpenSwift no compila Swift. Si el archivo usa una vista que no conoce, la dibuja como una caja con el nombre. Eso significa "esto no lo sé pintar", no "así se ve en el iPhone".

## Cómo leer el dibujo

| Lo que ves | Qué es |
|---|---|
| El texto que escribiste en `Text` o `Button` | Lo que el lector entendió |
| Una caja gris con un nombre (`Gauge`, `List`, …) | Esa vista no se dibuja todavía |
| El pie "not compiled Swift" | El archivo se generó sin pasar por un compilador |

## Trampas

- No es MiniSwift. MiniSwift corre Swift de verdad en el navegador. Esto solo bosqueja la pantalla.
- El primer `var body` del archivo es el que se dibuja. Si hay varios, los demás no salen.
- Un `Button { } label: { Text("hola") }` y un `Button("hola")` se dibujan los dos. Un botón armado con otra forma puede salir vacío.
