"""
bombe_mtm.py
============

La Máquina Bombe construida como una Máquina de Turing Multicinta de 5 cintas
que contiene, dentro de su control finito, el subautómata Enigma
(ver enigma_modelo.MaquinaEnigma).

    M_Bombe = (Q, Σ, Γ, δ, q0, A, R),   k = 5

Cintas
------
    Cinta 1  Configuraciones posibles (bloques)      III.II.IV#KNG#AAA#B#AHCODE...$ ...
    Cinta 2  Texto cifrado (mensaje interceptado)    XTSYNWAEUG...
    Cinta 3  Descifrado tentativo                    (lo escribe la máquina)
    Cinta 4  Criba / patrón esperado                 ??????HELLO   ('?' = comodín)
    Cinta 5  Registro: configuración ganadora        III.II.IV#KNG#OPM#B#...>HELLOCYBER...

Entrada estándar (solo en la cinta 1):
        w = BLOQUE_1 BLOQUE_2 ... BLOQUE_n % CIFRADO % CRIBA
La fase de DISTRIBUCIÓN copia CIFRADO a la cinta 2 y CRIBA a la cinta 4.

Cada bloque fija rotores, anillos, reflector y plugboard; su campo de
posiciones funciona como un ODÓMETRO: la máquina prueba la posición escrita,
y si falla incrementa el campo en la propia cinta (AAA, AAB, ..., ZZZ).
Al desbordar pasa al siguiente bloque. Así la cinta 1 recorre el espacio
de configuraciones  bloques x Z26^3.

Estados
-------
    Q = F x Reg   (finito)
      F   = {DIST, COP_CIF, COP_CRIB, REB, CARGAR, APARCAR, DESCIFRAR, COMPARAR,
             EMITIR, COMPLETO, COPIA, INC, VOLVER, SALTAR, NUEVO_BLOQUE,
             q_acepta, q_rechaza, q_error}
      Reg = registros acotados del control finito: campos leídos de la cinta 1
            (longitud <= 26), clave de la Enigma (catálogo finito), posiciones
            iniciales y actuales (Z26^3), contadores pequeños y una bandera.
    El estado interno de la Enigma (posición de los rotores) es parte de Q:
    el subautómata Enigma "vive" dentro del control finito de la MTM.

    A = {q_acepta}     R = {q_rechaza, q_error}
"""

from __future__ import annotations

from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

from enigma_modelo import (ALFABETO, CATALOGO_REFLECTORES, ConfiguracionEnigma,
                           MaquinaEnigma, a_letra, a_num, normalizar_texto,
                           ordenes_de_rotores)
from mtm import BLANCO, L, R, S, MaquinaTuringMultinta, Resultado

B = BLANCO
LETRAS = frozenset(ALFABETO)
SIGMA = frozenset(ALFABETO + ".#$%?")
GAMMA = frozenset(SIGMA | {BLANCO, ">", ";"})
MAX_BUFFER = 26           # cota de los registros => Q es finito
K = 5

FASES = ("DIST", "COP_CIF", "COP_CRIB", "REB", "CARGAR", "APARCAR", "DESCIFRAR",
         "COMPARAR", "EMITIR", "COMPLETO", "COPIA", "INC", "VOLVER", "SALTAR",
         "NUEVO_BLOQUE", "q_acepta", "q_rechaza", "q_error")

DESCRIPCION_FASES = {
    "DIST": "Busca el primer '%' en la cinta 1 (inicio del cifrado)",
    "COP_CIF": "Copia el texto cifrado a la cinta 2",
    "COP_CRIB": "Copia la criba a la cinta 4",
    "REB": "Rebobina cabezales hasta el extremo izquierdo",
    "CARGAR": "Lee una configuración de la cinta 1 al control finito",
    "APARCAR": "Coloca el cabezal 1 sobre el campo de posiciones (odómetro)",
    "DESCIFRAR": "Subautómata Enigma: cinta 2 -> cinta 3",
    "COMPARAR": "Compara cinta 3 con la criba de la cinta 4",
    "EMITIR": "Escribe la configuración ganadora en la cinta 5",
    "COMPLETO": "Descifra el mensaje completo con la clave hallada",
    "COPIA": "Copia el descifrado tentativo a la cinta 5 (modo todas)",
    "INC": "Incrementa el odómetro de posiciones en la cinta 1",
    "VOLVER": "Regresa el cabezal 1 al último dígito del odómetro",
    "SALTAR": "Odómetro desbordado: avanza al siguiente bloque",
    "NUEVO_BLOQUE": "¿Quedan bloques en la cinta 1?",
    "q_acepta": "Coincidencia encontrada (parada de la Bombe)",
    "q_rechaza": "Se agotaron las configuraciones sin coincidencia",
    "q_error": "Entrada mal formada",
}


