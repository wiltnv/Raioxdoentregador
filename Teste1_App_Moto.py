import streamlit as st
import pandas as pd
import json
import os
from datetime import date

try:
    from supabase import create_client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

try:
    from streamlit_searchbox import st_searchbox
    HAS_SEARCHBOX = True
except ImportError:
    HAS_SEARCHBOX = False

try:
    from streamlit_js_eval import get_geolocation
    HAS_GEO = True
except ImportError:
    HAS_GEO = False

import urllib.request
import urllib.parse

st.set_page_config(page_title="Raio-X do Entregador", page_icon="🏍️", layout="centered")

DATA_FILE = "dados_entregador.json"
DATA_INICIO_CICLO = "2026-11-22"

ESTABELECIMENTOS_LISTA = [
    "Nenhum (Apenas Apps)",
    "Sta. Efigênia",
    "Golden Sushi",
    "O Chef",
    "Particular",
    "Extra 1",
    "Extra 2"
]

CATALOGO_MOTOS = {
    "Honda NXR 150 Bros ESD 2008 (Carburada)": {
        "preco_gasolina": 5.99,
        "consumo_kml": 29.0,
        "seguro_anual": 984.08,
        "licenciamento_anual": 174.08,
        "projecao_anual_km": 37286.64,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "ultima_km": 80346, "custo": 34.0},
            {"nome": "Limpeza/Regulagem Carburador", "intervalo": 12000, "ultima_km": 70050, "custo": 120.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "ultima_km": 51560, "custo": 70.0},
            {"nome": "Pastilha Freio Dianteiro (ESD)", "intervalo": 12000, "ultima_km": 74545, "custo": 65.0},
            {"nome": "Lona Freio Traseiro", "intervalo": 15000, "ultima_km": 74545, "custo": 65.0},
            {"nome": "Cabos + Lubrificação", "intervalo": 15000, "ultima_km": 70050, "custo": 120.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "ultima_km": 75056, "custo": 225.0},
            {"nome": "Par de Pneus", "intervalo": 30000, "ultima_km": 68824, "custo": 550.0},
            {"nome": "Bateria (Partida Elétrica)", "intervalo": 50000, "ultima_km": 58098, "custo": 160.0}
        ]
    },
    "Honda CG 160 (Titan / Fan / Start)": {
        "preco_gasolina": 5.99,
        "consumo_kml": 35.0,
        "seguro_anual": 1100.00,
        "licenciamento_anual": 174.08,
        "projecao_anual_km": 37286.64,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "ultima_km": 0, "custo": 38.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "ultima_km": 0, "custo": 65.0},
            {"nome": "Pastilha Freio Dianteiro", "intervalo": 12000, "ultima_km": 0, "custo": 55.0},
            {"nome": "Lona Freio Traseiro", "intervalo": 15000, "ultima_km": 0, "custo": 55.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "ultima_km": 0, "custo": 190.0},
            {"nome": "Par de Pneus", "intervalo": 30000, "ultima_km": 0, "custo": 520.0},
            {"nome": "Bateria", "intervalo": 50000, "ultima_km": 0, "custo": 160.0}
        ]
    },
    "Yamaha Factor / Fazer 150": {
        "preco_gasolina": 5.99,
        "consumo_kml": 36.0,
        "seguro_anual": 1050.00,
        "licenciamento_anual": 174.08,
        "projecao_anual_km": 37286.64,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "ultima_km": 0, "custo": 38.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "ultima_km": 0, "custo": 70.0},
            {"nome": "Pastilha Freio Dianteiro", "intervalo": 12000, "ultima_km": 0, "custo": 60.0},
            {"nome": "Lona Freio Traseiro", "intervalo": 15000, "ultima_km": 0, "custo": 60.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "ultima_km": 0, "custo": 200.0},
            {"nome": "Par de Pneus", "intervalo": 30000, "ultima_km": 0, "custo": 530.0},
            {"nome": "Bateria", "intervalo": 50000, "ultima_km": 0, "custo": 165.0}
        ]
    }
}

