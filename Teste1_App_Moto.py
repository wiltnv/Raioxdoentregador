import streamlit as st
import pandas as pd
import urllib.parse
from datetime import date, datetime
from catalogo_motos import ESTABELECIMENTOS_LISTA, CATALOGO_MOTOS, criar_moto_do_catalogo
from calculos_moto import DATA_INICIO_CICLO, PISO_CLT_MENSAL, META_CLT_DIARIA, migrate_data, calc_custos_moto
from servicos_externos import load_state, save_state, buscar_enderecos_online, calcular_rota_osrm, interpretar_audio_gemini

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

st.set_page_config(page_title="Raio-X do Entregador", page_icon="🏍️", layout="centered")

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
    guia_txt = "\n".join([
        "1. **Garagem:** Ajuste o preço da gasolina, consumo e peças da sua moto para descobrir seu **Custo Real por Km**.",
        "2. **Simular & Orçar:** Antes de aceitar uma entrega ou passar preço para cliente, calcule o **Lucro Líquido Real** já descontando desgaste e combustível.",
        "3. **Meu Dia & Termômetro CLT:** No fim do turno, lance os km rodados e ganhos. O app separa a **Caixinha da Moto** e mostra se você ganhou acima do **Piso CLT + 30% Periculosidade**."
    ])
    st.markdown(guia_txt)

tab_hoje, tab_sim, tab_garagem, tab_clt = st.tabs([
    "📊 1. Meu Dia",
    "⚡ 2. Simular & Orçar",
    "🔧 3. Garagem & Custos",
    "⚖️ 4. Termômetro CLT"
])

