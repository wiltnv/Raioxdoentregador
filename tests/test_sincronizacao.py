import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculos_moto import get_default_data
from sincronizacao import mesclar_estados, salvar_com_versao


def estado_base():
    e = copy.deepcopy(get_default_data())
    e["turnos"] = []
    e["abastecimentos"] = []
    e["manutencoes"] = []
    return e


def turno(data, bruto=100.0):
    return {"data": data, "km": 50.0, "bruto": bruto, "estabelecimento": "Teste",
            "moto_id": "moto_1", "ganho_app": bruto, "ganho_estab": 0.0, "extras": 0.0}


class TestMesclarEstados(unittest.TestCase):
    def test_soma_registros_de_lados_diferentes(self):
        base = estado_base()
        local = copy.deepcopy(base)
        servidor = copy.deepcopy(base)
        local["turnos"].append(turno("2026-11-27"))
        servidor["abastecimentos"].append({"data": "2026-11-27", "litros": 10})
        r = mesclar_estados(base, local, servidor)
        self.assertEqual(len(r["turnos"]), 1)
        self.assertEqual(len(r["abastecimentos"]), 1)

    def test_nao_duplica_registro_igual_nos_dois_lados(self):
        base = estado_base()
        local = copy.deepcopy(base)
        servidor = copy.deepcopy(base)
        t = turno("2026-11-27")
        local["turnos"].append(copy.deepcopy(t))
        servidor["turnos"].append(copy.deepcopy(t))
        r = mesclar_estados(base, local, servidor)
        self.assertEqual(len(r["turnos"]), 1)

    def test_remocao_local_e_respeitada(self):
        base = estado_base()
        t1, t2 = turno("2026-11-25"), turno("2026-11-26")
        base["turnos"] = [t1, t2]
        local = copy.deepcopy(base)
        local["turnos"].remove(t1)
        servidor = copy.deepcopy(base)
        servidor["turnos"].append(turno("2026-11-27"))
        r = mesclar_estados(base, local, servidor)
        datas = [t["data"] for t in r["turnos"]]
        self.assertEqual(sorted(datas), ["2026-11-26", "2026-11-27"])

    def test_campo_simples_alterado_localmente_vence(self):
        base = estado_base()
        local = copy.deepcopy(base)
        servidor = copy.deepcopy(base)
        local["config_empresa"] = {"valor_km_cobrar": 3.0, "taxa_minima": 10.0}
        r = mesclar_estados(base, local, servidor)
        self.assertEqual(r["config_empresa"]["valor_km_cobrar"], 3.0)

    def test_campo_simples_alterado_so_no_servidor_e_mantido(self):
        base = estado_base()
        local = copy.deepcopy(base)
        servidor = copy.deepcopy(base)
        servidor["config_empresa"] = {"valor_km_cobrar": 2.5, "taxa_minima": 9.0}
        r = mesclar_estados(base, local, servidor)
        self.assertEqual(r["config_empresa"]["valor_km_cobrar"], 2.5)

    def test_moto_campo_a_campo(self):
        base = estado_base()
        local = copy.deepcopy(base)
        servidor = copy.deepcopy(base)
        local["motos"][0]["apelido"] = "Minha Bros"
        servidor["motos"][0]["preco_gasolina"] = 6.49
        r = mesclar_estados(base, local, servidor)
        self.assertEqual(r["motos"][0]["apelido"], "Minha Bros")
        self.assertEqual(r["motos"][0]["preco_gasolina"], 6.49)

    def test_hodometro_nunca_volta_para_tras(self):
        base = estado_base()
        base["motos"][0]["hodometro"] = 1000
        local = copy.deepcopy(base)
        servidor = copy.deepcopy(base)
        local["motos"][0]["hodometro"] = 1050
        servidor["motos"][0]["hodometro"] = 1200
        r = mesclar_estados(base, local, servidor)
        self.assertEqual(r["motos"][0]["hodometro"], 1200)

    def test_moto_nova_e_removida(self):
        base = estado_base()
        extra = copy.deepcopy(base["motos"][0])
        extra["id"] = "moto_x"
        base["motos"].append(extra)
        local = copy.deepcopy(base)
        servidor = copy.deepcopy(base)
        nova = copy.deepcopy(base["motos"][0])
        nova["id"] = "moto_nova"
        local["motos"].append(nova)
        local["motos"] = [m for m in local["motos"] if m["id"] != "moto_x"]
        r = mesclar_estados(base, local, servidor)
        ids = sorted(m["id"] for m in r["motos"])
        self.assertEqual(ids, sorted(["moto_1", "moto_nova"]))


class _Res:
    def __init__(self, data):
        self.data = data


