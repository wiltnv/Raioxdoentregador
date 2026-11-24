# -*- coding: utf-8 -*-
"""
Raio-X do Entregador — Aplicativo Principal
"""

from datetime import datetime, date
import streamlit as st
from streamlit_searchbox import st_searchbox
from streamlit_js_eval import get_geolocation

from catalogo_motos import CATALOGO_MOTOS, ESTABELECIMENTOS_LISTA, criar_moto_do_catalogo
from database_supabase import (
    DATA_INICIO_CICLO,
    get_supabase_client,
    get_default_user_key,
    carregar_estado,
    salvar_estado,
    registrar_metrica_observatorio,
)
from calculos_e_rotas import (
    DIAS_UTEIS_MES,
    HORAS_DIA_CLT,
    PISO_DIARIO_CLT_2026,
    calcular_custo_km_detalhado,
    avaliar_pecas,
    buscar_enderecos_autocomplete,
    buscar_nomes_searchbox,
    reverso_gps_nominatim,
    calcular_rota_osrm,
    gerar_texto_whatsapp_rota,
)

st.set_page_config(
    page_title="Raio-X do Entregador",
    page_icon="🏍️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1100px; }
    div[data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 12px 14px;
        border-radius: 10px;
    }
    .badge-ok { background:#1f6feb22; color:#58a6ff; padding:4px 10px; border-radius:6px; font-size:0.85rem; }
    .badge-err { background:#f8514922; color:#ff7b72; padding:4px 10px; border-radius:6px; font-size:0.85rem; }
</style>
""", unsafe_allow_html=True)


def persistir_estado():
    ok = salvar_estado(st.session_state["user_key"], st.session_state["estado"])
    st.session_state["ultimo_save_ok"] = ok
    return ok


if "user_key" not in st.session_state:
    st.session_state["user_key"] = get_default_user_key()

if "estado" not in st.session_state:
    st.session_state["estado"] = carregar_estado(st.session_state["user_key"])

estado = st.session_state["estado"]
motos = estado.get("motos", {})
moto_ativa_id = estado.get("moto_ativa_id")
if moto_ativa_id not in motos and motos:
    moto_ativa_id = next(iter(motos.keys()))
    estado["moto_ativa_id"] = moto_ativa_id

moto_atual = motos[moto_ativa_id]


with st.sidebar:
    st.header("🏍️ Garagem & Perfil")
    sb_client = get_supabase_client()
    if sb_client is None:
        st.markdown('<span class="badge-err">⚠️ Supabase: Chaves ausentes</span>', unsafe_allow_html=True)
    elif st.session_state.get("ultimo_save_ok") is False:
        st.markdown('<span class="badge-err">❌ Falha ao gravar no Supabase</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-ok">✅ Supabase: Conectado</span>', unsafe_allow_html=True)

    st.divider()
    nomes_motos = {mid: f"{m['apelido']} ({m['hodometro']:,} km)" for mid, m in motos.items()}
    nova_selecao = st.selectbox(
        "Veículo Ativo",
        options=list(nomes_motos.keys()),
        index=list(nomes_motos.keys()).index(moto_ativa_id),
        format_func=lambda x: nomes_motos[x],
        key="sb_seletor_moto",
    )
    if nova_selecao != moto_ativa_id:
        estado["moto_ativa_id"] = nova_selecao
        persistir_estado()
        st.rerun()

    st.divider()
    st.subheader("📍 Localidade (Observatório)")
    cidade_in = st.text_input("Cidade", value=estado.get("cidade", "Araras"), key="sb_cidade")
    uf_in = st.text_input("UF", value=estado.get("estado", "SP"), max_chars=2, key="sb_uf")
    if st.button("Salvar Localidade", use_container_width=True, key="sb_btn_loc"):
        estado["cidade"] = cidade_in.strip() or "Araras"
        estado["estado"] = uf_in.strip().upper() or "SP"
        if persistir_estado():
            st.success("Localidade salva!")
custo_info = calcular_custo_km_detalhado(moto_atual, estado)
custo_km_total = custo_info["custo_km_total"]
pecas_avaliadas = avaliar_pecas(moto_atual)
alertas_criticos = [p for p in pecas_avaliadas if p["status"] in ("VENCIDA", "ATENÇÃO")]

turnos_moto = [
    t for t in estado.get("turnos", [])
    if t.get("moto_id") == moto_ativa_id and t.get("data", "") >= DATA_INICIO_CICLO
]
total_km_ciclo = sum(float(t.get("km_rodado", 0)) for t in turnos_moto)
total_bruto_ciclo = sum(float(t.get("bruto", 0)) for t in turnos_moto)
total_horas_ciclo = sum(float(t.get("horas", 0)) for t in turnos_moto)
custo_operacional_ciclo = total_km_ciclo * custo_km_total
lucro_liquido_ciclo = total_bruto_ciclo - custo_operacional_ciclo


@st.dialog("⏱️ Registrar Novo Turno")
def modal_turno():
    with st.form("form_modal_turno"):
        data_t = st.date_input("Data do Turno", value=date.today())
        col1, col2 = st.columns(2)
        km_ini = col1.number_input("KM Inicial", min_value=0, value=int(moto_atual["hodometro"]), step=1)
        km_fim = col2.number_input("KM Final", min_value=0, value=int(moto_atual["hodometro"]) + 100, step=1)
        col3, col4 = st.columns(2)
        bruto_t = col3.number_input("Faturamento Bruto (R$)", min_value=0.0, value=150.0, step=5.0)
        horas_t = col4.number_input("Horas Trabalhadas", min_value=0.5, max_value=24.0, value=8.0, step=0.5)
        estab_t = st.selectbox("Estabelecimento / Origem", options=ESTABELECIMENTOS_LISTA)
        obs_t = st.text_input("Observação (opcional)")
        if st.form_submit_button("✅ Salvar Turno", type="primary", use_container_width=True):
            if km_fim <= km_ini:
                st.error("KM Final deve ser maior que KM Inicial.")
            else:
                km_rod = float(km_fim - km_ini)
                novo_t = {
                    "id": f"turno_{int(datetime.now().timestamp())}",
                    "data": data_t.strftime("%Y-%m-%d"),
                    "moto_id": moto_ativa_id,
                    "km_inicial": int(km_ini),
                    "km_final": int(km_fim),
                    "km_rodado": km_rod,
                    "bruto": float(bruto_t),
                    "horas": float(horas_t),
                    "estabelecimento": estab_t,
                    "obs": obs_t.strip(),
                }
                estado["turnos"].append(novo_t)
                if int(km_fim) > int(moto_atual["hodometro"]):
                    moto_atual["hodometro"] = int(km_fim)
                persistir_estado()
                st.rerun()


@st.dialog("⛽ Registrar Abastecimento")
def modal_abastecimento():
    with st.form("form_modal_abast"):
        data_a = st.date_input("Data", value=date.today())
        col1, col2 = st.columns(2)
        litros_a = col1.number_input("Litros Abastecidos", min_value=0.1, value=10.0, step=0.5)
        valor_a = col2.number_input("Valor Total Pago (R$)", min_value=1.0, value=60.0, step=1.0)
        km_a = st.number_input("Hodômetro no Abastecimento (km)", min_value=0, value=int(moto_atual["hodometro"]), step=1)
        tanque_cheio = st.checkbox("Tanque Completo (para cálculo real de km/L)", value=True)
        if st.form_submit_button("✅ Salvar Abastecimento", type="primary", use_container_width=True):
            novo_a = {
                "id": f"abast_{int(datetime.now().timestamp())}",
                "data": data_a.strftime("%Y-%m-%d"),
                "moto_id": moto_ativa_id,
                "litros": float(litros_a),
                "valor_total": float(valor_a),
                "km": int(km_a),
                "tanque_cheio": tanque_cheio,
            }
            estado["abastecimentos"].append(novo_a)
            if int(km_a) > int(moto_atual["hodometro"]):
                moto_atual["hodometro"] = int(km_a)
            persistir_estado()
            st.rerun()


@st.dialog("🔧 Registrar Manutenção / Troca de Peça")
def modal_manutencao():
    nomes_pecas = [p["nome"] for p in moto_atual.get("pecas", [])] + ["Outra / Serviço Geral"]
    with st.form("form_modal_manut"):
        data_m = st.date_input("Data do Serviço", value=date.today())
        peca_sel = st.selectbox("Peça ou Serviço", options=nomes_pecas)
        col1, col2 = st.columns(2)
        km_m = col1.number_input("Hodômetro na Troca (km)", min_value=0, value=int(moto_atual["hodometro"]), step=1)
        valor_m = col2.number_input("Valor Total (Peça + Mão de Obra R$)", min_value=0.0, value=50.0, step=5.0)
        col3, col4 = st.columns(2)
        tipo_m = col3.selectbox("Tipo", ["Preventiva", "Corretiva"])
        oficina_m = col4.text_input("Oficina / Mecânico", value="Amaral")
        obs_m = st.text_input("Observação (opcional)")
        if st.form_submit_button("✅ Salvar Manutenção", type="primary", use_container_width=True):
            novo_m = {
                "id": f"man_{int(datetime.now().timestamp())}",
                "data": data_m.strftime("%Y-%m-%d"),
                "moto_id": moto_ativa_id,
                "km": int(km_m),
                "peca": peca_sel,
                "tipo": tipo_m,
                "oficina": oficina_m.strip(),
                "valor": float(valor_m),
                "obs": obs_m.strip(),
            }
            estado["manutencoes"].append(novo_m)
            for p in moto_atual.get("pecas", []):
                if p["nome"] == peca_sel:
                    p["ultima_km"] = int(km_m)
                    if valor_m > 0:
                        p["custo"] = float(valor_m)
            if int(km_m) > int(moto_atual["hodometro"]):
                moto_atual["hodometro"] = int(km_m)
            persistir_estado()
            st.rerun()
st.title("🏍️ Raio-X do Entregador")
st.caption(
    f"Veículo ativo: **{moto_atual['apelido']}** ({moto_atual['modelo']}) • "
    f"Hodômetro: **{moto_atual['hodometro']:,} km** • Ciclo ativo desde **{DATA_INICIO_CICLO}**"
)

aba1, aba2, aba3, aba4 = st.tabs([
    "📊 Painel & Ações",
    "🗺️ Cotação & WhatsApp",
    f"🔧 Saúde da Moto ({len(alertas_criticos)} alertas)",
    "📑 Relatórios & CLT",
])


with aba1:
    b1, b2, b3 = st.columns(3)
    if b1.button("⏱️ + Registrar Turno", type="primary", use_container_width=True):
        modal_turno()
    if b2.button("⛽ + Abastecimento", use_container_width=True):
        modal_abastecimento()
    if b3.button("🔧 + Manutenção", use_container_width=True):
        modal_manutencao()

    st.divider()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Custo Real / km", f"R$ {custo_km_total:.2f}", help="Combustível + Desgaste de Peças + Fixos/Aluguel")
    m2.metric("Faturamento Bruto (Ciclo)", f"R$ {total_bruto_ciclo:,.2f}", f"{total_km_ciclo:.0f} km rodados")
    m3.metric("Lucro Líquido Real", f"R$ {lucro_liquido_ciclo:,.2f}", f"Custo: R$ {custo_operacional_ciclo:,.2f}")
    ganho_hora_liq = (lucro_liquido_ciclo / total_horas_ciclo) if total_horas_ciclo > 0 else 0.0
    m4.metric("Ganho Líquido / Hora", f"R$ {ganho_hora_liq:.2f}", f"{total_horas_ciclo:.1f}h trabalhadas")

    with st.expander("🔍 Composição Detalhada do Custo por KM", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Combustível / km", f"R$ {custo_info['custo_comb_km']:.3f}", f"{custo_info['consumo_real']:.1f} km/L")
        c2.metric("Reserva Peças / km", f"R$ {custo_info['custo_pecas_km']:.3f}")
        c3.metric("Custos Fixos / km", f"R$ {custo_info['custo_fixo_km']:.3f}")
        c4.metric("Aluguel / km", f"R$ {custo_info['custo_aluguel_km']:.3f}")


with aba2:
    st.subheader("🗺️ Simulador de Corrida & Orçamento WhatsApp")
    cfg_orc = estado.get("orcamento_config", {"valor_km": 2.0, "taxa_minima": 8.0, "retorno_incluso": True})

    usar_gps = st.checkbox("📍 Usar minha localização atual (GPS) como ponto de partida", value=False)
    gps_atual = None
    if usar_gps:
        loc_data = get_geolocation()
        if loc_data and "coords" in loc_data:
            lat_gps = float(loc_data["coords"]["latitude"])
            lon_gps = float(loc_data["coords"]["longitude"])
            label_gps = reverso_gps_nominatim(lat_gps, lon_gps)
            gps_atual = {"label": label_gps, "lat": lat_gps, "lon": lon_gps}
            st.success(f"Localização capturada: **{label_gps}**")
        else:
            st.info("Aguardando permissão de localização no navegador/celular...")

    col_o, col_d = st.columns(2)
    with col_o:
        st.markdown("**1. Endereço de Coleta / Origem**")
        sel_o = st_searchbox(
            buscar_nomes_searchbox,
            placeholder="Digite rua, número ou local de coleta...",
            key="sb_origem_entrega",
        )
    with col_d:
        st.markdown("**2. Endereço de Entrega / Destino**")
        sel_d = st_searchbox(
            buscar_nomes_searchbox,
            placeholder="Digite rua, número ou local de entrega...",
            key="sb_destino_entrega",
        )

    col_p1, col_p2, col_p3 = st.columns(3)
    valor_km_cobrado = col_p1.number_input("Cobrar por KM (R$)", min_value=0.5, value=float(cfg_orc.get("valor_km", 2.0)), step=0.1)
    taxa_min = col_p2.number_input("Taxa Mínima (R$)", min_value=0.0, value=float(cfg_orc.get("taxa_minima", 8.0)), step=1.0)
    retorno_inc = col_p3.checkbox("Incluir volta (Ida + Volta)", value=bool(cfg_orc.get("retorno_incluso", True)))

    if isinstance(sel_o, dict) and isinstance(sel_d, dict):
        rota = calcular_rota_osrm(sel_o["lat"], sel_o["lon"], sel_d["lat"], sel_d["lon"])
        if rota:
            dist_desloc = 0.0
            if gps_atual:
                rota_desloc = calcular_rota_osrm(gps_atual["lat"], gps_atual["lon"], sel_o["lat"], sel_o["lon"])
                if rota_desloc:
                    dist_desloc = rota_desloc["distancia_km"]

            dist_ida = rota["distancia_km"]
            dist_total = (dist_ida * 2 if retorno_inc else dist_ida) + dist_desloc
            valor_calculado = max(taxa_min, dist_total * valor_km_cobrado)
            custo_corrida = dist_total * custo_km_total
            lucro_corrida = valor_calculado - custo_corrida

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Distância Total", f"{dist_total:.1f} km", f"Desloc: {dist_desloc:.1f} km | Ida: {dist_ida:.1f} km")
            r2.metric("Valor ao Cliente", f"R$ {valor_calculado:.2f}")
            r3.metric("Custo Operacional", f"R$ {custo_corrida:.2f}")
            r4.metric("Lucro Líquido", f"R$ {lucro_corrida:.2f}")

            msg_wpp, link_wpp = gerar_texto_whatsapp_rota(
                origem_label=sel_o["label"],
                destino_label=sel_d["label"],
                dist_km=dist_total,
                tempo_min=rota["duracao_min"],
                valor_cobrado=valor_calculado,
                retorno_incluso=retorno_inc,
                dist_deslocamento_km=dist_desloc,
            )
            st.link_button("📲 Enviar Orçamento no WhatsApp", url=link_wpp, type="primary", use_container_width=True)
            st.text_area("Texto do Orçamento:", value=msg_wpp, height=150)
        else:
            st.warning("Não foi possível calcular a rota viária entre esses pontos.")

with aba3:
    with st.expander(f"🔩 Plano de Manutenção Preventiva — {moto_atual['apelido']} ({len(pecas_avaliadas)} itens)", expanded=False):
        for idx, p in enumerate(pecas_avaliadas):
            cor_emoji = "🔴" if p["status"] == "VENCIDA" else ("🟡" if p["status"] == "ATENÇÃO" else "🟢")
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 1.2, 1.3])
                c1.markdown(f"**{cor_emoji} {p['nome']}** — `{p['status']}`")
                c1.caption(
                    f"Última troca: {p['ultima_km']:,} km • Próxima: {p['proxima_km']:,} km • "
                    f"Restam: **{p['km_restantes']:,} km**"
                )
                progresso = min(1.0, max(0.0, p["percentual_uso"] / 100.0))
                c2.progress(progresso, text=f"{p['percentual_uso']:.0f}% da vida útil")
                c3.metric("Reserva/km", f"R$ {p['custo_por_km']:.3f}")
                if c4.button("✅ Troquei Hoje", key=f"btn_zerar_{moto_ativa_id}_{idx}", use_container_width=True):
                    hodo_atual = int(moto_atual["hodometro"])
                    moto_atual["pecas"][idx]["ultima_km"] = hodo_atual
                    estado["manutencoes"].append({
                        "id": f"man_quick_{int(datetime.now().timestamp())}_{idx}",
                        "data": date.today().strftime("%Y-%m-%d"),
                        "moto_id": moto_ativa_id,
                        "km": hodo_atual,
                        "peca": p["nome"],
                        "tipo": "Preventiva",
                        "oficina": "Troca Rápida",
                        "valor": float(p.get("custo", 0.0)),
                        "obs": "Zerado pelo botão Troquei Hoje",
                    })
                    if persistir_estado():
                        st.success(f"{p['nome']} zerado em {hodo_atual:,} km!")
                        st.rerun()

    with st.expander("➕ Adicionar Nova Peça / Item de Desgaste", expanded=False):
        with st.form("form_nova_peca", clear_on_submit=True):
            np_col1, np_col2, np_col3 = st.columns(3)
            nome_nova_peca = np_col1.text_input("Nome da Peça/Serviço", placeholder="Ex: Rolamento Roda Traseira")
            intervalo_nova_peca = np_col2.number_input("Vida Útil (km)", min_value=500, value=10000, step=500)
            custo_nova_peca = np_col3.number_input("Custo Médio Troca (R$)", min_value=1.0, value=80.0, step=5.0)
            ultima_km_nova_peca = st.number_input("KM da Última Troca", min_value=0, value=int(moto_atual["hodometro"]), step=100)
            if st.form_submit_button("💾 Adicionar Peça ao Plano", type="primary"):
                if not nome_nova_peca.strip():
                    st.error("Informe o nome da peça.")
                else:
                    moto_atual.setdefault("pecas", []).append({
                        "nome": nome_nova_peca.strip(),
                        "intervalo": int(intervalo_nova_peca),
                        "custo": float(custo_nova_peca),
                        "ultima_km": int(ultima_km_nova_peca),
                    })
                    if persistir_estado():
                        st.success(f"Peça '{nome_nova_peca}' adicionada!")
                        st.rerun()

    with st.expander("⚙️ Editar Parâmetros de Consumo e Custos Fixos desta Moto", expanded=False):
        with st.form("form_config_moto"):
            col1, col2, col3 = st.columns(3)
            novo_hodo = col1.number_input("Hodômetro Atual (km)", min_value=0, value=int(moto_atual["hodometro"]), step=1)
            novo_cons = col2.number_input("Consumo Médio Base (km/L)", min_value=5.0, value=float(moto_atual.get("consumo_kml", 29.0)), step=0.5)
            novo_preco_comb = col3.number_input("Preço Gasolina/Etanol (R$/L)", min_value=1.0, value=float(moto_atual.get("preco_gasolina", 5.99)), step=0.05)

            col4, col5, col6 = st.columns(3)
            novo_doc = col4.number_input("Licenciamento / IPVA Anual (R$)", min_value=0.0, value=float(moto_atual.get("licenciamento_anual", 340.66)), step=10.0)
            novo_seg = col5.number_input("Seguro / Rastreador Anual (R$)", min_value=0.0, value=float(moto_atual.get("seguro_anual", 830.00)), step=10.0)
            nova_meta_km = col6.number_input("Projeção Anual (km/ano)", min_value=1000, value=int(float(moto_atual.get("projecao_anual_km", 37287))), step=500)

            if st.form_submit_button("💾 Atualizar Configurações da Moto", type="primary"):
                moto_atual["hodometro"] = int(novo_hodo)
                moto_atual["consumo_kml"] = float(novo_cons)
                moto_atual["preco_gasolina"] = float(novo_preco_comb)
                moto_atual["licenciamento_anual"] = float(novo_doc)
                moto_atual["seguro_anual"] = float(novo_seg)
                moto_atual["projecao_anual_km"] = float(nova_meta_km)
                if persistir_estado():
                    st.success("Configurações atualizadas e salvas!")
                    st.rerun()

    st.divider()
    st.subheader("🏍️ Garagem & Cadastro de Novo Veículo")
    nomes_motos_aba = {mid: f"{m['apelido']} ({m['hodometro']:,} km)" for mid, m in motos.items()}
    sel_moto_aba = st.selectbox(
        "Trocar Veículo Ativo",
        options=list(nomes_motos_aba.keys()),
        index=list(nomes_motos_aba.keys()).index(moto_ativa_id),
        format_func=lambda x: nomes_motos_aba[x],
        key="aba3_seletor_moto",
    )
    if sel_moto_aba != moto_ativa_id:
        estado["moto_ativa_id"] = sel_moto_aba
        persistir_estado()
        st.rerun()

    with st.expander("➕ Cadastrar Novo Veículo", expanded=False):
        with st.form("form_nova_moto_aba3", clear_on_submit=True):
            novo_apelido = st.text_input("Apelido da Moto", placeholder="Ex: CG 160 Start Trabalho")
            modelo_sel = st.selectbox("Perfil Base do Catálogo", options=list(CATALOGO_MOTOS.keys()))
            hodometro_novo = st.number_input("Hodômetro Atual (km)", min_value=0, value=0, step=100)
            tipo_posse_novo = st.radio("Posse do Veículo", ["Própria", "Alugada"], horizontal=True)
            aluguel_semanal_novo = st.number_input("Aluguel Semanal (R$)", min_value=0.0, value=0.0, step=10.0)
            km_franquia_novo = st.number_input("Franquia Semanal (km)", min_value=100, value=1000, step=100)
            sub_moto = st.form_submit_button("💾 Salvar Novo Veículo", type="primary", use_container_width=True)

            if sub_moto:
                if not novo_apelido.strip():
                    st.error("Informe um apelido para a moto.")
                else:
                    novo_id = f"moto_{int(datetime.now().timestamp())}"
                    nova_moto = criar_moto_do_catalogo(
                        moto_id=novo_id,
                        apelido=novo_apelido.strip(),
                        modelo_catalogo=modelo_sel,
                        hodometro_inicial=int(hodometro_novo),
                    )
                    nova_moto["tipo"] = "alugada" if tipo_posse_novo == "Alugada" else "propria"
                    nova_moto["aluguel_semanal"] = float(aluguel_semanal_novo)
                    nova_moto["km_franquia_semanal"] = float(km_franquia_novo)

                    estado["motos"][novo_id] = nova_moto
                    estado["moto_ativa_id"] = novo_id
                    if persistir_estado():
                        st.success(f"Veículo '{novo_apelido}' salvo no Supabase!")
                        st.rerun()


with aba4:
    st.subheader("⚖️ Comparativo Equivalência CLT 2026 (Piso + 30% Periculosidade)")
    dias_trabalhados = len({t["data"] for t in turnos_moto})
    meta_clt_periodo = dias_trabalhados * PISO_DIARIO_CLT_2026
    indice_clt = (lucro_liquido_ciclo / meta_clt_periodo * 100.0) if meta_clt_periodo > 0 else 0.0

    k1, k2, k3 = st.columns(3)
    k1.metric("Dias Trabalhados no Ciclo", f"{dias_trabalhados} dias", f"Piso CLT/dia: R$ {PISO_DIARIO_CLT_2026:.2f}")
    k2.metric("Referência CLT Equivalente", f"R$ {meta_clt_periodo:,.2f}", f"Base: {DIAS_UTEIS_MES}d x {HORAS_DIA_CLT:.2f}h")
    k3.metric("Índice de Eficiência CLT", f"{indice_clt:.1f}%", "Acima de 100% supera o piso CLT")

    if st.button("📡 Contribuir Anonimamente com o Observatório Nacional"):
        registrar_metrica_observatorio(
            cidade=estado.get("cidade", "Araras"),
            estado_uf=estado.get("estado", "SP"),
            categoria_moto=moto_atual.get("categoria", "Urbana"),
            custo_km=custo_km_total,
            indice_clt=indice_clt,
        )
        st.success("Métrica anônima enviada ao Observatório!")

    st.divider()
    st.subheader("📋 Histórico de Turnos do Ciclo")
    if turnos_moto:
        for t in reversed(turnos_moto):
            liq_t = float(t["bruto"]) - (float(t["km_rodado"]) * custo_km_total)
            st.markdown(
                f"- **{t['data']}** | {t['estabelecimento']} | "
                f"`{t['km_rodado']:.0f} km` ({t['horas']}h) | "
                f"Bruto: **R$ {t['bruto']:.2f}** → Líquido: **R$ {liq_t:.2f}**"
            )
    else:
        st.info("Nenhum turno registrado neste ciclo para esta moto.")

    st.divider()
    st.subheader("🛠️ Histórico Completo de Manutenções")
    manut_moto = [m for m in estado.get("manutencoes", []) if m.get("moto_id") == moto_ativa_id]
    if manut_moto:
        for m in reversed(manut_moto):
            st.markdown(
                f"- **{m['data']}** (`{m['km']:,} km`) | **{m['peca']}** ({m['tipo']}) | "
                f"Oficina: {m.get('oficina', '-')} | **R$ {m['valor']:.2f}**"
            )
    else:
        st.info("Nenhuma manutenção registrada para este veículo.")
