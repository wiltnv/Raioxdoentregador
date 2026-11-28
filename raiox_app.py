import streamlit as st
import pandas as pd
import json
import urllib.parse
from datetime import date, datetime
from catalogo_motos import CATALOGO_MOTOS, criar_moto_do_catalogo
from origens import campos_de_ganho
from calculos_moto import DATA_INICIO_CICLO, PISO_CLT_MENSAL, META_CLT_DIARIA, migrate_data, calc_custos_moto
from servicos_externos import (
    load_state, save_state, buscar_enderecos_online, calcular_rota_osrm, interpretar_audio_gemini,
    carregar_config_precos, salvar_config_precos, obter_moto_ativa_id, definir_moto_ativa,
)
from auth_manager import render_tela_login
from ui_turno import render_turno_em_andamento
from ui_convites import render_convites_gestor
from ui_origens import render_origens, render_gerenciar_locais, limpar_prefixo
from turnos import formatar_duracao

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

APP_VERSION = "3.0-beta2"

st.set_page_config(page_title="Raio-X do Entregador", page_icon="🏍️", layout="centered")

if "perfil_logado" not in st.session_state:
    render_tela_login()
    st.stop()

perfil = st.session_state["perfil_logado"]
papel = perfil.get("papel", "autonomo")
empresa_info = perfil.get("empresa")
user_key = perfil.get("state_key")
if not user_key:
    st.error("Sua conta está sem identificação de dados. Recarregue a página e entre novamente.")
    st.session_state.pop("perfil_logado", None)
    st.stop()
nome_usuario = perfil.get("nome", "Entregador")
email_usuario = perfil.get("email", "")

if st.secrets.get("APP_ENV", "prod") == "staging":
    st.warning("🧪 **AMBIENTE BETA (V3.0)** — Você está testando a nova versão com dados isolados.")

with st.sidebar:
    st.header("👤 Minha Conta")
    badge_papel = "🏢 Gestor" if papel == "gestor" else ("🛵 Piloto" if papel == "piloto" else "🏍️ Autônomo")
    st.markdown(f"**{nome_usuario}** ({badge_papel})")
    if empresa_info:
        st.info(f"🏢 **{empresa_info.get('nome_empresa')}**")
    if st.button("🔄 Recarregar da Nuvem", use_container_width=True):
        st.session_state.pop("db", None)
        st.rerun()
    if st.button("🚪 Sair / Trocar Conta", use_container_width=True):
        st.session_state.pop("perfil_logado", None)
        st.session_state.pop("db", None)
        st.rerun()

aviso_salvar = st.session_state.pop("_aviso_persistencia", None)
if aviso_salvar:
    st.error(aviso_salvar)

if "db" not in st.session_state or st.session_state.get("loaded_key") != user_key:
    loaded_db, cloud_ok = load_state(user_key)
    if not cloud_ok or loaded_db is None:
        st.error("☁️ Não consegui carregar seus dados da nuvem. Por segurança, nada será gravado até a conexão voltar.")
        if st.button("🔄 Tentar de novo", type="primary"):
            st.rerun()
        st.stop()
    st.session_state.db = migrate_data(loaded_db)
    st.session_state.loaded_key = user_key
    st.session_state.cloud_ok = True
else:
    st.session_state.db = migrate_data(st.session_state.db)

db = st.session_state.db

if papel in ("autonomo", "gestor"):
    with st.sidebar:
        st.download_button(
            "💾 Baixar backup (JSON)",
            data=json.dumps(db, ensure_ascii=False, indent=2, default=str),
            file_name=f"raiox_backup_{date.today().isoformat()}.json",
            mime="application/json",
            use_container_width=True,
        )

if empresa_info:
    for m_item in db["motos"]:
        m_item["empresa_id"] = empresa_info.get("id")

motos_visiveis = db["motos"]
if papel == "piloto":
    motos_visiveis = [m for m in db["motos"] if m.get("piloto_email") == email_usuario]
    if not motos_visiveis:
        st.warning("🛵 Nenhuma moto foi atribuída a você ainda. Peça ao gestor da empresa para atribuir uma moto ao seu perfil e depois toque em 🔄 Recarregar da Nuvem.")
        st.stop()

motos_dict = {m["id"]: m for m in motos_visiveis}
moto_ativa_id = obter_moto_ativa_id(db, papel, motos_dict)

col_t1, col_t2, col_t3 = st.columns([1.6, 1, 0.55])
col_t1.title("🏍️ Raio-X")

if papel == "piloto" and len(motos_visiveis) <= 1:
    col_t2.markdown(f"**🏍️ {motos_dict[moto_ativa_id]['apelido']}**")
    moto_escolhida_id = moto_ativa_id
