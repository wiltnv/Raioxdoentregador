import streamlit as st
import pandas as pd
import json
import os
import urllib.request
import urllib.parse
from datetime import date

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

try:
    from supabase import create_client, Client
    HAS_SUPABASE_LIB = True
except ImportError:
    HAS_SUPABASE_LIB = False

st.set_page_config(page_title="Raio-X do Entregador", page_icon="🏍️", layout="centered")

DATA_FILE = "dados_entregador.json"

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
        "consumo_kml": 29.0,
        "seguro_anual": 984.08,
        "licenciamento_anual": 174.08,
        "projecao_anual_km": 37286.64,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "custo": 34.0},
            {"nome": "Limpeza/Regulagem Carburador", "intervalo": 12000, "custo": 120.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 70.0},
            {"nome": "Pastilha Freio Dianteiro (ESD)", "intervalo": 12000, "custo": 65.0},
            {"nome": "Lona Freio Traseiro", "intervalo": 15000, "custo": 65.0},
            {"nome": "Cabos + Lubrificação", "intervalo": 15000, "custo": 120.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "custo": 225.0},
            {"nome": "Par de Pneus", "intervalo": 30000, "custo": 550.0},
            {"nome": "Bateria (Partida Elétrica)", "intervalo": 50000, "custo": 160.0}
        ]
    },
    "Honda CG 160 Titan / Fan / Start (Flex)": {
        "consumo_kml": 35.0,
        "seguro_anual": 1100.00,
        "licenciamento_anual": 380.00,
        "projecao_anual_km": 40000.0,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "custo": 38.0},
            {"nome": "Limpeza Bico Injetor / Corpo TBI", "intervalo": 15000, "custo": 110.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 75.0},
            {"nome": "Pastilha Freio Dianteiro", "intervalo": 12000, "custo": 60.0},
            {"nome": "Lona Freio Traseiro", "intervalo": 15000, "custo": 60.0},
            {"nome": "Cabos + Lubrificação", "intervalo": 15000, "custo": 100.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "custo": 190.0},
            {"nome": "Par de Pneus", "intervalo": 30000, "custo": 520.0},
            {"nome": "Bateria", "intervalo": 50000, "custo": 170.0}
        ]
    },
    "Yamaha Factor / Fazer 150 (Flex)": {
        "consumo_kml": 36.0,
        "seguro_anual": 1050.00,
        "licenciamento_anual": 380.00,
        "projecao_anual_km": 40000.0,
        "pecas": [
            {"nome": "Troca de Óleo + Filtro", "intervalo": 2000, "custo": 48.0},
            {"nome": "Limpeza Sistema Injeção", "intervalo": 15000, "custo": 110.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 80.0},
            {"nome": "Pastilha Freio Dianteiro", "intervalo": 12000, "custo": 65.0},
            {"nome": "Lona Freio Traseiro", "intervalo": 15000, "custo": 65.0},
            {"nome": "Cabos + Lubrificação", "intervalo": 15000, "custo": 100.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "custo": 210.0},
            {"nome": "Par de Pneus", "intervalo": 30000, "custo": 530.0},
            {"nome": "Bateria", "intervalo": 50000, "custo": 170.0}
        ]
    },
    "Honda NXR 160 Bros (Flex)": {
        "consumo_kml": 32.0,
        "seguro_anual": 1150.00,
        "licenciamento_anual": 390.00,
        "projecao_anual_km": 38000.0,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "custo": 38.0},
            {"nome": "Limpeza Sistema Injeção", "intervalo": 15000, "custo": 120.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 80.0},
            {"nome": "Pastilha Freio Dianteiro", "intervalo": 12000, "custo": 65.0},
            {"nome": "Pastilha/Lona Freio Traseiro", "intervalo": 15000, "custo": 65.0},
            {"nome": "Cabos + Lubrificação", "intervalo": 15000, "custo": 110.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "custo": 230.0},
            {"nome": "Par de Pneus", "intervalo": 30000, "custo": 580.0},
            {"nome": "Bateria", "intervalo": 50000, "custo": 170.0}
        ]
    },
    "Yamaha Fazer / Lander 250": {
        "consumo_kml": 27.0,
        "seguro_anual": 1400.00,
        "licenciamento_anual": 480.00,
        "projecao_anual_km": 38000.0,
        "pecas": [
            {"nome": "Troca de Óleo + Filtro", "intervalo": 2500, "custo": 65.0},
            {"nome": "Limpeza Sistema Injeção", "intervalo": 15000, "custo": 140.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 95.0},
            {"nome": "Pastilha Freio Dianteiro", "intervalo": 12000, "custo": 75.0},
            {"nome": "Pastilha Freio Traseiro", "intervalo": 15000, "custo": 75.0},
            {"nome": "Cabos + Lubrificação", "intervalo": 15000, "custo": 120.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "custo": 290.0},
            {"nome": "Par de Pneus", "intervalo": 25000, "custo": 750.0},
            {"nome": "Bateria", "intervalo": 50000, "custo": 210.0}
        ]
    },
    "Personalizada (Zerar Valores)": {
        "consumo_kml": 30.0,
        "seguro_anual": 1000.00,
        "licenciamento_anual": 350.00,
        "projecao_anual_km": 36000.0,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "custo": 40.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 75.0},
            {"nome": "Freio Dianteiro", "intervalo": 12000, "custo": 65.0},
            {"nome": "Freio Traseiro", "intervalo": 15000, "custo": 65.0},
            {"nome": "Kit Relação", "intervalo": 20000, "custo": 200.0},
            {"nome": "Par de Pneus", "intervalo": 30000, "custo": 550.0},
            {"nome": "Bateria", "intervalo": 50000, "custo": 170.0}
        ]
    }
}

