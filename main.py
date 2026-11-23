#!/usr/bin/env python3
"""
main.py — Interfaz de línea de comandos del proyecto
"Máquina de Turing Multicinta que simula la Bombe (con Enigma integrada)".

Ejemplos:
    python main.py demo                       # ejemplo de CyberChef: la Bombe recupera OPM
    python main.py demo --traza 60 --desde 190 # muestra 60 pasos de la MTM desde el paso 190
    python main.py demo --criba TESTMESSAGE --desplazamiento 26
    python main.py demo --orden-desconocido   # también busca el orden de los rotores
    python main.py cifrar "HOLA MUNDO" --rotores I II III --posiciones ABC
    python main.py bombe --cifrado "..." --criba "WETTER" --rotores I II III
    python main.py cyberchef "<url de CyberChef>"
    python main.py ejemplo-mtm "ab#ab"
"""

from __future__ import annotations

import argparse
import sys
import time

from bombe_mtm import (DESCRIPCION_FASES, GAMMA, K, SIGMA, bloques_busqueda, construir_entrada,
                       ejecutar_bombe)
from cyberchef import URL_EJEMPLO, leer_url
from enigma_modelo import (CATALOGO_ROTORES, ConfiguracionEnigma, agrupar5, cifrar, normalizar_texto,
                           ordenes_de_rotores)
from mtm import BLANCO, ejemplo_ww

NOMBRES_CINTAS = {
    1: "Cinta 1 · configuraciones",
    2: "Cinta 2 · texto cifrado",
    3: "Cinta 3 · descifrado",
    4: "Cinta 4 · criba",
    5: "Cinta 5 · registro",
}


def recortar(s: str, n: int = 70) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


def observador_traza(limite: int, desde: int = 0):
    def obs(paso, q, cintas, t):
        if (paso < desde or paso >= desde + limite) and t is not None:
            return
        print(f"\npaso {paso:>5}  estado = {q}   ({DESCRIPCION_FASES.get(q.fase, '')})")
        for i, c in enumerate(cintas, 1):
            print(f"   C{i}: {c.ventana(14)}")
        if t is not None:
            q2, esc, movs = t
            print(f"   δ -> {q2.fase}, escribe {''.join(esc)}, mueve {''.join(movs)}")
        if paso == desde + limite - 1:
            print("\n   ... (traza truncada; la ejecución continúa) ...")
    return obs


def mostrar_cintas(res) -> None:
    print("\nCintas al detenerse la máquina:")
    for i in range(1, K + 1):
        print(f"  {NOMBRES_CINTAS[i]:<28} {recortar(res.resultado.contenido(i)) or BLANCO}")


def mostrar_resultado(r, segundos: float, esperado: ConfiguracionEnigma | None = None) -> None:
    print("\n" + "=" * 78)
    estado = "ACEPTA" if r.aceptada else "RECHAZA"
    print(f" Estado final: {r.estado_final}  =>  la MTM {estado}")
    print(f" Configuraciones probadas: {r.configuraciones_probadas:,}   "
          f"Pasos de la MTM: {r.pasos:,}   Tiempo: {segundos:.2f} s")
    print("=" * 78)
    for n, (cfg, texto) in enumerate(r.paradas, 1):
        print(f" Parada {n}: {cfg.texto()}")
        print(f"   Texto: {agrupar5(texto)}")
        if esperado is not None:
            ok = (cfg.rotores, cfg.posiciones, cfg.reflector) == (esperado.rotores, esperado.posiciones, esperado.reflector)
            print(f"   ¿Coincide con la clave real? {'SÍ' if ok else 'no (parada falsa)'}")
    mostrar_cintas(r)


def ejecutar_escenario(cifrado, criba, bloques, desplazamiento, modo, traza, esperado=None, desde=0):
    total = len(bloques) * 26 ** 3
    print(f"\nEspacio de búsqueda: {len(bloques)} bloque(s) x 26³ posiciones = {total:,} configuraciones")
    print(f"Criba (cinta 4): {'?' * desplazamiento + normalizar_texto(criba)}")
    w = construir_entrada(bloques, cifrado, criba, desplazamiento)
    print(f"Entrada w en la cinta 1 ({len(w)} símbolos): {recortar(w, 90)}")
    obs = observador_traza(traza, desde) if traza else None
    t0 = time.time()
    r = ejecutar_bombe(bloques, cifrado, criba, desplazamiento, modo, observador=obs)
    mostrar_resultado(r, time.time() - t0, esperado)
    return r


# ---------------------------------------------------------------------------
def cmd_demo(a):
    cfg, entrada = leer_url(a.url or URL_EJEMPLO)
    cifrado = normalizar_texto(entrada)
    print("Escenario tomado de CyberChef")
    print(f"  Clave real (oculta para la Bombe): {cfg.texto()}")
    print(f"  Mensaje interceptado: {agrupar5(cifrado)}")
    print(f"  Descifrado de control con la clave real: {agrupar5(cifrar(cfg, cifrado))}")
    print("\nSupuesto de criptoanálisis: se conocen anillos, reflector y plugboard;"
          "\nse desconocen las posiciones iniciales de los rotores"
          + (" y su orden." if a.orden_desconocido else "."))
    if a.orden_desconocido:
        catalogo = list(CATALOGO_ROTORES)
        candidatos = sorted(a.candidatos or cfg.rotores, key=catalogo.index)
        ordenes = ordenes_de_rotores(candidatos)
    else:
        ordenes = [cfg.rotores]
    bloques = bloques_busqueda(ordenes, cfg.anillos, [cfg.reflector], cfg.plugboard, "AAA")
    ejecutar_escenario(cifrado, a.criba, bloques, a.desplazamiento, a.modo, a.traza, cfg, a.desde)


