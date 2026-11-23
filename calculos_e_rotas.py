# -*- coding: utf-8 -*-
"""
Módulo de Cálculos Operacionais, Equivalência CLT 2026 e Rotas/Orçamento
Raio-X do Entregador
"""

import urllib.parse
import urllib.request
import json

# Parâmetros Equivalência CLT 2026
CLT_SALARIO_MINIMO = 1621.00
CLT_PERICULOSIDADE = 486.30
CLT_DECIMO_TERCEIRO = 175.61
CLT_FERIAS_TERCO = 234.14
CLT_FGTS = 201.36
CLT_INSS_MEI = 86.05
CLT_VALE_ALIMENTACAO = 450.00

CLT_TOTAL_MENSAL = (
    CLT_SALARIO_MINIMO
    + CLT_PERICULOSIDADE
    + CLT_DECIMO_TERCEIRO
    + CLT_FERIAS_TERCO
    + CLT_FGTS
    + CLT_INSS_MEI
    + CLT_VALE_ALIMENTACAO
)
CLT_META_DIARIA = round(CLT_TOTAL_MENSAL / 26.0, 2)
CLT_META_HORA = round(CLT_TOTAL_MENSAL / 176.0, 2)


def calcular_custos_moto(moto: dict) -> dict:
    preco_gas = float(moto.get("preco_gasolina", 5.99))
    consumo = max(float(moto.get("consumo_kml", 29.0)), 1.0)
    custo_combustivel_km = preco_gas / consumo

    tipo = moto.get("tipo", "propria")
    projecao_anual_km = max(float(moto.get("projecao_anual_km", 37286.64)), 1.0)

    if tipo == "alugada":
        aluguel_semanal = float(moto.get("aluguel_semanal", 0.0))
        km_semanal = projecao_anual_km / 52.0
        custo_fixo_km = aluguel_semanal / max(km_semanal, 1.0)
        custo_pecas_km = 0.0
    else:
        seguro = float(moto.get("seguro_anual", 0.0))
        licenc = float(moto.get("licenciamento_anual", 0.0))
        custo_fixo_km = (seguro + licenc) / projecao_anual_km

        custo_pecas_km = 0.0
        for p in moto.get("pecas", []):
            intervalo = max(float(p.get("intervalo", 1)), 1.0)
            custo = float(p.get("custo", 0.0))
            custo_pecas_km += custo / intervalo

    custo_reserva_km = custo_pecas_km + custo_fixo_km
    custo_total_km = custo_combustivel_km + custo_reserva_km

    return {
        "custo_combustivel_km": custo_combustivel_km,
        "custo_pecas_km": custo_pecas_km,
        "custo_fixo_km": custo_fixo_km,
        "custo_reserva_km": custo_reserva_km,
        "custo_total_km": custo_total_km
    }


