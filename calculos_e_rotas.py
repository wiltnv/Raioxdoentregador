# -*- coding: utf-8 -*-
"""
Módulo de Cálculos Financeiros, Manutenção, CLT e Rotas
Raio-X do Entregador
"""

import urllib.parse
import requests
import streamlit as st

SALARIO_BASE_SP_2026 = 1621.00
PERICULOSIDADE_PCT = 0.30
SALARIO_COM_PERICULOSIDADE = 2107.30
FERIAS_TERCO_MENSAL = 234.14
DECIMO_TERCEIRO_MENSAL = 175.61
FGTS_MENSAL = 201.36
INSS_MEI_MENSAL = 86.05
VALE_ALIMENTACAO_MENSAL = 450.00
DIAS_UTEIS_MES = 26
HORAS_DIA_CLT = 176.0 / 26.0
PISO_DIARIO_CLT_2026 = 125.17
PISO_HORA_CLT_2026 = 18.49

HEADERS_HTTP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RaioXDoEntregador/3.0"
}


def calcular_custo_km_detalhado(moto: dict, contexto: dict | float = 2500.0) -> dict:
    moto_id = moto.get("id", "moto_bros_2008")
    preco_comb = float(moto.get("preco_gasolina", moto.get("preco_combustivel", 5.99)))
    consumo = max(float(moto.get("consumo_kml", moto.get("consumo_km_l", 29.0))), 1.0)
    projecao_anual = max(float(moto.get("projecao_anual_km", 37286.64)), 1000.0)

    if isinstance(contexto, dict):
        abast_moto = [
            a for a in contexto.get("abastecimentos", [])
            if a.get("moto_id", moto_id) == moto_id
        ]
        if abast_moto:
            litros_totais = sum(float(a.get("litros", 0.0)) for a in abast_moto)
            valor_totais = sum(float(a.get("valor_total", a.get("valor", 0.0))) for a in abast_moto)
            if litros_totais > 0 and valor_totais > 0:
                preco_comb = valor_totais / litros_totais
            kms_abast = [int(a.get("km", 0)) for a in abast_moto if int(a.get("km", 0)) > 0]
            if len(kms_abast) >= 2:
                delta_km = max(kms_abast) - min(kms_abast)
                abast_ordenados = sorted(abast_moto, key=lambda x: int(x.get("km", 0)))
                litros_apos_primeiro = sum(
                    float(a.get("litros", 0.0)) for a in abast_ordenados[1:]
                )
                if delta_km > 0 and litros_apos_primeiro > 0:
                    consumo = delta_km / litros_apos_primeiro

    custo_combustivel_km = preco_comb / consumo

    custo_pecas_km = 0.0
    for peca in moto.get("pecas", []):
        custo_troca = float(peca.get("custo", peca.get("custo_estimado", 0.0)))
        intervalo = max(float(peca.get("intervalo", peca.get("vida_util", 1000.0))), 100.0)
        custo_pecas_km += custo_troca / intervalo

    seguro_anual = float(moto.get("seguro_anual", 0.0))
    licenciamento_anual = float(moto.get("licenciamento_anual", 0.0))
    if seguro_anual == 0.0 and float(moto.get("seguro_mensal", 0.0)) > 0.0:
        seguro_anual = float(moto.get("seguro_mensal", 0.0)) * 12.0
    if licenciamento_anual == 0.0 and float(moto.get("ipva_licenciamento_anual", 0.0)) > 0.0:
        licenciamento_anual = float(moto.get("ipva_licenciamento_anual", 0.0))

    custo_fixo_anual = seguro_anual + licenciamento_anual
    custo_fixo_km = custo_fixo_anual / projecao_anual

    tipo = str(moto.get("tipo", moto.get("tipo_posse", "propria"))).lower()
    aluguel_semanal = float(moto.get("aluguel_semanal", 0.0))
    if tipo == "alugada" or aluguel_semanal > 0.0:
        km_semanal = float(moto.get("km_franquia_semanal", 0.0)) or (projecao_anual / 52.0)
        custo_aluguel_km = aluguel_semanal / max(km_semanal, 100.0)
    else:
        custo_aluguel_km = 0.0

    custo_total_km = custo_combustivel_km + custo_pecas_km + custo_fixo_km + custo_aluguel_km

    return {
        "custo_comb_km": round(custo_combustivel_km, 4),
        "custo_pecas_km": round(custo_pecas_km, 4),
        "custo_fixo_km": round(custo_fixo_km, 4),
        "custo_aluguel_km": round(custo_aluguel_km, 4),
        "custo_km_total": round(custo_total_km, 4),
        "consumo_real": round(consumo, 1),
        "preco_combustivel_real": round(preco_comb, 2),
    }
