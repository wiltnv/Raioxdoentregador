import copy
import os
import sys
import unittest
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import turnos as T


class TestTempo(unittest.TestCase):
    def test_parse_variantes_do_supabase(self):
        for s in ["2026-11-28T14:05:11.123456+00:00", "2026-11-28T14:05:11.12345+00:00",
                  "2026-11-28T14:05:11+00:00", "2026-11-28T14:05:11.1Z", "2026-11-28 14:05:11+00"]:
            dt = T.parse_iso(s)
            self.assertEqual((dt.hour, dt.minute), (14, 5), s)
            self.assertIsNotNone(dt.tzinfo)

    def test_duracao_e_formato(self):
        self.assertEqual(T.duracao_minutos("2026-11-28T10:00:00+00:00", "2026-11-28T12:13:30+00:00"), 133)
        self.assertEqual(T.duracao_minutos("2026-11-28T12:00:00+00:00", "2026-11-28T10:00:00+00:00"), 0)
        self.assertEqual(T.formatar_duracao(133), "2h13")
        self.assertEqual(T.formatar_duracao(45), "45 min")
        self.assertEqual(T.formatar_duracao(120), "2h00")


class TestRegras(unittest.TestCase):
    def test_km_particular(self):
        self.assertEqual(T.km_particular(81420, 81350), 70)
        self.assertEqual(T.km_particular(81350, 81350), 0)
        self.assertEqual(T.km_particular(81000, 81350), 0)
        self.assertEqual(T.km_particular(81420, None), 0)

    def test_validar_inicio(self):
        self.assertIsNone(T.validar_inicio(1000, 1000))
        self.assertIsNone(T.validar_inicio(1050, 1000))
        self.assertIn("menor", T.validar_inicio(900, 1000))
        self.assertIn("gestor", T.validar_inicio(900, 1000, papel="piloto"))
        self.assertIn("Garagem", T.validar_inicio(900, 1000, papel="autonomo"))

    def test_validar_encerramento(self):
        self.assertIsNone(T.validar_encerramento(1000, 1080))
        self.assertIsNotNone(T.validar_encerramento(1000, 1000))
        self.assertIsNotNone(T.validar_encerramento(1000, 900))
        self.assertIn("digitação", T.validar_encerramento(1000, 3000))

    def test_montar_turno(self):
        aberto = {"id": "t1", "moto_id": "moto_1", "hodometro_ini": 81420,
                  "hodometro_anterior": 81350, "inicio": "2026-11-28T01:30:00+00:00"}
        r = T.montar_turno(aberto, 81500, 100.0, 20.0, 5.0, "Pizzaria X", "Zezinho", "z@x.com",
                           0.4123456, "2026-11-28T05:00:00+00:00")
        self.assertEqual(r["km"], 80)
        self.assertEqual(r["bruto"], 120.0)
        self.assertEqual(r["estabelecimento"], "Apps + Pizzaria X")
        self.assertEqual(r["duracao_min"], 210)
        self.assertEqual(r["km_particular_antes"], 70)
        self.assertEqual(r["piloto_email"], "z@x.com")
        self.assertEqual(r["custo_km"], 0.4123)
        # 01:30 UTC = 22:30 do dia anterior em Brasília
        self.assertEqual(r["data"], "2026-11-27")

    def test_origem_so_apps_ou_so_estabelecimento(self):
        aberto = {"moto_id": "m", "hodometro_ini": 10, "inicio": "2026-11-28T15:00:00+00:00"}
        a = T.montar_turno(aberto, 20, 50.0, 0.0, 0.0, "Loja", "n", "e", 0.3, "2026-11-28T16:00:00+00:00")
        b = T.montar_turno(aberto, 20, 0.0, 50.0, 0.0, "Loja", "n", "e", 0.3, "2026-11-28T16:00:00+00:00")
        self.assertEqual(a["estabelecimento"], "iFood / Apps")
        self.assertEqual(b["estabelecimento"], "Loja")


class _Res:
    def __init__(self, data):
        self.data = data


