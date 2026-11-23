import streamlit as st
import pandas as pd
import json
import os
import re
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
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

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
    "Honda CG 160 Titan / Fan / Start (Injetada)": {
        "consumo_kml": 36.0,
        "seguro_anual": 1250.00,
        "licenciamento_anual": 480.00,
        "projecao_anual_km": 36000.0,
        "pecas": [
            {"nome": "Troca de Óleo (10W30)", "intervalo": 1500, "custo": 42.0},
            {"nome": "Limpeza Bico / Corpo Injeção", "intervalo": 15000, "custo": 110.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 75.0},
            {"nome": "Pastilha Freio Dianteiro", "intervalo": 12000, "custo": 60.0},
            {"nome": "Lona Freio Traseiro", "intervalo": 15000, "custo": 60.0},
            {"nome": "Cabos + Lubrificação", "intervalo": 15000, "custo": 100.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "custo": 210.0},
            {"nome": "Par de Pneus", "intervalo": 30000, "custo": 520.0},
            {"nome": "Bateria", "intervalo": 50000, "custo": 170.0}
        ]
    },
    "Yamaha Factor 150 / Fazer 150 (Injetada)": {
        "consumo_kml": 38.0,
        "seguro_anual": 1150.00,
        "licenciamento_anual": 460.00,
        "projecao_anual_km": 36000.0,
        "pecas": [
            {"nome": "Troca de Óleo (Yamalube)", "intervalo": 2000, "custo": 48.0},
            {"nome": "Limpeza Bico / Corpo Injeção", "intervalo": 15000, "custo": 110.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 80.0},
            {"nome": "Pastilha Freio Dianteiro", "intervalo": 12000, "custo": 65.0},
            {"nome": "Lona Freio Traseiro", "intervalo": 15000, "custo": 65.0},
            {"nome": "Cabos + Lubrificação", "intervalo": 15000, "custo": 100.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "custo": 220.0},
            {"nome": "Par de Pneus", "intervalo": 30000, "custo": 530.0},
            {"nome": "Bateria", "intervalo": 50000, "custo": 170.0}
        ]
    },
    "Honda NXR 160 Bros (Injetada)": {
        "consumo_kml": 33.0,
        "seguro_anual": 1300.00,
        "licenciamento_anual": 510.00,
        "projecao_anual_km": 36000.0,
        "pecas": [
            {"nome": "Troca de Óleo (10W30)", "intervalo": 1500, "custo": 42.0},
            {"nome": "Limpeza Bico / Corpo Injeção", "intervalo": 15000, "custo": 120.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 80.0},
            {"nome": "Pastilha Freio Dianteiro", "intervalo": 12000, "custo": 65.0},
            {"nome": "Pastilha/Lona Freio Traseiro", "intervalo": 15000, "custo": 65.0},
            {"nome": "Cabos + Lubrificação", "intervalo": 15000, "custo": 110.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "custo": 240.0},
            {"nome": "Par de Pneus", "intervalo": 30000, "custo": 580.0},
            {"nome": "Bateria", "intervalo": 50000, "custo": 175.0}
        ]
    },
    "Yamaha Fazer 250 / Lander 250": {
        "consumo_kml": 27.0,
        "seguro_anual": 1650.00,
        "licenciamento_anual": 620.00,
        "projecao_anual_km": 36000.0,
        "pecas": [
            {"nome": "Troca de Óleo + Filtro Óleo", "intervalo": 3000, "custo": 85.0},
            {"nome": "Limpeza Bico / Corpo Injeção", "intervalo": 15000, "custo": 140.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 95.0},
            {"nome": "Pastilha Freio Dianteiro", "intervalo": 12000, "custo": 80.0},
            {"nome": "Pastilha Freio Traseiro", "intervalo": 15000, "custo": 75.0},
            {"nome": "Cabos + Lubrificação", "intervalo": 15000, "custo": 120.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "custo": 320.0},
            {"nome": "Par de Pneus", "intervalo": 25000, "custo": 780.0},
            {"nome": "Bateria", "intervalo": 50000, "custo": 220.0}
        ]
    },
    "Personalizada (Outro Modelo)": {
        "consumo_kml": 35.0,
        "seguro_anual": 1000.00,
        "licenciamento_anual": 400.00,
        "projecao_anual_km": 36000.0,
        "pecas": [
            {"nome": "Troca de Óleo", "intervalo": 1500, "custo": 40.0},
            {"nome": "Limpeza Carburador / Injeção", "intervalo": 15000, "custo": 110.0},
            {"nome": "Filtro de Ar + Vela", "intervalo": 12000, "custo": 75.0},
            {"nome": "Freio Dianteiro", "intervalo": 12000, "custo": 65.0},
            {"nome": "Freio Traseiro", "intervalo": 15000, "custo": 65.0},
            {"nome": "Cabos + Lubrificação", "intervalo": 15000, "custo": 100.0},
            {"nome": "Kit Relação / Transmissão", "intervalo": 20000, "custo": 220.0},
            {"nome": "Par de Pneus", "intervalo": 30000, "custo": 550.0},
            {"nome": "Bateria", "intervalo": 50000, "custo": 170.0}
        ]
    }
}