MANUTENCOES_RETROATIVAS = [
    {"data": "2026-04-10", "moto_id": "moto_1", "hodometro": 58098, "componente": "Bateria (Partida Elétrica)", "oficina": "Poty", "valor_peca": 180.0, "valor_total": 180.0, "obs": "Retroativo pré-ciclo"},
    {"data": "2026-07-24", "moto_id": "moto_1", "hodometro": 68824, "componente": "Par de Pneus", "oficina": "Amaral", "valor_peca": 288.0, "valor_total": 308.0, "obs": "Retroativo pré-ciclo"},
    {"data": "2026-08-05", "moto_id": "moto_1", "hodometro": 70050, "componente": "Limpeza/Regulagem Carburador", "oficina": "Mineiro", "valor_peca": 120.0, "valor_total": 120.0, "obs": "Retroativo pré-ciclo"},
    {"data": "2026-08-05", "moto_id": "moto_1", "hodometro": 70050, "componente": "Cabos + Lubrificação", "oficina": "Mineiro", "valor_peca": 30.0, "valor_total": 45.0, "obs": "Retroativo pré-ciclo"},
    {"data": "2026-09-18", "moto_id": "moto_1", "hodometro": 74545, "componente": "Pastilha Freio Dianteiro (ESD)", "oficina": "Amaral", "valor_peca": 60.0, "valor_total": 60.0, "obs": "Retroativo pré-ciclo"},
    {"data": "2026-09-18", "moto_id": "moto_1", "hodometro": 74545, "componente": "Lona Freio Traseiro", "oficina": "Amaral", "valor_peca": 40.0, "valor_total": 40.0, "obs": "Retroativo pré-ciclo"},
    {"data": "2026-09-23", "moto_id": "moto_1", "hodometro": 75056, "componente": "Kit Relação / Transmissão", "oficina": "Amaral", "valor_peca": 165.0, "valor_total": 225.0, "obs": "Retroativo pré-ciclo"},
    {"data": "2026-11-14", "moto_id": "moto_1", "hodometro": 80346, "componente": "Troca de Óleo", "oficina": "Amaral", "valor_peca": 30.0, "valor_total": 34.0, "obs": "Retroativo pré-ciclo"}
]