def avaliar_pecas(moto: dict) -> list:
    hodometro_atual = int(moto.get("hodometro", moto.get("hodometro_atual", 0)))
    lista_avaliada = []
    for peca in moto.get("pecas", []):
        ultima_km = int(peca.get("ultima_km", 0))
        intervalo = max(int(peca.get("intervalo", peca.get("vida_util", 1000))), 1)
        custo_peca = float(peca.get("custo", peca.get("custo_estimado", 0.0)))
        custo_por_km = custo_peca / float(intervalo)
        proxima_km = ultima_km + intervalo
        km_rodado = max(hodometro_atual - ultima_km, 0)
        km_restante = proxima_km - hodometro_atual
        pct_desgaste = min(round((km_rodado / intervalo) * 100.0, 1), 150.0)
        pct_saude = max(round(100.0 - pct_desgaste, 1), 0.0)
        em_alerta = km_restante <= 0 or pct_desgaste >= 80.0

        if km_restante <= 0:
            status = "VENCIDA"
            cor = "red"
        elif pct_desgaste >= 80.0:
            status = "ATENÇÃO"
            cor = "orange"
        else:
            status = "OK"
            cor = "green"

        item = dict(peca)
        item.update({
            "ultima_km": ultima_km,
            "intervalo": intervalo,
            "proxima_km": proxima_km,
            "custo_por_km": round(custo_por_km, 4),
            "km_rodados": km_rodado,
            "km_restantes": km_restante,
            "percentual_uso": pct_desgaste,
            "pct_saude": pct_saude,
            "alerta": em_alerta,
            "status": status,
            "cor": cor,
        })
        lista_avaliada.append(item)
    return lista_avaliada


def buscar_enderecos_autocomplete(termo: str, cidade_padrao: str = "Araras", estado_padrao: str = "SP") -> list:
    consulta = str(termo or "").strip()
    if len(consulta) < 3:
        return []

    if "cache_enderecos" not in st.session_state:
        st.session_state["cache_enderecos"] = {}

    resultados = []
    vistos = set()

    try:
        resp = requests.get(
            "https://komoot.io",
            params={"q": f"{consulta} {cidade_padrao}", "lat": -22.3572, "lon": -47.3842, "limit": 6},
            headers=HEADERS_HTTP,
            timeout=4,
        )
        if resp.status_code == 200:
            for feat in resp.json().get("features", []):
                props = feat.get("properties", {})
                coords = feat.get("geometry", {}).get("coordinates", [])
                if isinstance(coords, list) and len(coords) >= 2:
                    lon_val = float(coords.pop(0))
                    lat_val = float(coords.pop(0))
                    rua = props.get("street") or props.get("name") or ""
                    numero = props.get("housenumber") or ""
                    bairro = props.get("district") or props.get("suburb") or ""
                    cidade = props.get("city") or props.get("town") or cidade_padrao
                    uf = props.get("state") or estado_padrao
                    partes = [p for p in [f"{rua} {numero}".strip(), bairro, f"{cidade}/{uf}"] if p]
                    label = " - ".join(partes) if partes else consulta
                    if label not in vistos:
                        vistos.add(label)
                        item = {"label": label, "lat": lat_val, "lon": lon_val}
                        st.session_state["cache_enderecos"][label] = item
                        resultados.append(item)
    except Exception:
        pass

    if len(resultados) < 3:
        try:
            q_nom = (
                f"{consulta}, {cidade_padrao}, {estado_padrao}, Brasil"
                if cidade_padrao.lower() not in consulta.lower()
                else f"{consulta}, Brasil"
            )
            resp_nom = requests.get(
                "https://openstreetmap.org",
                params={"q": q_nom, "format": "json", "addressdetails": 1, "limit": 6, "countrycodes": "br"},
                headers=HEADERS_HTTP,
                timeout=5,
            )
            if resp_nom.status_code == 200:
                for it in resp_nom.json():
                    lat_val = float(it.get("lat", 0))
                    lon_val = float(it.get("lon", 0))
                    addr = it.get("address", {})
                    rua = addr.get("road") or addr.get("pedestrian") or it.get("name") or ""
                    numero = addr.get("house_number") or ""
                    bairro = addr.get("suburb") or addr.get("neighbourhood") or ""
                    cidade = addr.get("city") or addr.get("town") or cidade_padrao
                    uf = addr.get("state") or estado_padrao
                    partes = [p for p in [f"{rua} {numero}".strip(), bairro, f"{cidade}/{uf}"] if p]
                    label = " - ".join(partes) if partes else it.get("display_name", consulta)
                    if label not in vistos and lat_val != 0:
                        vistos.add(label)
                        item = {"label": label, "lat": lat_val, "lon": lon_val}
                        st.session_state["cache_enderecos"][label] = item
                        resultados.append(item)
        except Exception:
            pass

    return resultados
