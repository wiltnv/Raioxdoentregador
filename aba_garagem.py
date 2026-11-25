import streamlit as st
import pandas as pd
from datetime import date, datetime
from catalogo_motos import CATALOGO_MOTOS, criar_moto_do_catalogo
from calculos_moto import DATA_INICIO_CICLO
from servicos_externos import save_state

def render_aba_garagem(db, user_key, moto_ativa, custo_gas_km, custo_reserva_km):
    sub_pecas, sub_manut, sub_abast, sub_config = st.tabs([
        "🔧 Saúde das Peças",
        "🛠️ Manutenções (Previsto x Real)",
        "⛽ Abastecimentos (Gasolina)",
        "⚙️ Config. & Nova Moto"
    ])

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
                    "data": str(date.today()), "moto_id": moto_ativa["id"],
                    "hodometro": int(moto_ativa["hodometro"]), "tipo": "preventiva",
                    "componente": p["nome"], "oficina": "Troca Rápida",
                    "valor_peca": float(p["custo"]), "valor_total": float(p["custo"]),
                    "obs": "Registrado pelo botão Troquei Hoje"
                })
                save_state(user_key, db)
                st.toast(f"{p['nome']} zerado em {moto_ativa['hodometro']} km!")
                st.rerun()

        st.divider()
        with st.expander("✏️ Editar Custo, Intervalo ou Km de Troca das Peças"):
            pecas_lista = moto_ativa.get("pecas", [])
            if pecas_lista:
                peca_nomes = [p["nome"] for p in pecas_lista]
                peca_esc = st.selectbox("Escolha o componente para editar:", options=peca_nomes, key="sel_edit_peca")
                idx_p = peca_nomes.index(peca_esc)
                p_atual = pecas_lista[idx_p]

                with st.form("form_editar_peca"):
                    ep1, ep2, ep3 = st.columns(3)
                    novo_custo_p = ep1.number_input("Valor Base Pago (R$)", value=float(p_atual["custo"]), step=5.0)
                    novo_interv_p = ep2.number_input("Intervalo (km)", value=int(p_atual["intervalo"]), step=500)
                    nova_ult_km = ep3.number_input("Km Última Troca", value=int(p_atual["ultima_km"]), step=100)

                    if st.form_submit_button("Atualizar Parâmetros da Peça", use_container_width=True):
                        pecas_lista[idx_p]["custo"] = float(novo_custo_p)
                        pecas_lista[idx_p]["intervalo"] = int(novo_interv_p)
                        pecas_lista[idx_p]["ultima_km"] = int(nova_ult_km)
                        save_state(user_key, db)
                        st.success(f"{peca_esc} atualizado com sucesso!")
                        st.rerun()

    with sub_manut:
        st.subheader("Balanço Caixinha: Previsto vs. Gasto Real")
        dt_inicio_padrao = datetime.strptime(DATA_INICIO_CICLO, "%Y-%m-%d").date()
        col_pm1, col_pm2 = st.columns(2)
        dt_ini_m = col_pm1.date_input("De (Data Inicial):", value=dt_inicio_padrao, key="dt_ini_manut")
        dt_fim_m = col_pm2.date_input("Até (Data Final):", value=date.today(), key="dt_fim_manut")

        str_ini_m, str_fim_m = str(dt_ini_m), str(dt_fim_m)
        turnos_periodo_m = [t for t in db["turnos"] if t.get("moto_id") == moto_ativa["id"] and str_ini_m <= t["data"] <= str_fim_m]
        km_periodo_m = sum(t["km"] for t in turnos_periodo_m)
        reservado_manut_periodo = km_periodo_m * custo_reserva_km

        manut_moto = [m for m in db.get("manutencoes", []) if m.get("moto_id") == moto_ativa["id"]]
        manut_periodo = [m for m in manut_moto if str_ini_m <= m["data"] <= str_fim_m]
        gasto_real_periodo = sum(float(m["valor_total"]) for m in manut_periodo)
        saldo_caixinha_manut = reservado_manut_periodo - gasto_real_periodo

        bm1, bm2, bm3 = st.columns(3)
        bm1.metric(f"Reservado ({km_periodo_m} km)", f"R$ {reservado_manut_periodo:.2f}")
        bm2.metric("Gasto Real no Período", f"R$ {gasto_real_periodo:.2f}")
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
                        "data": str(data_m), "moto_id": moto_ativa["id"], "hodometro": int(odo_m),
                        "tipo": "preventiva", "componente": comp_m, "oficina": oficina_m or "Não informada",
                        "valor_peca": float(val_peca_m), "valor_total": float(val_total_m), "obs": obs_m
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
            df_m["Período"] = df_m["data"].apply(lambda d: "No Filtro" if str_ini_m <= d <= str_fim_m else "Fora do Filtro")
            st.dataframe(
                df_m[["data", "Período", "hodometro", "componente", "oficina", "valor_total", "obs"]].rename(
                    columns={"data": "Data", "hodometro": "Km", "componente": "Serviço", "oficina": "Oficina", "valor_total": "Pago (R$)", "obs": "Obs."}
                ),
                use_container_width=True,
                hide_index=True
            )

            st.divider()
            st.markdown("#### ✏️ Editar ou Excluir um Registro de Manutenção")
            indices_m = [i for i, m in enumerate(db["manutencoes"]) if m.get("moto_id") == moto_ativa["id"]]
            opcoes_m = [f"{i} | {db['manutencoes'][i]['data']} — {db['manutencoes'][i]['componente']} (Km {db['manutencoes'][i]['hodometro']} | R$ {db['manutencoes'][i]['valor_total']:.2f})" for i in indices_m]
            sel_m = st.selectbox("Selecione o registro para editar ou apagar:", options=opcoes_m, key="sel_edit_manut_web")
            idx_m_edit = int(sel_m.split(" | ")[0])
            m_reg = db["manutencoes"][idx_m_edit]

            em1, em2, em3 = st.columns(3)
            ed_data = em1.text_input("Data (AAAA-MM-DD)", value=str(m_reg["data"]), key=f"ed_dt_{idx_m_edit}")
            ed_odo = em2.number_input("Hodômetro (km)", value=int(m_reg["hodometro"]), step=1, key=f"ed_od_{idx_m_edit}")
            ed_comp = em3.text_input("Componente / Serviço", value=str(m_reg["componente"]), key=f"ed_cp_{idx_m_edit}")

            em4, em5, em6 = st.columns(3)
            ed_ofic = em4.text_input("Oficina / Loja", value=str(m_reg["oficina"]), key=f"ed_of_{idx_m_edit}")
            ed_peca = em5.number_input("Valor Peça (R$)", value=float(m_reg.get("valor_peca", 0.0)), step=5.0, key=f"ed_pc_{idx_m_edit}")
            ed_tot = em6.number_input("Valor Total Pago (R$)", value=float(m_reg["valor_total"]), step=5.0, key=f"ed_tt_{idx_m_edit}")
            ed_obs = st.text_input("Observações", value=str(m_reg.get("obs", "")), key=f"ed_ob_{idx_m_edit}")

            col_bm1, col_bm2 = st.columns(2)
            if col_bm1.button("💾 Salvar Alterações na Nuvem", key=f"btn_save_m_{idx_m_edit}", use_container_width=True):
                db["manutencoes"][idx_m_edit] = {
                    "data": ed_data.strip(), "moto_id": moto_ativa["id"], "hodometro": int(ed_odo),
                    "tipo": m_reg.get("tipo", "preventiva"), "componente": ed_comp.strip(),
                    "oficina": ed_ofic.strip(), "valor_peca": float(ed_peca),
                    "valor_total": float(ed_tot), "obs": ed_obs.strip()
                }
                save_state(user_key, db)
                st.success("Alterações salvas!")
                st.rerun()

            if col_bm2.button("🗑️ Excluir Registro Definitivamente", key=f"btn_del_m_{idx_m_edit}", type="primary", use_container_width=True):
                db["manutencoes"].pop(idx_m_edit)
                save_state(user_key, db)
                st.warning("Registro excluído!")
                st.rerun()

    with sub_abast:
        st.subheader("Controle de Combustível: Previsto vs. Bomba")
        turnos_ciclo_gas = [t for t in db["turnos"] if t.get("moto_id") == moto_ativa["id"] and t["data"] >= DATA_INICIO_CICLO]
        km_ciclo_gas = sum(t["km"] for t in turnos_ciclo_gas)
        gas_prevista_ciclo = km_ciclo_gas * custo_gas_km

        abast_moto = [a for a in db.get("abastecimentos", []) if a.get("moto_id") == moto_ativa["id"] and a["data"] >= DATA_INICIO_CICLO]
        gas_real_bomba = sum(float(a["valor_pago"]) for a in abast_moto)
        litros_totais = sum(float(a["litros"]) for a in abast_moto)
        saldo_gas = gas_prevista_ciclo - gas_real_bomba

        ga1, ga2, ga3 = st.columns(3)
        ga1.metric(f"Reservado ({km_ciclo_gas} km)", f"R$ {gas_prevista_ciclo:.2f}")
        ga2.metric("Pago na Bomba", f"R$ {gas_real_bomba:.2f}")
        ga3.metric("Diferença", f"R$ {saldo_gas:+.2f}")

        if litros_totais > 0 and km_ciclo_gas > 0:
            st.caption(f"Consumo médio no ciclo: **{km_ciclo_gas / litros_totais:.1f} km/L** (Base: {moto_ativa['consumo_kml']} km/L)")

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
                        "data": str(data_a), "moto_id": moto_ativa["id"], "hodometro": int(odo_a),
                        "litros": float(litros_a), "valor_pago": float(valor_a),
                        "preco_litro": preco_l_calc, "posto": posto_a
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