def criar_moto_do_catalogo(moto_id, apelido, modelo_catalogo, hodometro_atual, preco_gasolina=5.99, ultimas_trocas_custom=None):
    base = CATALOGO_MOTOS.get(modelo_catalogo, CATALOGO_MOTOS["Personalizada (Outro Modelo)"])
    pecas_novas = []
    for p in base["pecas"]:
        ult_km = hodometro_atual
        if ultimas_trocas_custom and p["nome"] in ultimas_trocas_custom:
            ult_km = ultimas_trocas_custom[p["nome"]]
        pecas_novas.append({
            "nome": p["nome"],
            "intervalo": p["intervalo"],
            "ultima_km": ult_km,
            "custo": p["custo"]
        })
    return {
        "id": moto_id,
        "apelido": apelido,
        "modelo": modelo_catalogo,
        "hodometro": hodometro_atual,
        "preco_gasolina": preco_gasolina,
        "consumo_kml": base["consumo_kml"],
        "seguro_anual": base["seguro_anual"],
        "licenciamento_anual": base["licenciamento_anual"],
        "projecao_anual_km": base["projecao_anual_km"],
        "pecas": pecas_novas
    }

def get_default_multi_data():
    ultimas_bros = {
        "Troca de Óleo": 80346,
        "Limpeza/Regulagem Carburador": 70050,
        "Filtro de Ar + Vela": 51560,
        "Pastilha Freio Dianteiro (ESD)": 74545,
        "Lona Freio Traseiro": 74545,
        "Cabos + Lubrificação": 70050,
        "Kit Relação / Transmissão": 75056,
        "Par de Pneus": 68824,
        "Bateria (Partida Elétrica)": 58098
    }
    moto_principal = criar_moto_do_catalogo(
        moto_id="moto_1",
        apelido="Bros 150 (Trabalho)",
        modelo_catalogo="Honda NXR 150 Bros ESD 2008 (Carburada)",
        hodometro_atual=81185,
        preco_gasolina=5.99,
        ultimas_trocas_custom=ultimas_bros
    )
    return {
        "perfil": {
            "cidade_uf": "Araras - SP",
            "compartilhar_observatorio": True
        },
        "moto_ativa_id": "moto_1",
        "motos": {
            "moto_1": moto_principal
        },
        "turnos": [
            {
                "moto_id": "moto_1",
                "moto_nome": "Bros 150 (Trabalho)",
                "data": "2026-11-21",
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
        ]
    }

@st.cache_resource
def get_supabase_client():
    if not HAS_SUPABASE:
        return None
    url = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
    key = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))
    if url and key:
        try:
            return create_client(url, key)
        except Exception:
            return None
    return None

def normalizar_estrutura(data):
    if "motos" not in data and "moto" in data:
        m_antiga = data["moto"]
        moto_migrada = {
            "id": "moto_1",
            "apelido": "Minha Moto Principal",
            "modelo": m_antiga.get("modelo", "Honda NXR 150 Bros ESD 2008 (Carburada)"),
            "hodometro": m_antiga.get("hodometro", 81185),
            "preco_gasolina": m_antiga.get("preco_gasolina", 5.99),
            "consumo_kml": m_antiga.get("consumo_kml", 29.0),
            "seguro_anual": m_antiga.get("seguro_anual", 984.08),
            "licenciamento_anual": m_antiga.get("licenciamento_anual", 174.08),
            "projecao_anual_km": m_antiga.get("projecao_anual_km", 37286.64),
            "pecas": data.get("pecas", [])
        }
        data = {
            "perfil": {"cidade_uf": "Araras - SP", "compartilhar_observatorio": True},
            "moto_ativa_id": "moto_1",
            "motos": {"moto_1": moto_migrada},
            "turnos": data.get("turnos", [])
        }
    data.setdefault("perfil", {"cidade_uf": "Araras - SP", "compartilhar_observatorio": True})
    for t in data.get("turnos", []):
        t.setdefault("moto_id", data.get("moto_ativa_id", "moto_1"))
        t.setdefault("moto_nome", data["motos"].get(t["moto_id"], {}).get("apelido", "Moto"))
        t.setdefault("estabelecimento", "Não informado")
        t.setdefault("ganho_app", 0.0)
        t.setdefault("ganho_estab", 0.0)
    return data

def load_data(user_key="entregador_padrao"):
    sb = get_supabase_client()
    if sb:
        try:
            res = sb.table("user_states").select("state_json").eq("user_key", user_key).execute()
            if res.data and len(res.data) > 0:
                return normalizar_estrutura(res.data[0]["state_json"])
        except Exception:
            pass

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return normalizar_estrutura(json.load(f))

    return get_default_multi_data()

def save_data(data, user_key="entregador_padrao"):
    # Salva localmente como backup instantâneo
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # Sincroniza na nuvem permanente (Supabase) se configurado
    sb = get_supabase_client()
    if sb:
        try:
            sb.table("user_states").upsert({
                "user_key": user_key,
                "state_json": data
            }).execute()
        except Exception as e:
            st.warning(f"Aviso ao sincronizar nuvem: {e}")

def enviar_metrica_observatorio(perfil, moto_obj, turno_obj, custo_km_real, liquido_turno):
    """Envia métrica 100% anônima (LGPD) para o Observatório da Categoria."""
    if not perfil.get("compartilhar_observatorio", True):
        return
    sb = get_supabase_client()
    if not sb:
        return
    try:
        meta_diaria = 3254.46 / 26.0
        clt_pct = round((liquido_turno / meta_diaria) * 100, 1) if meta_diaria > 0 else 0.0
        sb.table("observatory_metrics").insert({
            "city_state": perfil.get("cidade_uf", "Não informado"),
            "moto_model": moto_obj.get("modelo", "Não informado"),
            "shift_date": turno_obj["data"],
            "total_km": turno_obj["km"],
            "gross_brl": turno_obj["bruto"],
            "real_cost_per_km": round(custo_km_real, 4),
            "net_profit_brl": round(liquido_turno, 2),
            "clt_index_pct": clt_pct
        }).execute()
    except Exception:
        pass