class _Q:
    def __init__(self, sb, nome):
        self.sb, self.nome = sb, nome
        self.op, self.payload, self.filtros = None, None, []

    def select(self, cols):
        self.op = "select"
        return self

    def insert(self, row):
        self.op, self.payload = "insert", row
        return self

    def update(self, vals):
        self.op, self.payload = "update", vals
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, c, v):
        self.filtros.append((c, "eq", v))
        return self

    def is_(self, c, v):
        self.filtros.append((c, "is", v))
        return self

    def _casa(self, row):
        for c, tipo, v in self.filtros:
            if tipo == "eq" and row.get(c) != v:
                return False
            if tipo == "is" and v == "null" and row.get(c) is not None:
                return False
        return True

    def execute(self):
        if self.sb.falhar:
            raise RuntimeError("falha de rede")
        rows = self.sb.rows
        if self.op == "insert":
            novo = dict(self.payload)
            novo.setdefault("id", str(uuid.uuid4()))
            novo.setdefault("inicio", datetime.now(timezone.utc).isoformat())
            novo.setdefault("encerrado_em", None)
            for r in rows:  # índice único parcial: um turno aberto por perfil
                if r["profile_id"] == novo["profile_id"] and r["encerrado_em"] is None:
                    raise Exception("duplicate key value violates unique constraint (23505)")
            rows.append(novo)
            return _Res([copy.deepcopy(novo)])
        alvo = [r for r in rows if self._casa(r)]
        if self.op == "select":
            return _Res(copy.deepcopy(alvo))
        if self.op == "update":
            for r in alvo:
                r.update(self.payload)
            return _Res(copy.deepcopy(alvo))
        if self.op == "delete":
            for r in alvo:
                rows.remove(r)
            return _Res(copy.deepcopy(alvo))


class FakeSB:
    def __init__(self):
        self.rows, self.falhar = [], False

    def table(self, nome):
        return _Q(self, nome)


class TestBanco(unittest.TestCase):
    def setUp(self):
        self.sb = FakeSB()

    def _iniciar(self, pid="p1", key="empresa_1"):
        return T.iniciar_turno(self.sb, pid, key, "moto_1", 81420, 81350, "Zezinho")

    def test_inicia_e_busca(self):
        linha, erro = self._iniciar()
        self.assertIsNone(erro)
        self.assertEqual(linha["hodometro_ini"], 81420)
        aberto, ok = T.buscar_turno_aberto(self.sb, "p1")
        self.assertTrue(ok)
        self.assertEqual(aberto["hodometro_anterior"], 81350)

    def test_nao_inicia_dois_turnos_para_o_mesmo_perfil(self):
        self._iniciar()
        linha, erro = self._iniciar()
        self.assertIsNone(linha)
        self.assertIn("já tem um turno aberto", erro)

    def test_sem_turno_aberto(self):
        aberto, ok = T.buscar_turno_aberto(self.sb, "p1")
        self.assertTrue(ok)
        self.assertIsNone(aberto)

    def test_fechar_so_funciona_uma_vez(self):
        linha, _ = self._iniciar()
        agora = datetime.now(timezone.utc)
        self.assertTrue(T.fechar_turno_aberto(self.sb, linha["id"], agora))
        self.assertFalse(T.fechar_turno_aberto(self.sb, linha["id"], agora))
        aberto, _ = T.buscar_turno_aberto(self.sb, "p1")
        self.assertIsNone(aberto)

    def test_reabrir_depois_de_falha_ao_salvar(self):
        linha, _ = self._iniciar()
        T.fechar_turno_aberto(self.sb, linha["id"], datetime.now(timezone.utc))
        self.assertTrue(T.reabrir_turno(self.sb, linha["id"]))
        aberto, _ = T.buscar_turno_aberto(self.sb, "p1")
        self.assertIsNotNone(aberto)

    def test_pode_iniciar_outro_depois_de_encerrar(self):
        linha, _ = self._iniciar()
        T.fechar_turno_aberto(self.sb, linha["id"], datetime.now(timezone.utc))
        nova, erro = self._iniciar()
        self.assertIsNone(erro)

    def test_cancelar_remove_turno_aberto(self):
        linha, _ = self._iniciar()
        self.assertTrue(T.cancelar_turno(self.sb, linha["id"]))
        self.assertEqual(self.sb.rows, [])

    def test_lista_turnos_abertos_da_empresa(self):
        self._iniciar("p1", "empresa_1")
        self._iniciar("p2", "empresa_1")
        self._iniciar("p3", "empresa_2")
        self.assertEqual(len(T.listar_turnos_abertos(self.sb, "empresa_1")), 2)

    def test_falha_de_rede_nao_quebra(self):
        self.sb.falhar = True
        aberto, ok = T.buscar_turno_aberto(self.sb, "p1")
        self.assertFalse(ok)
        linha, erro = self._iniciar()
        self.assertIsNone(linha)
        self.assertIn("rede", erro)
        self.assertFalse(T.fechar_turno_aberto(self.sb, "x", datetime.now(timezone.utc)))
        self.assertEqual(T.listar_turnos_abertos(self.sb, "empresa_1"), [])


if __name__ == "__main__":
    unittest.main()