class Estado(NamedTuple):
    """Un elemento q ∈ Q = F x Reg."""
    fase: str
    campo: int = 0                       # índice del campo que se está leyendo
    buf: str = ""                        # buffer del campo actual (<= MAX_BUFFER)
    campos: Tuple[str, ...] = ()         # campos ya leídos
    clave: Tuple = ()                    # (rotores, anillos, reflector, plugboard)
    pos_ini: Tuple[int, int, int] = (0, 0, 0)   # posiciones de la config. en prueba
    pos: Tuple[int, int, int] = (0, 0, 0)       # ESTADO del subautómata Enigma
    cont: int = 0                        # contador de '#'
    i: int = 2                           # dígito del odómetro
    pend: str = ""                       # cadena pendiente de escribir en cinta 5
    idx: int = 0
    sig: str = ""                        # fase de continuación
    reb: Tuple[int, ...] = ()            # cintas a rebobinar
    hallado: bool = False                # ¿ya hubo alguna parada? (modo 'todas')

    def __str__(self) -> str:
        extra = ""
        if self.clave:
            extra = f" pos={''.join(a_letra(x) for x in self.pos)}"
        if self.fase == "REB":
            extra += f" cintas={[t + 1 for t in self.reb]}->{self.sig}"
        return f"{self.fase}{extra}"


Q0 = Estado("DIST")


def texto_config(clave: Tuple, pos: Tuple[int, int, int]) -> str:
    rot, ani, ref, pb = clave
    return ".".join(rot) + "#" + ani + "#" + "".join(a_letra(x) for x in pos) + "#" + ref + "#" + pb


def parsear_config(texto: str) -> ConfiguracionEnigma:
    """Inverso de texto_config / ConfiguracionEnigma.a_cinta."""
    rot, ani, pos, ref, pb = texto.rstrip("$").split("#")
    return ConfiguracionEnigma(tuple(rot.split(".")), ani, pos, ref,
                               " ".join(pb[i:i + 2] for i in range(0, len(pb), 2)))


