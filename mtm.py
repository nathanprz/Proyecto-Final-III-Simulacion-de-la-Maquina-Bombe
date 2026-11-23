"""
mtm.py
======

Simulador genérico de una Máquina de Turing Multicinta (MTM).

    M = (Q, Σ, Γ, δ, q0, A, R)

    Q   conjunto finito de estados
    Σ   alfabeto de entrada            (Σ ⊆ Γ,  ⊔ ∉ Σ)
    Γ   alfabeto de cinta              (⊔ ∈ Γ)
    δ   función de transición          δ : Q x Γ^k  ->  Q x Γ^k x {L, R, S}^k
    q0  estado inicial                 (q0 ∈ Q)
    A   estados de aceptación          (A ⊆ Q)
    R   estados de rechazo             (R ⊆ Q,  A ∩ R = ∅)

Convenciones:
    * Las k cintas son infinitas en ambos sentidos; cada celda no escrita contiene ⊔.
    * En un paso la máquina lee los k símbolos bajo los cabezales, y según δ:
      cambia de estado, escribe k símbolos y mueve cada cabezal L, R o S.
    * La máquina se detiene al entrar en A (acepta) o en R (rechaza).
      Si δ no está definida para (q, a1..ak) la máquina se detiene y rechaza.

δ puede darse como:
    - un diccionario  {(q, (a1,...,ak)): (q', (b1,...,bk), (m1,...,mk))}   (tabla explícita)
    - una función     δ(q, (a1,...,ak)) -> (q', (b1,...,bk), (m1,...,mk)) o None
      (útil cuando Q es finito pero demasiado grande para listarlo, como en la Bombe:
       la función es simplemente una descripción compacta de la tabla).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Hashable, Iterable, List, Optional, Sequence, Tuple, Union

BLANCO = "⊔"
L, R, S = "L", "R", "S"
MOVIMIENTOS = {L: -1, R: +1, S: 0}

Transicion = Tuple[Hashable, Tuple[str, ...], Tuple[str, ...]]
FuncionDelta = Callable[[Hashable, Tuple[str, ...]], Optional[Transicion]]


class Cinta:
    """Cinta bi-infinita con un cabezal. Implementada con dos listas (izquierda/derecha)
    para que leer/escribir/mover sean O(1)."""

    __slots__ = ("der", "izq", "cabezal")

    def __init__(self, contenido: Iterable[str] = ""):
        self.der: List[str] = list(contenido)   # celdas 0, 1, 2, ...
        self.izq: List[str] = []                # celdas -1, -2, ...
        self.cabezal = 0

    def leer(self) -> str:
        p = self.cabezal
        if p >= 0:
            return self.der[p] if p < len(self.der) else BLANCO
        p = -p - 1
        return self.izq[p] if p < len(self.izq) else BLANCO

    def escribir(self, simbolo: str) -> None:
        p = self.cabezal
        if p >= 0:
            if p >= len(self.der):
                if simbolo == BLANCO:
                    return
                self.der.extend(BLANCO * (p - len(self.der) + 1))
            self.der[p] = simbolo
        else:
            p = -p - 1
            if p >= len(self.izq):
                if simbolo == BLANCO:
                    return
                self.izq.extend(BLANCO * (p - len(self.izq) + 1))
            self.izq[p] = simbolo

    def mover(self, m: str) -> None:
        self.cabezal += MOVIMIENTOS[m]

    def contenido(self) -> str:
        """Contenido no blanco (de la primera a la última celda no blanca)."""
        celdas = list(reversed(self.izq)) + self.der
        s = "".join(celdas).strip(BLANCO)
        return s

    def ventana(self, radio: int = 12) -> str:
        """Fragmento alrededor del cabezal, marcándolo con [ ]."""
        partes = []
        guardado = self.cabezal
        for p in range(guardado - radio, guardado + radio + 1):
            self.cabezal = p
            s = self.leer()
            partes.append(f"[{s}]" if p == guardado else s)
        self.cabezal = guardado
        return "".join(partes)


@dataclass
class Resultado:
    aceptada: bool
    estado_final: Hashable
    pasos: int
    cintas: List[Cinta]
    detenida_por_limite: bool = False

    def contenido(self, i: int) -> str:
        """Contenido de la cinta i (numeración 1..k, como en la teoría)."""
        return self.cintas[i - 1].contenido()


@dataclass
class MaquinaTuringMultinta:
    """M = (Q, Σ, Γ, δ, q0, A, R) con k cintas."""
    k: int
    Q: object                           # conjunto (o descripción con __contains__)
    Sigma: frozenset
    Gamma: frozenset
    delta: Union[Dict, FuncionDelta]
    q0: Hashable
    A: object                           # conjunto o predicado (q -> bool)
    R: object                           # conjunto o predicado (q -> bool)
    nombre: str = "M"
    validar: bool = True                # comprobar que δ respeta Γ y {L,R,S}

    # ------------------------------------------------------------------
    def _pertenece(self, conjunto, q) -> bool:
        return conjunto(q) if callable(conjunto) else q in conjunto

    def es_aceptacion(self, q) -> bool:
        return self._pertenece(self.A, q)

    def es_rechazo(self, q) -> bool:
        return self._pertenece(self.R, q)

    def _delta(self, q, simbolos: Tuple[str, ...]) -> Optional[Transicion]:
        if callable(self.delta):
            return self.delta(q, simbolos)
        return self.delta.get((q, simbolos))

    # ------------------------------------------------------------------
    def cintas_iniciales(self, entradas: Sequence[str]) -> List[Cinta]:
        if len(entradas) > self.k:
            raise ValueError("Más entradas que cintas")
        for w in entradas:
            for c in w:
                if c not in self.Sigma:
                    raise ValueError(f"Símbolo '{c}' no pertenece a Σ")
        entradas = list(entradas) + [""] * (self.k - len(entradas))
        return [Cinta(w) for w in entradas]

    def ejecutar(self, entradas: Sequence[str], max_pasos: Optional[int] = None,
                 observador: Optional[Callable[[int, Hashable, List[Cinta], Optional[Transicion]], None]] = None
                 ) -> Resultado:
        """Ejecuta M sobre las entradas (entrada estándar: solo la cinta 1).

        observador(paso, estado, cintas, transicion) se llama antes de aplicar cada
        transición (y una vez al final con transicion=None)."""
        cintas = self.cintas_iniciales(entradas)
        q = self.q0
        pasos = 0
        k = self.k
        Gamma = self.Gamma
        while True:
            if self.es_aceptacion(q) or self.es_rechazo(q):
                if observador:
                    observador(pasos, q, cintas, None)
                return Resultado(self.es_aceptacion(q), q, pasos, cintas)
            if max_pasos is not None and pasos >= max_pasos:
                return Resultado(False, q, pasos, cintas, detenida_por_limite=True)
            leidos = tuple(c.leer() for c in cintas)
            t = self._delta(q, leidos)
            if observador:
                observador(pasos, q, cintas, t)
            if t is None:                                  # δ indefinida => rechazo
                return Resultado(False, q, pasos, cintas)
            q2, escritos, movs = t
            if self.validar:
                if len(escritos) != k or len(movs) != k:
                    raise RuntimeError("δ debe devolver k símbolos y k movimientos")
                for b in escritos:
                    if b not in Gamma:
                        raise RuntimeError(f"δ escribe '{b}' ∉ Γ (estado {q})")
                for m in movs:
                    if m not in MOVIMIENTOS:
                        raise RuntimeError(f"Movimiento inválido {m}")
            for c, b, m in zip(cintas, escritos, movs):
                c.escribir(b)
                c.mover(m)
            q = q2
            pasos += 1


# ---------------------------------------------------------------------------
# Ejemplo pequeño con TABLA δ explícita: L = { w#w : w ∈ {a,b}* }  (2 cintas)
# Sirve para mostrar que el simulador es genérico y que la Bombe es solo
# otra instancia de la misma definición.
# ---------------------------------------------------------------------------
def ejemplo_ww() -> MaquinaTuringMultinta:
    B = BLANCO
    d = {}
    # q0: copiar w a la cinta 2 hasta '#'
    for x in "ab":
        d[("q0", (x, B))] = ("q0", (x, x), (R, R))
    d[("q0", ("#", B))] = ("q1", ("#", B), (S, L))
    # q1: rebobinar cinta 2
    for x in "ab":
        d[("q1", ("#", x))] = ("q1", ("#", x), (S, L))
    d[("q1", ("#", B))] = ("q2", ("#", B), (R, R))
    # q2: comparar
    for x in "ab":
        d[("q2", (x, x))] = ("q2", (x, x), (R, R))
    d[("q2", (B, B))] = ("qA", (B, B), (S, S))
    # cualquier otra combinación: δ indefinida => rechazo
    return MaquinaTuringMultinta(
        k=2, Q={"q0", "q1", "q2", "qA"}, Sigma=frozenset("ab#"),
        Gamma=frozenset("ab#" + B), delta=d, q0="q0", A={"qA"}, R=set(), nombre="M_ww")
