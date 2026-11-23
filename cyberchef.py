"""
cyberchef.py
============

Lee una URL de CyberChef con la receta Enigma(...) y la convierte en una
ConfiguracionEnigma + texto de entrada. Así el proyecto puede verificarse
contra el ejemplo de referencia:

https://gchq.github.io/CyberChef/#recipe=Enigma('3-rotor','','','',
    'BDFHJLCPRTXVZNYEIWGAKMUSQO<W','K','O',
    'AJDKSIRUXBLHWTMCQGZNPYFVOE<F','N','P',
    'ESOVPZJAYQUIRHXLNFTGKDCMWB<K','G','M',
    'AY BR CU DH EQ FS GL IP JX KN MO TZ VW',
    'AH CO DE GZ IJ KM LQ NY PS TW',true)&input=...

Orden de argumentos de CyberChef: modelo, (4º rotor, anillo, posición),
rotor izquierdo, anillo, posición, rotor central, ..., rotor derecho, ...,
reflector (pares), plugboard (pares), salida estricta.
"""

from __future__ import annotations

import base64
import re
from typing import List, Tuple
from urllib.parse import unquote

from enigma_modelo import (CATALOGO_REFLECTORES, CATALOGO_ROTORES, ConfiguracionEnigma,
                           normalizar_texto)

URL_EJEMPLO = (
    "https://gchq.github.io/CyberChef/#recipe=Enigma('3-rotor','','','',"
    "'BDFHJLCPRTXVZNYEIWGAKMUSQO%3CW','K','O','AJDKSIRUXBLHWTMCQGZNPYFVOE%3CF','N','P',"
    "'ESOVPZJAYQUIRHXLNFTGKDCMWB%3CK','G','M','AY%20BR%20CU%20DH%20EQ%20FS%20GL%20IP%20JX%20KN%20MO%20TZ%20VW',"
    "'AH%20CO%20DE%20GZ%20IJ%20KM%20LQ%20NY%20PS%20TW',true)"
    "&input=WFRTWU4gV0FFVUcgRVpBTFkgTlJRSU0gQU1MWlggTUZVT0QgQVdYTFkgTFpDVVogUU9RQlEgSkxDUEsgTkREUlcgRg"
)


def _argumentos(texto: str) -> List[str]:
    """Divide "'a','b',true" respetando comillas simples."""
    return [m.group(1) if m.group(1) is not None else m.group(2)
            for m in re.finditer(r"\s*(?:'((?:[^'\\]|\\.)*)'|([^,]+))\s*(?:,|$)", texto)]


def _rotor_por_cableado(cableado: str) -> str:
    cab = cableado.split("<")[0]
    for nombre, (c, _) in CATALOGO_ROTORES.items():
        if c == cab:
            return nombre
    raise ValueError(f"Cableado de rotor no reconocido: {cab}")


def _reflector_por_pares(pares: str) -> str:
    mapa = {}
    for p in pares.split():
        mapa[p[0]], mapa[p[1]] = p[1], p[0]
    imagen = "".join(mapa.get(c, c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    for nombre, c in CATALOGO_REFLECTORES.items():
        if c == imagen:
            return nombre
    raise ValueError(f"Reflector no reconocido: {pares}")


def leer_url(url: str) -> Tuple[ConfiguracionEnigma, str]:
    """Devuelve (configuración, texto de entrada) de una URL de CyberChef."""
    frag = url.split("#", 1)[-1]
    partes = dict(p.split("=", 1) for p in frag.split("&") if "=" in p)
    receta = unquote(partes.get("recipe", ""))
    m = re.search(r"Enigma\((.*)\)", receta)
    if not m:
        raise ValueError("La URL no contiene una receta Enigma(...)")
    args = _argumentos(m.group(1))
    if args[0] != "3-rotor":
        raise ValueError("Solo se admite el modelo '3-rotor'")
    rot = tuple(_rotor_por_cableado(args[i]) for i in (4, 7, 10))
    anillos = "".join(args[i] for i in (5, 8, 11))
    posiciones = "".join(args[i] for i in (6, 9, 12))
    reflector = _reflector_por_pares(args[13])
    plugboard = args[14]
    entrada = ""
    if "input" in partes:
        b64 = unquote(partes["input"])
        b64 += "=" * (-len(b64) % 4)
        entrada = base64.b64decode(b64).decode("utf-8", errors="replace")
    return ConfiguracionEnigma(rot, anillos, posiciones, reflector, plugboard), entrada