# ---------------------------------------------------------------------------
# Construcción de la máquina
# ---------------------------------------------------------------------------
def construir_bombe(modo: str = "primero", estadisticas: Optional[Dict] = None) -> MaquinaTuringMultinta:
    """modo='primero': acepta en la primera coincidencia (flujo del enunciado).
    modo='todas'   : registra TODAS las paradas en la cinta 5 y acepta al final
                     si hubo al menos una (como la Bombe real, que podía dar
                     paradas falsas que luego se verificaban a mano)."""
    if modo not in ("primero", "todas"):
        raise ValueError("modo debe ser 'primero' o 'todas'")
    est = estadisticas if estadisticas is not None else {}
    est.setdefault("configuraciones", 0)
    est.setdefault("paradas", 0)
    cache: Dict[Tuple, MaquinaEnigma] = {}

    def enigma(clave) -> MaquinaEnigma:
        m = cache.get(clave)
        if m is None:
            rot, ani, ref, pb = clave
            m = cache[clave] = MaquinaEnigma(rot, ani, ref, pb)
        return m

    def mov(**m) -> Tuple[str, ...]:
        """mov(c1=R, c3=L) -> (R, S, L, S, S)"""
        return tuple(m.get(f"c{t}", S) for t in range(1, K + 1))

    def error(a):
        return Estado("q_error"), a, mov()

    def iniciar_reb(q: Estado, cintas: Tuple[int, ...], sig: str, escritos, extra_movs=None):
        movs = [S] * K
        for t in cintas:
            movs[t] = L
        if extra_movs:
            for t, m in extra_movs.items():
                movs[t] = m
        return q._replace(fase="REB", reb=cintas, sig=sig), escritos, tuple(movs)

    def entrar(q: Estado, fase: str) -> Estado:
        """Inicializa los registros que necesita cada fase al entrar en ella."""
        if fase == "INC":
            return q._replace(fase="INC", i=2)
        if fase == "CARGAR":
            return Estado("CARGAR", hallado=q.hallado)
        if fase == "COMPLETO":
            return q._replace(fase="COMPLETO", pos=q.pos_ini)
        if fase == "DESCIFRAR":
            est["configuraciones"] += 1
            return q._replace(fase="DESCIFRAR", pos=q.pos_ini)
        return q._replace(fase=fase)

    def delta(q: Estado, a: Tuple[str, ...]):
        f = q.fase
        a1, a2, a3, a4, a5 = a

        # ---------------- Distribución de la entrada ----------------
        if f == "DIST":
            if a1 == "%":
                return q._replace(fase="COP_CIF"), a, mov(c1=R)
            if a1 == B:
                return error(a)
            return q, a, mov(c1=R)

        if f == "COP_CIF":
            if a1 in LETRAS:
                return q, (a1, a1, a3, a4, a5), mov(c1=R, c2=R)
            if a1 == "%":
                return q._replace(fase="COP_CRIB"), a, mov(c1=R)
            return error(a)

        if f == "COP_CRIB":
            if a1 in LETRAS or a1 == "?":
                return q, (a1, a2, a3, a1, a5), mov(c1=R, c4=R)
            if a1 == B:
                return iniciar_reb(q, (0, 1, 3), "CARGAR", a)
            return error(a)

        # ---------------- Rebobinado genérico ----------------
        if f == "REB":
            movs = [S] * K
            listo = True
            for t in q.reb:
                if a[t] != B:
                    movs[t] = L
                    listo = False
            if listo:
                for t in q.reb:
                    movs[t] = R
                return entrar(q, q.sig), a, tuple(movs)
            return q, a, tuple(movs)

        # ---------------- Lectura de una configuración (cinta 1) ----------------
        if f == "CARGAR":
            if a1 in LETRAS or a1 == ".":
                if len(q.buf) >= MAX_BUFFER:
                    return error(a)
                return q._replace(buf=q.buf + a1), a, mov(c1=R)
            if a1 == "#":
                if q.campo >= 4:
                    return error(a)
                return q._replace(campos=q.campos + (q.buf,), buf="", campo=q.campo + 1), a, mov(c1=R)
            if a1 == "$":
                campos = q.campos + (q.buf,)
                if len(campos) != 5:
                    return error(a)
                rot, ani, pos, ref, pb = campos
                try:
                    ConfiguracionEnigma(tuple(rot.split(".")), ani, pos, ref, pb)
                except ValueError:
                    return error(a)
                p = tuple(a_num(c) for c in pos)
                q2 = q._replace(fase="APARCAR", cont=0, clave=(tuple(rot.split(".")), ani, ref, pb),
                                pos_ini=p, pos=p, buf="", campos=(), campo=0)
                return q2, a, mov(c1=L)
            return error(a)

        if f == "APARCAR":                       # retroceder hasta el campo de posiciones
            if a1 == "#":
                if q.cont + 1 == 2:
                    return entrar(q, "DESCIFRAR"), a, mov(c1=L)
                return q._replace(cont=q.cont + 1), a, mov(c1=L)
            return q, a, mov(c1=L)

        # ---------------- Subautómata Enigma: cinta 2 -> cinta 3 ----------------
        if f == "DESCIFRAR":
            if a4 == B:                          # se cubrió toda la ventana de la criba
                return iniciar_reb(q, (1, 2, 3), "COMPARAR", a)
            if a2 == B:                          # mensaje más corto que la criba
                return iniciar_reb(q, (1, 2, 3), "INC", a)
            pos2, e = enigma(q.clave).transicion(q.pos, a2)
            return q._replace(pos=pos2), (a1, a2, e, a4, a5), mov(c2=R, c3=R, c4=R)

        # ---------------- Comparación con la criba ----------------
        if f == "COMPARAR":
            if a4 == B:                          # ¡coincidencia! (parada de la Bombe)
                est["paradas"] += 1
                sig = "COMPLETO" if modo == "primero" else "COPIA"
                q2 = q._replace(fase="EMITIR", pend=texto_config(q.clave, q.pos_ini) + ">",
                                idx=0, sig=sig, hallado=True)
                return q2, a, mov()
            if a4 == "?" or a3 == a4:
                return q, a, mov(c3=R, c4=R)
            return iniciar_reb(q, (2, 3), "INC", a)

        if f == "EMITIR":
            if q.idx < len(q.pend):
                return q._replace(idx=q.idx + 1), (a1, a2, a3, a4, q.pend[q.idx]), mov(c5=R)
            if q.sig == "COMPLETO":
                return iniciar_reb(q, (1, 2), "COMPLETO", a)
            return iniciar_reb(q, (2,), "COPIA", a)

        if f == "COMPLETO":                      # descifrado completo con la clave hallada
            if a2 == B:
                return Estado("q_acepta", clave=q.clave, pos_ini=q.pos_ini, pos=q.pos, hallado=True), a, mov()
            pos2, e = enigma(q.clave).transicion(q.pos, a2)
            return q._replace(pos=pos2), (a1, a2, e, a4, e), mov(c2=R, c3=R, c5=R)

        if f == "COPIA":                         # modo 'todas': registrar descifrado tentativo
            if a3 == B:
                return iniciar_reb(q, (2, 3), "INC", (a1, a2, a3, a4, ";"), {4: R})
            return q, (a1, a2, a3, a4, a3), mov(c3=R, c5=R)

        # ---------------- Odómetro: siguiente configuración ----------------
        if f == "INC":
            if a1 == "#":                        # desbordamiento (ZZZ -> AAA)
                return q._replace(fase="SALTAR"), a, mov(c1=R)
            if a1 in LETRAS:
                p = list(q.pos_ini)
                if a1 != "Z":
                    nuevo = chr(ord(a1) + 1)
                    p[q.i] = a_num(nuevo)
                    q2 = q._replace(pos_ini=tuple(p))
                    escritos = (nuevo, a2, a3, a4, a5)
                    if q.i == 2:
                        return entrar(q2, "DESCIFRAR"), escritos, mov()
                    return q2._replace(fase="VOLVER"), escritos, mov(c1=R)
                p[q.i] = 0
                return q._replace(pos_ini=tuple(p), i=q.i - 1), ("A", a2, a3, a4, a5), mov(c1=L)
            return error(a)

        if f == "VOLVER":
            if a1 == "#":
                return entrar(q, "DESCIFRAR"), a, mov(c1=L)
            return q, a, mov(c1=R)

        if f == "SALTAR":
            if a1 == "$":
                return q._replace(fase="NUEVO_BLOQUE"), a, mov(c1=R)
            if a1 == B:
                return error(a)
            return q, a, mov(c1=R)

        if f == "NUEVO_BLOQUE":
            if a1 == "%" or a1 == B:             # no quedan configuraciones
                final = "q_acepta" if q.hallado else "q_rechaza"
                return Estado(final, hallado=q.hallado), a, mov()
            return entrar(q, "CARGAR"), a, mov()

        return None                              # δ indefinida

    return MaquinaTuringMultinta(
        k=K,
        Q=_ConjuntoQ(),
        Sigma=SIGMA,
        Gamma=GAMMA,
        delta=delta,
        q0=Q0,
        A=lambda q: q.fase == "q_acepta",
        R=lambda q: q.fase in ("q_rechaza", "q_error"),
        nombre=f"M_Bombe[{modo}]",
    )


