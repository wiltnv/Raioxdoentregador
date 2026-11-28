import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import origens as O
from calculos_moto import get_default_data, migrate_data
from sincronizacao import mesclar_estados


def lista(*nomes):
    locais = []
    for n in nomes:
        O.adicionar_local(locais, n)
    return locais


class TestNomes(unittest.TestCase):
    def test_normalizar(self):
        self.assertEqual(O.normalizar_nome("  Golden   Sushi "), "golden sushi")
        self.assertEqual(O.normalizar_nome("Sta. Efigênia"), "sta. efigenia")
        self.assertEqual(O.normalizar_nome(None), "")


class TestLista(unittest.TestCase):
    def test_adicionar_cria_com_id_e_ativo(self):
        locais = []
        l, criado = O.adicionar_local(locais, "  Golden   Sushi ")
        self.assertTrue(criado)
        self.assertEqual(l["nome"], "Golden Sushi")
        self.assertTrue(l["ativo"])
        self.assertTrue(l["id"].startswith("loc_"))

    def test_nome_igual_reaproveita(self):
        locais = lista("Golden Sushi")
        l, criado = O.adicionar_local(locais, "golden sushi")
        self.assertFalse(criado)
        self.assertEqual(len(locais), 1)

    def test_arquivado_volta_ao_adicionar_de_novo(self):
        locais = lista("O Chef")
        O.arquivar_local(locais, locais[0]["id"])
        self.assertEqual(O.locais_ativos(locais), [])
        l, criado = O.adicionar_local(locais, "o chef")
        self.assertFalse(criado)
        self.assertEqual(len(O.locais_ativos(locais)), 1)

    def test_nomes_reservados_e_vazios(self):
        locais = []
        for nome in ("Particular", "outro", "APPS", "", "   ", None):
            self.assertEqual(O.adicionar_local(locais, nome), (None, False))
        self.assertEqual(locais, [])

    def test_parecidos(self):
        locais = lista("Golden Sushi", "Padaria Central")
        self.assertEqual([l["nome"] for l in O.locais_parecidos(locais, "Golden Suchi")], ["Golden Sushi"])
        self.assertEqual(O.locais_parecidos(locais, "Golden Sushi"), [])  # igual não conta como parecido
        self.assertEqual(O.locais_parecidos(locais, "Farmácia"), [])
        O.arquivar_local(locais, locais[0]["id"])
        self.assertEqual(O.locais_parecidos(locais, "Golden Suchi"), [])  # arquivado não entra

    def test_renomear(self):
        locais = lista("A", "B")
        self.assertEqual(O.renomear_local(locais, locais[0]["id"], "Novo A"), (True, None))
        self.assertEqual(locais[0]["nome"], "Novo A")
        ok, erro = O.renomear_local(locais, locais[0]["id"], "b")
        self.assertFalse(ok)
        self.assertIn("Já existe", erro)
        self.assertFalse(O.renomear_local(locais, locais[0]["id"], "Particular")[0])
        self.assertFalse(O.renomear_local(locais, "nao_existe", "X")[0])
        self.assertFalse(O.renomear_local(locais, locais[0]["id"], "  ")[0])
        # pode "renomear" para o mesmo nome (só trocando maiúsculas)
        self.assertTrue(O.renomear_local(locais, locais[1]["id"], "b")[0])


class TestOrigensDoTurno(unittest.TestCase):
    def test_montar_soma_repetidos_e_ignora_zero(self):
        a = {"id": "loc_a", "nome": "A"}
        b = {"id": "loc_b", "nome": "B"}
        r = O.montar_origens([(a, 10), (b, 0), (None, 0), (a, 5.5), (b, 20)])
        self.assertEqual([(o["local"], o["valor"]) for o in r], [("A", 15.5), ("B", 20.0)])

    def test_validar_linhas(self):
        a = {"id": "loc_a", "nome": "A"}
        self.assertIsNone(O.validar_linhas([(a, 10), (None, 0)]))
        self.assertIn("origem", O.validar_linhas([(None, 12)]))

    def test_campos_de_ganho(self):
        loc = [{"local_id": "x", "local": "X", "valor": 30.0}]
        c = O.campos_de_ganho(0, [])
        self.assertEqual((c["bruto"], c["estabelecimento"]), (0, "iFood / Apps"))
        c = O.campos_de_ganho(20, [])
        self.assertEqual((c["bruto"], c["estabelecimento"]), (20, "iFood / Apps"))
        c = O.campos_de_ganho(0, loc)
        self.assertEqual((c["bruto"], c["estabelecimento"], c["ganho_estab"]), (30, "X", 30))
        c = O.campos_de_ganho(20, loc)
        self.assertEqual((c["bruto"], c["estabelecimento"]), (50, "Apps + X"))

    def test_renomear_nao_altera_historico(self):
        locais = lista("Golden Sushi")
        origens = O.montar_origens([(locais[0], 40)])
        O.renomear_local(locais, locais[0]["id"], "Golden Sushi Bar")
        self.assertEqual(origens[0]["local"], "Golden Sushi")          # nome da época
        self.assertEqual(origens[0]["local_id"], locais[0]["id"])      # id para relatório por cliente

    def test_turno_antigo_vira_origens(self):
        antigo = {"ganho_app": 10.0, "ganho_estab": 25.0, "estabelecimento": "Apps + Golden Sushi"}
        r = O.origens_do_turno(antigo)
        self.assertEqual([(o["local"], o["valor"]) for o in r], [("Apps", 10.0), ("Golden Sushi", 25.0)])
        so_estab = {"ganho_app": 0.0, "ganho_estab": 348.0, "estabelecimento": "Sta. Efigênia / Golden"}
        self.assertEqual(O.origens_do_turno(so_estab)[0]["valor"], 348.0)
        novo = {"origens": [{"local_id": "l", "local": "L", "valor": 5.0}], "ganho_estab": 5.0}
        self.assertEqual(O.origens_do_turno(novo), novo["origens"])


class TestDadosEMesclagem(unittest.TestCase):
    def test_conta_nova_ou_antiga_ganha_lista_vazia(self):
        self.assertEqual(get_default_data()["locais"], [])
        velho = migrate_data({"motos": [{"id": "m1"}], "moto_ativa_id": "m1",
                              "turnos": [], "manutencoes": [], "abastecimentos": []})
        self.assertEqual(velho["locais"], [])

    def test_piloto_com_lista_velha_nao_apaga_locais_do_gestor(self):
        base = migrate_data({"motos": [{"id": "m1"}], "moto_ativa_id": "m1",
                             "turnos": [], "manutencoes": [], "abastecimentos": []})
        local = copy.deepcopy(base)  # sessão do piloto: nunca mexeu em locais
        servidor = copy.deepcopy(base)
        O.adicionar_local(servidor["locais"], "Cliente Novo")  # gestor cadastrou depois
        local["turnos"].append({"data": "2026-11-28", "km": 10, "bruto": 20.0})
        r = mesclar_estados(base, local, servidor)
        self.assertEqual([l["nome"] for l in r["locais"]], ["Cliente Novo"])
        self.assertEqual(len(r["turnos"]), 1)


if __name__ == "__main__":
    unittest.main()