else:
    moto_escolhida_id = col_t2.selectbox(
        "Moto Ativa:",
        options=list(motos_dict.keys()),
        format_func=lambda mid: motos_dict[mid]["apelido"],
        index=list(motos_dict.keys()).index(moto_ativa_id),
        label_visibility="collapsed"
    )

if col_t3.button("🚪 Sair", use_container_width=True, help="Sair / Trocar Usuário"):
    st.session_state.pop("perfil_logado", None)
    st.session_state.pop("db", None)
    st.rerun()

if moto_escolhida_id != moto_ativa_id:
    definir_moto_ativa(db, moto_escolhida_id, papel)
    if papel not in ("gestor", "piloto"):
        save_state(user_key, db)
    st.rerun()

moto_ativa = motos_dict[moto_ativa_id]
custo_gas_km, custo_reserva_km, custo_total_km = calc_custos_moto(moto_ativa)

if papel == "piloto":
    st.caption(f"Hodômetro: **{int(moto_ativa['hodometro']):,} km**")
else:
    st.caption(
        f"**{moto_ativa['apelido']}** • Hodômetro: **{int(moto_ativa['hodometro']):,} km** • "
        f"Custo Real: **R$ {custo_total_km:.3f}/km** (Gasolina R$ {custo_gas_km:.3f} + Reserva R$ {custo_reserva_km:.3f})"
    )
