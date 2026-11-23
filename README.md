# Máquina de Turing Multicinta que simula la Bombe (con una Enigma integrada)

Implementación en Python de una **Máquina de Turing Multicinta de 5 cintas** que reproduce el principio de la **Bombe** de Turing–Welchman. Dentro de su control finito lleva un **subautómata Enigma** (rotores, reflector y plugboard) con el que prueba configuraciones hasta encontrar la que descifra una **criba**.

El escenario de prueba es el mismo de la receta de CyberChef del enunciado: la MTM recupera la clave `OPM` y descifra
`HELLO CYBER CHEFU SERST HISIS ATEST MESSA GEFOR THEDO CUMEN TATIO N`.

La fundamentación teórica completa (7-tupla, Enigma formal, función δ por fases, decidibilidad y Chomsky) está en **[`docs/teoria.md`](docs/teoria.md)**.

## Requisitos

- Python 3.8 o superior.
- **No necesita bibliotecas externas** (solo la biblioteca estándar).

## Estructura

```
├── mtm.py              Simulador genérico de MTM: M = (Q, Σ, Γ, δ, q0, A, R), δ: Q×Γ^k → Q×Γ^k×{L,R,S}^k
├── enigma_modelo.py    Enigma como transductor de Mealy: rotores (permutaciones que rotan),
│                       reflector (involución), plugboard (permutación parcial), doble paso
├── bombe_mtm.py        La Bombe como MTM de 5 cintas (δ por fases; la Enigma vive en el control finito)
├── cyberchef.py        Lee una URL de CyberChef con la receta Enigma(...)
├── main.py             Interfaz de línea de comandos
├── tests/              19 pruebas (vector de CyberChef, doble paso, involuciones, oráculo de la Bombe…)
└── docs/teoria.md      Documento teórico
```

## Uso rápido

```bash
# Escenario de CyberChef: se desconocen las posiciones iniciales (26³ = 17 576 configuraciones)
python main.py demo

# Ver las 5 cintas paso a paso (carga de configuración → descifrado → comparación → odómetro)
python main.py demo --traza 70 --desde 265

# Ver el momento de la "parada" y la escritura en la cinta 5
python main.py demo --traza 25 --desde 327900

# Criba en otra posición del mensaje (se codifica con '?' en la cinta 4)
python main.py demo --criba TESTMESSAGE --desplazamiento 26

# Orden de rotores también desconocido (6 bloques en la cinta 1)
python main.py demo --orden-desconocido
python main.py demo --orden-desconocido --candidatos I II III IV V    # 60 órdenes (tarda ~1-2 min)

# Criba corta: aparecen paradas falsas, como en la Bombe real
python main.py demo --criba HEL --modo todas

# Muestra la 7-tupla de la máquina
python main.py definicion

# Enigma suelta (cifrar = descifrar)
python main.py cifrar "ATAQUE AL AMANECER" --rotores I II III --anillos AAA --posiciones XYZ --plugboard "AB CD"

# Bombe sobre un mensaje propio
python main.py bombe --cifrado "<texto cifrado>" --criba ATAQUE --rotores I II III --plugboard "AB CD"

# Leer cualquier receta Enigma de CyberChef
python main.py cyberchef "https://gchq.github.io/CyberChef/#recipe=Enigma(...)&input=..."

# MTM de ejemplo con tabla δ explícita ({w#w})
python main.py ejemplo-mtm ab#ab ab#ba
```

## Pruebas

```bash
python -m unittest discover -s tests -v
```

Incluyen:

- el vector de CyberChef y el vector clásico `AAAAA → BDZGO`;
- el doble paso de los rotores;
- que el reflector, el plugboard y la permutación global sean involuciones sin puntos fijos;
- una comparación de las paradas de la MTM con una búsqueda directa sin Máquina de Turing (oráculo);
- rechazo cuando no hay coincidencia;
- detección de entrada mal formada.

## Cómo se cubre cada requerimiento

| Requerimiento | Dónde |
|---|---|
| 7-tupla $M = (Q, Σ, Γ, δ, q_0, A, R)$ y δ multicinta | `mtm.py` · `docs/teoria.md §1` |
| Rotores como permutaciones que cambian tras cada símbolo | `enigma_modelo.Rotor`, `MaquinaEnigma.avanzar` · §2.1–2.2 |
| Reflector involutivo | `enigma_modelo.Reflector` · §2.3 |
| Plugboard como permutación parcial | `enigma_modelo.Plugboard` · §2.4 |
| Estado interno dinámico | `MaquinaEnigma.transicion(s, x)` (Mealy) · §2.5 |
| Enigma como subautómata dentro de la MTM | fase `DESCIFRAR` de `bombe_mtm.py` · §3.3(d) |
| Cintas 1–5 y flujo leer → descifrar → comparar → aceptar/avanzar → rechazar | `bombe_mtm.py` · §3.1–3.4 |
| Justificación (Turing-computabilidad, RE, complejidad, tipo 0) | §4 |

## Supuesto de criptoanálisis

La máquina busca en el espacio *bloques × 26³ posiciones*. Cada bloque fija el orden de rotores, los anillos, el reflector y el plugboard. La Bombe histórica además deducía el plugboard por contradicciones lógicas (menús y *diagonal board*). Aquí se supone conocido para seguir el flujo pedido en el enunciado (ver `docs/teoria.md §4.4`).

## Referencias

- Receta de CyberChef del enunciado (`cyberchef.URL_EJEMPLO`).
- Repositorio de referencia: <https://github.com/modemn/enigma> (simulador en Python de Enigma y Bombe).
