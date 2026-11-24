# -*- coding: utf-8 -*-
"""
Módulo de Cálculos Financeiros, Manutenção, CLT e Rotas
Raio-X do Entregador
"""

import urllib.parse
import requests

# Constantes CLT 2026 (exportadas diretamente para o Teste1_App_Moto.py)
SALARIO_BASE_SP_2026 = 1850.00
PERICULOSIDADE_PCT = 0.30
SALARIO_COM_PERICULOSIDADE = 2405.00
FERIAS_TERCO_MENSAL = 267.22
DECIMO_TERCEIRO_MENSAL = 200.42
FGTS_MENSAL = 192.40
VALE_ALIMENTACAO_MENSAL = 200.00
DIAS_UTEIS_MES = 26
HORAS_DIA_CLT = 8.0
PISO_DIARIO_CLT_2026 = 125.17
PISO_HORA_CLT_2026 = 15.65

CLT_REFERENCIA = {
    "salario_base_sp": SALARIO_BASE_SP_2026,
    "periculosidade_pct": PERICULOSIDADE_PCT,
    "salario_com_periculosidade": SALARIO_COM_PERICULOSIDADE,
    "ferias_terco_mensal": FERIAS_TERCO_MENSAL,
    "decimo_terceiro_mensal": DECIMO_TERCEIRO_MENSAL,
    "fgts_mensal": FGTS_MENSAL,
    "vale_alimentacao": VALE_ALIMENTACAO_MENSAL,
    "dias_uteis_mes": DIAS_UTEIS_MES,
    "horas_dia": HORAS_DIA_CLT,
    "meta_diaria": PISO_DIARIO_CLT_2026,
    "meta_hora": PISO_HORA_CLT_2026,
}


def calcular_custo_km_moto(moto: dict, km_mensal_estimado: float = 2500.0) -> dict:
    km_mes = max(float(km_mensal_estimado), 500.0)
    preco_comb = float(moto.get("preco_combustivel", 6.19))
    consumo = max(float(moto.get("consumo_km_l", 35.0)), 1.0)
    custo_combustivel_km = preco_comb / consumo

    custo_pecas_km = 0.0
    for peca in moto.get("pecas", []):
        custo_troca = float(peca.get("custo", 0.0))
        vida_util = max(float(peca.get("vida_util", 1000.0)), 100.0)
        custo_pecas_km += custo_troca / vida_util

    tipo_posse = moto.get("tipo_posse", "Própria")
    if tipo_posse == "Alugada":
        aluguel_semanal = float(moto.get("aluguel_semanal", 0.0))
        custo_fixo_mensal = (aluguel_semanal * 4.33) + float(moto.get("seguro_mensal", 0.0))
        custo_fixo_km = custo_fixo_mensal / km_mes
    else:
        seguro_mensal = float(moto.get("seguro_mensal", 0.0))
        ipva_anual = float(moto.get("ipva_anual", 0.0))
        custo_fixo_mensal = seguro_mensal + (ipva_anual / 12.0)
        custo_fixo_km = custo_fixo_mensal / km_mes

    custo_total_km = custo_combustivel_km + custo_pecas_km + custo_fixo_km

    return {
        "combustivel_km": round(custo_combustivel_km, 4),
        "pecas_km": round(custo_pecas_km, 4),
        "fixo_km": round(custo_fixo_km, 4),
        "total_km": round(custo_total_km, 4),
        "custo_fixo_mensal": round(custo_fixo_mensal, 2),
    }


def calcular_custo_km_frota(motos: dict, turnos: list, moto_ativa_id: str) -> dict:
    if not motos:
        return {"combustivel_km": 0.0, "pecas_km": 0.0, "fixo_km": 0.0, "total_km": 0.0, "custo_fixo_mensal": 0.0}

    moto_ref = motos.get(moto_ativa_id) or next(iter(motos.values()))
    if len(motos) == 1 or not turnos:
        return calcular_custo_km_moto(moto_ref)

    km_por_moto = {}
    for t in turnos:
        mid = t.get("moto_id", moto_ativa_id)
        km_por_moto[mid] = km_por_moto.get(mid, 0.0) + float(t.get("km_rodado", 0.0))

    total_km_frota = sum(km_por_moto.values())
    if total_km_frota <= 0:
        return calcular_custo_km_moto(moto_ref)

    comb_pond = 0.0
    pecas_pond = 0.0
    fixo_pond = 0.0
    fixo_mensal_soma = 0.0

    for mid, m in motos.items():
        c = calcular_custo_km_moto(m)
        peso = km_por_moto.get(mid, 0.0) / total_km_frota
        comb_pond += c["combustivel_km"] * peso
        pecas_pond += c["pecas_km"] * peso
        fixo_pond += c["fixo_km"] * peso
        fixo_mensal_soma += c["custo_fixo_mensal"]

    return {
        "combustivel_km": round(comb_pond, 4),
        "pecas_km": round(pecas_pond, 4),
        "fixo_km": round(fixo_pond, 4),
        "total_km": round(comb_pond + pecas_pond + fixo_pond, 4),
        "custo_fixo_mensal": round(fixo_mensal_soma, 2),
    }


