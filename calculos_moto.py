import json
from catalogo_motos import CATALOGO_MOTOS, MANUTENCOES_RETROATIVAS

DATA_INICIO_CICLO = "2026-11-21"
PISO_CLT_MENSAL = 3254.46
META_CLT_DIARIA = PISO_CLT_MENSAL / 26.0

def get_default_data():
    base = CATALOGO_MOTOS["Honda NXR 150 Bros ESD 2008 (Carburada)"]
    return {
        "moto_ativa_id": "moto_1",
        "motos": [
            {
                "id": "moto_1",
                "apelido": "Bros 150 ESD 2008",
                "modelo": "Honda NXR 150 Bros ESD 2008 (Carburada)",
                "tipo_posse": "propria",
                "hodometro": 81185,
                "preco_gasolina": base["preco_gasolina"],
                "consumo_kml": base["consumo_kml"],
                "seguro_anual": base["seguro_anual"],
                "seguro_mensal": 0.0,
                "licenciamento_anual": base["licenciamento_anual"],
                "aluguel_semanal": 0.0,
                "franquia_km_semanal": 0.0,
                "km_excedente_valor": 0.0,
                "projecao_anual_km": base["projecao_anual_km"],
                "pecas": [dict(p) for p in base["pecas"]]
            }
        ],
        "turnos": [
            {
                "data": "2026-11-21",
                "moto_id": "moto_1",
                "km_ini": 81011,
                "km_fim": 81185,
                "km": 174,
                "ganho_app": 0.0,
                "estabelecimento": "Sta. Efigênia / Golden",
                "ganho_estab": 348.0,
                "bruto": 348.0,
                "extras": 0.0,
                "custo_km": 0.3266
            }
        ],
        "manutencoes": [dict(m) for m in MANUTENCOES_RETROATIVAS],
        "abastecimentos": []
    }

def migrate_data(raw):
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return get_default_data()
    if not isinstance(raw, dict):
        return get_default_data()

    default = get_default_data()

    if "motos" not in raw or not isinstance(raw["motos"], list) or len(raw["motos"]) == 0:
        if "moto" in raw and isinstance(raw["moto"], dict):
            m_old = raw["moto"]
            raw["motos"] = [{
                "id": "moto_1",
                "apelido": m_old.get("modelo", "Moto Principal"),
                "modelo": m_old.get("modelo", "Honda NXR 150 Bros ESD 2008 (Carburada)"),
                "hodometro": int(m_old.get("hodometro", 81185)),
                "preco_gasolina": float(m_old.get("preco_gasolina", 5.99)),
                "consumo_kml": float(m_old.get("consumo_kml", 29.0)),
                "seguro_anual": float(m_old.get("seguro_anual", 984.08)),
                "licenciamento_anual": float(m_old.get("licenciamento_anual", 174.08)),
                "projecao_anual_km": float(m_old.get("projecao_anual_km", 37286.64)),
                "pecas": raw.get("pecas", default["motos"][0]["pecas"])
            }]
        else:
            raw["motos"] = default["motos"]

    valid_motos = []
    for idx, m in enumerate(raw["motos"]):
        if isinstance(m, str):
            try:
                m = json.loads(m)
            except Exception:
                continue
        if isinstance(m, dict):
            m.setdefault("id", f"moto_{idx+1}")
            m.setdefault("apelido", f"Moto {idx+1}")
            m.setdefault("modelo", "Personalizada")
            m.setdefault("tipo_posse", "propria")
            m.setdefault("hodometro", 0)
            m.setdefault("preco_gasolina", 5.99)
            m.setdefault("consumo_kml", 30.0)
            m.setdefault("seguro_anual", 900.0)
            m.setdefault("seguro_mensal", 0.0)
            m.setdefault("licenciamento_anual", 174.08)
            m.setdefault("aluguel_semanal", 0.0)
            m.setdefault("franquia_km_semanal", 0.0)
            m.setdefault("km_excedente_valor", 0.0)
            m.setdefault("projecao_anual_km", 36000.0)
            m.setdefault("pecas", [])
            valid_motos.append(m)

    raw["motos"] = valid_motos if valid_motos else default["motos"]
    ids_validos = [m["id"] for m in raw["motos"]]
    if raw.get("moto_ativa_id") not in ids_validos:
        raw["moto_ativa_id"] = ids_validos[0]

    if "turnos" not in raw or not isinstance(raw["turnos"], list):
        raw["turnos"] = []
    for t in raw["turnos"]:
        if isinstance(t, dict):
            t.setdefault("moto_id", raw["moto_ativa_id"])
            t.setdefault("estabelecimento", "Não informado")
            t.setdefault("ganho_app", 0.0)
            t.setdefault("ganho_estab", 0.0)
            t.setdefault("extras", 0.0)

    if "manutencoes" not in raw or not isinstance(raw["manutencoes"], list):
        raw["manutencoes"] = [dict(m) for m in MANUTENCOES_RETROATIVAS]

    for m in raw["manutencoes"]:
        if isinstance(m, dict):
            m.setdefault("moto_id", raw["moto_ativa_id"])
            m.setdefault("hodometro", 0)
            m.setdefault("tipo", "preventiva")
            m.setdefault("componente", "Serviço")
            m.setdefault("oficina", "Não informada")
            m.setdefault("valor_peca", 0.0)
            m.setdefault("valor_total", 0.0)
            m.setdefault("obs", "")

    if "abastecimentos" not in raw or not isinstance(raw["abastecimentos"], list):
        raw["abastecimentos"] = []

    return raw

def calc_custos_moto(m):
    gas_km = float(m["preco_gasolina"]) / max(float(m["consumo_kml"]), 1.0)
    proj_anual = max(float(m.get("projecao_anual_km", 36000.0)), 1.0)
    seg_total_anual = float(m.get("seguro_anual", 0.0)) + (float(m.get("seguro_mensal", 0.0)) * 12.0)

    if m.get("tipo_posse") == "alugada":
        km_semana_ref = max(float(m.get("franquia_km_semanal", 0.0)), proj_anual / 52.0, 1.0)
        aluguel_km = float(m.get("aluguel_semanal", 0.0)) / km_semana_ref
        fixos_km = aluguel_km + ((seg_total_anual + float(m.get("licenciamento_anual", 0.0))) / proj_anual)
    else:
        fixos_km = (seg_total_anual + float(m.get("licenciamento_anual", 0.0))) / proj_anual

    pecas_km = sum(float(p["custo"]) / max(float(p["intervalo"]), 1.0) for p in m.get("pecas", []))
    reserva_km = fixos_km + pecas_km
    total_km = gas_km + reserva_km
    return gas_km, reserva_km, total_km
