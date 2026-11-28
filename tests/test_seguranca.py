import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import seguranca as S


class TestPin(unittest.TestCase):
    def test_formato(self):
        for ok in ("1234", "123456", " 4321 "):
            self.assertTrue(S.pin_formato_valido(ok), ok)
        for ruim in ("", "123", "1234567", "12a4", "12 34", None):
            self.assertFalse(S.pin_formato_valido(ruim), ruim)

    def test_hash_e_verificacao(self):
        h = S.hash_pin("Zezinho@x.com", "1234")
        self.assertTrue(h.startswith("pbkdf2$"))
        self.assertEqual(S.verificar_pin(h, "zezinho@x.com", "1234"), (True, False))
        self.assertEqual(S.verificar_pin(h, "zezinho@x.com", "9999"), (False, False))
        self.assertEqual(S.verificar_pin(h, "outro@x.com", "1234"), (False, False))

    def test_sal_aleatorio_por_hash(self):
        self.assertNotEqual(S.hash_pin("a@a.com", "1234"), S.hash_pin("a@a.com", "1234"))

    def test_hash_antigo_entra_e_pede_atualizacao(self):
        antigo = S._hash_legado("velho@x.com", "4321")
        self.assertEqual(S.verificar_pin(antigo, "velho@x.com", "4321"), (True, True))
        self.assertEqual(S.verificar_pin(antigo, "velho@x.com", "0000"), (False, False))

    def test_pepper(self):
        h = S.hash_pin("a@a.com", "1234", pepper="segredo-longo")
        self.assertTrue(h.startswith("pbkdf2p$"))
        self.assertEqual(S.verificar_pin(h, "a@a.com", "1234", "segredo-longo"), (True, False))
        self.assertEqual(S.verificar_pin(h, "a@a.com", "1234", "outro"), (False, False))
        self.assertEqual(S.verificar_pin(h, "a@a.com", "1234", ""), (False, False))

    def test_hash_sem_pepper_pede_atualizacao_quando_pepper_ligado(self):
        h = S.hash_pin("a@a.com", "1234")
        self.assertEqual(S.verificar_pin(h, "a@a.com", "1234", "segredo"), (True, True))

    def test_hash_corrompido_nao_quebra(self):
        self.assertEqual(S.verificar_pin("pbkdf2$abc", "a@a.com", "1234"), (False, False))
        self.assertEqual(S.verificar_pin(None, "a@a.com", "1234"), (False, False))
        self.assertEqual(S.verificar_pin("", "a@a.com", "1234"), (False, False))


class TestBloqueio(unittest.TestCase):
    AGORA = datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc)

    def test_sem_bloqueio_ate_o_quinto_erro(self):
        tent = 0
        for _ in range(4):
            tent, bloq = S.proximo_estado_falha(tent, self.AGORA)
            self.assertIsNone(bloq)
        self.assertEqual(tent, 4)

    def test_progressao_das_esperas(self):
        casos = {5: timedelta(minutes=15), 9: timedelta(minutes=15),
                 10: timedelta(hours=1), 14: timedelta(hours=1),
                 15: timedelta(hours=24), 40: timedelta(hours=24)}
        for tentativa, espera in casos.items():
            tent, bloq = S.proximo_estado_falha(tentativa - 1, self.AGORA)
            self.assertEqual(tent, tentativa)
            self.assertEqual(bloq, self.AGORA + espera, tentativa)

    def test_none_conta_como_zero(self):
        self.assertEqual(S.proximo_estado_falha(None, self.AGORA), (1, None))

    def test_minutos_restantes_arredonda_para_cima(self):
        self.assertEqual(S.minutos_restantes(self.AGORA + timedelta(seconds=61), self.AGORA), 2)
        self.assertEqual(S.minutos_restantes(self.AGORA + timedelta(minutes=15), self.AGORA), 15)
        self.assertEqual(S.minutos_restantes(self.AGORA + timedelta(seconds=1), self.AGORA), 1)


if __name__ == "__main__":
    unittest.main()
