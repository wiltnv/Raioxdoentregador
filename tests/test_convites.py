import copy
import os
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import convites as C

AGORA = datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc)


class _Res:
    def __init__(self, data):
        self.data = data


class _Q:
    def __init__(self, sb):
        self.sb, self.op, self.payload, self.filtros = sb, None, None, []

    def select(self, cols):
        self.op = "select"
        return self

    def insert(self, row):
        self.op, self.payload = "insert", row
        return self

    def update(self, vals):
        self.op, self.payload = "update", vals
        return self

    def eq(self, c, v):
        self.filtros.append((c, v))
        return self

    def execute(self):
        sb = self.sb
        if self.op == "insert":
            if any(r["codigo"] == self.payload["codigo"] for r in sb.rows):
                raise Exception("duplicate key value violates unique constraint (23505)")
            novo = {"id": str(uuid.uuid4()), "criado_em": sb.proximo_criado_em(),
                    "usos": 0, "usos_max": 1, "revogado": False}
            novo.update(self.payload)
            sb.rows.append(novo)
            return _Res([copy.deepcopy(novo)])
        if self.op == "update" and sb.antes_do_update:
            sb.antes_do_update(sb)
            sb.antes_do_update = None
        alvo = [r for r in sb.rows if all(r.get(c) == v for c, v in self.filtros)]
        if self.op == "update":
            for r in alvo:
                r.update(self.payload)
        return _Res(copy.deepcopy(alvo))


class FakeSB:
    def __init__(self):
        self.rows = []
        self.antes_do_update = None
        self._n = 0

    def proximo_criado_em(self):
        self._n += 1
        return f"2026-11-28T12:00:{self._n:02d}+00:00"

    def table(self, nome):
        assert nome == "convites"
        return _Q(self)


def convite_pronto(sb, dias=7, usos_max=1, empresa="emp1"):
    linha, erro = C.criar_convite(sb, empresa, "gestor1", dias, usos_max)
    assert erro is None
    return linha


class TestCodigo(unittest.TestCase):
    def test_formato_e_alfabeto(self):
        for _ in range(200):
            c = C.gerar_codigo()
            self.assertRegex(c, r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")
            for ruim in "IO01":
                self.assertNotIn(ruim, c)

    def test_codigos_diferentes(self):
        self.assertEqual(len({C.gerar_codigo() for _ in range(500)}), 500)

    def test_normalizar(self):
        self.assertEqual(C.normalizar_codigo("k7qm 4xpd"), "K7QM-4XPD")
        self.assertEqual(C.normalizar_codigo("k7qm4xpd"), "K7QM-4XPD")
        self.assertEqual(C.normalizar_codigo(" K7QM-4XPD "), "K7QM-4XPD")
        self.assertEqual(C.normalizar_codigo(""), "")
        self.assertEqual(C.normalizar_codigo(None), "")


class TestValidade(unittest.TestCase):
    def base(self, **kw):
        c = {"expira_em": (AGORA + timedelta(days=1)).isoformat(), "usos": 0, "usos_max": 1, "revogado": False}
        c.update(kw)
        return c

    def test_valido(self):
        self.assertEqual(C.convite_valido(self.base(), AGORA), (True, None))

    def test_revogado_expirado_esgotado(self):
        self.assertIn("revogado", C.convite_valido(self.base(revogado=True), AGORA)[1])
        self.assertIn("expirado", C.convite_valido(self.base(expira_em=(AGORA - timedelta(seconds=1)).isoformat()), AGORA)[1])
        self.assertIn("utilizado", C.convite_valido(self.base(usos=1), AGORA)[1])

    def test_mensagens_comecam_com_convite(self):
        # a tela conta tentativas inválidas pelo prefixo da mensagem
        for kw in ({"revogado": True}, {"usos": 1}):
            self.assertTrue(C.convite_valido(self.base(**kw), AGORA)[1].startswith("Convite"))


class TestBanco(unittest.TestCase):
    def setUp(self):
        self.sb = FakeSB()

    def test_criar_define_validade(self):
        linha = convite_pronto(self.sb, dias=7, usos_max=5)
        exp = C.parse_iso(linha["expira_em"])
        delta = exp - C.agora_utc()
        self.assertTrue(timedelta(days=6, hours=23) < delta <= timedelta(days=7))
        self.assertEqual(linha["usos_max"], 5)

    def test_usar_uma_vez(self):
        c = convite_pronto(self.sb)
        linha, erro = C.consumir_convite(self.sb, c["codigo"].lower())
        self.assertIsNone(erro)
        self.assertEqual(linha["usos"], 1)
        linha2, erro2 = C.consumir_convite(self.sb, c["codigo"])
        self.assertIsNone(linha2)
        self.assertIn("utilizado", erro2)

    def test_varios_usos(self):
        c = convite_pronto(self.sb, usos_max=2)
        self.assertIsNone(C.consumir_convite(self.sb, c["codigo"])[1])
        self.assertIsNone(C.consumir_convite(self.sb, c["codigo"])[1])
        self.assertIn("utilizado", C.consumir_convite(self.sb, c["codigo"])[1])

    def test_codigo_inexistente_e_vazio(self):
        self.assertIn("inválido", C.consumir_convite(self.sb, "ZZZZ-ZZZZ")[1])
        self.assertIn("Informe", C.consumir_convite(self.sb, "  ")[1])

    def test_expirado_e_revogado(self):
        c = convite_pronto(self.sb)
        futuro = C.agora_utc() + timedelta(days=8)
        self.assertIn("expirado", C.consumir_convite(self.sb, c["codigo"], agora=futuro)[1])
        self.assertTrue(C.revogar_convite(self.sb, c["id"], "emp1"))
        self.assertIn("revogado", C.consumir_convite(self.sb, c["codigo"])[1])

    def test_revogar_so_da_propria_empresa(self):
        c = convite_pronto(self.sb, empresa="emp1")
        self.assertFalse(C.revogar_convite(self.sb, c["id"], "emp2"))
        self.assertIsNone(C.consumir_convite(self.sb, c["codigo"])[1])

    def test_corrida_entre_duas_pessoas_so_uma_passa(self):
        c = convite_pronto(self.sb, usos_max=1)

        def outra_pessoa_usa_primeiro(sb):
            for r in sb.rows:
                r["usos"] += 1

        self.sb.antes_do_update = outra_pessoa_usa_primeiro
        linha, erro = C.consumir_convite(self.sb, c["codigo"])
        self.assertIsNone(linha)
        self.assertIn("utilizado", erro)
        self.assertEqual(self.sb.rows[0]["usos"], 1)

    def test_devolver_uso(self):
        c = convite_pronto(self.sb)
        C.consumir_convite(self.sb, c["codigo"])
        self.assertTrue(C.devolver_uso(self.sb, c["id"]))
        self.assertEqual(self.sb.rows[0]["usos"], 0)
        self.assertFalse(C.devolver_uso(self.sb, c["id"]))  # nunca abaixo de zero
        self.assertIsNone(C.consumir_convite(self.sb, c["codigo"])[1])

    def test_listar_do_mais_novo_para_o_mais_antigo(self):
        a = convite_pronto(self.sb)
        b = convite_pronto(self.sb)
        convite_pronto(self.sb, empresa="emp2")
        lista = C.listar_convites(self.sb, "emp1")
        self.assertEqual([x["id"] for x in lista], [b["id"], a["id"]])


if __name__ == "__main__":
    unittest.main()