def calcular_resumo_periodo(
    estado: dict,
    moto_id: str,
    data_ini: str,
    data_fim: str
) -> dict:
    moto = estado["motos"][moto_id]
    custos = calcular_custos_moto(moto)

    turnos = [
        t for t in estado.get("turnos", [])
        if t.get("moto_id") == moto_id and data_ini <= t.get("data", "") <= data_fim
    ]
    abastecimentos = [
        a for a in estado.get("abastecimentos", [])
        if a.get("moto_id") == moto_id and data_ini <= a.get("data", "") <= data_fim
    ]
    manutencoes = [
        m for m in estado.get("manutencoes", [])
        if m.get("moto_id") == moto_id and data_ini <= m.get("data", "") <= data_fim
    ]

    km_total = sum(float(t.get("km_rodado", 0.0)) for t in turnos)
    bruto_total = sum(float(t.get("bruto", 0.0)) for t in turnos)
    horas_total = sum(float(t.get("horas", 0.0)) for t in turnos)
    dias_trabalhados = len(set(t.get("data") for t in turnos if t.get("data")))

    combustivel_previsto = km_total * custos["custo_combustivel_km"]
    reserva_pecas_prevista = km_total * custos["custo_pecas_km"]
    reserva_fixos_prevista = km_total * custos["custo_fixo_km"]
    caixinha_prevista = km_total * custos["custo_reserva_km"]

    gasto_preventiva = sum(
        float(m.get("valor", 0.0)) for m in manutencoes if m.get("tipo") == "Preventiva"
    )
    gasto_corretiva = sum(
        float(m.get("valor", 0.0)) for m in manutencoes if m.get("tipo") != "Preventiva"
    )

    saldo_caixinha_preventiva = caixinha_prevista - gasto_preventiva
    lucro_liquido_operacional = bruto_total - combustivel_previsto - caixinha_prevista
    lucro_liquido_final = lucro_liquido_operacional - gasto_corretiva

    gasto_bomba_real = sum(float(a.get("valor_total", 0.0)) for a in abastecimentos)
    litros_bomba_real = sum(float(a.get("litros", 0.0)) for a in abastecimentos)
    consumo_real_kml = (km_total / litros_bomba_real) if litros_bomba_real > 0 else 0.0

    meta_clt_periodo = CLT_META_DIARIA * max(dias_trabalhados, 1)
    indice_clt_pct = (lucro_liquido_final / meta_clt_periodo * 100.0) if meta_clt_periodo > 0 else 0.0
    ganho_hora_liquido = (lucro_liquido_final / horas_total) if horas_total > 0 else 0.0

    return {
        "km_total": km_total,
        "bruto_total": bruto_total,
        "horas_total": horas_total,
        "dias_trabalhados": dias_trabalhados,
        "combustivel_previsto": combustivel_previsto,
        "reserva_pecas_prevista": reserva_pecas_prevista,
        "reserva_fixos_prevista": reserva_fixos_prevista,
        "caixinha_prevista": caixinha_prevista,
        "gasto_preventiva": gasto_preventiva,
        "gasto_corretiva": gasto_corretiva,
        "saldo_caixinha_preventiva": saldo_caixinha_preventiva,
        "lucro_liquido_operacional": lucro_liquido_operacional,
        "lucro_liquido_final": lucro_liquido_final,
        "gasto_bomba_real": gasto_bomba_real,
        "litros_bomba_real": litros_bomba_real,
        "consumo_real_kml": consumo_real_kml,
        "meta_clt_periodo": meta_clt_periodo,
        "indice_clt_pct": indice_clt_pct,
        "ganho_hora_liquido": ganho_hora_liquido,
        "turnos": turnos,
        "abastecimentos": abastecimentos,
        "manutencoes": manutencoes
    }


def buscar_enderecos_photon(query: str, cidade_bias: str = "Araras SP") -> list[dict]:
    if not query or len(query.strip()) < 3:
        return []
    termo = f"{query.strip()}, {cidade_bias}, Brasil" if cidade_bias else f"{query.strip()}, Brasil"
    url = "https://photon.komoot.io/api/?q=" + urllib.parse.quote(termo) + "&limit=6"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RaioXEntregador/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        resultados = []
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates", [0.0, 0.0])
            nome = props.get("name", "")
            rua = props.get("street", "")
            numero = props.get("housenumber", "")
            bairro = props.get("district", props.get("suburb", ""))
            cidade = props.get("city", props.get("town", props.get("municipality", "")))
            uf = props.get("state", "")

            partes = [p for p in [nome, f"{rua} {numero}".strip(), bairro, cidade, uf] if p]
            label = ", ".join(dict.fromkeys(partes))
            if label:
                resultados.append({
                    "label": label,
                    "lon": float(coords[0]),
                    "lat": float(coords[1])
                })
        return resultados
    except Exception:
        return []


def calcular_rota_osrm(lat1: float, lon1: float, lat2: float, lon2: float) -> dict | None:
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}?overview=false"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RaioXEntregador/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") == "Ok" and data.get("routes"):
            rota = data["routes"][0]
            dist_km = round(float(rota["distance"]) / 1000.0, 2)
            duracao_min = max(1, round(float(rota["duration"]) / 60.0))
            return {"distancia_km": dist_km, "duracao_min": duracao_min}
    except Exception:
        pass
    return None


def gerar_mensagem_whatsapp(
    origem: str,
    destino: str,
    km_ida: float,
    ida_e_volta: bool,
    valor_cobrado: float,
    custo_operacional: float,
    lucro_estimado: float
) -> str:
    km_total = km_ida * 2.0 if ida_e_volta else km_ida
    modalidade = "Ida e Volta" if ida_e_volta else "Somente Ida"
    linhas = [
        "*ORÇAMENTO DE ENTREGA*",
        f"*Origem:* {origem}",
        f"*Destino:* {destino}",
        f"*Trajeto:* {modalidade} ({km_total:.1f} km)",
        f"*Valor da Corrida:* R$ {valor_cobrado:.2f}",
        "",
        "_Orçamento gerado via Raio-X do Entregador_"
    ]
    return "\n".join(linhas)