def calcular_custos_moto(moto_obj):
    custo_gas_km = moto_obj["preco_gasolina"] / moto_obj["consumo_kml"]
    custo_fixos_km = (moto_obj["seguro_anual"] + moto_obj["licenciamento_anual"]) / moto_obj["projecao_anual_km"]
    custo_pecas_km = sum(p["custo"] / p["intervalo"] for p in moto_obj["pecas"])
    custo_reserva_km = custo_fixos_km + custo_pecas_km
    custo_total_km = custo_gas_km + custo_reserva_km
    return custo_gas_km, custo_reserva_km, custo_total_km

@st.cache_data(ttl=600)
def consultar_api_enderecos(termo):
    if not termo or len(termo.strip()) < 3:
        return []
    consulta_raw = termo.strip()

    partes_split = [p.strip() for p in consulta_raw.split(",") if p.strip()]
    rua_base = partes_split[0]
    numero_digitado = ""
    resto_cidade = ""

    if len(partes_split) >= 2:
        if re.match(r"^\d+[a-zA-Z0-9\-]*$", partes_split[1]):
            numero_digitado = partes_split[1]
            if len(partes_split) >= 3:
                resto_cidade = ", ".join(partes_split[2:])
        else:
            resto_cidade = ", ".join(partes_split[1:])

    consultas_tentar = [f"{consulta_raw}, Brasil"]
    if numero_digitado and resto_cidade:
        consultas_tentar.append(f"{rua_base}, {resto_cidade}, Brasil")
    elif numero_digitado:
        consultas_tentar.append(f"{rua_base}, Brasil")
    elif re.search(r"\b\d+\b", consulta_raw):
        sem_num = re.sub(r"\b\d+\b", "", consulta_raw).replace("  ", " ").strip(" ,")
        if sem_num:
            consultas_tentar.append(f"{sem_num}, Brasil")

    resultados = []
    for q in consultas_tentar:
        try:
            url_photon = f"https://photon.komoot.io/api/?q={urllib.parse.quote(q)}&limit=8"
            req = urllib.request.Request(url_photon, headers={"User-Agent": "RaioXEntregadorApp/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                dados = json.loads(resp.read().decode("utf-8"))
                for feat in dados.get("features", []):
                    props = feat.get("properties", {})
                    if props.get("countrycode") and props.get("countrycode") != "BR":
                        continue
                    coords = feat.get("geometry", {}).get("coordinates", [])
                    if len(coords) >= 2:
                        lon, lat = float(coords[0]), float(coords[1])
                        partes = []
                        if props.get("name"):
                            partes.append(props["name"])
                        if props.get("street"):
                            rua = props["street"]
                            num = props.get("housenumber") or numero_digitado
                            if num:
                                rua += f", {num}"
                            if rua not in partes:
                                partes.append(rua)
                        elif numero_digitado and partes:
                            partes[0] = f"{partes[0]}, {numero_digitado}"
                        if props.get("district"):
                            partes.append(props["district"])
                        if props.get("city"):
                            partes.append(props["city"])
                        if props.get("state"):
                            partes.append(props["state"])
                        label = " - ".join(partes) if partes else q
                        resultados.append({"label": label, "lat": lat, "lon": lon})
        except Exception:
            pass
        if resultados:
            break

    if not resultados:
        for q in consultas_tentar:
            try:
                url_nom = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(q)}&countrycodes=br&format=json&limit=6"
                req = urllib.request.Request(url_nom, headers={"User-Agent": "RaioXEntregadorApp/1.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    dados = json.loads(resp.read().decode("utf-8"))
                    for item in dados:
                        lbl = item["display_name"]
                        if numero_digitado and numero_digitado not in lbl:
                            lbl = f"{rua_base}, {numero_digitado} — {lbl[:60]}"
                        resultados.append({
                            "label": lbl,
                            "lat": float(item["lat"]),
                            "lon": float(item["lon"])
                        })
            except Exception:
                pass
            if resultados:
                break

    vistos = set()
    unicos = []
    for r in resultados:
        if r["label"] not in vistos:
            vistos.add(r["label"])
            unicos.append(r)
    return unicos

@st.cache_data(ttl=600)
def calcular_rota_osrm(lat1, lon1, lat2, lon2):
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
    req = urllib.request.Request(url, headers={"User-Agent": "RaioXEntregadorApp/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
            if dados.get("code") == "Ok" and dados.get("routes"):
                dist_km = dados["routes"][0]["distance"] / 1000.0
                dur_min = dados["routes"][0]["duration"] / 60.0
                return round(dist_km, 2), round(dur_min)
    except Exception:
        pass
    return None

# --- IDENTIFICAÇÃO DE PERFIL / SINCRONIZAÇÃO NUVEM ---
if "user_key" not in st.session_state:
    st.session_state.user_key = st.secrets.get("DEFAULT_USER_KEY", "entregador_principal")

if "db" not in st.session_state:
    st.session_state.db = load_data(st.session_state.user_key)

if "orc_km_entrega" not in st.session_state:
    st.session_state.orc_km_entrega = 5.0
if "orc_km_desloc" not in st.session_state:
    st.session_state.orc_km_desloc = 0.0
if "orc_tempo" not in st.session_state:
    st.session_state.orc_tempo = 12
if "ultima_rota_chave" not in st.session_state:
    st.session_state.ultima_rota_chave = ""
if "gps_atual" not in st.session_state:
    st.session_state.gps_atual = None

db = st.session_state.db
motos_dict = db["motos"]
if db["moto_ativa_id"] not in motos_dict:
    db["moto_ativa_id"] = list(motos_dict.keys())[0]
    save_data(db, st.session_state.user_key)

def buscar_no_searchbox(searchterm: str):
    itens = consultar_api_enderecos(searchterm)
    return [(item["label"], item) for item in itens]

PISO_CLT_MENSAL = 3254.46
META_CLT_DIARIA = PISO_CLT_MENSAL / 26.0
META_CLT_HORA = PISO_CLT_MENSAL / 176.0

# --- BARRA LATERAL: STATUS NUVEM & PERFIL ---
with st.sidebar:
    st.header("☁️ Sincronização & Perfil")
    sb_ativo = get_supabase_client() is not None
    if sb_ativo:
        st.success("Conectado ao Supabase (Nuvem Ativa)")
    else:
        st.warning("Modo Local (Configure SUPABASE_URL e SUPABASE_KEY nos Secrets para salvar na nuvem)")

    nova_chave = st.text_input("Código / Chave da Conta:", value=st.session_state.user_key, help="Use o mesmo código no PC e no Celular para sincronizar seus dados.")
    if nova_chave.strip() and nova_chave.strip() != st.session_state.user_key:
        st.session_state.user_key = nova_chave.strip()
        st.session_state.db = load_data(st.session_state.user_key)
        st.rerun()

    st.divider()
    st.subheader("Observatório da Categoria (LGPD)")
    cidade_uf_in = st.text_input("Sua Cidade - UF", value=db["perfil"].get("cidade_uf", "Araras - SP"))
    compartilhar_in = st.checkbox(
        "Contribuir anonimamente com estatísticas da categoria",
        value=db["perfil"].get("compartilhar_observatorio", True),
        help="Envia apenas Km, Custo/Km e Índice CLT sem nenhum dado pessoal."
    )
    if st.button("Salvar Preferências", use_container_width=True):
        db["perfil"]["cidade_uf"] = cidade_uf_in.strip()
        db["perfil"]["compartilhar_observatorio"] = compartilhar_in
        save_data(db, st.session_state.user_key)
        st.toast("Preferências salvas!")

# --- CABEÇALHO E SELETOR MULTI-MOTO ---
col_titulo, col_seletor = st.columns([1.6, 1])
with col_titulo:
    st.title("🏍️ Raio-X do Entregador")

with col_seletor:
    ids_motos = list(motos_dict.keys())
    nomes_motos = [f"{motos_dict[mid]['apelido']}" for mid in ids_motos]
    idx_atual = ids_motos.index(db["moto_ativa_id"])
    escolha_moto_nome = st.selectbox("Moto Ativa no Turno:", options=nomes_motos, index=idx_atual)
    novo_id_ativo = ids_motos[nomes_motos.index(escolha_moto_nome)]
    if novo_id_ativo != db["moto_ativa_id"]:
        db["moto_ativa_id"] = novo_id_ativo
        save_data(db, st.session_state.user_key)
        st.rerun()

moto_ativa = motos_dict[db["moto_ativa_id"]]
custo_gas_km, custo_reserva_km, custo_total_km = calcular_custos_moto(moto_ativa)

st.caption(
    f"Ativa: **{moto_ativa['apelido']}** ({moto_ativa['modelo']}) • "
    f"Hodômetro: **{moto_ativa['hodometro']:,} km** • "
    f"Custo Real: **R$ {custo_total_km:.3f}/km**"
)

tab_hoje, tab_sim, tab_garagem, tab_clt = st.tabs(["📊 Hoje", "⚡ Simulador & Orçamento", "🔧 Garagem Multi-Moto", "⚖️ Termômetro CLT"])

# --- ABA 1: HOJE ---
with tab_hoje:
    filtro_visao = st.radio(
        "Exibir resultados de:",
        [f"🏍️ Apenas {moto_ativa['apelido']}", "🌐 Todas as Motos Cadastradas"],
        horizontal=True
    )

    turnos_filtrados = (
        [t for t in db["turnos"] if t.get("moto_id") == moto_ativa["id"]]
        if filtro_visao.startswith("🏍️")
        else db["turnos"]
    )

    total_km = sum(t["km"] for t in turnos_filtrados)
    total_bruto = sum(t["bruto"] for t in turnos_filtrados)
    total_extras = sum(t["extras"] for t in turnos_filtrados)

    total_gas = 0.0
    total_reserva = 0.0
    for t in turnos_filtrados:
        m_turno = motos_dict.get(t.get("moto_id"), moto_ativa)
        g_km, r_km, _ = calcular_custos_moto(m_turno)
        total_gas += t["km"] * g_km
        total_reserva += t["km"] * r_km

    lucro_liquido = total_bruto - total_gas - total_reserva - total_extras

    c1, c2, c3 = st.columns(3)
    c1.metric("Lucro Líquido Real", f"R$ {lucro_liquido:.2f}")
    c2.metric("Faturamento Bruto", f"R$ {total_bruto:.2f}")
    c3.metric("Km Rodados", f"{total_km} km")

    st.info(
        f"💰 **Caixinha da Moto (Não Gastar):** Separe **R$ {total_gas + total_reserva:.2f}** "
        f"(R$ {total_gas:.2f} Gasolina + R$ {total_reserva:.2f} Reserva Peças/Fixos)"
    )

    with st.expander(f"➕ Registrar Turno na {moto_ativa['apelido']}", expanded=True):
        with st.form("form_turno"):
            col_d, col1, col2 = st.columns([1.2, 1, 1])
            data_turno = col_d.date_input("Data", value=date.today())
            km_ini = col1.number_input("Km Inicial", value=int(moto_ativa["hodometro"]), step=1)
            km_fim = col2.number_input("Km Final", value=int(moto_ativa["hodometro"]), step=1)

            col3, col4 = st.columns(2)
            ganho_app = col3.number_input("Ganhos Apps / iFood-Bee (R$)", min_value=0.0, step=5.0)
            gastos_extras = col4.number_input("Gastos Extras (R$)", min_value=0.0, step=5.0)

            col5, col6 = st.columns(2)
            estabelecimento = col5.selectbox("Estabelecimento", options=ESTABELECIMENTOS_LISTA)
            ganho_fixo = col6.number_input("Ganho no Estabelecimento (R$)", min_value=0.0, step=5.0)

            submitted = st.form_submit_button(f"Salvar Turno ({moto_ativa['apelido']})", use_container_width=True)
            if submitted:
                dist = km_fim - km_ini
                bruto_dia = ganho_app + ganho_fixo
                if dist <= 0:
                    st.error("O Km Final deve ser maior que o Km Inicial.")
                else:
                    local_registrado = estabelecimento if ganho_fixo > 0 else "iFood / Apps"
                    if ganho_app > 0 and ganho_fixo > 0:
                        local_registrado = f"Apps + {estabelecimento}"

                    novo_turno = {
                        "moto_id": moto_ativa["id"],
                        "moto_nome": moto_ativa["apelido"],
                        "data": str(data_turno),
                        "km_ini": km_ini,
                        "km_fim": km_fim,
                        "km": dist,
                        "ganho_app": ganho_app,
                        "estabelecimento": local_registrado,
                        "ganho_estab": ganho_fixo,
                        "bruto": bruto_dia,
                        "extras": gastos_extras,
                        "custo_km": round(custo_total_km, 4)
                    }
                    db["turnos"].append(novo_turno)
                    if km_fim > motos_dict[moto_ativa["id"]]["hodometro"]:
                        motos_dict[moto_ativa["id"]]["hodometro"] = km_fim

                    liq_turno = bruto_dia - (dist * custo_total_km) - gastos_extras
                    save_data(db, st.session_state.user_key)
                    enviar_metrica_observatorio(db["perfil"], moto_ativa, novo_turno, custo_total_km, liq_turno)
                    st.success(f"Turno salvo na {moto_ativa['apelido']}! +{dist} km ({local_registrado}).")
                    st.rerun()

    if turnos_filtrados:
        st.subheader("Histórico de Turnos")
        linhas_hist = []
        for t in turnos_filtrados:
            m_t = motos_dict.get(t.get("moto_id"), moto_ativa)
            _, _, c_km_t = calcular_custos_moto(m_t)
            liq_t = round(t["bruto"] - (t["km"] * c_km_t) - t["extras"], 2)
            linhas_hist.append({
                "Data": t["data"],
                "Moto": t.get("moto_nome", moto_ativa["apelido"]),
                "Origem / Local": t["estabelecimento"],
                "Km": t["km"],
                "Bruto (R$)": t["bruto"],
                "Líquido (R$)": liq_t
            })
        st.dataframe(pd.DataFrame(linhas_hist), use_container_width=True, hide_index=True)

        with st.expander("🗑️ Excluir um turno lançado errado"):
            opcoes_excluir = [
                f"{i} | {t['data']} [{t.get('moto_nome', '')}] — {t['estabelecimento']} ({t['km']} km | R$ {t['bruto']:.2f})"
                for i, t in enumerate(db["turnos"])
            ]
            selecionado = st.selectbox("Selecione o turno para remover:", options=opcoes_excluir)
            if st.button("Confirmar Exclusão", type="primary"):
                idx_remover = int(selecionado.split(" | ")[0])
                turno_rem = db["turnos"].pop(idx_remover)
                mid_rem = turno_rem.get("moto_id")
                if mid_rem and mid_rem in motos_dict:
                    turnos_rest = [t["km_fim"] for t in db["turnos"] if t.get("moto_id") == mid_rem]
                    if turnos_rest:
                        motos_dict[mid_rem]["hodometro"] = max(turnos_rest)
                save_data(db, st.session_state.user_key)
                st.toast("Turno removido com sucesso!")
                st.rerun()

# --- ABA 2: SIMULADOR & ORÇAMENTO ---
with tab_sim:
    modo_sim = st.radio(
        "Escolha o modo:",
        ["📝 Gerar Orçamento por Endereço (Cliente Particular)", "⚡ Avaliar Corrida de App"],
        horizontal=True
    )

    if modo_sim.startswith("📝"):
        st.subheader(f"Calculadora de Orçamento por Rota ({moto_ativa['apelido']})")
        st.caption("Digite rua, número e cidade para buscar em qualquer município do Brasil.")

        modo_partida = st.radio(
            "De onde você vai sair até a retirada?",
            ["📍 Estou no local / Não cobrar deslocamento", "📡 Meu GPS Atual (Navegador)", "🏍️ Informar Rua/Ponto onde estou agora"],
            horizontal=False
        )
        gps_coords = None

        if modo_partida.startswith("📡"):
            if HAS_GEO:
                loc = get_geolocation(component_key="get_gps_entregador")
                if loc and isinstance(loc, dict) and "coords" in loc:
                    lat_gps = loc["coords"]["latitude"]
                    lon_gps = loc["coords"]["longitude"]
                    st.session_state.gps_atual = (lat_gps, lon_gps)
                    gps_coords = (lat_gps, lon_gps)
                    st.success(f"📍 GPS capturado ({lat_gps:.5f}, {lon_gps:.5f})!")
                elif st.session_state.gps_atual:
                    gps_coords = st.session_state.gps_atual
                    st.info(f"📍 Usando última posição GPS ({gps_coords[0]:.5f}, {gps_coords[1]:.5f}).")
                else:
                    st.warning("Permita a localização no navegador (funciona automaticamente no link HTTPS publicado).")
            else:
                st.warning("Pacote `streamlit-js-eval` não instalado.")

        elif modo_partida.startswith("🏍️"):
            if HAS_SEARCHBOX:
                ponto_atual_sel = st_searchbox(
                    buscar_no_searchbox,
                    placeholder="Onde você está agora? Ex: Praça Barão, Araras...",
                    key="sb_onde_estou",
                    clear_on_submit=False
                )
                if isinstance(ponto_atual_sel, dict):
                    gps_coords = (ponto_atual_sel["lat"], ponto_atual_sel["lon"])

        orig_sel = None
        dest_sel = None

        if HAS_SEARCHBOX:
            col_o, col_d = st.columns(2)
            with col_o:
                st.markdown("**📍 Retirada (Coleta)**")
                orig_sel = st_searchbox(
                    buscar_no_searchbox,
                    placeholder="Ex: Av. Loreto, Araras...",
                    key="sb_origem",
                    clear_on_submit=False
                )
                num_orig = st.text_input("Nº / Complemento Retirada (opcional)", placeholder="Ex: 500 - Loja 2", key="num_orig")

            with col_d:
                st.markdown("**🏁 Entrega (Destino)**")
                dest_sel = st_searchbox(
                    buscar_no_searchbox,
                    placeholder="Ex: Rua Joaquim André, 1285, Piracicaba...",
                    key="sb_destino",
                    clear_on_submit=False
                )
                num_dest = st.text_input("Nº / Complemento Entrega (opcional)", placeholder="Ex: 1285 - Casa", key="num_dest")

        if isinstance(orig_sel, dict) and isinstance(dest_sel, dict):
            gps_tag = f"{gps_coords[0]:.4f},{gps_coords[1]:.4f}" if gps_coords else "sem_gps"
            chave_atual = f"{gps_tag}|{orig_sel['lat']},{orig_sel['lon']}->{dest_sel['lat']},{dest_sel['lon']}"

            if chave_atual != st.session_state.ultima_rota_chave:
                rota_entrega = calcular_rota_osrm(orig_sel["lat"], orig_sel["lon"], dest_sel["lat"], dest_sel["lon"])
                km_desloc = 0.0
                tempo_desloc = 0
                if gps_coords:
                    rota_desloc = calcular_rota_osrm(gps_coords[0], gps_coords[1], orig_sel["lat"], orig_sel["lon"])
                    if rota_desloc:
                        km_desloc = rota_desloc[0]
                        tempo_desloc = rota_desloc[1]

                if rota_entrega:
                    st.session_state.orc_km_desloc = km_desloc
                    st.session_state.orc_km_entrega = rota_entrega[0]
                    st.session_state.orc_tempo = rota_entrega[1] + tempo_desloc
                    st.session_state.ultima_rota_chave = chave_atual

            if st.session_state.orc_km_desloc > 0:
                st.success(
                    f"🛣️ **Deslocamento:** {st.session_state.orc_km_desloc:.2f} km + "
                    f"**Entrega:** {st.session_state.orc_km_entrega:.2f} km = "
                    f"**Total: {st.session_state.orc_km_desloc + st.session_state.orc_km_entrega:.2f} km** (~{st.session_state.orc_tempo} min)"
                )
            else:
                st.success(f"🛣️ **Rota da Entrega:** {st.session_state.orc_km_entrega:.2f} km (~{st.session_state.orc_tempo} min)")

        st.divider()
        col_o1, col_o2, col_o3, col_o4 = st.columns(4)
        dist_desloc = col_o1.number_input("Deslocamento (km)", min_value=0.0, value=float(st.session_state.orc_km_desloc), step=0.5)
        dist_entrega = col_o2.number_input("Entrega (km)", min_value=0.1, value=float(st.session_state.orc_km_entrega), step=0.5)
        valor_por_km = col_o3.number_input("Cobrar/Km (R$)", min_value=0.5, value=2.00, step=0.10, format="%.2f")
        taxa_minima = col_o4.number_input("Taxa Mínima (R$)", min_value=0.0, value=8.00, step=1.00, format="%.2f")

        col_chk1, col_chk2 = st.columns(2)
        cobrar_desloc_cliente = col_chk1.checkbox("Cobrar deslocamento até retirada no orçamento?", value=True)
        incluir_retorno = col_chk2.checkbox("Considerar retorno no meu custo real?", value=False)

        km_cobrado_cliente = (dist_desloc + dist_entrega) if cobrar_desloc_cliente else dist_entrega
        valor_calculado = km_cobrado_cliente * valor_por_km
        valor_final_cliente = max(valor_calculado, taxa_minima)

        km_real_moto = dist_desloc + dist_entrega + (dist_entrega if incluir_retorno else 0.0)
        custo_operacional_orc = km_real_moto * custo_total_km
        lucro_liquido_orc = valor_final_cliente - custo_operacional_orc

        oc1, oc2, oc3 = st.columns(3)
        oc1.metric("Valor para o Cliente", f"R$ {valor_final_cliente:.2f}")
        oc2.metric(f"Custo {moto_ativa['apelido']} ({km_real_moto:.1f} km)", f"- R$ {custo_operacional_orc:.2f}")
        oc3.metric("Seu Lucro Líquido", f"R$ {lucro_liquido_orc:.2f}")

        nome_orig_msg = orig_sel["label"] if isinstance(orig_sel, dict) else "A combinar"
        if num_orig and nome_orig_msg != "A combinar":
            nome_orig_msg = f"{nome_orig_msg} ({num_orig})"

        nome_dest_msg = dest_sel["label"] if isinstance(dest_sel, dict) else "A combinar"
        if num_dest and nome_dest_msg != "A combinar":
            nome_dest_msg = f"{nome_dest_msg} ({num_dest})"

        st.markdown("**📲 Mensagem Pronta para Enviar no WhatsApp:**")
        detalhe_km = (
            f"{km_cobrado_cliente:.1f} km (inclui {dist_desloc:.1f} km deslocamento + {dist_entrega:.1f} km entrega)"
            if (cobrar_desloc_cliente and dist_desloc > 0)
            else f"{dist_entrega:.1f} km"
        )
        texto_whatsapp = (
            f"Olá! Segue o orçamento da entrega de moto:\n"
            f"📍 *Retirada:* {nome_orig_msg}\n"
            f"🏁 *Entrega:* {nome_dest_msg}\n"
            f"📏 *Percurso:* {detalhe_km} (aprox. {st.session_state.orc_tempo} min)\n"
            f"💰 *Valor da entrega:* R$ {valor_final_cliente:.2f}"
        )
        st.code(texto_whatsapp, language="text")

    else:
        st.subheader(f"Simulador Rápido de Corrida ({moto_ativa['apelido']})")
        col_s1, col_s2 = st.columns(2)
        valor_corrida = col_s1.number_input("Valor da Corrida (R$)", min_value=0.0, value=12.0, step=0.5)
        dist_corrida = col_s2.number_input("Distância Total (km)", min_value=0.1, value=6.0, step=0.5)

        custo_corrida = dist_corrida * custo_total_km
        lucro_corrida = valor_corrida - custo_corrida
        liquido_por_km = lucro_corrida / dist_corrida if dist_corrida > 0 else 0

        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("Lucro Líquido", f"R$ {lucro_corrida:.2f}")
        m2.metric("Custo Moto", f"- R$ {custo_corrida:.2f}")
        m3.metric("Ganho Líquido/Km", f"R$ {liquido_por_km:.2f}/km")

        if liquido_por_km >= 1.30:
            st.success("✅ **CORRIDA BOA:** Acima da meta de rentabilidade líquida!")
        elif liquido_por_km >= 0.80:
            st.warning("⚠️ **EMPATE / ATENÇÃO:** Margem apertada, avalie o trânsito e retorno.")
        else:
            st.error("🚨 **PREJUÍZO / FURADA:** Você está desgastando a moto abaixo do mínimo viável.")

# --- ABA 3: GARAGEM MULTI-MOTO ---
with tab_garagem:
    st.subheader("➕ Cadastrar Nova Moto na Garagem")
    with st.expander("Adicionar Segunda Moto (Reserva, Alugada ou Outro Modelo)"):
        with st.form("form_nova_moto"):
            nm1, nm2 = st.columns(2)
            novo_apelido = nm1.text_input("Apelido da Moto", placeholder="Ex: CG 160 Reserva")
            modelo_escolhido = nm2.selectbox("Modelo Base (Tabela Pré-Calibrada)", options=list(CATALOGO_MOTOS.keys()))

            nm3, nm4 = st.columns(2)
            odo_nova = nm3.number_input("Hodômetro Atual (km)", min_value=0, value=10000, step=100)
            gas_nova = nm4.number_input("Preço Gasolina (R$/L)", min_value=1.0, value=5.99, step=0.05, format="%.2f")

            if st.form_submit_button("Cadastrar e Ativar Moto", use_container_width=True):
                if not novo_apelido.strip():
                    st.error("Dê um apelido para identificar a moto.")
                else:
                    novo_id = f"moto_{len(motos_dict) + 1}_{int(date.today().strftime('%d%H%M'))}"
                    motos_dict[novo_id] = criar_moto_do_catalogo(
                        moto_id=novo_id,
                        apelido=novo_apelido.strip(),
                        modelo_catalogo=modelo_escolhido,
                        hodometro_atual=odo_nova,
                        preco_gasolina=gas_nova
                    )
                    db["moto_ativa_id"] = novo_id
                    save_data(db, st.session_state.user_key)
                    st.success(f"Moto '{novo_apelido}' cadastrada!")
                    st.rerun()

    st.divider()
    st.subheader(f"⚙️ Parâmetros de Custo — {moto_ativa['apelido']}")
    with st.expander("Editar Apelido, Gasolina, Consumo, Hodômetro e Custos Fixos"):
        with st.form("form_config_moto"):
            cg_nome1, cg_nome2 = st.columns(2)
            edit_apelido = cg_nome1.text_input("Apelido da Moto", value=moto_ativa["apelido"])
            novo_odo = cg_nome2.number_input("Hodômetro Atual (km)", value=int(moto_ativa["hodometro"]), step=1)

            cg1, cg2 = st.columns(2)
            novo_preco_gas = cg1.number_input("Gasolina (R$/L)", value=float(moto_ativa["preco_gasolina"]), step=0.05, format="%.2f")
            novo_consumo = cg2.number_input("Consumo (km/L)", value=float(moto_ativa["consumo_kml"]), step=0.5, format="%.1f")

            cg4, cg5, cg6 = st.columns(3)
            novo_seguro = cg4.number_input("Seguro Anual (R$)", value=float(moto_ativa["seguro_anual"]), step=10.0, format="%.2f")
            novo_licenc = cg5.number_input("IPVA/Licenc. (R$)", value=float(moto_ativa["licenciamento_anual"]), step=5.0, format="%.2f")
            nova_proj = cg6.number_input("Projeção Anual (km)", value=float(moto_ativa["projecao_anual_km"]), step=500.0, format="%.0f")

            if st.form_submit_button("Salvar Parâmetros da Moto", use_container_width=True):
                moto_ativa["apelido"] = edit_apelido.strip() or moto_ativa["apelido"]
                moto_ativa["hodometro"] = novo_odo
                moto_ativa["preco_gasolina"] = novo_preco_gas
                moto_ativa["consumo_kml"] = novo_consumo
                moto_ativa["seguro_anual"] = novo_seguro
                moto_ativa["licenciamento_anual"] = novo_licenc
                moto_ativa["projecao_anual_km"] = nova_proj
                save_data(db, st.session_state.user_key)
                st.success("Parâmetros atualizados e Custo/Km recalculado!")
                st.rerun()

    st.subheader(f"🔧 Saúde das Peças — {moto_ativa['apelido']}")
    for idx, p in enumerate(moto_ativa["pecas"]):
        rodados = moto_ativa["hodometro"] - p["ultima_km"]
        restantes = p["intervalo"] - rodados
        pct = min(max(rodados / p["intervalo"], 0.0), 1.0)
        status_icon = "🟢 OK" if restantes > p["intervalo"] * 0.15 else ("🟡 ATENÇÃO" if restantes > 0 else "🔴 VENCIDO")
        col_p1, col_p2 = st.columns([3, 1])
        col_p1.markdown(f"**{p['nome']}** — {status_icon} (`{restantes:,} km restantes` | R$ {p['custo']:.0f})")
        col_p1.progress(pct)
        if col_p2.button("Troquei Hoje", key=f"troca_{moto_ativa['id']}_{idx}", use_container_width=True):
            moto_ativa["pecas"][idx]["ultima_km"] = moto_ativa["hodometro"]
            save_data(db, st.session_state.user_key)
            st.toast(f"{p['nome']} zerado em {moto_ativa['hodometro']} km!")
            st.rerun()

    with st.expander("✏️ Editar Custo, Intervalo ou Última Troca das Peças"):
        peca_nomes = [p["nome"] for p in moto_ativa["pecas"]]
        peca_esc = st.selectbox("Escolha o componente:", options=peca_nomes, key=f"sel_peca_{moto_ativa['id']}")
        idx_p = peca_nomes.index(peca_esc)
        p_atual = moto_ativa["pecas"][idx_p]

        with st.form("form_editar_peca"):
            ep1, ep2, ep3 = st.columns(3)
            novo_custo_p = ep1.number_input("Valor Pago (R$)", value=float(p_atual["custo"]), step=5.0)
            novo_interv_p = ep2.number_input("Intervalo (km)", value=int(p_atual["intervalo"]), step=500)
            nova_ult_km = ep3.number_input("Km Última Troca", value=int(p_atual["ultima_km"]), step=100)

            if st.form_submit_button("Atualizar Peça", use_container_width=True):
                moto_ativa["pecas"][idx_p]["custo"] = novo_custo_p
                moto_ativa["pecas"][idx_p]["intervalo"] = novo_interv_p
                moto_ativa["pecas"][idx_p]["ultima_km"] = nova_ult_km
                save_data(db, st.session_state.user_key)
                st.success(f"{peca_esc} atualizado!")
                st.rerun()

    if len(motos_dict) > 1:
        with st.expander("🗑️ Excluir Moto da Garagem"):
            st.warning(f"Isso removerá '{moto_ativa['apelido']}' da garagem.")
            if st.button(f"Remover {moto_ativa['apelido']}", type="primary"):
                del motos_dict[moto_ativa["id"]]
                db["moto_ativa_id"] = list(motos_dict.keys())[0]
                save_data(db, st.session_state.user_key)
                st.toast("Moto removida da garagem!")
                st.rerun()

# --- ABA 4: TERMÔMETRO CLT ---
with tab_clt:
    st.subheader("Comparativo Real vs. CLT (+30% Periculosidade)")
    dias_trab = len(set(t["data"] for t in db["turnos"])) if db["turnos"] else 0
    total_km_clt = sum(t["km"] for t in db["turnos"])
    bruto_clt = sum(t["bruto"] for t in db["turnos"])

    custo_moto_clt = 0.0
    for t in db["turnos"]:
        m_t = motos_dict.get(t.get("moto_id"), moto_ativa)
        _, _, c_km_t = calcular_custos_moto(m_t)
        custo_moto_clt += t["km"] * c_km_t

    liquido_clt = bruto_clt - custo_moto_clt - sum(t["extras"] for t in db["turnos"])
    
    meta_proporcional = dias_trab * META_CLT_DIARIA
    empate_bruto = meta_proporcional + custo_moto_clt
    indice_clt = (liquido_clt / meta_proporcional * 100) if meta_proporcional > 0 else 0

    st.metric("Índice de Remuneração Real (% do Piso CLT)", f"{indice_clt:.1f}%", delta=f"R$ {liquido_clt - meta_proporcional:+.2f} vs CLT")
    
    c_clt1, c_clt2 = st.columns(2)
    c_clt1.metric("Meta Líquida CLT (Período)", f"R$ {meta_proporcional:.2f}")
    c_clt2.metric("Bruto Mínimo de Empate", f"R$ {empate_bruto:.2f}")

    st.caption(
        f"Base CLT 2026: R$ {PISO_CLT_MENSAL:.2f}/mês (Salário Mínimo + 30% Periculosidade + 13º + Férias 1/3 + FGTS + INSS MEI + VA = R$ {META_CLT_DIARIA:.2f}/dia). "
        f"Calculado sobre **{dias_trab} dia(s) único(s)** trabalhado(s)."
    )