def cmd_cifrar(a):
    cfg = ConfiguracionEnigma(tuple(a.rotores), a.anillos, a.posiciones, a.reflector, a.plugboard)
    print(cfg.texto())
    print(agrupar5(cifrar(cfg, a.texto)))


def cmd_bombe(a):
    ordenes = ordenes_de_rotores(a.candidatos) if a.candidatos else [tuple(a.rotores)]
    bloques = bloques_busqueda(ordenes, a.anillos, a.reflectores, a.plugboard, a.inicio)
    ejecutar_escenario(a.cifrado, a.criba, bloques, a.desplazamiento, a.modo, a.traza, desde=a.desde)


def cmd_cyberchef(a):
    cfg, entrada = leer_url(a.url)
    print(cfg.texto())
    print("Entrada :", agrupar5(normalizar_texto(entrada)))
    print("Salida  :", agrupar5(cifrar(cfg, entrada)))


def cmd_ejemplo_mtm(a):
    M = ejemplo_ww()
    for w in a.palabras or ["ab#ab", "abba#abba", "ab#ba"]:
        r = M.ejecutar([w])
        print(f"{M.nombre} sobre '{w}': {'ACEPTA' if r.aceptada else 'RECHAZA'} en {r.pasos} pasos")


def cmd_definicion(a):
    print("M_Bombe = (Q, Σ, Γ, δ, q0, A, R),  k = 5")
    print("Σ =", "{" + ", ".join(sorted(SIGMA)) + "}")
    print("Γ =", "{" + ", ".join(sorted(GAMMA)) + "}")
    print("q0 = DIST    A = {q_acepta}    R = {q_rechaza, q_error}")
    print("F (fases del control finito):")
    for f, d in DESCRIPCION_FASES.items():
        print(f"   {f:<13} {d}")


def main(argv=None):
    p = argparse.ArgumentParser(description="MTM-Bombe con subautómata Enigma")
    sub = p.add_subparsers(dest="cmd", required=True)

    def opciones_busqueda(sp, criba_defecto=None):
        sp.add_argument("--criba", default=criba_defecto, required=criba_defecto is None,
                        help="palabra o patrón esperado en el texto claro")
        sp.add_argument("--desplazamiento", type=int, default=0,
                        help="posición de la criba dentro del mensaje (se codifica con '?')")
        sp.add_argument("--modo", choices=["primero", "todas"], default="primero",
                        help="'primero': acepta en la primera coincidencia; 'todas': registra todas las paradas")
        sp.add_argument("--traza", type=int, default=0, metavar="N",
                        help="muestra las cinco cintas durante N pasos")
        sp.add_argument("--desde", type=int, default=0, metavar="P",
                        help="paso a partir del cual se muestra la traza (por defecto 0)")

    d = sub.add_parser("demo", help="ejemplo de CyberChef")
    d.add_argument("--url", help="otra URL de CyberChef (por defecto, la del enunciado)")
    d.add_argument("--orden-desconocido", action="store_true",
                   help="buscar también el orden de los rotores")
    d.add_argument("--candidatos", nargs="+", help="rotores candidatos para --orden-desconocido")
    opciones_busqueda(d, "HELLOCYBERCHEF")
    d.set_defaults(f=cmd_demo)

    c = sub.add_parser("cifrar", help="cifrar/descifrar con la Enigma")
    c.add_argument("texto")
    c.add_argument("--rotores", nargs=3, default=["I", "II", "III"])
    c.add_argument("--anillos", default="AAA")
    c.add_argument("--posiciones", default="AAA")
    c.add_argument("--reflector", default="B")
    c.add_argument("--plugboard", default="")
    c.set_defaults(f=cmd_cifrar)

    b = sub.add_parser("bombe", help="búsqueda de clave con la MTM")
    b.add_argument("--cifrado", required=True)
    b.add_argument("--rotores", nargs=3, default=["I", "II", "III"])
    b.add_argument("--candidatos", nargs="+", help="probar todas las ordenaciones de estos rotores")
    b.add_argument("--anillos", default="AAA")
    b.add_argument("--reflectores", nargs="+", default=["B"])
    b.add_argument("--plugboard", default="")
    b.add_argument("--inicio", default="AAA", help="posición inicial del odómetro")
    opciones_busqueda(b)
    b.set_defaults(f=cmd_bombe)

    cc = sub.add_parser("cyberchef", help="leer una receta Enigma de CyberChef")
    cc.add_argument("url", nargs="?", default=URL_EJEMPLO)
    cc.set_defaults(f=cmd_cyberchef)

    e = sub.add_parser("ejemplo-mtm", help="MTM de 2 cintas para {w#w} con tabla δ explícita")
    e.add_argument("palabras", nargs="*")
    e.set_defaults(f=cmd_ejemplo_mtm)

    df = sub.add_parser("definicion", help="muestra la 7-tupla de la MTM-Bombe")
    df.set_defaults(f=cmd_definicion)

    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    sys.exit(main())