HISTORICO_MANUTENCOES_INICIAL = [
    {"id": "m1", "moto_id": "moto_1", "data": "2026-04-10", "hodometro": 58098, "componente": "Bateria (Partida Elétrica)", "oficina": "Poty", "valor_peca": 180.0, "valor_total": 180.0, "obs": "Troca preventiva"},
    {"id": "m2", "moto_id": "moto_1", "data": "2026-07-24", "hodometro": 68824, "componente": "Par de Pneus", "oficina": "Amaral", "valor_peca": 288.0, "valor_total": 308.0, "obs": "Dianteiro + Traseiro"},
    {"id": "m3", "moto_id": "moto_1", "data": "2026-08-05", "hodometro": 70050, "componente": "Limpeza/Regulagem Carburador", "oficina": "Mineiro", "valor_peca": 120.0, "valor_total": 120.0, "obs": "Limpeza e acerto"},
    {"id": "m4", "moto_id": "moto_1", "data": "2026-08-05", "hodometro": 70050, "componente": "Cabos + Lubrificação", "oficina": "Mineiro", "valor_peca": 30.0, "valor_total": 45.0, "obs": "Cabo acelerador"},
    {"id": "m5", "moto_id": "moto_1", "data": "2026-09-18", "hodometro": 74545, "componente": "Pastilha Freio Dianteiro (ESD)", "oficina": "Amaral", "valor_peca": 60.0, "valor_total": 60.0, "obs": "Pastilha dianteira"},
    {"id": "m6", "moto_id": "moto_1", "data": "2026-09-18", "hodometro": 74545, "componente": "Lona Freio Traseiro", "oficina": "Amaral", "valor_peca": 60.0, "valor_total": 40.0, "obs": "Lona traseira"},
    {"id": "m7", "moto_id": "moto_1", "data": "2026-09-23", "hodometro": 75056, "componente": "Kit Relação / Transmissão", "oficina": "Amaral", "valor_peca": 165.0, "valor_total": 225.0, "obs": "Kit completo"},
    {"id": "m8", "moto_id": "moto_1", "data": "2026-11-14", "hodometro": 80346, "componente": "Troca de Óleo", "oficina": "Amaral", "valor_peca": 30.0, "valor_total": 34.0, "obs": "Óleo 1L + troca"}
]

DEFAULT_DATA = {
    "moto_ativa_id": "moto_1",
    "motos": [
        {
            "id": "moto_1",
            "apelido": "Bros 150 Principal",
            "modelo": "Honda NXR 150 Bros ESD 2008 (Carburada)",
            "hodometro": 81185,
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
        }
    ],
    "turnos": [
        {
            "data": "2026-11-21",
            "moto_id": "moto_1",
            "moto_nome": "Bros 150 Principal",
            "km_ini": 81011,
            "km_fim": 81185,
            "km": 174,
            "ganho_app": 0.0,
            "estabelecimento": "Sta. Efigênia / Golden",
            "ganho_estab": 348.0,
            "bruto": 348.0,
            "extras": 0.0,
            "custo_km": 0.3266,
            "custo_reserva_km": 0.1201
        }
    ],
    "manutencoes": HISTORICO_MANUTENCOES_INICIAL
}

def get_supabase():
    if not HAS_SUPABASE_LIB:
        return None
    try:
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None

def migrate_data(data):
    if "motos" not in data and "moto" in data:
        old_moto = data.pop("moto")
        old_pecas = data.pop("pecas", [])
        data["moto_ativa_id"] = "moto_1"
        data["motos"] = [{
            "id": "moto_1",
            "apelido": "Moto Principal",
            "modelo": old_moto.get("modelo", "Honda NXR 150 Bros ESD 2008"),
            "hodometro": old_moto.get("hodometro", 81185),
            "preco_gasolina": old_moto.get("preco_gasolina", 5.99),
            "consumo_kml": old_moto.get("consumo_kml", 29.0),
            "seguro_anual": old_moto.get("seguro_anual", 984.08),
            "licenciamento_anual": old_moto.get("licenciamento_anual", 174.08),
            "projecao_anual_km": old_moto.get("projecao_anual_km", 37286.64),
            "pecas": old_pecas
        }]
    for t in data.get("turnos", []):
        t.setdefault("moto_id", "moto_1")
        t.setdefault("moto_nome", "Bros 150 Principal")
        t.setdefault("estabelecimento", "Não informado")
        t.setdefault("ganho_app", 0.0)
        t.setdefault("ganho_estab", 0.0)
        t.setdefault("custo_reserva_km", 0.1201)
    if "manutencoes" not in data:
        data["manutencoes"] = HISTORICO_MANUTENCOES_INICIAL
    return data

def load_data(user_key):
    sb = get_supabase()
    if sb and user_key:
        try:
            res = sb.table("user_states").select("state_json").eq("user_key", user_key).execute()
            if res.data and len(res.data) > 0:
                return migrate_data(res.data[0]["state_json"]), True
            else:
                initial = migrate_data(json.loads(json.dumps(DEFAULT_DATA)))
                sb.table("user_states").upsert({"user_key": user_key, "state_json": initial}).execute()
                return initial, True
        except Exception:
            pass
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return migrate_data(json.load(f)), False
    return migrate_data(json.loads(json.dumps(DEFAULT_DATA))), False

