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

MANUTENCOES_BROS_PADRAO = [
    {"moto_id": "moto_1", "data": "2026-04-10", "hodometro": 58098, "componente": "Bateria (Partida Elétrica)", "oficina": "Poty", "valor_peca": 180.0, "valor_total": 180.0, "obs": "Garantia 50.000 km"},
    {"moto_id": "moto_1", "data": "2026-07-24", "hodometro": 68824, "componente": "Par de Pneus", "oficina": "Amaral", "valor_peca": 288.0, "valor_total": 308.0, "obs": "Dianteiro + Traseiro"},
    {"moto_id": "moto_1", "data": "2026-08-05", "hodometro": 70050, "componente": "Limpeza/Regulagem Carburador", "oficina": "Mineiro", "valor_peca": 120.0, "valor_total": 120.0, "obs": "Revisão completa"},
    {"moto_id": "moto_1", "data": "2026-08-05", "hodometro": 70050, "componente": "Cabos + Lubrificação", "oficina": "Mineiro", "valor_peca": 30.0, "valor_total": 45.0, "obs": "Acelerador/Embreagem"},
    {"moto_id": "moto_1", "data": "2026-09-18", "hodometro": 74545, "componente": "Pastilha Freio Dianteiro (ESD)", "oficina": "Amaral", "valor_peca": 60.0, "valor_total": 60.0, "obs": "Freio a disco dianteiro"},
    {"moto_id": "moto_1", "data": "2026-09-18", "hodometro": 74545, "componente": "Lona Freio Traseiro", "oficina": "Amaral", "valor_peca": 60.0, "valor_total": 40.0, "obs": "Tambor traseiro"},
    {"moto_id": "moto_1", "data": "2026-09-23", "hodometro": 75056, "componente": "Kit Relação / Transmissão", "oficina": "Amaral", "valor_peca": 165.0, "valor_total": 225.0, "obs": "Corrente, coroa e pinhão"},
    {"moto_id": "moto_1", "data": "2026-11-14", "hodometro": 80346, "componente": "Troca de Óleo", "oficina": "Amaral", "valor_peca": 30.0, "valor_total": 34.0, "obs": "Intervalo 1.500 km"}
]

def criar_moto_do_catalogo(moto_id, apelido, modelo_catalogo, hodometro_atual, preco_gasolina=5.99, ultimas_trocas_custom=None, hodometro_inicial=None):
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
        "hodometro_inicial": hodometro_inicial if hodometro_inicial is not None else hodometro_atual,
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
### 📋 Parte 2 de 2 (Cole logo abaixo da Parte 1 no `Teste1_App_Moto.py`)

```python
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
custo_gas_km, custo_reserva_km, custo_total_km, custo_pecas_km, custo_fixos_km = calcular_custos_moto(moto_ativa)

st.caption(
    f"Ativa: **{moto_ativa['apelido']}** ({moto_ativa['modelo']}) • "
    f"Hodômetro: **{moto_ativa['hodometro']:,} km** • "
    f"Custo Real: **R$ {custo_total_km:.3f}/km**"
)

with st.expander("📖 Como usar o app (Guia Rápido em 3 Passos)", expanded=False):
    st.markdown(
        """
        1. **Configure sua Moto (`3. Garagem & Manutenções`):** Ajuste o preço da gasolina, consumo e registre quando trocar peças para manter o **Custo Real/Km** calibrado.
        2. **Avalie Corridas ou Gere Orçamentos (`2. Simular & Orçar`):** Descubra na hora se uma corrida de app dá lucro líquido ou calcule rotas com GPS para clientes particulares no WhatsApp.
        3. **Feche o Turno (`1. Meu Dia`):** Ao encerrar o expediente, lance o Km inicial/final e os ganhos. O app separa automaticamente a **Caixinha da Moto** e compara seu ganho real com o piso CLT (`4. Termômetro CLT`).
        """
    )

tab_hoje, tab_sim, tab_garagem, tab_clt = st.tabs([
    "📊 1. Meu Dia (Turnos)",
    "⚡ 2. Simular & Orçar",
    "🔧 3. Garagem & Manutenções",
    "⚖️ 4. Termômetro CLT"
])

# --- ABA 1: MEU DIA (TURNOS) ---
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
        g_km, r_km, _, _, _ = calcular_custos_moto(m_turno)
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
            _, _, c_km_t, _, _ = calcular_custos_moto(m_t)
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