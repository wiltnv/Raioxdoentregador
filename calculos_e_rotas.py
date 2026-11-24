# -*- coding: utf-8 -*-
"""
Módulo de Cálculos de Custo/Km, Equivalência CLT 2026, Rotas e WhatsApp
Raio-X do Entregador
"""

import urllib.parse
import requests
from catalogo_motos import ESTABELECIMENTOS_LISTA

# Parâmetros CLT 2026 (Equivalência Diária)
CLT_SALARIO_BASE = 1621.00
CLT_ADICIONAL_PERICULOSIDADE = 0.30
CLT_DIAS_UTEIS_MES = 22
CLT_HORAS_DIA = 8.0
CLT_ENCARGOS_MENSAL = 417.30  # 13º + Férias + 1/3 + FGTS

CLT_BRUTO_MENSAL = CLT_SALARIO_BASE * (1 + CLT_ADICIONAL_PERICULOSIDADE)  # R$ 2.107,30
CLT_DIARIA_BASE = CLT_BRUTO_MENSAL / CLT_DIAS_UTEIS_MES  # R$ 95,79
CLT_DIARIA_BENEFICIOS = CLT_ENCARGOS_MENSAL / CLT_DIAS_UTEIS_MES  # R$ 18,97
CLT_AUXILIO_COMBUSTIVEL_DIA = 10.41
CLT_META_DIARIA_EQUIVALENTE = round(CLT_DIARIA_BASE + CLT_DIARIA_BENEFICIOS + CLT_AUXILIO_COMBUSTIVEL_DIA, 2)  # R$ 125,17
CLT_META_HORA_EQUIVALENTE = round(CLT_META_DIARIA_EQUIVALENTE / CLT_HORAS_DIA, 2)  # R$ 15,65/h


def calcular_custo_km_moto(moto: dict, km_mensal_estimado: float = 3000.0) -> dict:
    """Calcula a decomposição completa de custo/km de um veículo."""
    km_mes = max(float(km_mensal_estimado), 500.0)
    consumo = max(float(moto.get("consumo_km_l", 35.0)), 1.0)
    preco_gas = max(float(moto.get("preco_combustivel", 6.19)), 0.0)
    custo_combustivel_km = preco_gas / consumo

    tipo_posse = moto.get("tipo_posse", "Própria")

    if tipo_posse == "Alugada":
        aluguel_semanal = float(moto.get("aluguel_semanal", 0.0))
        custo_aluguel_km = (aluguel_semanal * 4.33) / km_mes
        custo_pecas_km = 0.0
        custo_fixos_km = 0.0
        custo_total_km = custo_combustivel_km + custo_aluguel_km
        return {
            "combustivel_km": round(custo_combustivel_km, 4),
            "pecas_km": 0.0,
            "fixos_km": 0.0,
            "aluguel_km": round(custo_aluguel_km, 4),
            "total_km": round(custo_total_km, 4),
            "tipo_posse": "Alugada"
        }

    # Moto Própria
    custo_pecas_km = 0.0
    for peca in moto.get("pecas", []):
        vida = max(float(peca.get("vida_util_km", 10000)), 100.0)
        custo = max(float(peca.get("custo_medio", 0.0)), 0.0)
        custo_pecas_km += (custo / vida)

    ipva = float(moto.get("ipva_anual", 0.0))
    seguro = float(moto.get("seguro_anual", 0.0))
    depreciacao = float(moto.get("depreciacao_anual", 0.0))
    custo_fixos_km = ((ipva + seguro + depreciacao) / 12.0) / km_mes

    custo_total_km = custo_combustivel_km + custo_pecas_km + custo_fixos_km

    return {
        "combustivel_km": round(custo_combustivel_km, 4),
        "pecas_km": round(custo_pecas_km, 4),
        "fixos_km": round(custo_fixos_km, 4),
        "aluguel_km": 0.0,
        "total_km": round(custo_total_km, 4),
        "tipo_posse": "Própria"
    }


def calcular_custo_km_frota(motos: dict, moto_ativa_id: str, km_mensal_estimado: float = 3000.0) -> dict:
    """Wrapper seguro para calcular o custo/km da moto ativa na frota."""
    if not motos:
        return {
            "combustivel_km": 0.18,
            "pecas_km": 0.08,
            "fixos_km": 0.05,
            "aluguel_km": 0.0,
            "total_km": 0.31,
            "tipo_posse": "Própria"
        }
    moto = motos.get(moto_ativa_id) or next(iter(motos.values()))
    return calcular_custo_km_moto(moto, km_mensal_estimado)


