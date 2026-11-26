import streamlit as st
import pandas as pd
from datetime import date
from catalogo_motos import CATALOGO_MOTOS, criar_moto_do_catalogo
from servicos_externos import save_state

def render_aba_garagem(db, user_key, moto_ativa, custo_gas_km, custo_reserva_km, papel="autonomo"):
    if papel == "piloto":
        sub_pecas, sub_abast, sub_manut = st.tabs(["🩺 Saúde das Peças", "⛽ Abastecer", "🛠️ Oficina"])
        sub_config = None
    else:
        sub_pecas, sub_abast, sub_manut, sub_config = st.tabs(["🩺 Saúde das Peças", "⛽ Abastecer", "🛠️ Oficina", "⚙️ Configurar Moto"])

    with sub_pecas:
        st.subheader(f"Painel de Desgaste — {moto_ativa['apelido']}")
        if papel != "piloto":
            g1, g2, g3 = st.columns(3)
            g1.metric("Combustível / Km", f"R$ {custo_gas_km:.3f}")
            g2.metric("Reserva Peças+Fixos / Km", f"R$ {custo_reserva_km:.3f}")
            g3.metric("Total / Km", f"R$ {custo_gas_km + custo_reserva_km:.3f}")

        pecas = moto_ativa["pecas"]
        for nome_p, info_p in pecas.items():
            km_rodado_p = max(0, int(moto_ativa["hodometro"]) - int(info_p["ultimo_km"]))
            vida_p = max(1, int(info_p["vida_util"]))
            pct_uso = min(1.0, km_rodado_p / vida_p)
            km_restante = vida_p - km_rodado_p

            if pct_uso >= 1.0:
                status_icon = "🚨 VENCIDA"
            elif pct_uso >= 0.80:
                status_icon = "⚠️ ATENÇÃO"
            else:
                status_icon = "✅ OK"

            col_p1, col_p2, col_p3 = st.columns([2, 1, 1])
            col_p1.markdown(f"**{nome_p}** ({status_icon})")
            col_p2.caption(f"Rodou: {km_rodado_p:,} / {vida_p:,} km")
            col_p3.caption(f"Resta: **{km_restante:,} km**")
            st.progress(pct_uso)

            if papel != "piloto":
                with st.expander(f"Editar parâmetro: {nome_p}"):
                    ep1, ep2, ep3 = st.columns(3)
                    novo_custo_p = ep1.number_input("Custo Troca (R$)", value=float(info_p["custo"]), step=5.0, key=f"c_{moto_ativa['id']}_{nome_p}")
                    nova_vida_p = ep2.number_input("Vida Útil (km)", value=int(info_p["vida_util"]), step=500, key=f"v_{moto_ativa['id']}_{nome_p}")
                    novo_ult_p = ep3.number_input("Última Troca (km)", value=int(info_p["ultimo_km"]), step=100, key=f"u_{moto_ativa['id']}_{nome_p}")
                    if st.button("Salvar Parâmetro", key=f"btn_{moto_ativa['id']}_{nome_p}"):
                        info_p["custo"] = float(novo_custo_p)
                        info_p["vida_util"] = int(nova_vida_p)
                        info_p["ultimo_km"] = int(novo_ult_p)
                        save_state(user_key, db)
                        st.success(f"{nome_p} atualizado!")
                        st.rerun()

    with sub_abast:
        st.subheader("Registrar Abastecimento (Consumo Real)")
        with st.form("form_abastecimento"):
            ab1, ab2, ab3 = st.columns(3)
            data_ab = ab1.date_input("Data", value=date.today())
            odo_ab = ab2.number_input("Hodômetro no Posto (km)", value=int(moto_ativa["hodometro"]), step=1)
            litros_ab = ab3.number_input("Litros Abastecidos", min_value=0.1, value=10.0, step=0.1, format="%.2f")

            ab4, ab5 = st.columns(2)
            valor_ab = ab4.number_input("Valor Total Pago (R$)", min_value=1.0, value=59.90, step=1.0, format="%.2f")
            posto_ab = ab5.text_input("Posto / Bandeira", value="Shell / Ipiranga")

            if st.form_submit_button("Salvar Abastecimento", use_container_width=True):
                preco_l_calc = round(valor_ab / litros_ab, 2)
                db["abastecimentos"].append({
                    "data": str(data_ab), "moto_id": moto_ativa["id"], "hodometro": int(odo_ab),
                    "litros": float(litros_ab), "valor_pago": float(valor_ab),
                    "preco_litro": preco_l_calc, "posto": posto_ab
                })
                moto_ativa["preco_gasolina"] = preco_l_calc
                if odo_ab > moto_ativa["hodometro"]:
                    moto_ativa["hodometro"] = int(odo_ab)
                save_state(user_key, db)
                st.success(f"Abastecimento salvo! Preço/L atualizado para R$ {preco_l_calc:.2f}.")
                st.rerun()

        abast_moto = [a for a in db["abastecimentos"] if a.get("moto_id") == moto_ativa["id"]]
        if len(abast_moto) >= 2:
            abast_ord = sorted(abast_moto, key=lambda x: x["hodometro"])
            ult, pen = abast_ord[-1], abast_ord[-2]
            km_trecho = ult["hodometro"] - pen["hodometro"]
            if km_trecho > 0 and ult["litros"] > 0:
                media_real = km_trecho / ult["litros"]
                st.info(f"⛽ **Última Média Real Medida:** **{media_real:.1f} km/L** ({km_trecho} km com {ult['litros']:.2f} L)")
                if papel != "piloto":
                    if st.button(f"Aplicar {media_real:.1f} km/L como consumo base da moto"):
                        moto_ativa["consumo_kml"] = round(media_real, 1)
                        save_state(user_key, db)
                        st.rerun()

        if abast_moto:
            st.dataframe(pd.DataFrame(abast_moto)[["data", "hodometro", "litros", "valor_pago", "preco_litro", "posto"]], use_container_width=True, hide_index=True)
    with sub_manut:
        st.subheader("Registrar Serviço / Troca de Peça")
        opcoes_comp = list(moto_ativa["pecas"].keys()) + ["Outro Serviço / Mão de Obra Avulsa"]
        with st.form("form_manutencao"):
            mn1, mn2, mn3 = st.columns(3)
            data_mn = mn1.date_input("Data", value=date.today())
            odo_mn = mn2.number_input("Hodômetro na Troca (km)", value=int(moto_ativa["hodometro"]), step=1)
            comp_mn = mn3.selectbox("Componente / Peça", options=opcoes_comp)

            mn4, mn5, mn6 = st.columns(3)
            oficina_mn = mn4.text_input("Oficina / Mecânico", value="Oficina Local")
            val_peca_mn = mn5.number_input("Valor Peça (R$)", min_value=0.0, value=0.0, step=5.0)
            val_mo_mn = mn6.number_input("Mão de Obra (R$)", min_value=0.0, value=0.0, step=5.0)

            obs_mn = st.text_input("Observação (marca da peça, garantia, etc.)")
            resetar_ciclo = st.checkbox("Zerar desgaste desta peça no painel (iniciar novo ciclo a partir deste km)", value=True)

            if st.form_submit_button("Registrar Manutenção", use_container_width=True):
                total_mn = val_peca_mn + val_mo_mn
                db["manutencoes"].append({
                    "data": str(data_mn), "moto_id": moto_ativa["id"], "hodometro": int(odo_mn),
                    "tipo": "preventiva", "componente": comp_mn, "oficina": oficina_mn,
                    "valor_peca": float(val_peca_mn), "valor_total": float(total_mn), "obs": obs_mn
                })
                if resetar_ciclo and comp_mn in moto_ativa["pecas"]:
                    moto_ativa["pecas"][comp_mn]["ultimo_km"] = int(odo_mn)
                    if total_mn > 0:
                        moto_ativa["pecas"][comp_mn]["custo"] = float(total_mn)
                if odo_mn > moto_ativa["hodometro"]:
                    moto_ativa["hodometro"] = int(odo_mn)
                save_state(user_key, db)
                st.success(f"Manutenção registrada (R$ {total_mn:.2f})!")
                st.rerun()

        manut_moto = [m for m in db["manutencoes"] if m.get("moto_id") == moto_ativa["id"]]
        if manut_moto:
            st.subheader("Histórico de Oficina")
            st.dataframe(pd.DataFrame(manut_moto)[["data", "hodometro", "componente", "oficina", "valor_total", "obs"]], use_container_width=True, hide_index=True)

    if sub_config is not None:
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
                    moto_ativa.update({
                        "apelido": novo_apelido, "hodometro": int(novo_odo), "preco_gasolina": float(novo_gas),
                        "consumo_kml": float(novo_kml), "seguro_anual": float(novo_seg), "licenciamento_anual": float(novo_lic)
                    })
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
                        db["motos"].append(criar_moto_do_catalogo(novo_id, apelido_nova, modelo_cat, int(odo_nova)))
                        db["moto_ativa_id"] = novo_id
                        save_state(user_key, db)
                        st.success("Nova moto cadastrada e ativada!")
                        st.rerun()

            if len(db["motos"]) > 1:
                st.divider()
                st.subheader("🗑️ Excluir Moto Cadastrada")
                opcoes_ex_moto = {
                    m["id"]: f"{m['apelido']} ({m['modelo']} • {int(m['hodometro']):,} km)"
                    for m in db["motos"]
                }
                moto_del_id = st.selectbox(
                    "Selecione a moto para remover:",
                    options=list(opcoes_ex_moto.keys()),
                    format_func=lambda mid: opcoes_ex_moto[mid],
                    key="sel_excluir_moto",
                )
                if st.button("Confirmar Exclusão da Moto", type="primary", key="btn_excluir_moto"):
                    db["motos"] = [m for m in db["motos"] if m["id"] != moto_del_id]
                    if db["moto_ativa_id"] == moto_del_id:
                        primeiro_m = next(iter(db["motos"]))
                        db["moto_ativa_id"] = primeiro_m["id"]
                    save_state(user_key, db)
                    st.warning("Moto removida com sucesso!")
                    st.rerun()