def save_data(data, user_key):
    sb = get_supabase()
    if sb and user_key:
        try:
            sb.table("user_states").upsert({"user_key": user_key, "state_json": data}).execute()
            return True
        except Exception:
            pass
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return False

def buscar_enderecos_online(termo):
    if not termo or len(termo.strip()) < 3:
        return []
    resultados = []
    try:
        query = urllib.parse.quote(termo.strip())
        url = f"https://photon.komoot.io/api/?q={query}&limit=6"
        req = urllib.request.Request(url, headers={"User-Agent": "RaioXEntregadorApp/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for feat in data.get("features", []):
                props = feat.get("properties", {})
                if props.get("countrycode", "").upper() not in ["BR", ""]:
                    continue
                coords = feat.get("geometry", {}).get("coordinates", [])
                rua = props.get("street") or props.get("name") or ""
                numero = props.get("housenumber") or ""
                bairro = props.get("district") or props.get("suburb") or ""
                cidade = props.get("city") or props.get("town") or props.get("municipality") or ""
                estado = props.get("state") or ""
                partes = []
                if rua:
                    partes.append(f"{rua}, {numero}" if numero else rua)
                if bairro:
                    partes.append(bairro)
                if cidade:
                    partes.append(f"{cidade} - {estado}" if estado else cidade)
                label = " | ".join(partes) if partes else props.get("name", "Local encontrado")
                if len(coords) == 2:
                    resultados.append((label, {"lat": coords[1], "lon": coords[0], "label": label}))
    except Exception:
        pass
    return resultados

def calcular_rota_osrm(lat1, lon1, lat2, lon2):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
        req = urllib.request.Request(url, headers={"User-Agent": "RaioXEntregadorApp/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") == "Ok" and data.get("routes"):
                rota = data["routes"][0]
                return round(rota["distance"] / 1000.0, 2), round(rota["duration"] / 60.0)
    except Exception:
        pass
    return None, None

def calc_custos_moto(m):
    c_gas = m["preco_gasolina"] / m["consumo_kml"]
    c_fixos = (m["seguro_anual"] + m["licenciamento_anual"]) / m["projecao_anual_km"]
    c_pecas = sum(p["custo"] / p["intervalo"] for p in m["pecas"])
    c_reserva = c_fixos + c_pecas
    return c_gas, c_fixos, c_pecas, c_reserva, (c_gas + c_reserva)

default_key = ""
try:
    default_key = st.secrets.get("DEFAULT_USER_KEY", "wil_bros150")
except Exception:
    default_key = "wil_bros150"

with st.sidebar:
    st.header("☁️ Conta e Sincronização")
    user_key = st.text_input("Código da Conta (PC e Celular):", value=default_key)
    if "loaded_user_key" not in st.session_state or st.session_state.loaded_user_key != user_key:
        st.session_state.db, st.session_state.cloud_ok = load_data(user_key)
        st.session_state.loaded_user_key = user_key

    if st.session_state.get("cloud_ok"):
        st.success("Conectado ao Supabase (Nuvem Ativa)")
    else:
        st.warning("Modo Local (Arquivo JSON)")
    st.caption("Use o mesmo código no navegador do celular e no computador para sincronizar.")

db = st.session_state.db

motos_dict = {m["id"]: m for m in db["motos"]}
if db["moto_ativa_id"] not in motos_dict:
    db["moto_ativa_id"] = db["motos"][0]["id"]

st.title("🏍️ Raio-X do Entregador")

with st.expander("🧭 Como funciona este aplicativo? (Guia Rápido em 3 Passos)", expanded=False):
    st.markdown("""
    1. **Configure sua moto na aba `🔧 3. Garagem & Manutenções`:** Informe o hodômetro atual, preço da gasolina e consumo médio. O app calcula quanto sua moto custa por quilômetro rodado (combustível + desgaste de peças + seguro/doc).
    2. **Antes de aceitar uma corrida, use `⚡ 2. Simular & Orçar`:** Descubra o lucro líquido real descontando o desgaste da moto ou gere um orçamento pronto para enviar ao cliente no WhatsApp.
    3. **No fim do expediente, feche o dia em `📊 1. Meu Dia (Turnos)`:** O sistema separa automaticamente sua **Caixinha da Moto** (dinheiro sagrado para gasolina e oficina) e mostra em **`⚖️ 4. Termômetro CLT`** se você está ganhando acima ou abaixo de um emprego registrado com 30% de periculosidade.
    """)

col_top1, col_top2 = st.columns([1.4, 1])
with col_top1:
    moto_ids = list(motos_dict.keys())
    idx_ativa = moto_ids.index(db["moto_ativa_id"])
    nova_ativa_id = st.selectbox(
        "Moto Ativa no Turno:",
        options=moto_ids,
        index=idx_ativa,
        format_func=lambda mid: f"{motos_dict[mid]['apelido']} ({motos_dict[mid]['hodometro']:,} km)"
    )
    if nova_ativa_id != db["moto_ativa_id"]:
        db["moto_ativa_id"] = nova_ativa_id
        save_data(db, user_key)
        st.rerun()

moto = motos_dict[db["moto_ativa_id"]]
custo_gas_km, custo_fixos_km, custo_pecas_km, custo_reserva_km, custo_total_km = calc_custos_moto(moto)

with col_top2:
    st.metric("Custo Real desta Moto", f"R$ {custo_total_km:.3f}/km", delta=f"Reserva: R$ {custo_reserva_km:.3f}/km", delta_color="off")

PISO_CLT_MENSAL = 3254.46
META_CLT_DIARIA = PISO_CLT_MENSAL / 26.0

tab_hoje, tab_sim, tab_garagem, tab_clt = st.tabs([
    "📊 1. Meu Dia (Turnos)",
    "⚡ 2. Simular & Orçar",
    "🔧 3. Garagem & Manutenções",
    "⚖️ 4. Termômetro CLT"
])

with tab_hoje:
    filtro_visao = st.radio(
        "Exibir resultados de:",
        options=["Apenas Moto Ativa", "Todas as Motos (Consolidado)"],
        horizontal=True
    )

    turnos_filtrados = [
        t for t in db["turnos"]
        if filtro_visao == "Todas as Motos (Consolidado)" or t.get("moto_id", "moto_1") == moto["id"]
    ]

    total_km = sum(t["km"] for t in turnos_filtrados)
    total_bruto = sum(t["bruto"] for t in turnos_filtrados)
    total_extras = sum(t["extras"] for t in turnos_filtrados)

    total_custo_op = 0.0
    total_gas_est = 0.0
    total_reserva_est = 0.0
    for t in turnos_filtrados:
        m_ref = motos_dict.get(t.get("moto_id", "moto_1"), moto)
        cg, _, _, cr, ct = calc_custos_moto(m_ref)
        c_usado = t.get("custo_km", ct)
        r_usado = t.get("custo_reserva_km", cr)
        total_custo_op += t["km"] * c_usado
        total_reserva_est += t["km"] * r_usado
        total_gas_est += t["km"] * max(c_usado - r_usado, cg)

    lucro_liquido = total_bruto - total_custo_op - total_extras

    c1, c2, c3 = st.columns(3)
    c1.metric("Lucro Líquido Real", f"R$ {lucro_liquido:.2f}")
    c2.metric("Faturamento Bruto", f"R$ {total_bruto:.2f}")
    c3.metric("Km Rodados", f"{total_km:,} km")

    st.info(f"💰 **Caixinha da Moto (Não Gastar):** Separe **R$ {total_custo_op:.2f}** (R$ {total_gas_est:.2f} Gasolina + R$ {total_reserva_est:.2f} Reserva Peças/Fixos)")

    with st.expander("➕ Registrar Novo Turno (Fechamento Rápido)", expanded=True):
        with st.form("form_turno"):
            col_d, col1, col2 = st.columns([1.2, 1, 1])
            data_turno = col_d.date_input("Data", value=date.today())
            km_ini = col1.number_input("Km Inicial", value=int(moto["hodometro"]), step=1)
            km_fim = col2.number_input("Km Final", value=int(moto["hodometro"]), step=1)

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
                    local_registrado = estabelecimento if ganho_fixo > 0 else "iFood / Apps"
                    if ganho_app > 0 and ganho_fixo > 0:
                        local_registrado = f"Apps + {estabelecimento}"

                    db["turnos"].append({
                        "data": str(data_turno),
                        "moto_id": moto["id"],
                        "moto_nome": moto["apelido"],
                        "km_ini": km_ini,
                        "km_fim": km_fim,
                        "km": dist,
                        "ganho_app": ganho_app,
                        "estabelecimento": local_registrado,
                        "ganho_estab": ganho_fixo,
                        "bruto": bruto_dia,
                        "extras": gastos_extras,
                        "custo_km": round(custo_total_km, 4),
                        "custo_reserva_km": round(custo_reserva_km, 4)
                    })
                    if km_fim > moto["hodometro"]:
                        moto["hodometro"] = km_fim
                    save_data(db, user_key)
                    st.success(f"Turno salvo na {moto['apelido']}! +{dist} km ({local_registrado}).")
                    st.rerun()

    if turnos_filtrados:
        st.subheader("Histórico de Turnos")
        df_turnos = pd.DataFrame(turnos_filtrados)
        df_turnos["Líquido (R$)"] = (df_turnos["bruto"] - (df_turnos["km"] * df_turnos["custo_km"]) - df_turnos["extras"]).round(2)
        st.dataframe(
            df_turnos[["data", "moto_nome", "estabelecimento", "km", "bruto", "Líquido (R$)"]].rename(
                columns={"data": "Data", "moto_nome": "Moto", "estabelecimento": "Origem", "km": "Km", "bruto": "Bruto (R$)"}
            ),
            use_container_width=True,
            hide_index=True
        )

        with st.expander("🗑️ Excluir um turno lançado errado"):
            opcoes_excluir = [
                f"{i} | {t['data']} [{t.get('moto_nome', 'Moto')}] — {t['estabelecimento']} ({t['km']} km | R$ {t['bruto']:.2f})"
                for i, t in enumerate(db["turnos"])
            ]
            selecionado = st.selectbox("Selecione o turno para remover:", options=opcoes_excluir)
            if st.button("Confirmar Exclusão", type="primary"):
                idx_remover = int(selecionado.split(" | ")[0])
                removido = db["turnos"].pop(idx_remover)
                m_alvo = motos_dict.get(removido.get("moto_id", "moto_1"))
                if m_alvo:
                    turnos_m = [t["km_fim"] for t in db["turnos"] if t.get("moto_id") == m_alvo["id"]]
                    if turnos_m:
                        m_alvo["hodometro"] = max(turnos_m)
                save_data(db, user_key)
                st.toast("Turno removido!")
                st.rerun()

with tab_sim:
    st.subheader(f"Calculadora de Corrida e Orçamento ({moto['apelido']})")
    modo_sim = st.radio(
        "O que você deseja fazer agora?",
        options=["⚡ Simular Corrida de App (Rápido)", "📍 Gerar Orçamento por Endereço (Cliente Particular)"],
        horizontal=True
    )

    st.divider()

    if modo_sim == "⚡ Simular Corrida de App (Rápido)":
        col_s1, col_s2 = st.columns(2)
        valor_corrida = col_s1.number_input("Valor Ofertado pelo App (R$)", min_value=0.0, value=12.0, step=0.5)
        dist_corrida = col_s2.number_input("Distância Total: Coleta + Entrega (km)", min_value=0.1, value=6.0, step=0.5)

        custo_corrida = dist_corrida * custo_total_km
        lucro_corrida = valor_corrida - custo_corrida
        liquido_por_km = lucro_corrida / dist_corrida if dist_corrida > 0 else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Lucro Líquido Real", f"R$ {lucro_corrida:.2f}")
        m2.metric("Custo da Moto", f"- R$ {custo_corrida:.2f}")
        m3.metric("Líquido por Km", f"R$ {liquido_por_km:.2f}/km")

        if liquido_por_km >= 1.30:
            st.success("✅ **CORRIDA BOA:** Acima da meta de rentabilidade líquida!")
        elif liquido_por_km >= 0.80:
            st.warning("⚠️ **EMPATE / ATENÇÃO:** Margem apertada, avalie o trânsito e o retorno.")
        else:
            st.error("🚨 **PREJUÍZO / FURADA:** Você está desgastando a moto abaixo do mínimo viável.")

    else:
        st.markdown("#### 1. Ponto de Partida (Deslocamento até a Retirada)")
        modo_partida = st.radio(
            "Como deseja informar onde você está agora?",
            options=[
                "📍 Já estou na retirada / Não cobrar deslocamento",
                "📡 Meu GPS Atual (Navegador)",
                "🏍️ Digitar Rua/Ponto onde estou agora"
            ],
            horizontal=False
        )

        coord_atual = None
        if modo_partida == "📡 Meu GPS Atual (Navegador)":
            if HAS_GEO:
                loc = get_geolocation(component_key="gps_entregador")
                if loc and "coords" in loc:
                    coord_atual = {
                        "lat": loc["coords"]["latitude"],
                        "lon": loc["coords"]["longitude"],
                        "label": "Minha Localização Atual (GPS)"
                    }
                    st.success(f"📡 GPS capturado ({coord_atual['lat']:.5f}, {coord_atual['lon']:.5f})")
                else:
                    st.info("Aguardando permissão de localização do navegador...")
            else:
                st.warning("Pacote `streamlit-js-eval` não instalado.")
        elif modo_partida == "🏍️ Digitar Rua/Ponto onde estou agora":
            if HAS_SEARCHBOX:
                coord_atual = st_searchbox(
                    buscar_enderecos_online,
                    key="sb_partida",
                    placeholder="Ex: Av. Loreto, Araras ou Praça Central..."
                )
            else:
                txt_p = st.text_input("Rua/Local onde estou agora:", key="txt_p")
                if txt_p:
                    res_p = buscar_enderecos_online(txt_p)
                    if res_p:
                        coord_atual = res_p[0][1]

        st.markdown("#### 2. Endereços da Entrega")
        col_o1, col_o2 = st.columns([3, 1])
        with col_o1:
            st.caption("Endereço de Retirada / Coleta:")
            if HAS_SEARCHBOX:
                sel_origem = st_searchbox(buscar_enderecos_online, key="sb_origem", placeholder="Rua, número e cidade da retirada...")
            else:
                txt_o = st.text_input("Retirada:", key="txt_o")
                sel_origem = buscar_enderecos_online(txt_o)[0][1] if (txt_o and buscar_enderecos_online(txt_o)) else None
        with col_o2:
            num_origem = st.text_input("Nº / Compl.", key="num_o", placeholder="Ex: 120")

        col_d1, col_d2 = st.columns([3, 1])
        with col_d1:
            st.caption("Endereço de Entrega / Destino:")
            if HAS_SEARCHBOX:
                sel_destino = st_searchbox(buscar_enderecos_online, key="sb_destino", placeholder="Rua, número e cidade da entrega...")
            else:
                txt_d = st.text_input("Entrega:", key="txt_d")
                sel_destino = buscar_enderecos_online(txt_d)[0][1] if (txt_d and buscar_enderecos_online(txt_d)) else None
        with col_d2:
            num_destino = st.text_input("Nº / Compl.", key="num_d", placeholder="Ex: 1285")

        dist_desloc_km = 0.0
        dist_entrega_km = 6.0
        tempo_min = 15

        if sel_origem and sel_destino:
            d_ent, t_ent = calcular_rota_osrm(sel_origem["lat"], sel_origem["lon"], sel_destino["lat"], sel_destino["lon"])
            if d_ent is not None:
                dist_entrega_km = d_ent
                tempo_min = t_ent

            if coord_atual:
                d_desl, t_desl = calcular_rota_osrm(coord_atual["lat"], coord_atual["lon"], sel_origem["lat"], sel_origem["lon"])
                if d_desl is not None:
                    dist_desloc_km = d_desl
                    tempo_min += t_desl

            resumo_rota = f"📍 **Entrega:** {dist_entrega_km:.2f} km (~{tempo_min} min)"
            if dist_desloc_km > 0:
                resumo_rota += f" | 🏍️ **Deslocamento até coleta:** +{dist_desloc_km:.2f} km (**Total:** {dist_desloc_km + dist_entrega_km:.2f} km)"
            st.success(resumo_rota)

        st.markdown("#### 3. Precificação do Orçamento")
        col_p1, col_p2, col_p3 = st.columns(3)
        dist_entrega_manual = col_p1.number_input("Km da Entrega:", min_value=0.1, value=float(dist_entrega_km), step=0.5)
        valor_km_cobrar = col_p2.number_input("Cobrar por Km (R$):", min_value=0.5, value=2.00, step=0.25, format="%.2f")
        taxa_minima = col_p3.number_input("Taxa Mínima (R$):", min_value=0.0, value=8.00, step=1.0, format="%.2f")

        col_chk1, col_chk2 = st.columns(2)
        cobrar_desloc = col_chk1.checkbox(f"Cobrar deslocamento até coleta (+{dist_desloc_km:.1f} km)", value=True, disabled=(dist_desloc_km == 0))
        considerar_volta = col_chk2.checkbox("Calcular custo de retorno vazio (volta)", value=False)

        km_cobrado_cliente = dist_entrega_manual + (dist_desloc_km if cobrar_desloc else 0.0)
        valor_orcamento = max(km_cobrado_cliente * valor_km_cobrar, taxa_minima)

        km_real_moto = (dist_desloc_km + dist_entrega_manual) * (2 if considerar_volta else 1)
        custo_operacional_orc = km_real_moto * custo_total_km
        lucro_orcamento = valor_orcamento - custo_operacional_orc

        st.divider()
        r1, r2, r3 = st.columns(3)
        r1.metric("Valor para o Cliente", f"R$ {valor_orcamento:.2f}")
        r2.metric("Seu Custo Real Moto", f"- R$ {custo_operacional_orc:.2f}")
        r3.metric("Seu Lucro Líquido", f"R$ {lucro_orcamento:.2f}")

        origem_txt = f"{sel_origem['label']} (Nº {num_origem})" if (sel_origem and num_origem) else (sel_origem["label"] if sel_origem else "A definir")
        destino_txt = f"{sel_destino['label']} (Nº {num_destino})" if (sel_destino and num_destino) else (sel_destino["label"] if sel_destino else "A definir")

        msg_whats = "\n".join([
            "🏍️ *ORÇAMENTO DE ENTREGA*",
            f"📍 *Retirada:* {origem_txt}",
            f"🏁 *Entrega:* {destino_txt}",
            f"📏 *Distância considerada:* {km_cobrado_cliente:.1f} km",
            f"💰 *Valor da Corrida:* R$ {valor_orcamento:.2f}",
            "",
            "Posso confirmar a coleta?"
        ])
        st.text_area("📲 Copie e envie no WhatsApp do Cliente:", value=msg_whats, height=165)

with tab_garagem:
    st.subheader(f"💰 Balanço da Caixinha: Previsto vs. Gasto Real ({moto['apelido']})")

    turnos_moto = [t for t in db["turnos"] if t.get("moto_id", "moto_1") == moto["id"]]
    manuts_moto = [m for m in db.get("manutencoes", []) if m.get("moto_id", "moto_1") == moto["id"]]

    reserva_acumulada_app = sum(t["km"] * t.get("custo_reserva_km", custo_reserva_km) for t in turnos_moto)
    total_gasto_manut_real = sum(m["valor_total"] for m in manuts_moto)

    b1, b2, b3 = st.columns(3)
    b1.metric("Reservado nos Turnos (App)", f"R$ {reserva_acumulada_app:.2f}", help="Valor separado automaticamente pelos km rodados registrados no app")
    b2.metric("Total Gasto em Oficina (Histórico)", f"R$ {total_gasto_manut_real:.2f}", help="Soma de todas as manutenções registradas abaixo")
    b3.metric("Custo Real Peças + Fixos", f"R$ {custo_reserva_km:.3f}/km", help="Quanto você deve guardar por km rodado")

    st.divider()

    st.subheader("🛠️ Registrar Manutenção / Serviço Realizado")
    with st.expander("➕ Lançar Nova Manutenção Feita na Oficina", expanded=False):
        with st.form("form_nova_manutencao"):
            hm1, hm2, hm3 = st.columns([1.1, 1, 1.4])
            data_manut = hm1.date_input("Data do Serviço", value=date.today())
            odo_manut = hm2.number_input("Hodômetro (km)", value=int(moto["hodometro"]), step=1)
            opcoes_comp = [p["nome"] for p in moto["pecas"]] + ["Outro Serviço / Peça Avulsa"]
            comp_escolhido = hm3.selectbox("Componente / Serviço", options=opcoes_comp)

            hm4, hm5, hm6 = st.columns([1.2, 1, 1])
            oficina_nome = hm4.text_input("Oficina / Loja", placeholder="Ex: Amaral, Mineiro, Poty...")
            val_peca = hm5.number_input("Valor Peça (R$)", min_value=0.0, step=5.0)
            val_total_pago = hm6.number_input("Valor Total Pago (R$)", min_value=0.0, step=5.0)

            hm7, hm8 = st.columns([2, 1])
            obs_manut = hm7.text_input("Observações", placeholder="Ex: Troca preventiva, marca da peça...")
            atualizar_param = hm8.checkbox("Atualizar barra de desgaste e custo/km", value=True)

            if st.form_submit_button("Salvar Manutenção no Histórico", use_container_width=True):
                novo_reg = {
                    "id": f"m_{len(db.get('manutencoes', [])) + 1}_{odo_manut}",
                    "moto_id": moto["id"],
                    "data": str(data_manut),
                    "hodometro": int(odo_manut),
                    "componente": comp_escolhido,
                    "oficina": oficina_nome if oficina_nome.strip() else "Não informada",
                    "valor_peca": float(val_peca),
                    "valor_total": float(val_total_pago),
                    "obs": obs_manut
                }
                db.setdefault("manutencoes", []).append(novo_reg)

                if atualizar_param:
                    for p in moto["pecas"]:
                        if p["nome"] == comp_escolhido:
                            if odo_manut >= p["ultima_km"]:
                                p["ultima_km"] = int(odo_manut)
                            if val_total_pago > 0:
                                p["custo"] = float(val_total_pago)
                    if odo_manut > moto["hodometro"]:
                        moto["hodometro"] = int(odo_manut)

                save_data(db, user_key)
                st.success(f"Serviço '{comp_escolhido}' registrado com sucesso!")
                st.rerun()

    if manuts_moto:
        with st.expander(f"📋 Ver Histórico Completo de Serviços ({len(manuts_moto)} registros — Total: R$ {total_gasto_manut_real:.2f})", expanded=True):
            df_manut = pd.DataFrame(manuts_moto)
            st.dataframe(
                df_manut[["data", "hodometro", "componente", "oficina", "valor_peca", "valor_total", "obs"]].rename(
                    columns={
                        "data": "Data",
                        "hodometro": "Hodômetro",
                        "componente": "Componente / Serviço",
                        "oficina": "Oficina / Loja",
                        "valor_peca": "Peça (R$)",
                        "valor_total": "Total Pago (R$)",
                        "obs": "Observações"
                    }
                ),
                use_container_width=True,
                hide_index=True
            )

            opcoes_del_m = [
                f"{i} | {m['data']} — {m['componente']} ({m['hodometro']} km | R$ {m['valor_total']:.2f})"
                for i, m in enumerate(db["manutencoes"])
                if m.get("moto_id", "moto_1") == moto["id"]
            ]
            if opcoes_del_m:
                col_dm1, col_dm2 = st.columns([3, 1])
                sel_del_m = col_dm1.selectbox("Remover lançamento incorreto:", options=opcoes_del_m, label_visibility="collapsed")
                if col_dm2.button("Excluir Serviço"):
                    idx_m_del = int(sel_del_m.split(" | ")[0])
                    db["manutencoes"].pop(idx_m_del)
                    save_data(db, user_key)
                    st.toast("Registro de manutenção excluído!")
                    st.rerun()

    st.divider()

    st.subheader(f"🚦 Alertas de Desgaste Preventivo ({moto['apelido']})")
    for idx, p in enumerate(moto["pecas"]):
        rodados = moto["hodometro"] - p["ultima_km"]
        restantes = p["intervalo"] - rodados
        pct = min(max(rodados / p["intervalo"], 0.0), 1.0)
        status_icon = "🟢 OK" if restantes > p["intervalo"] * 0.15 else ("🟡 ATENÇÃO" if restantes > 0 else "🔴 VENCIDO")
        col_p1, col_p2 = st.columns([3, 1])
        col_p1.markdown(f"**{p['nome']}** — {status_icon} (`{restantes:,} km restantes` | Base: R$ {p['custo']:.0f})")
        col_p1.progress(pct)
        if col_p2.button("Troquei Hoje", key=f"troca_{moto['id']}_{idx}", use_container_width=True):
            moto["pecas"][idx]["ultima_km"] = moto["hodometro"]
            save_data(db, user_key)
            st.toast(f"{p['nome']} zerado em {moto['hodometro']} km!")
            st.rerun()

    st.divider()

    st.subheader("⚙️ Parâmetros de Combustível, Fixos e Multi-Moto")
    with st.expander("Editar Gasolina, Consumo, Hodômetro e Custos Fixos"):
        with st.form("form_config_moto"):
            cg0_1, cg0_2 = st.columns(2)
            novo_apelido = cg0_1.text_input("Apelido da Moto", value=moto["apelido"])
            novo_odo = cg0_2.number_input("Hodômetro Atual (km)", value=int(moto["hodometro"]), step=1)

            cg1, cg2, cg3 = st.columns(3)
            novo_preco_gas = cg1.number_input("Gasolina (R$/L)", value=float(moto["preco_gasolina"]), step=0.05, format="%.2f")
            novo_consumo = cg2.number_input("Consumo (km/L)", value=float(moto["consumo_kml"]), step=0.5, format="%.1f")
            novo_seguro = cg3.number_input("Seguro Anual (R$)", value=float(moto["seguro_anual"]), step=10.0, format="%.2f")

            cg4, cg5 = st.columns(2)
            novo_licenc = cg4.number_input("IPVA/Licenc. (R$)", value=float(moto["licenciamento_anual"]), step=5.0, format="%.2f")
            nova_proj = cg5.number_input("Projeção Anual (km)", value=float(moto["projecao_anual_km"]), step=500.0, format="%.0f")

            if st.form_submit_button("Salvar Parâmetros", use_container_width=True):
                moto["apelido"] = novo_apelido.strip() or moto["apelido"]
                moto["hodometro"] = novo_odo
                moto["preco_gasolina"] = novo_preco_gas
                moto["consumo_kml"] = novo_consumo
                moto["seguro_anual"] = novo_seguro
                moto["licenciamento_anual"] = novo_licenc
                moto["projecao_anual_km"] = nova_proj
                save_data(db, user_key)
                st.success("Parâmetros atualizados!")
                st.rerun()

    with st.expander("✏️ Editar Custo Base ou Intervalo das Peças"):
        peca_nomes = [p["nome"] for p in moto["pecas"]]
        peca_esc = st.selectbox("Escolha o componente:", options=peca_nomes)
        idx_p = peca_nomes.index(peca_esc)
        p_atual = moto["pecas"][idx_p]

        with st.form("form_editar_peca"):
            ep1, ep2, ep3 = st.columns(3)
            novo_custo_p = ep1.number_input("Custo Base (R$)", value=float(p_atual["custo"]), step=5.0)
            novo_interv_p = ep2.number_input("Intervalo (km)", value=int(p_atual["intervalo"]), step=500)
            nova_ult_km = ep3.number_input("Km Última Troca", value=int(p_atual["ultima_km"]), step=100)

            if st.form_submit_button("Atualizar Peça", use_container_width=True):
                moto["pecas"][idx_p]["custo"] = novo_custo_p
                moto["pecas"][idx_p]["intervalo"] = novo_interv_p
                moto["pecas"][idx_p]["ultima_km"] = nova_ult_km
                save_data(db, user_key)
                st.success(f"{peca_esc} atualizado!")
                st.rerun()

    with st.expander("➕ Adicionar Segunda Moto (Reserva, Alugada ou Outro Modelo)"):
        with st.form("form_nova_moto"):
            nm1, nm2 = st.columns(2)
            apelido_nova = nm1.text_input("Apelido (ex: CG 160 Reserva)", placeholder="Minha Segunda Moto")
            modelo_cat = nm2.selectbox("Modelo Pré-Calibrado:", options=list(CATALOGO_MOTOS.keys()))

            nm3, nm4 = st.columns(2)
            odo_nova = nm3.number_input("Hodômetro Atual (km):", min_value=0, value=10000, step=100)
            gas_nova = nm4.number_input("Preço Gasolina (R$/L):", min_value=1.0, value=5.99, step=0.05)

            if st.form_submit_button("Cadastrar e Ativar Moto", use_container_width=True):
                base = CATALOGO_MOTOS[modelo_cat]
                novo_id = f"moto_{len(db['motos']) + 1}_{int(odo_nova)}"
                pecas_novas = [
                    {"nome": p["nome"], "intervalo": p["intervalo"], "ultima_km": int(odo_nova), "custo": p["custo"]}
                    for p in base["pecas"]
                ]
                db["motos"].append({
                    "id": novo_id,
                    "apelido": apelido_nova.strip() if apelido_nova.strip() else modelo_cat.split("(")[0].strip(),
                    "modelo": modelo_cat,
                    "hodometro": int(odo_nova),
                    "preco_gasolina": float(gas_nova),
                    "consumo_kml": base["consumo_kml"],
                    "seguro_anual": base["seguro_anual"],
                    "licenciamento_anual": base["licenciamento_anual"],
                    "projecao_anual_km": base["projecao_anual_km"],
                    "pecas": pecas_novas
                })
                db["moto_ativa_id"] = novo_id
                save_data(db, user_key)
                st.success("Nova moto cadastrada!")
                st.rerun()

with tab_clt:
    st.subheader("Comparativo Real vs. CLT (+30% Periculosidade)")
    dias_unicos = len(set(t["data"] for t in db["turnos"]))
    total_km_clt = sum(t["km"] for t in db["turnos"])
    bruto_clt = sum(t["bruto"] for t in db["turnos"])

    custo_op_clt = 0.0
    for t in db["turnos"]:
        m_ref = motos_dict.get(t.get("moto_id", "moto_1"), moto)
        _, _, _, _, ct = calc_custos_moto(m_ref)
        custo_op_clt += t["km"] * t.get("custo_km", ct)

    liquido_clt = bruto_clt - custo_op_clt - sum(t["extras"] for t in db["turnos"])
    meta_proporcional = dias_unicos * META_CLT_DIARIA
    empate_bruto = meta_proporcional + custo_op_clt
    indice_clt = (liquido_clt / meta_proporcional * 100) if meta_proporcional > 0 else 0

    st.metric(
        f"Índice de Remuneração Real ({dias_unicos} dias trabalhados)",
        f"{indice_clt:.1f}% do Piso CLT",
        delta=f"R$ {liquido_clt - meta_proporcional:+.2f} vs CLT"
    )

    c_clt1, c_clt2 = st.columns(2)
    c_clt1.metric("Meta Líquida CLT (Período)", f"R$ {meta_proporcional:.2f}")
    c_clt2.metric("Bruto Mínimo de Empate", f"R$ {empate_bruto:.2f}")

    st.caption(f"Base CLT 2026: R$ {PISO_CLT_MENSAL:.2f}/mês (Salário Mínimo + 30% Periculosidade + 13º + Férias 1/3 + FGTS + INSS MEI + VA = R$ {META_CLT_DIARIA:.2f}/dia).")