def avaliar_saude_pecas(moto: dict) -> list:
    """Retorna lista ordenada das peças da moto com % de desgaste e status visual."""
    hodometro = float(moto.get("hodometro_atual", 0.0))
    resultado = []

    for peca in moto.get("pecas", []):
        ultima_km = float(peca.get("ultima_km", hodometro))
        vida_util = max(float(peca.get("vida_util_km", 10000)), 1.0)
        km_rodado_peca = max(0.0, hodometro - ultima_km)
        pct_uso = (km_rodado_peca / vida_util) * 100.0
        km_restante = vida_util - km_rodado_peca

        if pct_uso >= 100.0:
            status = "🔴 Vencida"
            prioridade = 0
        elif pct_uso >= 80.0:
            status = "🟡 Atenção"
            prioridade = 1
        else:
            status = "🟢 Saudável"
            prioridade = 2

        resultado.append({
            "nome": peca.get("nome", "Peça"),
            "ultima_km": int(ultima_km),
            "vida_util_km": int(vida_util),
            "km_rodado": int(km_rodado_peca),
            "km_restante": int(km_restante),
            "pct_uso": round(pct_uso, 1),
            "custo_medio": float(peca.get("custo_medio", 0.0)),
            "status": status,
            "prioridade": prioridade
        })

    resultado.sort(key=lambda x: (x["prioridade"], -x["pct_uso"]))
    return resultado


def calcular_resumo_financeiro(estado: dict, moto_id_filtro: str = "TODAS") -> dict:
    """Consolida KPIs do ciclo atual filtrando por moto ou frota inteira."""
    data_inicio = estado.get("data_inicio_ciclo", "2026-11-21")
    motos = estado.get("motos", {})

    turnos = [
        t for t in estado.get("turnos", [])
        if t.get("data", "") >= data_inicio and (moto_id_filtro == "TODAS" or t.get("moto_id") == moto_id_filtro)
    ]
    abastecimentos = [
        a for a in estado.get("abastecimentos", [])
        if a.get("data", "") >= data_inicio and (moto_id_filtro == "TODAS" or a.get("moto_id") == moto_id_filtro)
    ]
    manutencoes = [
        m for m in estado.get("manutencoes", [])
        if m.get("data", "") >= data_inicio and (moto_id_filtro == "TODAS" or m.get("moto_id") == moto_id_filtro)
    ]

    faturamento_bruto = sum(float(t.get("bruto", 0.0)) for t in turnos)
    km_total = sum(float(t.get("km_rodado", 0.0)) for t in turnos)
    horas_total = sum(float(t.get("horas", 0.0)) for t in turnos)
    dias_trabalhados = len(set(t.get("data", "") for t in turnos if t.get("data")))

    gasto_combustivel_real = sum(float(a.get("valor", 0.0)) for a in abastecimentos)
    gasto_manutencao_real = sum(float(m.get("valor", 0.0)) for m in manutencoes)

    # Estimativa técnica caso ainda não haja abastecimentos registrados no ciclo
    moto_ref = motos.get(moto_id_filtro) if moto_id_filtro != "TODAS" else motos.get(estado.get("moto_ativa_id"))
    if not moto_ref and motos:
        moto_ref = next(iter(motos.values()))

    decomposicao = calcular_custo_km_moto(moto_ref) if moto_ref else {"total_km": 0.30, "combustivel_km": 0.18, "pecas_km": 0.08, "fixos_km": 0.04, "aluguel_km": 0.0}

    custo_estimado_km = decomposicao["total_km"]
    custo_operacional_estimado = km_total * custo_estimado_km
    custo_real_caixa = gasto_combustivel_real + gasto_manutencao_real

    custo_considerado = custo_real_caixa if custo_real_caixa > 0 else custo_operacional_estimado
    lucro_liquido = faturamento_bruto - custo_considerado

    ganho_km_bruto = (faturamento_bruto / km_total) if km_total > 0 else 0.0
    ganho_km_liquido = (lucro_liquido / km_total) if km_total > 0 else 0.0
    ganho_hora_liquido = (lucro_liquido / horas_total) if horas_total > 0 else 0.0
    media_diaria_liquida = (lucro_liquido / dias_trabalhados) if dias_trabalhados > 0 else 0.0

    indice_clt = (media_diaria_liquida / CLT_META_DIARIA_EQUIVALENTE * 100.0) if dias_trabalhados > 0 else 0.0

    return {
        "faturamento_bruto": round(faturamento_bruto, 2),
        "km_total": round(km_total, 1),
        "horas_total": round(horas_total, 1),
        "dias_trabalhados": dias_trabalhados,
        "gasto_combustivel_real": round(gasto_combustivel_real, 2),
        "gasto_manutencao_real": round(gasto_manutencao_real, 2),
        "custo_operacional_estimado": round(custo_operacional_estimado, 2),
        "custo_considerado": round(custo_considerado, 2),
        "lucro_liquido": round(lucro_liquido, 2),
        "ganho_km_bruto": round(ganho_km_bruto, 2),
        "ganho_km_liquido": round(ganho_km_liquido, 2),
        "ganho_hora_liquido": round(ganho_hora_liquido, 2),
        "media_diaria_liquida": round(media_diaria_liquida, 2),
        "indice_clt": round(indice_clt, 1),
        "decomposicao_km": decomposicao,
        "turnos_filtrados": turnos,
        "abastecimentos_filtrados": abastecimentos,
        "manutencoes_filtradas": manutencoes
    }


