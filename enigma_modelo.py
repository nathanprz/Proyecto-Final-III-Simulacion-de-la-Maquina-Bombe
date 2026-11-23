"""
enigma_modelo.py
================

Modelo abstracto de la Máquina Enigma (3 rotores) como **subautómata**.

La Enigma se modela como un transductor finito de tipo Mealy

        M_E = (S, Σ, Σ, δ_E, λ_E, s0)

donde
    Σ = {A, ..., Z}                         alfabeto de entrada y salida
    S = Z26 x Z26 x Z26                     posiciones (izq, centro, der) de los rotores
    δ_E(s, x) = avanzar(s)                  el estado cambia tras CADA símbolo leído
    λ_E(s, x) = P⁻¹ ∘ R⁻¹ ∘ U ∘ R ∘ P (x)   salida, calculada con s' = avanzar(s)

Los componentes fijos (orden de rotores, anillos, reflector y plugboard) son
parámetros de la máquina; las posiciones de los rotores son su estado interno.

Componentes:
    * Rotor      -> permutación π del alfabeto, desplazada por la rotación:
                    ρ_k(x) = π(x + k) - k   (mod 26),  k = posición - anillo
    * Reflector  -> involución sin puntos fijos: U(U(x)) = x y U(x) != x
    * Plugboard  -> permutación parcial involutiva definida por pares (a, b)

Todas las letras se representan internamente como enteros 0..25.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import permutations
from typing import Dict, Iterable, List, Sequence, Tuple

ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
N = 26


def a_num(c: str) -> int:
    """'A' -> 0, ..., 'Z' -> 25."""
    return ord(c) - 65


def a_letra(i: int) -> str:
    """0 -> 'A', ..., 25 -> 'Z' (módulo 26)."""
    return chr(i % N + 65)


def normalizar_texto(texto: str) -> str:
    """Mayúsculas y solo letras A-Z (elimina espacios, signos, dígitos)."""
    return "".join(c for c in texto.upper() if "A" <= c <= "Z")


# ---------------------------------------------------------------------------
# Catálogo histórico (Wehrmacht / Kriegsmarine)
#   cableado: imagen de A..Z ;  muescas: letra(s) visibles en la ventana
#   cuando el rotor hace avanzar al de su izquierda.
# ---------------------------------------------------------------------------
CATALOGO_ROTORES: Dict[str, Tuple[str, str]] = {
    "I":    ("EKMFLGDQVZNTOWYHXUSPAIBRCJ", "Q"),
    "II":   ("AJDKSIRUXBLHWTMCQGZNPYFVOE", "E"),
    "III":  ("BDFHJLCPRTXVZNYEIWGAKMUSQO", "V"),
    "IV":   ("ESOVPZJAYQUIRHXLNFTGKDCMWB", "J"),
    "V":    ("VZBRGITYUPSDNHLXAWMJQOFECK", "Z"),
    "VI":   ("JPGVOUMFYQBENHZRDKASXLICTW", "ZM"),
    "VII":  ("NZJHGRCXMYSWBOUFAIVLPEKQDT", "ZM"),
    "VIII": ("FKQHTLXOCBJSPDZRAMEWNIUYGV", "ZM"),
}

CATALOGO_REFLECTORES: Dict[str, str] = {
    "B": "YRUHQSLDPXNGOKMIEBFZCWVJAT",
    "C": "FVPJIAOYEDRZXWGCTKUQSBNMHL",
}


# ---------------------------------------------------------------------------
# Utilidades sobre permutaciones (funciones de sustitución del alfabeto)
# ---------------------------------------------------------------------------
def permutacion(cableado: str) -> List[int]:
    """Convierte 'EKMF...' en la lista π con π[x] = y."""
    if sorted(cableado) != list(ALFABETO):
        raise ValueError(f"'{cableado}' no es una permutación de A-Z")
    return [a_num(c) for c in cableado]


def inversa(p: Sequence[int]) -> List[int]:
    inv = [0] * N
    for x, y in enumerate(p):
        inv[y] = x
    return inv


def es_involucion(p: Sequence[int]) -> bool:
    """f(f(x)) = x para todo x."""
    return all(p[p[x]] == x for x in range(N))


def puntos_fijos(p: Sequence[int]) -> List[int]:
    return [x for x in range(N) if p[x] == x]


# ---------------------------------------------------------------------------
# Componentes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Rotor:
    """Rotor = permutación π + muescas. La rotación se aplica desde fuera
    (la posición forma parte del ESTADO de la Enigma, no del rotor)."""
    nombre: str
    adelante: Tuple[int, ...]
    atras: Tuple[int, ...]
    muescas: frozenset

    @staticmethod
    def del_catalogo(nombre: str) -> "Rotor":
        if nombre not in CATALOGO_ROTORES:
            raise ValueError(f"Rotor desconocido: {nombre}")
        cab, mu = CATALOGO_ROTORES[nombre]
        p = permutacion(cab)
        return Rotor(nombre, tuple(p), tuple(inversa(p)), frozenset(a_num(m) for m in mu))

    def senal_adelante(self, x: int, k: int) -> int:
        """ρ_k(x) = π(x + k) - k   (camino derecha -> izquierda)."""
        return (self.adelante[(x + k) % N] - k) % N

    def senal_atras(self, x: int, k: int) -> int:
        """ρ_k⁻¹(x) = π⁻¹(x + k) - k   (camino de regreso desde el reflector)."""
        return (self.atras[(x + k) % N] - k) % N


@dataclass(frozen=True)
class Reflector:
    """Función involutiva sin puntos fijos: f(x) = y  <=>  f(y) = x."""
    nombre: str
    mapa: Tuple[int, ...]

    @staticmethod
    def del_catalogo(nombre: str) -> "Reflector":
        if nombre not in CATALOGO_REFLECTORES:
            raise ValueError(f"Reflector desconocido: {nombre}")
        p = permutacion(CATALOGO_REFLECTORES[nombre])
        assert es_involucion(p) and not puntos_fijos(p)
        return Reflector(nombre, tuple(p))

    def __call__(self, x: int) -> int:
        return self.mapa[x]


@dataclass(frozen=True)
class Plugboard:
    """Permutación parcial involutiva definida por pares (a, b).
    Las letras sin cable se mapean a sí mismas."""
    pares: Tuple[Tuple[str, str], ...]
    mapa: Tuple[int, ...]

    @staticmethod
    def desde_texto(texto: str) -> "Plugboard":
        letras = normalizar_texto(texto)
        if len(letras) % 2:
            raise ValueError("El plugboard necesita un número par de letras (pares a-b)")
        mapa = list(range(N))
        usadas = set()
        pares = []
        for i in range(0, len(letras), 2):
            a, b = letras[i], letras[i + 1]
            if a == b or a in usadas or b in usadas:
                raise ValueError(f"Par inválido o letra repetida en plugboard: {a}{b}")
            usadas.update((a, b))
            mapa[a_num(a)], mapa[a_num(b)] = a_num(b), a_num(a)
            pares.append((a, b))
        return Plugboard(tuple(pares), tuple(mapa))

    def __call__(self, x: int) -> int:
        return self.mapa[x]

    def texto(self) -> str:
        return " ".join(a + b for a, b in self.pares)


# ---------------------------------------------------------------------------
# Configuración y subautómata
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ConfiguracionEnigma:
    """Clave completa de una Enigma de 3 rotores.
    rotores: (izquierdo, central, derecho) ; anillos/posiciones: 3 letras."""
    rotores: Tuple[str, str, str]
    anillos: str = "AAA"
    posiciones: str = "AAA"
    reflector: str = "B"
    plugboard: str = ""

    def __post_init__(self):
        if len(self.rotores) != 3:
            raise ValueError("Se requieren exactamente 3 rotores")
        if len(set(self.rotores)) != 3:
            raise ValueError("Los rotores no pueden repetirse")
        for r in self.rotores:
            if r not in CATALOGO_ROTORES:
                raise ValueError(f"Rotor desconocido: {r}")
        for nom, v in (("anillos", self.anillos), ("posiciones", self.posiciones)):
            if len(v) != 3 or normalizar_texto(v) != v:
                raise ValueError(f"{nom} debe tener 3 letras A-Z: '{v}'")
        if self.reflector not in CATALOGO_REFLECTORES:
            raise ValueError(f"Reflector desconocido: {self.reflector}")
        Plugboard.desde_texto(self.plugboard)  # valida

    # --- codificación en cinta: III.II.IV#KNG#OPM#B#AHCODE...$
    def a_cinta(self) -> str:
        return (".".join(self.rotores) + "#" + self.anillos + "#" + self.posiciones
                + "#" + self.reflector + "#" + normalizar_texto(self.plugboard) + "$")

    def texto(self) -> str:
        pb = Plugboard.desde_texto(self.plugboard).texto() or "(sin cables)"
        return (f"Rotores {'-'.join(self.rotores)} | Anillos {self.anillos} | "
                f"Posiciones {self.posiciones} | Reflector UKW-{self.reflector} | Plugboard {pb}")

    def con_posiciones(self, pos: str) -> "ConfiguracionEnigma":
        return ConfiguracionEnigma(self.rotores, self.anillos, pos, self.reflector, self.plugboard)


class MaquinaEnigma:
    """Subautómata de Mealy con parámetros fijos (rotores, anillos, reflector,
    plugboard). Su estado s = (p_izq, p_centro, p_der) se pasa explícitamente,
    de modo que puede vivir dentro del control finito de la Máquina de Turing."""

    def __init__(self, rotores: Sequence[str], anillos: str, reflector: str, plugboard: str):
        self.rotores = tuple(Rotor.del_catalogo(r) for r in rotores)
        self.anillos = tuple(a_num(c) for c in anillos)
        self.reflector = Reflector.del_catalogo(reflector)
        self.plugboard = Plugboard.desde_texto(plugboard)

    @staticmethod
    def desde_config(cfg: ConfiguracionEnigma) -> "MaquinaEnigma":
        return MaquinaEnigma(cfg.rotores, cfg.anillos, cfg.reflector, cfg.plugboard)

    # -------- δ_E: actualización del estado (rotación con doble paso) --------
    def avanzar(self, s: Tuple[int, int, int]) -> Tuple[int, int, int]:
        izq, cen, der = s
        r_izq, r_cen, r_der = self.rotores
        cen_en_muesca = cen in r_cen.muescas
        der_en_muesca = der in r_der.muescas
        if cen_en_muesca:                     # doble paso: el central arrastra al izquierdo
            izq = (izq + 1) % N               # y avanza él mismo
        if cen_en_muesca or der_en_muesca:
            cen = (cen + 1) % N
        der = (der + 1) % N                   # el derecho avanza siempre
        return (izq, cen, der)

    # -------- λ_E: sustitución para un estado dado --------
    def sustituir(self, s: Tuple[int, int, int], x: int) -> int:
        k = [(s[i] - self.anillos[i]) % N for i in range(3)]
        r_izq, r_cen, r_der = self.rotores
        x = self.plugboard(x)
        x = r_der.senal_adelante(x, k[2])
        x = r_cen.senal_adelante(x, k[1])
        x = r_izq.senal_adelante(x, k[0])
        x = self.reflector(x)
        x = r_izq.senal_atras(x, k[0])
        x = r_cen.senal_atras(x, k[1])
        x = r_der.senal_atras(x, k[2])
        return self.plugboard(x)

    def transicion(self, s: Tuple[int, int, int], letra: str) -> Tuple[Tuple[int, int, int], str]:
        """Un paso del transductor: devuelve (nuevo estado, letra de salida)."""
        s2 = self.avanzar(s)
        return s2, a_letra(self.sustituir(s2, a_num(letra)))

    def permutacion_en(self, s: Tuple[int, int, int]) -> List[int]:
        """Permutación global E_s del alfabeto en el estado s (es involutiva)."""
        return [self.sustituir(s, x) for x in range(N)]

    def procesar(self, s: Tuple[int, int, int], texto: str) -> Tuple[Tuple[int, int, int], str]:
        salida = []
        for c in normalizar_texto(texto):
            s, y = self.transicion(s, c)
            salida.append(y)
        return s, "".join(salida)


class Enigma:
    """Envoltura cómoda con estado mutable, para cifrar/descifrar fuera de la MTM."""

    def __init__(self, cfg: ConfiguracionEnigma):
        self.cfg = cfg
        self.maquina = MaquinaEnigma.desde_config(cfg)
        self.estado = tuple(a_num(c) for c in cfg.posiciones)

    @property
    def ventana(self) -> str:
        return "".join(a_letra(i) for i in self.estado)

    def procesar(self, texto: str) -> str:
        self.estado, salida = self.maquina.procesar(self.estado, texto)
        return salida


def cifrar(cfg: ConfiguracionEnigma, texto: str) -> str:
    """Cifrar y descifrar son la misma operación (la Enigma es recíproca)."""
    return Enigma(cfg).procesar(texto)


def ordenes_de_rotores(candidatos: Iterable[str]) -> List[Tuple[str, str, str]]:
    """Todas las ordenaciones de 3 rotores distintos tomados de 'candidatos'."""
    return list(permutations(list(candidatos), 3))


def agrupar5(texto: str) -> str:
    return " ".join(texto[i:i + 5] for i in range(0, len(texto), 5))