class _ConjuntoQ:
    """Q = F x Reg descrito por comprensión (finito pero no listado)."""

    def __contains__(self, q) -> bool:
        return isinstance(q, Estado) and q.fase in FASES and len(q.buf) <= MAX_BUFFER

    def __repr__(self) -> str:
        return "Q = F x Reg  (|F| = %d, registros acotados)" % len(FASES)


# ---------------------------------------------------------------------------
# Preparación de la entrada
# ---------------------------------------------------------------------------
def bloques_busqueda(rotores_candidatos: Sequence[Sequence[str]], anillos: str = "AAA",
                     reflectores: Iterable[str] = ("B",), plugboard: str = "",
                     pos_inicio: str = "AAA") -> List[ConfiguracionEnigma]:
    """Un bloque por cada (orden de rotores, reflector). Las posiciones las
    recorre el odómetro de la máquina a partir de pos_inicio."""
    out = []
    for rot in rotores_candidatos:
        for ref in reflectores:
            out.append(ConfiguracionEnigma(tuple(rot), anillos, pos_inicio, ref, plugboard))
    return out


def construir_entrada(bloques: Sequence[ConfiguracionEnigma], cifrado: str, criba: str,
                      desplazamiento: int = 0) -> str:
    """w = BLOQUES % CIFRADO % CRIBA   (criba precedida de '?' si hay desplazamiento)."""
    cif = normalizar_texto(cifrado)
    cri = "?" * desplazamiento + normalizar_texto(criba)
    if not cif:
        raise ValueError("El texto cifrado está vacío")
    if not normalizar_texto(criba):
        raise ValueError("La criba está vacía")
    return "".join(b.a_cinta() for b in bloques) + "%" + cif + "%" + cri


class ResultadoBombe(NamedTuple):
    resultado: Resultado
    aceptada: bool
    estado_final: str
    configuraciones_probadas: int
    paradas: List[Tuple[ConfiguracionEnigma, str]]   # (config, texto descifrado)
    texto_claro: str                                  # cinta 3 al final (modo primero)
    pasos: int


def ejecutar_bombe(bloques: Sequence[ConfiguracionEnigma], cifrado: str, criba: str,
                   desplazamiento: int = 0, modo: str = "primero",
                   max_pasos: Optional[int] = None, observador=None) -> ResultadoBombe:
    est: Dict = {}
    M = construir_bombe(modo, est)
    w = construir_entrada(bloques, cifrado, criba, desplazamiento)
    res = M.ejecutar([w], max_pasos=max_pasos, observador=observador)
    registro = res.contenido(5)
    paradas = []
    for entrada in filter(None, registro.split(";")):
        cfg_txt, _, texto = entrada.partition(">")
        paradas.append((parsear_config(cfg_txt), texto))
    return ResultadoBombe(res, res.aceptada, res.estado_final.fase, est["configuraciones"],
                          paradas, res.contenido(3) if modo == "primero" else "", res.pasos)