def calcular_saude_peca(peca: dict, hodometro_atual: int) -> dict:
    ultima_km = int(peca.get("ultima_km", 0))
    vida_util = max(int(peca.get("vida_util", 1000)), 1)
    km_rodado = max(int(hodometro_atual) - ultima_km, 0)
    km_restante = vida_util - km_rodado
    pct_desgaste = min(round((km_rodado / vida_util) * 100.0, 1), 150.0)
    pct_saude = max(round(100.0 - pct_desgaste, 1), 0.0)

    if km_restante <= 0:
        status = "VENCIDA"
        cor = "red"
    elif pct_desgaste >= 80.0:
        status = "ATENÇÃO"
        cor = "orange"
    else:
        status = "OK"
        cor = "green"

    return {
        "km_rodado": km_rodado,
        "km_restante": km_restante,
        "pct_desgaste": pct_desgaste,
        "pct_saude": pct_saude,
        "status": status,
        "cor": cor,
    }


def calcular_equivalencia_clt(lucro_liquido_total: float, dias_trabalhados: int, horas_trabalhadas: float) -> dict:
    dias = max(int(dias_trabalhados), 1)
    horas = max(float(horas_trabalhadas), 0.1)

    meta_diaria = PISO_DIARIO_CLT_2026
    meta_hora = PISO_HORA_CLT_2026

    referencia_clt_periodo = dias * meta_diaria
    saldo_vs_clt = lucro_liquido_total - referencia_clt_periodo
    indice_clt = (lucro_liquido_total / referencia_clt_periodo * 100.0) if referencia_clt_periodo > 0 else 0.0

    lucro_dia = lucro_liquido_total / dias
    lucro_hora = lucro_liquido_total / horas

    return {
        "meta_diaria": meta_diaria,
        "meta_hora": meta_hora,
        "referencia_clt_periodo": round(referencia_clt_periodo, 2),
        "saldo_vs_clt": round(saldo_vs_clt, 2),
        "indice_clt": round(indice_clt, 1),
        "lucro_dia": round(lucro_dia, 2),
        "lucro_hora": round(lucro_hora, 2),
        "superou_clt": lucro_liquido_total >= referencia_clt_periodo,
    }


def buscar_enderecos_brasil(termo: str, cidade_padrao: str = "Araras", estado_padrao: str = "SP") -> list:
    consulta = termo.strip()
    if not consulta or len(consulta) < 3:
        return []

    if cidade_padrao and cidade_padrao.lower() not in consulta.lower():
        consulta_completa = f"{consulta}, {cidade_padrao}, {estado_padrao}, Brasil"
    else:
        consulta_completa = f"{consulta}, Brasil"

    resultados = []
    try:
        url = "https://komoot.io"
        params = {"q": consulta_completa, "limit": 5}
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            dados = resp.json()
            for feat in dados.get("features", []):
                props = feat.get("properties", {})
                coords = feat.get("geometry", {}).get("coordinates", [])
                if len(coords) >= 2:
                    rua = props.get("street") or props.get("name") or ""
                    numero = props.get("housenumber") or ""
                    bairro = props.get("district") or props.get("suburb") or ""
                    cidade = props.get("city") or props.get("town") or cidade_padrao
                    uf = props.get("state") or estado_padrao
                    partes = [p for p in [f"{rua} {numero}".strip(), bairro, f"{cidade}/{uf}"] if p]
                    label = " - ".join(partes)
                    resultados.append({
                        "label": label,
                        "lat": float(coords[1]),
                        "lon": float(coords[0]),
                    })
    except Exception:
        pass

    return resultados


def calcular_rota_osrm(lat1: float, lon1: float, lat2: float, lon2: float) -> dict | None:
    try:
        url = f"http://project-osrm.org{lon1},{lat1};{lon2},{lat2}?overview=false"
        resp = requests.get(url, timeout=6)
        if resp.status_code == 200:
            dados = resp.json()
            rotas = dados.get("routes", [])
            if rotas:
                dist_km = round(rotas[0]["distance"] / 1000.0, 2)
                dur_min = max(int(round(rotas[0]["duration"] / 60.0)), 1)
                return {"distancia_km": dist_km, "duracao_min": dur_min}
    except Exception:
        pass
    return None


def formatar_mensagem_whatsapp(
    origem: str,
    destino: str,
    distancia_km: float,
    duracao_min: int,
    valor_corrida: float,
    ida_e_volta: bool,
) -> tuple[str, str]:
    tipo_rota = "Ida e Volta" if ida_e_volta else "Somente Ida"
    texto = (
        f"*Orçamento de Entrega*\n"
        f"📍 *Origem:* {origem}\n"
        f"🏁 *Destino:* {destino}\n"
        f"🛣️ *Distância:* {distancia_km:.1f} km ({tipo_rota})\n"
        f"⏱️ *Tempo estimado:* ~{duracao_min} min\n"
        f"💰 *Valor da corrida:* R$ {valor_corrida:.2f}"
    )
    link = f"https://wa.me{urllib.parse.quote(texto)}"
    return texto, link
