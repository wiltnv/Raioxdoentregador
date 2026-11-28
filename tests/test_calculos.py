import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculos_moto import calc_custos_moto, migrate_data, get_default_data


def moto(**kw):
    m = {
        "preco_gasolina": 6.0, "consumo_kml": 30.0,
        "seguro_anual": 0.0, "seguro_mensal": 0.0, "licenciamento_anual": 0.0,
        "projecao_anual_km": 36000.0, "pecas": [],
    }
    m.update(kw)
    return m


class TestCalcCustosMoto(unittest.TestCase):
    def test_gasolina_por_km(self):
        gas, reserva, total = calc_custos_moto(moto())
        self.assertAlmostEqual(gas, 0.20)
        self.assertAlmostEqual(reserva, 0.0)
        self.assertAlmostEqual(total, 0.20)

    def test_consumo_zero_nao_divide_por_zero(self):
        gas, _, _ = calc_custos_moto(moto(consumo_kml=0))
        self.assertAlmostEqual(gas, 6.0)

    def test_projecao_zero_nao_divide_por_zero(self):
        _, reserva, _ = calc_custos_moto(moto(seguro_anual=1200.0, projecao_anual_km=0))
        self.assertAlmostEqual(reserva, 1200.0)

    def test_fixos_rateados_pelo_km_anual(self):
        _, reserva, _ = calc_custos_moto(moto(seguro_anual=900.0, licenciamento_anual=180.0,
                                              projecao_anual_km=36000.0))
        self.assertAlmostEqual(reserva, 1080.0 / 36000.0)

    def test_seguro_mensal_entra_no_calculo_anual(self):
        _, reserva, _ = calc_custos_moto(moto(seguro_mensal=100.0, projecao_anual_km=12000.0))
        self.assertAlmostEqual(reserva, 1200.0 / 12000.0)

    def test_reserva_das_pecas(self):
        pecas = [{"custo": 100.0, "intervalo": 5000.0}, {"custo": 300.0, "intervalo": 10000.0}]
        _, reserva, _ = calc_custos_moto(moto(pecas=pecas))
        self.assertAlmostEqual(reserva, 100.0 / 5000.0 + 300.0 / 10000.0)

    def test_intervalo_de_peca_zero_nao_quebra(self):
        _, reserva, _ = calc_custos_moto(moto(pecas=[{"custo": 50.0, "intervalo": 0}]))
        self.assertAlmostEqual(reserva, 50.0)

    def test_moto_alugada_sem_franquia_usa_projecao_semanal(self):
        m = moto(tipo_posse="alugada", aluguel_semanal=260.0, franquia_km_semanal=0.0,
                 projecao_anual_km=52000.0)
        _, reserva, _ = calc_custos_moto(m)
        self.assertAlmostEqual(reserva, 260.0 / 1000.0)


class TestMigrateData(unittest.TestCase):
    def test_entrada_invalida_devolve_padrao(self):
        self.assertIn("motos", migrate_data(None))
        self.assertIn("motos", migrate_data("{nao eh json"))

    def test_completa_campos_faltantes_da_moto(self):
        r = migrate_data({"motos": [{"id": "m1"}], "moto_ativa_id": "m1",
                          "turnos": [], "manutencoes": [], "abastecimentos": []})
        m = r["motos"][0]
        for campo in ("hodometro", "preco_gasolina", "consumo_kml", "projecao_anual_km", "pecas"):
            self.assertIn(campo, m)

    def test_moto_ativa_invalida_e_corrigida(self):
        r = migrate_data({"motos": [{"id": "m1"}], "moto_ativa_id": "inexistente",
                          "turnos": [], "manutencoes": [], "abastecimentos": []})
        self.assertEqual(r["moto_ativa_id"], "m1")

    def test_turno_antigo_ganha_campos_novos(self):
        r = migrate_data({"motos": [{"id": "m1"}], "moto_ativa_id": "m1",
                          "turnos": [{"data": "2026-11-01", "km": 10, "bruto": 50}],
                          "manutencoes": [], "abastecimentos": []})
        t = r["turnos"][0]
        self.assertEqual(t["moto_id"], "m1")
        self.assertEqual(t["extras"], 0.0)


if __name__ == "__main__":
    unittest.main()