with tab_hoje:
    col_f1, col_f2 = st.columns(2)
    filtro_visao = col_f1.radio("Moto:", ["Apenas Moto Ativa", "Todas as Motos"], horizontal=True)
    filtro_periodo = col_f2.radio("Período:", [f"Ciclo Atual (Desde {DATA_INICIO_CICLO})", "Todos os Registros"], horizontal=True)

    turnos_filtrados = [
        t for t in db["turnos"]
        if (filtro_visao == "Todas as Motos" or t.get("moto_id") == moto_ativa["id"])
        and (filtro_periodo == "Todos os Registros" or t["data"] >= DATA_INICIO_CICLO)
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
                        "data": str(data_turno), "moto_id": moto_ativa["id"],
                        "km_ini": km_ini, "km_fim": km_fim, "km": dist,
                        "ganho_app": ganho_app, "estabelecimento": local_reg,
                        "ganho_estab": ganho_fixo, "bruto": bruto_dia,
                        "extras": gastos_extras, "custo_km": round(custo_total_km, 4)
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
                "Data": t["data"], "Moto": m_ref["apelido"], "Origem": t["estabelecimento"],
                "Km": t["km"], "Bruto (R$)": round(t["bruto"], 2), "Líquido (R$)": round(liq, 2)
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with st.expander("🗑️ Excluir um turno lançado errado"):
            opcoes_ex = [f"{i} | {t['data']} — {t['estabelecimento']} ({t['km']} km | R$ {t['bruto']:.2f})" for i, t in enumerate(db["turnos"])]
            sel_ex = st.selectbox("Selecione o turno:", options=opcoes_ex)
            if st.button("Confirmar Exclusão do Turno", type="primary"):
                idx_rem = int(sel_ex.split(" | ")[0])
                db["turnos"].pop(idx_rem)
                save_state(user_key, db)
                st.rerun()
with tab_sim:
    sub_app, sub_orc = st.tabs(["⚡ Simular Corrida de App", "🧾 Calcular Orçamento para Cliente"])

    with sub_app:
        col_s1, col_s2 = st.columns(2)
        val_corrida = col_s1.number_input("Valor Ofertado (R$)", min_value=0.0, value=12.0, step=0.5, key="app_val")
        dist_corrida = col_s2.number_input("Distância Total até Entrega (km)", min_value=0.1, value=6.0, step=0.5, key="app_dist")

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

    with sub_orc:
        st.subheader("Cálculo de Rota e Orçamento")
        modo_partida = st.radio(
            "Deslocamento até a retirada:",
            ["📍 Estou no local / Não cobrar deslocamento", "📡 Meu GPS Atual (HTTPS)", "🏍️ Digitar Rua onde estou"],
            horizontal=True,
            key="orc_modo_partida"
        )

        def _ler_busca(res):
            if isinstance(res, dict) and "lat" in res:
                return res, res.get("label", "")
            if isinstance(res, (list, tuple)) and len(res) == 2:
                lbl, d = res
                if isinstance(d, dict) and "lat" in d:
                    return d, str(lbl)
            return None, ""

        coord_partida = None
        if modo_partida == "📡 Meu GPS Atual (HTTPS)":
            if HAS_GEO:
                loc = get_geolocation()
                if loc and "coords" in loc:
                    coord_partida = {"lat": loc["coords"]["latitude"], "lon": loc["coords"]["longitude"]}
                    st.success(f"GPS capturado: {coord_partida['lat']:.5f}, {coord_partida['lon']:.5f}")
                else:
                    st.info("Aguardando permissão de localização no navegador...")
            else:
                st.warning("Pacote streamlit-js-eval não instalado.")
        elif modo_partida == "🏍️ Digitar Rua onde estou":
            if HAS_SEARCHBOX:
                res_part = st_searchbox(buscar_enderecos_online, placeholder="Ex: Av. Loreto", key="sb_part")
                coord_partida, _ = _ler_busca(res_part)

        col_e1, col_e2 = st.columns([3, 1])
        coord_retirada, label_retirada = None, ""
        with col_e1:
            if HAS_SEARCHBOX:
                res_ret = st_searchbox(buscar_enderecos_online, placeholder="Endereço de Retirada (Rua, Comércio ou CEP)", key="sb_ret")
                coord_retirada, label_retirada = _ler_busca(res_ret)
            else:
                label_retirada = st.text_input("Endereço de Retirada")
        num_ret = col_e2.text_input("Nº / Compl. (Ret.)", key="num_ret")

        col_e3, col_e4 = st.columns([3, 1])
        coord_entrega, label_entrega = None, ""
        with col_e3:
            if HAS_SEARCHBOX:
                res_ent = st_searchbox(buscar_enderecos_online, placeholder="Endereço de Entrega (Rua, Comércio ou CEP)", key="sb_ent")
                coord_entrega, label_entrega = _ler_busca(res_ent)
            else:
                label_entrega = st.text_input("Endereço de Entrega")
        num_ent = col_e4.text_input("Nº / Compl. (Ent.)", key="num_ent")

        km_desloc = 0.0
        km_entrega_auto = 6.0
        tempo_total_min = 0
        if coord_retirada and coord_entrega:
            d_ent, t_ent = calcular_rota_osrm(coord_retirada, coord_entrega)
            if d_ent:
                km_entrega_auto = d_ent
                tempo_total_min += int(t_ent or 0)
                st.success(f"🗺️ Rota Retirada ➔ Entrega: **{d_ent} km** (~{t_ent} min)")
            if coord_partida:
                d_desl, t_desl = calcular_rota_osrm(coord_partida, coord_retirada)
                if d_desl:
                    km_desloc = d_desl
                    tempo_total_min += int(t_desl or 0)
                    st.caption(f"Deslocamento até Retirada: **{d_desl} km** (~{t_desl} min)")

        col_o1, col_o2, col_o3 = st.columns(3)
        km_entrega = col_o1.number_input("Km Entrega", min_value=0.1, value=float(km_entrega_auto), step=0.5, key=f"km_ent_{km_entrega_auto}")
        valor_km_cobrar = col_o2.number_input("Cobrar por Km (R$)", min_value=0.5, value=2.0, step=0.25, key="orc_val_km")
        taxa_minima = col_o3.number_input("Taxa Mínima (R$)", min_value=0.0, value=8.0, step=1.0, key="orc_taxa_min")

        cobrar_desloc = st.checkbox("Incluir km de deslocamento até retirada no preço ao cliente", value=False, key="orc_chk_desl")
        km_cobrado = km_entrega + (km_desloc if cobrar_desloc else 0.0)
        km_rodado_real = km_entrega + km_desloc

        preco_cliente = max(taxa_minima, round(km_cobrado * valor_km_cobrar, 2))
        custo_operacional_orc = km_rodado_real * custo_total_km
        lucro_orc = preco_cliente - custo_operacional_orc

        oc1, oc2, oc3 = st.columns(3)
        oc1.metric("Valor ao Cliente", f"R$ {preco_cliente:.2f}")
        oc2.metric("Seu Custo Moto", f"- R$ {custo_operacional_orc:.2f}")
        oc3.metric("Seu Lucro Líquido", f"R$ {lucro_orc:.2f}")

        txt_ret = f"{label_retirada} (Nº {num_ret})".strip() if (label_retirada and num_ret) else (label_retirada or num_ret or "Ponto de Coleta")
        txt_ent = f"{label_entrega} (Nº {num_ent})".strip() if (label_entrega and num_ent) else (label_entrega or num_ent or "Destino")
        detalhe_km = f" (inclui {km_desloc:.1f} km deslocamento + {km_entrega:.1f} km entrega)" if (cobrar_desloc and km_desloc > 0) else ""
        detalhe_tempo = f" (aprox. {tempo_total_min} min)" if tempo_total_min > 0 else ""

        msg_whats = "\n".join([
            "Olá! Segue o orçamento da entrega de moto:",
            f"📍 *Retirada:* {txt_ret}",
            f"🏁 *Entrega:* {txt_ent}",
            f"📏 *Percurso:* {km_cobrado:.1f} km{detalhe_km}{detalhe_tempo}",
            f"💰 *Valor da entrega:* R$ {preco_cliente:.2f}",
            "⚠️ *Obs.:* Eventuais pedágios no trajeto não estão inclusos no valor acima."
        ])

        st.caption("Toque no ícone no canto superior direito da caixa abaixo para copiar tudo com 1 clique:")
        st.code(msg_whats, language="markdown")
        link_whats = f"https://wa.me/?text={urllib.parse.quote(msg_whats)}"
        st.link_button("📲 Enviar Orçamento no WhatsApp", link_whats, type="primary", use_container_width=True)
                
from aba_garagem import render_aba_garagem
from aba_clt import render_aba_clt

with tab_garagem:
    render_aba_garagem(db, user_key, moto_ativa, custo_gas_km, custo_reserva_km)

with tab_clt:
    render_aba_clt(db, motos_dict, moto_ativa)