if papel == "gestor" and empresa_info:
    st.info(f"🏢 **{empresa_info.get('nome_empresa')}**")
    render_convites_gestor(perfil, empresa_info)

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
                        "posto": voz_res.get("posto_ou_oficina", "Via Voz"), "piloto": nome_usuario, "piloto_email": email_usuario
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
                            "data": str(date.today()), "moto_id": moto_ativa["id"], "piloto": nome_usuario, "piloto_email": email_usuario,
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
    if papel == "piloto":
        filtro_visao = "Apenas Moto Ativa"
        filtro_periodo = st.radio("Período:", [f"Ciclo Atual (Desde {DATA_INICIO_CICLO})", "Todos os Registros"], horizontal=True)
    else:
        col_f1, col_f2 = st.columns(2)
        filtro_visao = col_f1.radio("Moto:", ["Apenas Moto Ativa", "Todas as Motos"], horizontal=True)
        filtro_periodo = col_f2.radio("Período:", [f"Ciclo Atual (Desde {DATA_INICIO_CICLO})", "Todos os Registros"], horizontal=True)

    turnos_filtrados = [
        t for t in db["turnos"]
        if (filtro_visao == "Todas as Motos" or t.get("moto_id") == moto_ativa["id"])
        and (filtro_periodo == "Todos os Registros" or t["data"] >= DATA_INICIO_CICLO)
        and (papel != "piloto" or (t.get("piloto_email") == email_usuario if t.get("piloto_email") else t.get("piloto") == nome_usuario))
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

    if papel == "piloto":
        c1, c2 = st.columns(2)
        c1.metric("Turnos Registrados", f"{len(turnos_filtrados)}")
        c2.metric("Km Rodados", f"{total_km:,} km")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Lucro Líquido Real", f"R$ {lucro_liquido:.2f}")
        c2.metric("Faturamento Bruto", f"R$ {total_bruto:.2f}")
        c3.metric("Km Rodados", f"{total_km:,} km")
        st.info(
            f"💰 **Caixinha da Moto (Não Gastar):** Separe **R$ {total_gas + total_reserva:.2f}** "
            f"(**R$ {total_gas:.2f}** Gasolina + **R$ {total_reserva:.2f}** Reserva Manutenção/Fixos)"
        )
        if total_bruto > 0 and total_km > 0:
            dias_trab = len({t["data"] for t in turnos_filtrados})
            i1, i2, i3 = st.columns(3)
            i1.metric("Ganho por km", f"R$ {total_bruto / total_km:.2f}")
            i2.metric("% de despesa", f"{(total_bruto - lucro_liquido) / total_bruto * 100:.0f}%")
            i3.metric("Lucro médio/dia", f"R$ {lucro_liquido / max(dias_trab, 1):.2f}")
        turnos_dur = [t for t in turnos_filtrados if (t.get("duracao_min") or 0) >= 10]
        if turnos_dur:
            liq_dur = sum(
                t["bruto"] - t["km"] * calc_custos_moto(motos_dict.get(t.get("moto_id"), moto_ativa))[2] - t.get("extras", 0.0)
                for t in turnos_dur
            )
            horas_dur = sum(t["duracao_min"] for t in turnos_dur) / 60.0
            st.caption(f"⏱️ Líquido por hora (turnos com Iniciar/Encerrar): **R$ {liq_dur / horas_dur:.2f}/h** em {horas_dur:.1f} h")
        km_fora = sum(t.get("km_particular_antes", 0) or 0 for t in turnos_filtrados)
        if km_fora > 0:
            st.caption(f"🚶 Km rodados fora de turno (entre um turno e outro): **{int(km_fora):,} km**")

    render_turno_em_andamento(db, user_key, perfil, papel, motos_dict, moto_ativa, nome_usuario, email_usuario)

    with st.expander("➕ Registrar turno manualmente (sem Iniciar/Encerrar)", expanded=False):
        hodo_atual = int(moto_ativa["hodometro"])
        col_d, col1, col2 = st.columns([1.2, 1, 1])
        data_turno = col_d.date_input("Data", value=date.today(), key="man_data")
        km_ini = col1.number_input("Km Inicial", value=hodo_atual, step=1, key=f"man_kmi_{moto_ativa['id']}_{hodo_atual}")
        km_fim = col2.number_input("Km Final", value=hodo_atual, step=1, key=f"man_kmf_{moto_ativa['id']}_{hodo_atual}")
        gastos_extras = st.number_input("Gastos Extras no Dia (R$)", min_value=0.0, step=5.0, key="man_ext")
        ganho_app, origens, erro_origem = render_origens(db, papel, user_key, "man")
        obs_turno = st.text_input("Observação (opcional)", key="man_obs")

        if st.button("Salvar Turno", use_container_width=True, key="man_salvar"):
            dist = km_fim - km_ini
            if erro_origem:
                st.error(erro_origem)
            elif dist <= 0:
                st.error("O Km Final deve ser maior que o Km Inicial.")
            else:
                registro = {
                    "data": str(data_turno), "moto_id": moto_ativa["id"], "piloto": nome_usuario, "piloto_email": email_usuario,
                    "km_ini": km_ini, "km_fim": km_fim, "km": dist,
                    "extras": gastos_extras, "custo_km": round(custo_total_km, 4),
                    "observacao": obs_turno.strip(),
                }
                registro.update(campos_de_ganho(ganho_app, origens))
                db["turnos"].append(registro)
                if km_fim > moto_ativa["hodometro"]:
                    moto_ativa["hodometro"] = km_fim
                if save_state(user_key, db):
                    limpar_prefixo("man")
                    st.success(f"Turno salvo! +{dist} km ({registro['estabelecimento']}).")
                st.rerun()

    if papel != "piloto":
        render_gerenciar_locais(db, user_key)

    if turnos_filtrados:
        st.subheader("Histórico de Turnos")
        rows = []
        for t in turnos_filtrados:
            m_ref = motos_dict.get(t.get("moto_id"), moto_ativa)
            _, _, c_km_ref = calc_custos_moto(m_ref)
            liq = t["bruto"] - (t["km"] * c_km_ref) - t.get("extras", 0.0)
            row_item = {
                "Data": t["data"], "Moto": m_ref["apelido"], "Origem": t["estabelecimento"],
                "Km": t["km"]
            }
            row_item["Duração"] = formatar_duracao(t["duracao_min"]) if t.get("duracao_min") else "-"
            if papel != "piloto":
                row_item["Bruto (R$)"] = round(t["bruto"], 2)
                row_item["Gastos (R$)"] = round(t.get("extras", 0.0), 2)
                row_item["Custo/km (R$)"] = round(c_km_ref, 3)
                row_item["Piloto"] = t.get("piloto", "-")
                row_item["Líquido (R$)"] = round(liq, 2)
                dur_t = t.get("duracao_min") or 0
                row_item["Líq./h (R$)"] = round(liq / (dur_t / 60.0), 2) if dur_t >= 10 else "-"
            row_item["Obs."] = t.get("observacao", "") or ""
            rows.append(row_item)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if papel != "piloto":
            with st.expander("🗑️ Excluir um turno lançado errado"):
                opcoes_ex = [f"{i} | {t['data']} — {t['estabelecimento']} ({t['km']} km | R$ {t['bruto']:.2f})" for i, t in enumerate(db["turnos"])]
                sel_ex = st.selectbox("Selecione o turno:", options=opcoes_ex)
                if st.button("Confirmar Exclusão do Turno", type="primary"):
                    idx_rem = int(sel_ex.split(" | ")[0])
                    db["turnos"].pop(idx_rem)
                    save_state(user_key, db)
                    st.rerun()
with tab_sim:
    if papel == "piloto":
        sub_app = None
        sub_orc = st.container()
    else:
        sub_app, sub_orc = st.tabs(["⚡ Simular Corrida de App", "🧾 Calcular Orçamento para Cliente"])

    if sub_app is not None:
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
                res_part = st_searchbox(buscar_enderecos_online, placeholder="Ex: Av. Loreto, 500", key="sb_part")
                coord_partida, _ = _ler_busca(res_part)

        coord_retirada, label_retirada = None, ""
        if HAS_SEARCHBOX:
            res_ret = st_searchbox(buscar_enderecos_online, placeholder="Endereço de Retirada (Rua, Número, Comércio ou CEP)", key="sb_ret")
            coord_retirada, label_retirada = _ler_busca(res_ret)
        else:
            label_retirada = st.text_input("Endereço de Retirada")

        coord_entrega, label_entrega = None, ""
        if HAS_SEARCHBOX:
            res_ent = st_searchbox(buscar_enderecos_online, placeholder="Endereço de Entrega (Rua, Número, Comércio ou CEP)", key="sb_ent")
            coord_entrega, label_entrega = _ler_busca(res_ent)
        else:
            label_entrega = st.text_input("Endereço de Entrega")

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

        usa_precos_empresa = bool(empresa_info) and papel in ("gestor", "piloto")
        if usa_precos_empresa:
            cfg_emp, cfg_ok = carregar_config_precos(empresa_info.get("id"))
            if not cfg_ok:
                st.warning("⚠️ Não consegui ler a tabela de preços da empresa. Estou usando os valores padrão; confirme com o gestor antes de enviar o orçamento.")
        else:
            cfg_emp = db.setdefault("config_empresa", {"valor_km_cobrar": 2.0, "taxa_minima": 8.0})

        if papel == "piloto":
            km_entrega = st.number_input("Km Entrega", min_value=0.1, value=float(km_entrega_auto), step=0.5, key=f"km_ent_{km_entrega_auto}")
            valor_km_cobrar = float(cfg_emp.get("valor_km_cobrar", 2.0))
            taxa_minima = float(cfg_emp.get("taxa_minima", 8.0))
        else:
            col_o1, col_o2, col_o3 = st.columns(3)
            km_entrega = col_o1.number_input("Km Entrega", min_value=0.1, value=float(km_entrega_auto), step=0.5, key=f"km_ent_{km_entrega_auto}")
            valor_km_cobrar = col_o2.number_input("Cobrar por Km (R$)", min_value=0.5, value=float(cfg_emp.get("valor_km_cobrar", 2.0)), step=0.25, key="orc_val_km")
            taxa_minima = col_o3.number_input("Taxa Mínima (R$)", min_value=0.0, value=float(cfg_emp.get("taxa_minima", 8.0)), step=1.0, key="orc_taxa_min")

            if papel == "gestor" and (valor_km_cobrar != cfg_emp.get("valor_km_cobrar") or taxa_minima != cfg_emp.get("taxa_minima")):
                if st.button("💾 Salvar Tabela de Preços Padrão para Toda a Frota", use_container_width=True):
                    if usa_precos_empresa:
                        gravou = salvar_config_precos(empresa_info.get("id"), valor_km_cobrar, taxa_minima)
                    else:
                        cfg_emp["valor_km_cobrar"] = float(valor_km_cobrar)
                        cfg_emp["taxa_minima"] = float(taxa_minima)
                        gravou = save_state(user_key, db)
                    if gravou:
                        st.success("Tabela atualizada para todos os pilotos da empresa!")
                        st.rerun()

        cobrar_desloc = st.checkbox("Incluir km de deslocamento até retirada no preço ao cliente", value=False, key="orc_chk_desl")
        km_cobrado = km_entrega + (km_desloc if cobrar_desloc else 0.0)
        km_rodado_real = km_entrega + km_desloc

        preco_cliente = max(taxa_minima, round(km_cobrado * valor_km_cobrar, 2))
        custo_operacional_orc = km_rodado_real * custo_total_km
        lucro_orc = preco_cliente - custo_operacional_orc

        if papel == "piloto":
            st.metric("Valor da Entrega ao Cliente", f"R$ {preco_cliente:.2f}")
        else:
            oc1, oc2, oc3 = st.columns(3)
            oc1.metric("Valor ao Cliente", f"R$ {preco_cliente:.2f}")
            oc2.metric("Seu Custo Moto", f"- R$ {custo_operacional_orc:.2f}")
            oc3.metric("Seu Lucro Líquido", f"R$ {lucro_orc:.2f}")

        txt_ret = label_retirada or "Ponto de Coleta"
        txt_ent = label_entrega or "Destino"
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
        link_whats = "https://" + "wa.me/" + "?text=" + urllib.parse.quote(msg_whats)
        st.link_button("📲 Enviar Orçamento no WhatsApp", link_whats, type="primary", use_container_width=True)

from aba_garagem import render_aba_garagem
from aba_clt import render_aba_clt

with tab_garagem:
    render_aba_garagem(db, user_key, moto_ativa, custo_gas_km, custo_reserva_km, papel, empresa_info)

if tab_clt is not None:
    with tab_clt:
        render_aba_clt(db, motos_dict, moto_ativa)

st.divider()
st.caption(f"Raio-X do Entregador • v{APP_VERSION} • ambiente: {st.secrets.get('APP_ENV', 'prod')}")