class _Tabela:
    def __init__(self, sb):
        self.sb = sb
        self.op = None
        self.filtro = None

    def insert(self, row):
        self.op = ("insert", row)
        return self

    def select(self, cols):
        self.op = ("select",)
        return self

    def eq(self, col, val):
        self.filtro = (col, val)
        return self

    def execute(self):
        if self.sb.falhar:
            raise RuntimeError("falha de rede")
        if self.op[0] == "insert":
            row = self.op[1]
            if row["user_key"] in self.sb.rows:
                raise Exception("duplicate key value violates unique constraint (23505)")
            self.sb.rows[row["user_key"]] = {
                "state_json": copy.deepcopy(row["state_json"]), "version": row["version"]}
            return _Res([row])
        r = self.sb.rows.get(self.filtro[1])
        return _Res([copy.deepcopy(r)] if r else [])


class _Rpc:
    def __init__(self, sb, params):
        self.sb = sb
        self.params = params

    def execute(self):
        if self.sb.falhar:
            raise RuntimeError("falha de rede")
        if self.sb.sempre_conflito:
            return _Res(None)
        r = self.sb.rows.get(self.params["p_key"])
        if r and r["version"] == self.params["p_version"]:
            r["state_json"] = copy.deepcopy(self.params["p_json"])
            r["version"] += 1
            return _Res(r["version"])
        return _Res(None)


class FakeSB:
    def __init__(self):
        self.rows = {}
        self.falhar = False
        self.sempre_conflito = False

    def table(self, nome):
        return _Tabela(self)

    def rpc(self, nome, params):
        return _Rpc(self, params)


class TestSalvarComVersao(unittest.TestCase):
    def test_primeira_gravacao_cria_linha(self):
        sb = FakeSB()
        data = estado_base()
        ok, nova, erro = salvar_com_versao(sb, "u1", data, None, data)
        self.assertTrue(ok)
        self.assertEqual(nova, 1)
        self.assertIn("u1", sb.rows)

    def test_atualizacao_normal_incrementa_versao(self):
        sb = FakeSB()
        data = estado_base()
        salvar_com_versao(sb, "u1", data, None, data)
        base = copy.deepcopy(data)
        data["turnos"].append(turno("2026-11-27"))
        ok, nova, erro = salvar_com_versao(sb, "u1", data, 1, base)
        self.assertTrue(ok)
        self.assertEqual(nova, 2)
        self.assertEqual(len(sb.rows["u1"]["state_json"]["turnos"]), 1)

    def test_conflito_preserva_o_trabalho_dos_dois(self):
        sb = FakeSB()
        inicial = estado_base()
        salvar_com_versao(sb, "empresa_1", inicial, None, inicial)
        # duas sessões leram a versão 1
        a, b = copy.deepcopy(inicial), copy.deepcopy(inicial)
        base_a, base_b = copy.deepcopy(inicial), copy.deepcopy(inicial)
        a["turnos"].append(turno("2026-11-27", 120.0))
        ok_a, ver_a, _ = salvar_com_versao(sb, "empresa_1", a, 1, base_a)
        self.assertTrue(ok_a)
        b["abastecimentos"].append({"data": "2026-11-27", "litros": 8})
        ok_b, ver_b, _ = salvar_com_versao(sb, "empresa_1", b, 1, base_b)
        self.assertTrue(ok_b)
        final = sb.rows["empresa_1"]["state_json"]
        self.assertEqual(len(final["turnos"]), 1)
        self.assertEqual(len(final["abastecimentos"]), 1)
        # a sessão B passou a enxergar o turno da A
        self.assertEqual(len(b["turnos"]), 1)
        self.assertEqual(ver_b, 3)

    def test_insert_duplicado_cai_em_mesclagem(self):
        sb = FakeSB()
        existente = estado_base()
        existente["turnos"].append(turno("2026-11-20"))
        sb.rows["u1"] = {"state_json": existente, "version": 5}
        data = estado_base()
        base = copy.deepcopy(data)
        data["abastecimentos"].append({"data": "2026-11-27", "litros": 5})
        ok, nova, erro = salvar_com_versao(sb, "u1", data, None, base)
        self.assertTrue(ok)
        final = sb.rows["u1"]["state_json"]
        self.assertEqual(len(final["turnos"]), 1)
        self.assertEqual(len(final["abastecimentos"]), 1)

    def test_falha_de_rede_nao_altera_nada(self):
        sb = FakeSB()
        sb.falhar = True
        data = estado_base()
        ok, nova, erro = salvar_com_versao(sb, "u1", data, 1, data)
        self.assertFalse(ok)
        self.assertIn("rede", erro)
        self.assertEqual(sb.rows, {})

    def test_conflito_persistente_desiste_com_mensagem(self):
        sb = FakeSB()
        sb.rows["u1"] = {"state_json": estado_base(), "version": 1}
        sb.sempre_conflito = True
        data = estado_base()
        ok, nova, erro = salvar_com_versao(sb, "u1", data, 1, copy.deepcopy(data))
        self.assertFalse(ok)
        self.assertIn("Recarregue", erro)


if __name__ == "__main__":
    unittest.main()