def buscar_enderecos_autocomplete(query: str, cidade: str = "Araras", estado: str = "SP") -> list:
    """Busca endereços reais no Brasil via API Photon (OpenStreetMap)."""
    q = (query or "").strip()
    if len(q) < 3:
        return []

    busca_completa = f"{q}, {cidade}, {estado}, Brasil"
    url = "https://photon.komoot.io/api/"
    params = {"q": busca_completa, "limit": 6, "lang": "pt"}

    resultados = []
    try:
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            dados = resp.json()
            for feat in dados.get("features", []):
                props = feat.get("properties", {})
                coords = feat.get("geometry", {}).get("coordinates", [])
                if len(coords) < 2:
                    continue
                rua = props.get("street") or props.get("name") or ""
                numero = props.get("housenumber") or ""
                bairro = props.get("district") or props.get("suburb") or ""
                cid = props.get("city") or props.get("town") or cidade
                uf = props.get("state") or estado

                partes = [p for p in [f"{rua} {numero}".strip(), bairro, f"{cid}/{uf}"] if p]
                label = " - ".join(partes)
                if label:
                    resultados.append({
                        "label": label,
                        "lon": float(coords),
                        "lat": float(coords)
                    })
    except Exception:
        pass

    return resultados


def calcular_rota_osrm(origem: dict, destino: dict) -> dict | None:
    """Calcula distância real de condução (km) e tempo (min) entre dois pontos."""
    try:
        lon1, lat1 = origem["lon"], origem["lat"]
        lon2, lat2 = destino["lon"], destino["lat"]
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
        resp = requests.get(url, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            rotas = data.get("routes", [])
            if rotas:
                dist_km = rotas["distance"] / 1000.0
                duracao_min = rotas["duration"] / 60.0
                return {
                    "distancia_km": round(dist_km, 2),
                    "duracao_min": round(duracao_min, 1)
                }
    except Exception:
        pass
    return None


def gerar_link_whatsapp_orcamento(
    origem_label: str,
    destino_label: str,
    distancia_ida_km: float,
    distancia_cobrada_km: float,
    valor_total: float,
    custo_moto_estimado: float,
    lucro_estimado: float,
    retorno_incluso: bool
) -> str:
    """Monta texto profissional de orçamento e retorna link direto wa.me."""
    tipo_trajeto = "Ida e Volta" if retorno_incluso else "Somente Ida"
    texto = (
        f"🏍️ *ORÇAMENTO DE ENTREGA*\n"
        f"📍 *Origem:* {origem_label}\n"
        f"🏁 *Destino:* {destino_label}\n"
        f"🛣️ *Trajeto:* {tipo_trajeto} ({distancia_cobrada_km:.1f} km)\n"
        f"💰 *Valor da Corrida:* R$ {valor_total:.2f}\n"
        f"_(Custo est. moto: R$ {custo_moto_estimado:.2f} | Lucro líq.: R$ {lucro_estimado:.2f})_"
    )
    texto_encoded = urllib.parse.quote(texto)
    return f"https://wa.me/?text={texto_encoded}"
