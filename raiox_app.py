import streamlit as st
import pandas as pd
import urllib.parse
from datetime import date, datetime
from catalogo_motos import ESTABELECIMENTOS_LISTA, CATALOGO_MOTOS, criar_moto_do_catalogo
from calculos_moto import DATA_INICIO_CICLO, PISO_CLT_MENSAL, META_CLT_DIARIA, migrate_data, calc_custos_moto
from servicos_externos import load_state, save_state, buscar_enderecos_online, calcular_rota_osrm, interpretar_audio_gemini
from auth_manager import render_tela_login

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

if "perfil_logado" not in st.session_state:
    render_tela_login()
    st.stop()

perfil = st.session_state["perfil_logado"]
papel = perfil.get("papel", "autonomo")
empresa_info = perfil.get("empresa")
user_key = perfil.get("state_key", "beta_teste")
nome_usuario = perfil.get("nome", "Entregador")

if st.secrets.get("APP_ENV", "prod") == "staging":
    st.warning("🧪 **AMBIENTE BETA (V3.0)** — Você está testando a nova versão com dados isolados.")

with st.sidebar:
    st.header("👤 Minha Conta")
    badge_papel = "🏢 Gestor" if papel == "gestor" else ("🛵 Piloto" if papel == "piloto" else "🏍️ Autônomo")
    st.markdown(f"**{nome_usuario}** ({badge_papel})")
    if empresa_info:
        st.info(f"🏢 **{empresa_info.get('nome_empresa')}**\n\nCódigo Convite: `{empresa_info.get('codigo_convite')}`")
    if st.button("🔄 Recarregar da Nuvem", use_container_width=True):
        st.session_state.pop("db", None)
        st.rerun()
    if st.button("🚪 Sair / Trocar Conta", use_container_width=True):
        st.session_state.pop("perfil_logado", None)
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

