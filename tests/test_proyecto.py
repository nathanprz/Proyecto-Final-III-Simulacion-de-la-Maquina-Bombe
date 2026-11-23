"""
Pruebas del proyecto (solo biblioteca estándar):
    python -m unittest discover -s tests -v
"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bombe_mtm import (GAMMA, SIGMA, bloques_busqueda, construir_bombe, construir_entrada,
                       ejecutar_bombe)
from cyberchef import URL_EJEMPLO, leer_url
from enigma_modelo import (ALFABETO, CATALOGO_REFLECTORES, CATALOGO_ROTORES, ConfiguracionEnigma,
                           Enigma, MaquinaEnigma, Plugboard, Reflector, a_letra, a_num, cifrar,
                           es_involucion, normalizar_texto, permutacion, puntos_fijos)
from mtm import BLANCO, Cinta, ejemplo_ww

CIFRADO_CC = "XTSYNWAEUGEZALYNRQIMAMLZXMFUODAWXLYLZCUZQOQBQJLCPKNDDRWF"
CLARO_CC = "HELLOCYBERCHEFUSERSTHISISATESTMESSAGEFORTHEDOCUMENTATION"
CFG_CC = ConfiguracionEnigma(("III", "II", "IV"), "KNG", "OPM", "B", "AH CO DE GZ IJ KM LQ NY PS TW")


class TestEnigma(unittest.TestCase):
    def test_vector_cyberchef(self):
        self.assertEqual(cifrar(CFG_CC, CIFRADO_CC), CLARO_CC)
        self.assertEqual(cifrar(CFG_CC, CLARO_CC), CIFRADO_CC)

    def test_vector_clasico(self):
        # I-II-III, anillos AAA, posiciones AAA, UKW-B, sin plugboard: AAAAA -> BDZGO
        cfg = ConfiguracionEnigma(("I", "II", "III"))
        self.assertEqual(cifrar(cfg, "AAAAA"), "BDZGO")

    def test_doble_paso(self):
        e = Enigma(ConfiguracionEnigma(("I", "II", "III"), posiciones="ADU"))
        ventanas = []
        for _ in range(3):
            e.procesar("A")
            ventanas.append(e.ventana)
        self.assertEqual(ventanas, ["ADV", "AEW", "BFX"])

    def test_reciprocidad_aleatoria(self):
        rnd = random.Random(7)
        for _ in range(50):
            rot = tuple(rnd.sample(list(CATALOGO_ROTORES), 3))
            letras = rnd.sample(ALFABETO, 20)
            cfg = ConfiguracionEnigma(rot, "".join(rnd.choices(ALFABETO, k=3)),
                                      "".join(rnd.choices(ALFABETO, k=3)), rnd.choice("BC"),
                                      " ".join(letras[i] + letras[i + 1] for i in range(0, 20, 2)))
            texto = "".join(rnd.choices(ALFABETO, k=200))
            self.assertEqual(cifrar(cfg, cifrar(cfg, texto)), texto)

    def test_reflector_involutivo_sin_puntos_fijos(self):
        for nombre in CATALOGO_REFLECTORES:
            r = Reflector.del_catalogo(nombre)
            self.assertTrue(es_involucion(r.mapa))
            self.assertEqual(puntos_fijos(r.mapa), [])

    def test_plugboard_permutacion_parcial(self):
        p = Plugboard.desde_texto("AB CD")
        self.assertTrue(es_involucion(p.mapa))
        self.assertEqual(p(a_num("A")), a_num("B"))
        self.assertEqual(p(a_num("Z")), a_num("Z"))           # sin cable: identidad
        with self.assertRaises(ValueError):
            Plugboard.desde_texto("AB AC")                       # letra repetida

    def test_permutacion_global_involutiva(self):
        m = MaquinaEnigma.desde_config(CFG_CC)
        for s in [(0, 0, 0), (14, 15, 12), (25, 4, 21)]:
            E = m.permutacion_en(s)
            self.assertTrue(es_involucion(E))
            self.assertEqual(puntos_fijos(E), [])             # ninguna letra se cifra en sí misma

    def test_estado_cambia_tras_cada_simbolo(self):
        m = MaquinaEnigma.desde_config(CFG_CC)
        s = (14, 15, 12)
        s2, _ = m.transicion(s, "A")
        self.assertNotEqual(s, s2)


class TestMTM(unittest.TestCase):
    def test_cinta_biinfinita(self):
        c = Cinta("AB")
        c.mover("L")
        self.assertEqual(c.leer(), BLANCO)
        c.escribir("X")
        self.assertEqual(c.contenido(), "XAB")

    def test_ejemplo_ww(self):
        M = ejemplo_ww()
        self.assertTrue(M.ejecutar(["ab#ab"]).aceptada)
        self.assertTrue(M.ejecutar(["#"]).aceptada)
        self.assertFalse(M.ejecutar(["ab#ba"]).aceptada)
        self.assertFalse(M.ejecutar(["ab#abb"]).aceptada)

    def test_alfabetos(self):
        self.assertTrue(SIGMA < GAMMA)
        self.assertIn(BLANCO, GAMMA)
        self.assertNotIn(BLANCO, SIGMA)


def bombe_directa(bloques, cifrado, criba, desplazamiento=0):
    """Oráculo: misma búsqueda pero sin Máquina de Turing (para validar la MTM)."""
    paradas = []
    patron = "?" * desplazamiento + criba
    for b in bloques:
        m = MaquinaEnigma.desde_config(b)
        inicio = a_num(b.posiciones[0]) * 676 + a_num(b.posiciones[1]) * 26 + a_num(b.posiciones[2])
        for n in range(inicio, 26 ** 3):
            pos = (n // 676, n // 26 % 26, n % 26)
            _, texto = m.procesar(pos, cifrado[:len(patron)])
            if len(texto) == len(patron) and all(p in ("?", t) for p, t in zip(patron, texto)):
                paradas.append(b.con_posiciones("".join(a_letra(x) for x in pos)))
    return paradas


class TestBombe(unittest.TestCase):
    def setUp(self):
        self.bloques = bloques_busqueda([CFG_CC.rotores], CFG_CC.anillos, ["B"], CFG_CC.plugboard)

    def test_encuentra_clave_cyberchef(self):
        r = ejecutar_bombe(self.bloques, CIFRADO_CC, "HELLOCYBERCHEF")
        self.assertTrue(r.aceptada)
        self.assertEqual(r.paradas[0][0].posiciones, "OPM")
        self.assertEqual(r.texto_claro, CLARO_CC)
        self.assertEqual(r.resultado.contenido(3), CLARO_CC)
        self.assertEqual(r.configuraciones_probadas, 14 * 676 + 15 * 26 + 12 + 1)

    def test_criba_con_desplazamiento(self):
        r = ejecutar_bombe(self.bloques, CIFRADO_CC, "TESTMESSAGE", desplazamiento=26)
        self.assertTrue(r.aceptada)
        self.assertEqual(r.paradas[0][0].posiciones, "OPM")

    def test_rechazo(self):
        r = ejecutar_bombe(self.bloques, CIFRADO_CC, "XXXXXXXXXXXX")   # imposible: 'X' no cifra a 'X'
        self.assertFalse(r.aceptada)
        self.assertEqual(r.estado_final, "q_rechaza")
        self.assertEqual(r.configuraciones_probadas, 26 ** 3)

    def test_varios_bloques_orden_desconocido(self):
        bloques = bloques_busqueda([("II", "III", "IV"), ("III", "II", "IV")], CFG_CC.anillos,
                                   ["B"], CFG_CC.plugboard)
        r = ejecutar_bombe(bloques, CIFRADO_CC, "HELLOCYBERCHEF")
        self.assertTrue(r.aceptada)
        self.assertEqual(r.paradas[0][0].rotores, ("III", "II", "IV"))

    def test_modo_todas_coincide_con_oraculo(self):
        rnd = random.Random(3)
        for _ in range(2):
            rot = tuple(rnd.sample(["I", "II", "III", "IV", "V"], 3))
            clave = ConfiguracionEnigma(rot, "".join(rnd.choices(ALFABETO, k=3)),
                                        "".join(rnd.choices(ALFABETO, k=3)), "B", "AZ BY CX")
            claro = "ATAQUEALAMANECERENELSECTORNORTE"
            cif = cifrar(clave, claro)
            bloques = bloques_busqueda([rot], clave.anillos, ["B"], clave.plugboard)
            r = ejecutar_bombe(bloques, cif, "ATAQ", modo="todas")      # criba corta: habrá paradas falsas
            esperadas = bombe_directa(bloques, cif, "ATAQ")
            self.assertEqual([c for c, _ in r.paradas], esperadas)
            self.assertIn(clave.posiciones, [c.posiciones for c, _ in r.paradas])

    def test_entrada_mal_formada(self):
        M = construir_bombe()
        r = M.ejecutar(["III.II#AAA#AAA#B#$%ABC%A"])      # solo dos rotores
        self.assertEqual(r.estado_final.fase, "q_error")
        self.assertFalse(r.aceptada)

    def test_delta_respeta_gamma(self):
        # la propia MTM valida en cada paso que δ solo escribe símbolos de Γ
        M = construir_bombe()
        w = construir_entrada(self.bloques, CIFRADO_CC, "HELLO")
        self.assertTrue(M.ejecutar([w]).aceptada)


class TestCyberChef(unittest.TestCase):
    def test_leer_url(self):
        cfg, entrada = leer_url(URL_EJEMPLO)
        self.assertEqual(cfg.rotores, ("III", "II", "IV"))
        self.assertEqual((cfg.anillos, cfg.posiciones, cfg.reflector), ("KNG", "OPM", "B"))
        self.assertEqual(normalizar_texto(entrada), CIFRADO_CC)


if __name__ == "__main__":
    unittest.main()
