# -*- coding: utf-8 -*-
"""
Módulo de Cálculos Financeiros, Manutenção, CLT e Rotas
Raio-X do Entregador
"""

import urllib.parse
import requests

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
            valor_totais = sum(float(a.get("valor_total", 0.0)) for a in abast_moto)
            if litros_totais > 0 and valor_totais > 0:
                preco_comb = valor_totais / litros_totais
            kms_abast = [int(a.get("km", 0)) for a in abast_moto if int(a.get("km", 0)) > 0]
            if len(kms_abast) >= 2:
                delta_km = max(kms_abast) - min(kms_abast)
                litros_apos_primeiro = sum(
                    float(a.get("litros", 0.0))
                    for a in sorted(abast_moto, key=lambda x: int(x.get("km", 0)))[1:]
                )
                if delta_km > 0 and litros_apos_primeiro > 0:
                    consumo = delta_km / litros_apos_primeiro

    custo_combustivel_km = preco_comb / consumo

    custo_pecas_km = 0.0
    for peca in moto.get("pecas", []):
        custo_troca = float(peca.get("custo", 0.0))
        intervalo = max(float(peca.get("intervalo", peca.get("vida_util", 1000.0))), 100.0)
        custo_pecas_km += custo_troca / intervalo

    seguro_anual = float(moto.get("seguro_anual", 0.0))
    licenciamento_anual = float(moto.get("licenciamento_anual", 0.0))
    if seguro_anual == 0.0 and float(moto.get("seguro_mensal", 0.0)) > 0.0:
        seguro_anual = float(moto.get("seguro_mensal", 0.0)) * 12.0
    if licenciamento_anual == 0.0 and float(moto.get("ipva_anual", 0.0)) > 0.0:
        licenciamento_anual = float(moto.get("ipva_anual", 0.0))

    custo_fixo_anual = seguro_anual + licenciamento_anual
    custo_fixo_km = custo_fixo_anual / projecao_anual

    tipo = str(moto.get("tipo", moto.get("tipo_posse", "propria"))).lower()
    aluguel_semanal = float(moto.get("aluguel_semanal", 0.0))
    if tipo == "alugada" or aluguel_semanal > 0.0:
        km_semanal = projecao_anual / 52.0
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
        "custo_km_combustivel": round(custo_combustivel_km, 4),
        "custo_km_pecas": round(custo_pecas_km, 4),
        "custo_km_fixo": round(custo_fixo_km, 4),
        "combustivel_km": round(custo_combustivel_km, 4),
        "pecas_km": round(custo_pecas_km, 4),
        "fixo_km": round(custo_fixo_km, 4),
        "total_km": round(custo_total_km, 4),
        "consumo_real": round(consumo, 1),
        "preco_combustivel_real": round(preco_comb, 2),
    }


def avaliar_pecas(moto: dict) -> list:
    hodometro_atual = int(moto.get("hodometro", moto.get("hodometro_atual", 0)))
    lista_avaliada = []
    for peca in moto.get("pecas", []):
        ultima_km = int(peca.get("ultima_km", 0))
        intervalo = max(int(peca.get("intervalo", peca.get("vida_util", 1000))), 1)
        proxima_km = ultima_km + intervalo
        km_rodado = max(hodometro_atual - ultima_km, 0)
        km_restante = proxima_km - hodometro_atual
        pct_desgaste = min(round((km_rodado / intervalo) * 100.0, 1), 150.0)
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

        item = dict(peca)
        item.update({
            "ultima_km": ultima_km,
            "intervalo": intervalo,
            "proxima_km": proxima_km,
            "km_rodado": km_rodado,
            "km_restante": km_restante,
            "pct_desgaste": pct_desgaste,
            "pct_saude": pct_saude,
            "status": status,
            "cor": cor,
        })
        lista_avaliada.append(item)
    return lista_avaliada


def buscar_enderecos_autocomplete(termo: str, cidade_padrao: str = "Araras", estado_padrao: str = "SP") -> list:
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


def gerar_texto_whatsapp_rota(
    origem: str,
    destino: str,
    distancia_km: float,
    duracao_min: int,
    valor_corrida: float,
    ida_e_volta: bool = True,
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