motos_dict = {m["id"]: m for m in db["motos"]}
col_t1, col_t2 = st.columns([1.6, 1])
col_t1.title("🏍️ Raio-X do Entregador")
moto_escolhida_id = col_t2.selectbox(
    "Moto Ativa:",
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

with st.expander("🎙️ Lançar por Voz (IA Gemini — Gasolina, Turno ou Manutenção)"):
    audio_gravado = st.audio_input("Toque no microfone e fale (ex: 'Coloquei 10 litros, deu 60 reais, hodômetro 81350')", key="voz_cmd")
    if audio_gravado is not None:
        audio_bytes = audio_gravado.getvalue()
        if st.session_state.get("ultimo_audio_len") != len(audio_bytes):
            with st.spinner("Ouvindo e interpretando lançamento..."):
                res_ia = interpretar_audio_gemini(audio_bytes, audio_gravado.type, int(moto_ativa["hodometro"]))
                st.session_state["voz_resultado"] = res_ia
                st.session_state["ultimo_audio_len"] = len(audio_bytes)

    voz_res = st.session_state.get("voz_resultado")
    if isinstance(voz_res, dict):
        if "erro" in voz_res:
            st.error(voz_res["erro"])
        else:
            st.info(f"🤖 **Entendi:** {voz_res.get('resumo', 'Lançamento identificado')} (Tipo: **{voz_res.get('tipo', '').upper()}**)")
            tipo_v = voz_res.get("tipo", "")
            odo_v = int(voz_res.get("hodometro") or moto_ativa["hodometro"])

            if tipo_v == "abastecimento":
                cv1, cv2, cv3 = st.columns(3)
                v_litros = cv1.number_input("Litros", value=float(voz_res.get("litros") or 10.0), step=0.5, key="v_lit")
                v_valor = cv2.number_input("Valor Total (R$)", value=float(voz_res.get("valor_total") or 59.90), step=1.0, key="v_val")
                v_odo = cv3.number_input("Hodômetro", value=odo_v, step=1, key="v_odo_a")
                if st.button("✅ Confirmar Abastecimento por Voz", type="primary", use_container_width=True):
                    db["abastecimentos"].append({
                        "data": str(date.today()), "moto_id": moto_ativa["id"], "hodometro": int(v_odo),
                        "litros": float(v_litros), "valor_pago": float(v_valor),
                        "preco_litro": round(v_valor / max(v_litros, 0.1), 2),
                        "posto": voz_res.get("posto_ou_oficina", "Via Voz"), "piloto": nome_usuario
                    })
                    if int(v_odo) > int(moto_ativa["hodometro"]):
                        moto_ativa["hodometro"] = int(v_odo)
                    save_state(user_key, db)
                    st.session_state.pop("voz_resultado", None)
                    st.success("Abastecimento salvo!")
                    st.rerun()

            elif tipo_v == "turno":
                cv1, cv2, cv3 = st.columns(3)
                v_km_fim = cv1.number_input("Km Final", value=odo_v, step=1, key="v_kmf")
                v_app = cv2.number_input("Apps (R$)", value=float(voz_res.get("ganho_app") or 0.0), step=5.0, key="v_app")
                v_est = cv3.number_input("Estab. (R$)", value=float(voz_res.get("ganho_estab") or 0.0), step=5.0, key="v_est")
                if st.button("✅ Confirmar Turno por Voz", type="primary", use_container_width=True):
                    dist_v = int(v_km_fim) - int(moto_ativa["hodometro"])
                    if dist_v <= 0:
                        st.error("Km Final precisa ser maior que o hodômetro atual.")
                    else:
                        db["turnos"].append({
                            "data": str(date.today()), "moto_id": moto_ativa["id"], "piloto": nome_usuario,
                            "km_ini": int(moto_ativa["hodometro"]), "km_fim": int(v_km_fim), "km": dist_v,
                            "ganho_app": float(v_app), "estabelecimento": voz_res.get("estabelecimento") or "Via Voz",
                            "ganho_estab": float(v_est), "bruto": float(v_app + v_est),
                            "extras": 0.0, "custo_km": round(custo_total_km, 4)
                        })
                        moto_ativa["hodometro"] = int(v_km_fim)
                        save_state(user_key, db)
                        st.session_state.pop("voz_resultado", None)
                        st.success("Turno salvo!")
                        st.rerun()

            elif tipo_v == "manutencao":
                cv1, cv2, cv3 = st.columns(3)
                v_comp = cv1.text_input("Serviço / Peça", value=str(voz_res.get("componente") or "Manutenção Geral"), key="v_comp")
                v_ofic = cv2.text_input("Oficina", value=str(voz_res.get("posto_ou_oficina") or "Não informada"), key="v_ofic")
                v_tot_m = cv3.number_input("Valor Total (R$)", value=float(voz_res.get("valor_total") or 0.0), step=5.0, key="v_tot_m")
                v_odo_m = st.number_input("Hodômetro (km)", value=odo_v, step=1, key="v_odo_m")
                if st.button("✅ Confirmar Manutenção por Voz", type="primary", use_container_width=True):
                    db["manutencoes"].append({
                        "data": str(date.today()), "moto_id": moto_ativa["id"], "hodometro": int(v_odo_m),
                        "tipo": "preventiva", "componente": v_comp.strip() or "Serviço via Voz",
                        "oficina": v_ofic.strip() or "Não informada", "valor_peca": float(v_tot_m),
                        "valor_total": float(v_tot_m), "obs": f"[{nome_usuario}] {voz_res.get('resumo') or 'Via voz'}"
                    })
                    if int(v_odo_m) > int(moto_ativa["hodometro"]):
                        moto_ativa["hodometro"] = int(v_odo_m)
                    save_state(user_key, db)
                    st.session_state.pop("voz_resultado", None)
                    st.success("Manutenção salva!")
                    st.rerun()
if papel == "piloto":
    tab_hoje, tab_sim, tab_garagem = st.tabs([
        "📊 1. Meu Turno",
        "⚡ 2. Simular & Orçar",
        "🔧 3. Abastecer & Oficina"
    ])
    tab_clt = None
else:
    tab_hoje, tab_sim, tab_garagem, tab_clt = st.tabs([
        "📊 1. Meu Dia" if papel == "autonomo" else "📊 1. Operação Frota",
        "⚡ 2. Simular & Orçar",
        "🔧 3. Garagem & Frota",
        "⚖️ 4. Termômetro CLT" if papel == "autonomo" else "📈 4. Fechamento Gestão"
    ])

with tab_hoje:
    col_f1, col_f2 = st.columns(2)
    filtro_visao = col_f1.radio("Moto:", ["Apenas Moto Ativa", "Todas as Motos"], horizontal=True)
    filtro_periodo = col_f2.radio("Período:", [f"Ciclo Atual (Desde {DATA_INICIO_CICLO})", "Todos os Registros"], horizontal=True)

    turnos_filtrados = [
        t for t in db["turnos"]
        if (filtro_visao == "Todas as Motos" or t.get("moto_id") == moto_ativa["id"])
        and (filtro_periodo == "Todos os Registros" or t["data"] >= DATA_INICIO_CICLO)
        and (papel != "piloto" or t.get("piloto") == nome_usuario)
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
    if papel == "piloto":
        c1.metric("Meus Ganhos Brutos", f"R$ {total_bruto:.2f}")
        c2.metric("Combustível Estimado", f"R$ {total_gas:.2f}")
        c3.metric("Km Rodados", f"{total_km:,} km")
    else:
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
                        "data": str(data_turno), "moto_id": moto_ativa["id"], "piloto": nome_usuario,
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
            row_item = {
                "Data": t["data"], "Moto": m_ref["apelido"], "Origem": t["estabelecimento"],
                "Km": t["km"], "Bruto (R$)": round(t["bruto"], 2)
            }
            if papel != "piloto":
                row_item["Piloto"] = t.get("piloto", "-")
                row_item["Líquido (R$)"] = round(liq, 2)
            rows.append(row_item)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if papel != "piloto":
            with st.expander("🗑️ Excluir um turno lançado errado"):
                opcoes_ex = [f"{i} | {t['data']} — {t['estabelecimento']} ({t['km']} km | R$ {t['bruto']:.2f})" for i, t in enumerate(db["turnos"])]
                sel_ex = st.selectbox("Selecione o turno:", options=opcoes_ex)
                if st.button("Confirmar Exclusão do Turno", type="primary"):
                    idx_rem = int(sel_ex.split(" | "))
                    db["turnos"].pop(idx_rem)
                    save_state(user_key, db)
                    st.rerun()