def get_default_data():
    base = CATALOGO_MOTOS["Honda NXR 150 Bros ESD 2008 (Carburada)"]
    return {
        "moto_ativa_id": "moto_1",
        "motos": [
            {
                "id": "moto_1",
                "apelido": "Bros 150 ESD 2008",
                "modelo": "Honda NXR 150 Bros ESD 2008 (Carburada)",
                "hodometro": 81185,
                "preco_gasolina": base["preco_gasolina"],
                "consumo_kml": base["consumo_kml"],
                "seguro_anual": base["seguro_anual"],
                "licenciamento_anual": base["licenciamento_anual"],
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
            m.setdefault("hodometro", 0)
            m.setdefault("preco_gasolina", 5.99)
            m.setdefault("consumo_kml", 30.0)
            m.setdefault("seguro_anual", 900.0)
            m.setdefault("licenciamento_anual", 174.08)
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

    if "abastecimentos" not in raw or not isinstance(raw["abastecimentos"], list):
        raw["abastecimentos"] = []

    return raw

def get_supabase():
    if not HAS_SUPABASE:
        return None
    try:
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None

def load_state(user_key):
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("user_states").select("state_json").eq("user_key", user_key).execute()
            if res.data and len(res.data) > 0:
                return migrate_data(res.data[0]["state_json"]), True
        except Exception:
            pass
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return migrate_data(json.load(f)), False
        except Exception:
            pass
    return get_default_data(), bool(sb)

def save_state(user_key, data):
    sb = get_supabase()
    if sb:
        try:
            sb.table("user_states").upsert({"user_key": user_key, "state_json": data}).execute()
        except Exception:
            pass
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def calc_custos_moto(m):
    gas_km = float(m["preco_gasolina"]) / max(float(m["consumo_kml"]), 1.0)
    fixos_km = (float(m["seguro_anual"]) + float(m["licenciamento_anual"])) / max(float(m["projecao_anual_km"]), 1.0)
    pecas_km = sum(float(p["custo"]) / max(float(p["intervalo"]), 1.0) for p in m.get("pecas", []))
    reserva_km = fixos_km + pecas_km
    total_km = gas_km + reserva_km
    return gas_km, reserva_km, total_km

def buscar_enderecos_online(query):
    if not query or len(query.strip()) < 3:
        return []
    resultados = []
    try:
        q_enc = urllib.parse.quote(query.strip())
        url = f"https://photon.komoot.io/api/?q={q_enc}&limit=5&lang=pt&lat=-22.357&lon=-47.384"
        req = urllib.request.Request(url, headers={"User-Agent": "RaioXEntregador/1.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for feat in data.get("features", []):
                props = feat.get("properties", {})
                coords = feat.get("geometry", {}).get("coordinates", [])
                if props.get("countrycode", "BR") != "BR":
                    continue
                partes = [
                    props.get("street") or props.get("name", ""),
                    props.get("housenumber", ""),
                    props.get("district", ""),
                    props.get("city", ""),
                    props.get("state", "")
                ]
                label = ", ".join([p for p in partes if p])
                if label and len(coords) == 2:
                    resultados.append((label, (coords[1], coords[0])))
    except Exception:
        pass
    return resultados

def calcular_rota_osrm(coord1, coord2):
    try:
        lat1, lon1 = coord1
        lat2, lon2 = coord2
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
        req = urllib.request.Request(url, headers={"User-Agent": "RaioXEntregador/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") == "Ok" and data.get("routes"):
                r = data["routes"][0]
                return round(r["distance"] / 1000.0, 2), round(r["duration"] / 60.0)
    except Exception:
        pass
    return None, None

# --- SIDEBAR ---
with st.sidebar:
    st.header("☁️ Sincronização")
    default_key = "wil_bros150"
    try:
        default_key = st.secrets.get("DEFAULT_USER_KEY", "wil_bros150")
    except Exception:
        pass
    user_key = st.text_input("Código da Conta:", value=default_key)
    if st.button("Recarregar Dados da Nuvem", use_container_width=True):
        st.session_state.pop("db", None)
        st.rerun()

if "db" not in st.session_state or st.session_state.get("loaded_key") != user_key:
    loaded_db, cloud_ok = load_state(user_key)
    st.session_state.db = migrate_data(loaded_db)
    st.session_state.loaded_key = user_key
    st.session_state.cloud_ok = cloud_ok
else:
    st.session_state.db = migrate_data(st.session_state.db)

db = st.session_state.db

with st.sidebar:
    if st.session_state.get("cloud_ok"):
        st.success("Conectado ao Supabase (Nuvem Ativa)")
    else:
        st.warning("Modo Local (Arquivo JSON)")

# --- HEADER & MOTO ATIVA ---
motos_dict = {m["id"]: m for m in db["motos"]}
col_t1, col_t2 = st.columns([1.6, 1])
col_t1.title("🏍️ Raio-X do Entregador")
moto_escolhida_id = col_t2.selectbox(
    "Moto Ativa no Turno:",
    options=list(motos_dict.keys()),
    format_func=lambda mid: motos_dict[mid]["apelido"],
    index=list(motos_dict.keys()).index(db["moto_ativa_id"])
)
if moto_escolhida_id != db["moto_ativa_id"]:
    db["moto_ativa_id"] = moto_escolhida_id
    save_state(user_key, db)
    st.rerun()

moto_ativa = motos_dict[db["moto_ativa_id"]]
custo_gas_km, custo_reserva_km, custo_total_km = calc_custos_moto(moto_ativa)

st.caption(
    f"**{moto_ativa['apelido']}** • Hodômetro: **{int(moto_ativa['hodometro']):,} km** • "
    f"Custo Real: **R$ {custo_total_km:.3f}/km** (Gasolina R$ {custo_gas_km:.3f} + Reserva R$ {custo_reserva_km:.3f})"
)

with st.expander("💡 Como funciona o Raio-X? (Guia Rápido em 3 Passos)"):
    st.markdown(
        "1. **Garagem:** Ajuste o preço da gasolina, consumo e peças da sua moto para descobrir seu **Custo Real por Km**.
"
        "2. **Simular & Orçar:** Antes de aceitar uma entrega ou passar preço para cliente, calcule o **Lucro Líquido Real** já descontando desgaste e combustível.
"
        "3. **Meu Dia & Termômetro CLT:** No fim do turno, lance os km rodados e ganhos. O app separa a **Caixinha da Moto** e mostra se você ganhou acima do **Piso CLT + 30% Periculosidade**."
    )

PISO_CLT_MENSAL = 3254.46
META_CLT_DIARIA = PISO_CLT_MENSAL / 26.0

tab_hoje, tab_sim, tab_garagem, tab_clt = st.tabs([
    "📊 1. Meu Dia",
    "⚡ 2. Simular & Orçar",
    "🔧 3. Garagem & Custos",
    "⚖️ 4. Termômetro CLT"
])

# ==========================================
# ABA 1: MEU DIA (TURNOS)
# ==========================================
with tab_hoje:
    filtro_visao = st.radio("Exibir resultados de:", ["Apenas Moto Ativa", "Todas as Motos"], horizontal=True)
    turnos_filtrados = [
        t for t in db["turnos"]
        if filtro_visao == "Todas as Motos" or t.get("moto_id") == moto_ativa["id"]
    ]

    total_km = sum(t["km"] for t in turnos_filtrados)
    total_bruto = sum(t["bruto"] for t in turnos_filtrados)
    total_extras = sum(t.get("extras", 0.0) for t in turnos_filtrados)

    total_gas = 0.0
    total_reserva = 0.0
    for t in turnos_filtrados:
        m_ref = motos_dict.get(t.get("moto_id"), moto_ativa)
        g_km, r_km, _ = calc_custos_moto(m_ref)
        total_gas += t["km"] * g_km
        total_reserva += t["km"] * r_km

    lucro_liquido = total_bruto - total_gas - total_reserva - total_extras

    c1, c2, c3 = st.columns(3)
    c1.metric("Lucro Líquido Real", f"R$ {lucro_liquido:.2f}")
    c2.metric("Faturamento Bruto", f"R$ {total_bruto:.2f}")
    c3.metric("Km Rodados", f"{total_km:,} km")

    st.info(
        f"💰 **Caixinha da Moto (Não Gastar):** Separe **R$ {total_gas + total_reserva:.2f}** "
        f"(**R$ {total_gas:.2f}** Gasolina + **R$ {total_reserva:.2f}** Reserva Manutenção/Fixos)"
    )

    with st.expander("➕ Registrar Novo Turno (Fechamento Rápido)", expanded=True):
        with st.form("form_turno"):
            col_d, col1, col2 = st.columns([1.2, 1, 1])
            data_turno = col_d.date_input("Data", value=date.today())
            km_ini = col1.number_input("Km Inicial", value=int(moto_ativa["hodometro"]), step=1)
            km_fim = col2.number_input("Km Final", value=int(moto_ativa["hodometro"]), step=1)

            col3, col4 = st.columns(2)
            ganho_app = col3.number_input("Ganhos Apps / iFood-Bee (R$)", min_value=0.0, step=5.0)
            gastos_extras = col4.number_input("Gastos Extras no Dia (R$)", min_value=0.0, step=5.0)

            col5, col6 = st.columns(2)
            estabelecimento = col5.selectbox("Estabelecimento", options=ESTABELECIMENTOS_LISTA)
            ganho_fixo = col6.number_input("Ganho no Estabelecimento (R$)", min_value=0.0, step=5.0)

            if st.form_submit_button("Salvar Turno", use_container_width=True):
                dist = km_fim - km_ini
                bruto_dia = ganho_app + ganho_fixo
                if dist <= 0:
                    st.error("O Km Final deve ser maior que o Km Inicial.")
                else:
                    local_reg = estabelecimento if ganho_fixo > 0 else "iFood / Apps"
                    if ganho_app > 0 and ganho_fixo > 0:
                        local_reg = f"Apps + {estabelecimento}"

                    db["turnos"].append({
                        "data": str(data_turno),
                        "moto_id": moto_ativa["id"],
                        "km_ini": km_ini,
                        "km_fim": km_fim,
                        "km": dist,
                        "ganho_app": ganho_app,
                        "estabelecimento": local_reg,
                        "ganho_estab": ganho_fixo,
                        "bruto": bruto_dia,
                        "extras": gastos_extras,
                        "custo_km": round(custo_total_km, 4)
                    })
                    if km_fim > moto_ativa["hodometro"]:
                        moto_ativa["hodometro"] = km_fim
                    save_state(user_key, db)
                    st.success(f"Turno salvo! +{dist} km ({local_reg}).")
                    st.rerun()

    if turnos_filtrados:
        st.subheader("Histórico de Turnos")
        rows = []
        for t in turnos_filtrados:
            m_ref = motos_dict.get(t.get("moto_id"), moto_ativa)
            _, _, c_km_ref = calc_custos_moto(m_ref)
            liq = t["bruto"] - (t["km"] * c_km_ref) - t.get("extras", 0.0)
            rows.append({
                "Data": t["data"],
                "Moto": m_ref["apelido"],
                "Origem": t["estabelecimento"],
                "Km": t["km"],
                "Bruto (R$)": round(t["bruto"], 2),
                "Líquido (R$)": round(liq, 2)
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with st.expander("🗑️ Excluir um turno lançado errado"):
            opcoes_ex = [
                f"{i} | {t['data']} — {t['estabelecimento']} ({t['km']} km | R$ {t['bruto']:.2f})"
                for i, t in enumerate(db["turnos"])
            ]
            sel_ex = st.selectbox("Selecione o turno:", options=opcoes_ex)
            if st.button("Confirmar Exclusão do Turno", type="primary"):
                idx_rem = int(sel_ex.split(" | ")[0])
                db["turnos"].pop(idx_rem)
                save_state(user_key, db)
                st.rerun()

# ==========================================
# ABA 2: SIMULAR & ORÇAR
# ==========================================
with tab_sim:
    modo_sim = st.radio("Modo:", ["⚡ Simular Corrida de App", "🧾 Calcular Orçamento para Cliente"], horizontal=True)

    if modo_sim == "⚡ Simular Corrida de App":
        col_s1, col_s2 = st.columns(2)
        val_corrida = col_s1.number_input("Valor Ofertado (R$)", min_value=0.0, value=12.0, step=0.5)
        dist_corrida = col_s2.number_input("Distância Total até Entrega (km)", min_value=0.1, value=6.0, step=0.5)

        custo_c = dist_corrida * custo_total_km
        lucro_c = val_corrida - custo_c
        liq_km = lucro_c / dist_corrida if dist_corrida > 0 else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Lucro Líquido", f"R$ {lucro_c:.2f}")
        m2.metric("Custo Moto", f"- R$ {custo_c:.2f}")
        m3.metric("Líquido / Km", f"R$ {liq_km:.2f}/km")

        if liq_km >= 1.30:
            st.success("✅ **CORRIDA BOA:** Acima da meta de rentabilidade líquida!")
        elif liq_km >= 0.80:
            st.warning("⚠️ **EMPATE / ATENÇÃO:** Margem apertada, avalie o trânsito.")
        else:
            st.error("🚨 **FURADA / PREJUÍZO:** Abaixo do mínimo viável.")

    else:
        st.subheader("Cálculo de Rota e Orçamento")
        modo_partida = st.radio(
            "Deslocamento até a retirada:",
            ["📍 Estou no local / Não cobrar deslocamento", "📡 Meu GPS Atual (HTTPS)", "🏍️ Digitar Rua onde estou"],
            horizontal=True
        )

        coord_partida = None
        if modo_partida == "📡 Meu GPS Atual (HTTPS)":
            if HAS_GEO:
                loc = get_geolocation()
                if loc and "coords" in loc:
                    coord_partida = (loc["coords"]["latitude"], loc["coords"]["longitude"])
                    st.success(f"GPS capturado: {coord_partida[0]:.5f}, {coord_partida[1]:.5f}")
                else:
                    st.info("Aguardando permissão de localização no navegador...")
            else:
                st.warning("Pacote streamlit-js-eval não instalado.")
        elif modo_partida == "🏍️ Digitar Rua onde estou":
            if HAS_SEARCHBOX:
                res_part = st_searchbox(buscar_enderecos_online, placeholder="Ex: Av. Loreto, Araras", key="sb_part")
                if res_part:
                    coord_partida = res_part

        col_e1, col_e2 = st.columns([3, 1])
        coord_retirada, label_retirada = None, ""
        with col_e1:
            if HAS_SEARCHBOX:
                res_ret = st_searchbox(buscar_enderecos_online, placeholder="Endereço de Retirada (Rua, Cidade)", key="sb_ret")
                if res_ret:
                    coord_retirada = res_ret
                    label_retirada = "Endereço de Retirada"
            else:
                label_retirada = st.text_input("Endereço de Retirada")
        num_ret = col_e2.text_input("Nº / Compl. (Ret.)", key="num_ret")

        col_e3, col_e4 = st.columns([3, 1])
        coord_entrega, label_entrega = None, ""
        with col_e3:
            if HAS_SEARCHBOX:
                res_ent = st_searchbox(buscar_enderecos_online, placeholder="Endereço de Entrega (Rua, Cidade)", key="sb_ent")
                if res_ent:
                    coord_entrega = res_ent
                    label_entrega = "Endereço de Entrega"
            else:
                label_entrega = st.text_input("Endereço de Entrega")
        num_ent = col_e4.text_input("Nº / Compl. (Ent.)", key="num_ent")

        km_desloc = 0.0
        km_entrega_auto = 6.0
        if coord_retirada and coord_entrega:
            d_ent, t_ent = calcular_rota_osrm(coord_retirada, coord_entrega)
            if d_ent:
                km_entrega_auto = d_ent
                st.caption(f"Rota Retirada ➔ Entrega: **{d_ent} km** (~{t_ent} min)")
            if coord_partida:
                d_desl, _ = calcular_rota_osrm(coord_partida, coord_retirada)
                if d_desl:
                    km_desloc = d_desl
                    st.caption(f"Deslocamento até Retirada: **{d_desl} km**")

        col_o1, col_o2, col_o3 = st.columns(3)
        km_entrega = col_o1.number_input("Km Entrega", min_value=0.1, value=float(km_entrega_auto), step=0.5)
        valor_km_cobrar = col_o2.number_input("Cobrar por Km (R$)", min_value=0.5, value=2.0, step=0.25)
        taxa_minima = col_o3.number_input("Taxa Mínima (R$)", min_value=0.0, value=8.0, step=1.0)

        cobrar_desloc = st.checkbox("Incluir km de deslocamento até retirada no preço ao cliente", value=False)
        km_cobrado = km_entrega + (km_desloc if cobrar_desloc else 0.0)
        km_rodado_real = km_entrega + km_desloc

        preco_cliente = max(taxa_minima, round(km_cobrado * valor_km_cobrar, 2))
        custo_operacional_orc = km_rodado_real * custo_total_km
        lucro_orc = preco_cliente - custo_operacional_orc

        oc1, oc2, oc3 = st.columns(3)
        oc1.metric("Valor ao Cliente", f"R$ {preco_cliente:.2f}")
        oc2.metric("Seu Custo Moto", f"- R$ {custo_operacional_orc:.2f}")
        oc3.metric("Seu Lucro Líquido", f"R$ {lucro_orc:.2f}")

        txt_ret = f"{label_retirada} {num_ret}".strip() or "Ponto de Coleta"
        txt_ent = f"{label_entrega} {num_ent}".strip() or "Destino"
        msg_whats = "
".join([
            "🏍️ *ORÇAMENTO DE ENTREGA*",
            f"📍 *Retirada:* {txt_ret}",
            f"🏁 *Entrega:* {txt_ent}",
            f"📏 *Distância:* {km_cobrado:.1f} km",
            f"💰 *Valor Total:* R$ {preco_cliente:.2f}"
        ])
        st.text_area("Mensagem pronta para copiar e enviar no WhatsApp:", value=msg_whats, height=135)

# ==========================================
# ABA 3: GARAGEM, ABASTECIMENTOS & MANUTENÇÕES
# ==========================================
with tab_garagem:
    sub_pecas, sub_manut, sub_abast, sub_config = st.tabs([
        "🔧 Saúde das Peças",
        "🛠️ Manutenções (Previsto x Real)",
        "⛽ Abastecimentos (Gasolina)",
        "⚙️ Config. & Nova Moto"
    ])

    # --- SUB-ABA 3.1: SAÚDE DAS PEÇAS ---
    with sub_pecas:
        st.subheader(f"Desgaste Preventivo — {moto_ativa['apelido']}")
        for idx, p in enumerate(moto_ativa.get("pecas", [])):
            rodados = int(moto_ativa["hodometro"]) - int(p["ultima_km"])
            restantes = int(p["intervalo"]) - rodados
            pct = min(max(rodados / max(int(p["intervalo"]), 1), 0.0), 1.0)
            status_icon = "🟢 OK" if restantes > p["intervalo"] * 0.15 else ("🟡 ATENÇÃO" if restantes > 0 else "🔴 VENCIDO")

            cp1, cp2 = st.columns([3.5, 1.2])
            cp1.markdown(f"**{p['nome']}** — {status_icon} (`{restantes:,} km restantes` | Base: R$ {p['custo']:.0f})")
            cp1.progress(pct)
            if cp2.button("Troquei Hoje", key=f"troca_{moto_ativa['id']}_{idx}", use_container_width=True):
                p["ultima_km"] = int(moto_ativa["hodometro"])
                db["manutencoes"].append({
                    "data": str(date.today()),
                    "moto_id": moto_ativa["id"],
                    "hodometro": int(moto_ativa["hodometro"]),
                    "componente": p["nome"],
                    "oficina": "Troca Rápida",
                    "valor_peca": float(p["custo"]),
                    "valor_total": float(p["custo"]),
                    "obs": "Registrado pelo botão Troquei Hoje"
                })
                save_state(user_key, db)
                st.toast(f"{p['nome']} zerado em {moto_ativa['hodometro']} km!")
                st.rerun()

    # --- SUB-ABA 3.2: MANUTENÇÕES (DAQUI PRA FRENTE) ---
    with sub_manut:
        st.subheader("Balanço Caixinha: Previsto vs. Gasto Real")
        st.caption(f"Considerando apenas turnos e manutenções a partir de **{DATA_INICIO_CICLO}** (histórico anterior mantido apenas para alertas de km).")

        turnos_ciclo = [
            t for t in db["turnos"]
            if t.get("moto_id") == moto_ativa["id"] and t["data"] >= DATA_INICIO_CICLO
        ]
        km_ciclo = sum(t["km"] for t in turnos_ciclo)
        reservado_manut_ciclo = km_ciclo * custo_reserva_km

        manut_moto = [m for m in db.get("manutencoes", []) if m.get("moto_id") == moto_ativa["id"]]
        manut_ciclo = [m for m in manut_moto if m["data"] >= DATA_INICIO_CICLO]
        gasto_real_ciclo = sum(float(m["valor_total"]) for m in manut_ciclo)
        saldo_caixinha_manut = reservado_manut_ciclo - gasto_real_ciclo

        bm1, bm2, bm3 = st.columns(3)
        bm1.metric("Reservado na Caixinha", f"R$ {reservado_manut_ciclo:.2f}")
        bm2.metric("Gasto Real (Pós-22/11)", f"R$ {gasto_real_ciclo:.2f}")
        bm3.metric("Saldo da Reserva", f"R$ {saldo_caixinha_manut:+.2f}")

        with st.expander("➕ Registrar Nova Manutenção / Serviço Feito", expanded=True):
            nomes_pecas = [p["nome"] for p in moto_ativa.get("pecas", [])] + ["Outro Serviço / Peça Avulsa"]
            with st.form("form_nova_manut"):
                fm1, fm2, fm3 = st.columns(3)
                data_m = fm1.date_input("Data do Serviço", value=date.today())
                odo_m = fm2.number_input("Hodômetro (km)", value=int(moto_ativa["hodometro"]), step=1)
                comp_m = fm3.selectbox("Componente / Serviço", options=nomes_pecas)

                fm4, fm5, fm6 = st.columns(3)
                oficina_m = fm4.text_input("Oficina / Loja", placeholder="Ex: Amaral")
                val_peca_m = fm5.number_input("Valor Peça (R$)", min_value=0.0, step=5.0)
                val_total_m = fm6.number_input("Valor Total Pago (R$)", min_value=0.0, step=5.0)

                obs_m = st.text_input("Observações (opcional)")
                atualizar_peca = st.checkbox("Atualizar hodômetro de troca e custo base desta peça na Garagem", value=True)

                if st.form_submit_button("Salvar Manutenção", use_container_width=True):
                    db["manutencoes"].append({
                        "data": str(data_m),
                        "moto_id": moto_ativa["id"],
                        "hodometro": int(odo_m),
                        "componente": comp_m,
                        "oficina": oficina_m or "Não informada",
                        "valor_peca": float(val_peca_m),
                        "valor_total": float(val_total_m),
                        "obs": obs_m
                    })
                    if atualizar_peca:
                        for p in moto_ativa.get("pecas", []):
                            if p["nome"] == comp_m:
                                p["ultima_km"] = int(odo_m)
                                if val_total_m > 0:
                                    p["custo"] = float(val_total_m)
                    if int(odo_m) > int(moto_ativa["hodometro"]):
                        moto_ativa["hodometro"] = int(odo_m)
                    save_state(user_key, db)
                    st.success("Manutenção registrada com sucesso!")
                    st.rerun()

        if manut_moto:
            st.markdown("#### Histórico Completo de Serviços")
            df_m = pd.DataFrame(manut_moto).sort_values(by="data", ascending=False)
            df_m["Período"] = df_m["data"].apply(lambda d: "Ciclo Atual" if d >= DATA_INICIO_CICLO else "Pré-Ciclo (Ref.)")
            st.dataframe(
                df_m[["data", "Período", "hodometro", "componente", "oficina", "valor_total", "obs"]].rename(
                    columns={"data": "Data", "hodometro": "Km", "componente": "Serviço", "oficina": "Oficina", "valor_total": "Pago (R$)", "obs": "Obs."}
                ),
                use_container_width=True,
                hide_index=True
            )

    # --- SUB-ABA 3.3: ABASTECIMENTOS (GASOLINA PREVISTA X REAL) ---
    with sub_abast:
        st.subheader("Controle de Combustível: Previsto vs. Bomba")
        turnos_ciclo_gas = [
            t for t in db["turnos"]
            if t.get("moto_id") == moto_ativa["id"] and t["data"] >= DATA_INICIO_CICLO
        ]
        km_ciclo_gas = sum(t["km"] for t in turnos_ciclo_gas)
        gas_prevista_ciclo = km_ciclo_gas * custo_gas_km

        abast_moto = [
            a for a in db.get("abastecimentos", [])
            if a.get("moto_id") == moto_ativa["id"] and a["data"] >= DATA_INICIO_CICLO
        ]
        gas_real_bomba = sum(float(a["valor_pago"]) for a in abast_moto)
        litros_totais = sum(float(a["litros"]) for a in abast_moto)
        saldo_gas = gas_prevista_ciclo - gas_real_bomba

        ga1, ga2, ga3 = st.columns(3)
        ga1.metric("Reservado Gasolina", f"R$ {gas_prevista_ciclo:.2f}")
        ga2.metric("Pago na Bomba", f"R$ {gas_real_bomba:.2f}")
        ga3.metric("Diferença (Previsto - Real)", f"R$ {saldo_gas:+.2f}")

        if litros_totais > 0 and km_ciclo_gas > 0:
            consumo_real = km_ciclo_gas / litros_totais
            st.caption(f"Consumo médio estimado no ciclo: **{consumo_real:.1f} km/L** (Parâmetro configurado: {moto_ativa['consumo_kml']} km/L)")

        with st.expander("⛽ Registrar Novo Abastecimento", expanded=True):
            with st.form("form_abastecimento"):
                fa1, fa2, fa3, fa4 = st.columns(4)
                data_a = fa1.date_input("Data", value=date.today())
                odo_a = fa2.number_input("Hodômetro (km)", value=int(moto_ativa["hodometro"]), step=1)
                litros_a = fa3.number_input("Litros", min_value=0.1, value=10.0, step=0.5, format="%.2f")
                valor_a = fa4.number_input("Valor Pago (R$)", min_value=1.0, value=59.90, step=1.0, format="%.2f")
                posto_a = st.text_input("Posto / Observação (opcional)")

                if st.form_submit_button("Salvar Abastecimento", use_container_width=True):
                    preco_l_calc = round(valor_a / litros_a, 2)
                    db["abastecimentos"].append({
                        "data": str(data_a),
                        "moto_id": moto_ativa["id"],
                        "hodometro": int(odo_a),
                        "litros": float(litros_a),
                        "valor_pago": float(valor_a),
                        "preco_litro": preco_l_calc,
                        "posto": posto_a
                    })
                    if int(odo_a) > int(moto_ativa["hodometro"]):
                        moto_ativa["hodometro"] = int(odo_a)
                    save_state(user_key, db)
                    st.success(f"Abastecimento registrado! (R$ {preco_l_calc:.2f}/L)")
                    st.rerun()

        if abast_moto:
            df_a = pd.DataFrame(abast_moto).sort_values(by="data", ascending=False)
            st.dataframe(
                df_a[["data", "hodometro", "litros", "preco_litro", "valor_pago", "posto"]].rename(
                    columns={"data": "Data", "hodometro": "Km", "litros": "Litros", "preco_litro": "R$/L", "valor_pago": "Total (R$)", "posto": "Posto"}
                ),
                use_container_width=True,
                hide_index=True
            )

    # --- SUB-ABA 3.4: CONFIGURAÇÕES & NOVA MOTO ---
    with sub_config:
        st.subheader(f"Parâmetros — {moto_ativa['apelido']}")
        with st.form("form_cfg_moto"):
            cg1, cg2, cg3 = st.columns(3)
            novo_apelido = cg1.text_input("Apelido da Moto", value=moto_ativa["apelido"])
            novo_odo = cg2.number_input("Hodômetro Atual (km)", value=int(moto_ativa["hodometro"]), step=1)
            novo_gas = cg3.number_input("Gasolina Base (R$/L)", value=float(moto_ativa["preco_gasolina"]), step=0.05, format="%.2f")

            cg4, cg5, cg6 = st.columns(3)
            novo_kml = cg4.number_input("Consumo Base (km/L)", value=float(moto_ativa["consumo_kml"]), step=0.5, format="%.1f")
            novo_seg = cg5.number_input("Seguro Anual (R$)", value=float(moto_ativa["seguro_anual"]), step=10.0, format="%.2f")
            novo_lic = cg6.number_input("IPVA/Licenc. (R$)", value=float(moto_ativa["licenciamento_anual"]), step=5.0, format="%.2f")

            if st.form_submit_button("Salvar Configurações da Moto", use_container_width=True):
                moto_ativa["apelido"] = novo_apelido
                moto_ativa["hodometro"] = int(novo_odo)
                moto_ativa["preco_gasolina"] = float(novo_gas)
                moto_ativa["consumo_kml"] = float(novo_kml)
                moto_ativa["seguro_anual"] = float(novo_seg)
                moto_ativa["licenciamento_anual"] = float(novo_lic)
                save_state(user_key, db)
                st.success("Configurações atualizadas!")
                st.rerun()

        st.divider()
        st.subheader("➕ Cadastrar Outra Moto (Multi-Moto)")
        with st.form("form_add_moto"):
            am1, am2, am3 = st.columns([1.2, 1.5, 1])
            apelido_nova = am1.text_input("Apelido (ex: CG Reserva)")
            modelo_cat = am2.selectbox("Modelo Pré-Calibrado", options=list(CATALOGO_MOTOS.keys()))
            odo_nova = am3.number_input("Hodômetro Atual", min_value=0, value=0, step=100)

            if st.form_submit_button("Cadastrar e Ativar Nova Moto", use_container_width=True):
                if not apelido_nova.strip():
                    st.error("Informe um apelido para a moto.")
                else:
                    novo_id = f"moto_{len(db['motos']) + 1}_{int(date.today().strftime('%d%H%M'))}"
                    tpl = CATALOGO_MOTOS[modelo_cat]
                    pecas_novas = []
                    for p in tpl["pecas"]:
                        p_copy = dict(p)
                        p_copy["ultima_km"] = int(odo_nova)
                        pecas_novas.append(p_copy)

                    db["motos"].append({
                        "id": novo_id,
                        "apelido": apelido_nova.strip(),
                        "modelo": modelo_cat,
                        "hodometro": int(odo_nova),
                        "preco_gasolina": tpl["preco_gasolina"],
                        "consumo_kml": tpl["consumo_kml"],
                        "seguro_anual": tpl["seguro_anual"],
                        "licenciamento_anual": tpl["licenciamento_anual"],
                        "projecao_anual_km": tpl["projecao_anual_km"],
                        "pecas": pecas_novas
                    })
                    db["moto_ativa_id"] = novo_id
                    save_state(user_key, db)
                    st.success(f"Moto '{apelido_nova}' cadastrada e ativada!")
                    st.rerun()

# ==========================================
# ABA 4: TERMÔMETRO CLT
# ==========================================
with tab_clt:
    st.subheader("Comparativo Real vs. Piso CLT (+30% Periculosidade)")
    dias_unicos = len(set(t["data"] for t in db["turnos"]))
    km_total_clt = sum(t["km"] for t in db["turnos"])
    bruto_total_clt = sum(t["bruto"] for t in db["turnos"])

    custo_total_periodo = 0.0
    for t in db["turnos"]:
        m_ref = motos_dict.get(t.get("moto_id"), moto_ativa)
        _, _, c_km_ref = calc_custos_moto(m_ref)
        custo_total_periodo += (t["km"] * c_km_ref) + t.get("extras", 0.0)

    liquido_total_clt = bruto_total_clt - custo_total_periodo
    meta_proporcional = dias_unicos * META_CLT_DIARIA
    empate_bruto = meta_proporcional + custo_total_periodo
    indice_clt = (liquido_total_clt / meta_proporcional * 100) if meta_proporcional > 0 else 0

    st.metric(
        "Índice de Remuneração Real (% do Piso CLT)",
        f"{indice_clt:.1f}%",
        delta=f"R$ {liquido_total_clt - meta_proporcional:+.2f} vs CLT ({dias_unicos} dias)"
    )

    c_clt1, c_clt2 = st.columns(2)
    c_clt1.metric("Meta Líquida CLT (Período)", f"R$ {meta_proporcional:.2f}")
    c_clt2.metric("Faturamento Bruto de Empate", f"R$ {empate_bruto:.2f}")

    st.caption(
        f"Base CLT 2026: **R$ {PISO_CLT_MENSAL:.2f}/mês** (Salário Mínimo R$ 1.621 + 30% Periculosidade R$ 486,30 + "
        f"13º + Férias 1/3 + FGTS + INSS MEI + Vale-Alimentação = **R$ {META_CLT_DIARIA:.2f}/dia**)."
    )
