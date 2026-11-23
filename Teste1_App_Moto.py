# -*- coding: utf-8 -*-
"""
Raio-X do Entregador — Aplicativo Principal
"""

from datetime import date, datetime
import uuid
import pandas as pd
import streamlit as st
from streamlit_searchbox import st_searchbox
from streamlit_js_eval import get_geolocation

from catalogo_motos import (
    ESTABELECIMENTOS_LISTA,
    CATALOGO_MOTOS,
    criar_moto_do_catalogo,
)
from database_supabase import (
    DATA_INICIO_CICLO,
    get_default_user_key,
    carregar_estado,
    salvar_estado,
    registrar_metrica_observatorio,
)
from calculos_e_rotas import (
    CLT_TOTAL_MENSAL,
    CLT_META_DIARIA,
    CLT_META_HORA,
    calcular_custos_moto,
    calcular_resumo_periodo,
    buscar_enderecos_photon,
    calcular_rota_osrm,
    gerar_mensagem_whatsapp,
)

st.set_page_config(
    page_title="Raio-X do Entregador",
    page_icon="🏍️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "user_key" not in st.session_state:
    st.session_state.user_key = get_default_user_key()

if "estado" not in st.session_state:
    st.session_state.estado = carregar_estado(st.session_state.user_key)

if "acao_ativa" not in st.session_state:
    st.session_state.acao_ativa = None

estado = st.session_state.estado
moto_id = estado.get("moto_ativa_id", "moto_bros_2008")
if moto_id not in estado["motos"]:
    moto_id = list(estado["motos"].keys())[0]
    estado["moto_ativa_id"] = moto_id
moto = estado["motos"][moto_id]
custos_km = calcular_custos_moto(moto)


def persistir_e_atualizar(registrar_obs: bool = False) -> None:
    salvar_estado(st.session_state.user_key, estado)
    if registrar_obs:
        res_hoje = calcular_resumo_periodo(
            estado, moto_id, DATA_INICIO_CICLO, date.today().isoformat()
        )
        registrar_metrica_observatorio(
            cidade=estado.get("cidade", "Araras"),
            estado_uf=estado.get("estado", "SP"),
            categoria_moto=moto.get("modelo", "Outros"),
            custo_km=custos_km["custo_total_km"],
            indice_clt=res_hoje["indice_clt_pct"],
        )


# Cabeçalho Compacto
col_tit, col_sel = st.columns([3, 2])
with col_tit:
    st.markdown("### 🏍️ Raio-X do Entregador")
    st.caption(
        f"Moto Ativa: **{moto['apelido']}** | Hodômetro: **{int(moto['hodometro']):,} km** | "
        f"Custo Real/Km: **R$ {custos_km['custo_total_km']:.4f}**"
    )
with col_sel:
    opcoes_motos = {
        mid: f"{m['apelido']} ({int(m['hodometro'])} km)"
        for mid, m in estado["motos"].items()
    }
    nova_moto_sel = st.selectbox(
        "Trocar Moto",
        options=list(opcoes_motos.keys()),
        index=list(opcoes_motos.keys()).index(moto_id),
        format_func=lambda x: opcoes_motos[x],
        label_visibility="collapsed",
    )
    if nova_moto_sel != moto_id:
        estado["moto_ativa_id"] = nova_moto_sel
        persistir_e_atualizar()
        st.rerun()

aba1, aba2, aba3 = st.tabs(
    ["🏍️ 1. Painel & Ações", "🔧 2. Saúde da Moto", "📊 3. Relatórios & CLT"]
)

# ==============================================================================
# ABA 1: PAINEL & AÇÕES
# ==============================================================================
with aba1:
    hoje_str = date.today().isoformat()
    resumo_ciclo = calcular_resumo_periodo(estado, moto_id, DATA_INICIO_CICLO, hoje_str)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(
            label="Lucro Líquido Real (Ciclo)",
            value=f"R$ {resumo_ciclo['lucro_liquido_final']:.2f}",
            delta=f"Bruto: R$ {resumo_ciclo['bruto_total']:.2f}",
        )
    with c2:
        st.metric(
            label="Caixinha da Moto (Saldo)",
            value=f"R$ {resumo_ciclo['saldo_caixinha_preventiva']:.2f}",
            delta=f"Reservado: R$ {resumo_ciclo['caixinha_prevista']:.2f}",
        )
    with c3:
        st.metric(
            label="Índice Equivalência CLT",
            value=f"{resumo_ciclo['indice_clt_pct']:.1f}%",
            delta=f"Meta: R$ {CLT_META_DIARIA:.2f}/dia",
        )

    st.divider()

    # 3 Botões Diretos para Ações Rápidas
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("➕ Fechar Turno", use_container_width=True, type="primary"):
            st.session_state.acao_ativa = (
                None if st.session_state.acao_ativa == "turno" else "turno"
            )
    with b2:
        if st.button("⛽ Abastecer", use_container_width=True):
            st.session_state.acao_ativa = (
                None if st.session_state.acao_ativa == "abastecer" else "abastecer"
            )
    with b3:
        if st.button("🔧 Manutenção", use_container_width=True):
            st.session_state.acao_ativa = (
                None if st.session_state.acao_ativa == "manutencao" else "manutencao"
            )

    # Formulário Modal: Fechar Turno
    if st.session_state.acao_ativa == "turno":
        with st.container(border=True):
            st.subheader("Registrar Fechamento de Turno")
            t_col1, t_col2 = st.columns(2)
            with t_col1:
                t_data = st.date_input("Data do Turno", value=date.today(), key="t_data")
                t_km_ini = st.number_input(
                    "Km Inicial", min_value=0, value=int(moto["hodometro"]), step=1
                )
                t_km_fim = st.number_input(
                    "Km Final", min_value=0, value=int(moto["hodometro"]) + 80, step=1
                )
            with t_col2:
                t_bruto = st.number_input(
                    "Faturamento Bruto (R$)", min_value=0.0, value=150.0, step=5.0
                )
                t_horas = st.number_input(
                    "Horas Trabalhadas", min_value=0.5, max_value=24.0, value=8.0, step=0.5
                )
                t_estab = st.selectbox("Estabelecimento / Origem", ESTABELECIMENTOS_LISTA)
            t_obs = st.text_input("Observação (opcional)", placeholder="Ex: Chuva à noite")

            km_calc = max(0, t_km_fim - t_km_ini)
            custo_turno = km_calc * custos_km["custo_total_km"]
            liq_turno = t_bruto - custo_turno
            st.info(
                f"Rodado: **{km_calc} km** | Custo Operacional: **R$ {custo_turno:.2f}** | "
                f"Lucro Líquido Estimado: **R$ {liq_turno:.2f}**"
            )

            col_s1, col_s2 = st.columns(2)
            with col_s1:
                if st.button("Salvar Turno", type="primary", use_container_width=True):
                    if t_km_fim <= t_km_ini:
                        st.error("O Km Final deve ser maior que o Km Inicial.")
                    else:
                        estado["turnos"].append(
                            {
                                "id": f"turno_{uuid.uuid4().hex[:8]}",
                                "data": t_data.isoformat(),
                                "moto_id": moto_id,
                                "km_inicial": int(t_km_ini),
                                "km_final": int(t_km_fim),
                                "km_rodado": float(km_calc),
                                "bruto": float(t_bruto),
                                "horas": float(t_horas),
                                "estabelecimento": t_estab,
                                "obs": t_obs.strip(),
                            }
                        )
                        if t_km_fim > int(moto["hodometro"]):
                            moto["hodometro"] = int(t_km_fim)
                        st.session_state.acao_ativa = None
                        persistir_e_atualizar(registrar_obs=True)
                        st.rerun()
            with col_s2:
                if st.button("Cancelar", use_container_width=True):
                    st.session_state.acao_ativa = None
                    st.rerun()

    # Formulário Modal: Abastecer
    elif st.session_state.acao_ativa == "abastecer":
        with st.container(border=True):
            st.subheader("Registrar Abastecimento")
            a_col1, a_col2 = st.columns(2)
            with a_col1:
                a_data = st.date_input("Data", value=date.today(), key="a_data")
                a_km = st.number_input(
                    "Hodômetro no Posto (km)", min_value=0, value=int(moto["hodometro"]), step=1
                )
            with a_col2:
                a_preco = st.number_input(
                    "Preço por Litro (R$)",
                    min_value=1.0,
                    value=float(moto.get("preco_gasolina", 5.99)),
                    step=0.01,
                    format="%.2f",
                )
                a_valor = st.number_input(
                    "Valor Abastecido (R$)", min_value=1.0, value=40.0, step=5.0
                )
            a_tanque_cheio = st.checkbox("Tanque Completo", value=True)
            litros_calc = a_valor / max(a_preco, 0.01)
            st.caption(f"Volume calculado: **{litros_calc:.2f} litros**")

            col_a1, col_a2 = st.columns(2)
            with col_a1:
                if st.button("Salvar Abastecimento", type="primary", use_container_width=True):
                    estado["abastecimentos"].append(
                        {
                            "id": f"abast_{uuid.uuid4().hex[:8]}",
                            "data": a_data.isoformat(),
                            "moto_id": moto_id,
                            "km": int(a_km),
                            "preco_litro": float(a_preco),
                            "valor_total": float(a_valor),
                            "litros": round(litros_calc, 3),
                            "tanque_cheio": bool(a_tanque_cheio),
                        }
                    )
                    moto["preco_gasolina"] = float(a_preco)
                    if a_km > int(moto["hodometro"]):
                        moto["hodometro"] = int(a_km)
                    st.session_state.acao_ativa = None
                    persistir_e_atualizar()
                    st.rerun()
            with col_a2:
                if st.button("Cancelar", use_container_width=True, key="canc_ab"):
                    st.session_state.acao_ativa = None
                    st.rerun()

    # Formulário Modal: Manutenção
    elif st.session_state.acao_ativa == "manutencao":
        with st.container(border=True):
            st.subheader("Registrar Manutenção / Oficina")
            m_tipo = st.radio(
                "Classificação da Manutenção",
                options=["Preventiva", "Corretiva / Imprevisto"],
                horizontal=True,
                help=(
                    "Preventiva abate da Caixinha da Moto e zera o desgaste da peça. "
                    "Corretiva desconta apenas no lucro líquido sem alterar o custo/km padrão."
                ),
            )
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                m_data = st.date_input("Data do Serviço", value=date.today(), key="m_data")
                m_km = st.number_input(
                    "Hodômetro na Oficina (km)", min_value=0, value=int(moto["hodometro"]), step=1
                )
                nomes_pecas = [p["nome"] for p in moto.get("pecas", [])] + [
                    "Outra Peça / Serviço Geral"
                ]
                m_peca = st.selectbox("Peça / Componente", nomes_pecas)
            with m_col2:
                m_valor = st.number_input("Valor Pago (R$)", min_value=0.0, value=35.0, step=5.0)
                m_oficina = st.text_input("Oficina / Mecânico", placeholder="Ex: Amaral")
                m_obs = st.text_input("Detalhes do serviço", placeholder="Ex: Óleo Mobil 20W50")

            col_m1, col_m2 = st.columns(2)
            with col_m1:
                if st.button("Salvar Manutenção", type="primary", use_container_width=True):
                    estado["manutencoes"].append(
                        {
                            "id": f"man_{uuid.uuid4().hex[:8]}",
                            "data": m_data.isoformat(),
                            "moto_id": moto_id,
                            "km": int(m_km),
                            "peca": m_peca,
                            "tipo": "Preventiva" if m_tipo == "Preventiva" else "Corretiva",
                            "oficina": m_oficina.strip() or "Não informada",
                            "valor": float(m_valor),
                            "obs": m_obs.strip(),
                        }
                    )
                    if m_tipo == "Preventiva":
                        for p in moto.get("pecas", []):
                            if p["nome"] == m_peca:
                                p["ultima_km"] = int(m_km)
                                if m_valor > 0:
                                    p["custo"] = float(m_valor)
                                break
                    if m_km > int(moto["hodometro"]):
                        moto["hodometro"] = int(m_km)
                    st.session_state.acao_ativa = None
                    persistir_e_atualizar()
                    st.rerun()
            with col_m2:
                if st.button("Cancelar", use_container_width=True, key="canc_man"):
                    st.session_state.acao_ativa = None
                    st.rerun()

    st.divider()

    # Simulador & Orçamento com Rotas Reais e WhatsApp
    st.subheader("🧭 Simulador & Orçamento de Corrida Particular")

    usar_gps = st.checkbox("Usar minha localização GPS atual como Origem", value=False)
    coords_origem = None
    label_origem = ""

    cidade_bias = f"{estado.get('cidade', 'Araras')} {estado.get('estado', 'SP')}"

    if usar_gps:
        loc = get_geolocation()
        if loc and "coords" in loc:
            lat_gps = loc["coords"]["latitude"]
            lon_gps = loc["coords"]["longitude"]
            coords_origem = {"lat": lat_gps, "lon": lon_gps, "label": "Localização Atual (GPS)"}
            label_origem = "Localização Atual (GPS)"
            st.success(f"GPS capturado: {lat_gps:.5f}, {lon_gps:.5f}")
        else:
            st.warning("Aguardando permissão de GPS no navegador...")
    else:
        def search_origem(searchterm: str):
            res = buscar_enderecos_photon(searchterm, cidade_bias)
            return [(r["label"], r) for r in res]

        coords_origem = st_searchbox(
            search_origem,
            key="box_origem",
            placeholder="Digite o endereço de coleta (Rua, número, bairro)...",
        )
        if coords_origem:
            label_origem = coords_origem["label"]

    def search_destino(searchterm: str):
        res = buscar_enderecos_photon(searchterm, cidade_bias)
        return [(r["label"], r) for r in res]

    coords_destino = st_searchbox(
        search_destino,
        key="box_destino",
        placeholder="Digite o endereço de entrega (Rua, número, bairro)...",
    )

    orc_cfg = estado.setdefault(
        "orcamento_config", {"valor_km": 2.00, "taxa_minima": 8.00, "retorno_incluso": True}
    )

    oc1, oc2, oc3 = st.columns(3)
    with oc1:
        val_km = st.number_input(
            "Cobrar por Km (R$)", min_value=0.5, value=float(orc_cfg["valor_km"]), step=0.10
        )
    with oc2:
        taxa_min = st.number_input(
            "Taxa Mínima (R$)", min_value=1.0, value=float(orc_cfg["taxa_minima"]), step=1.0
        )
    with oc3:
        ida_volta = st.checkbox(
            "Cobrar Ida e Volta", value=bool(orc_cfg["retorno_incluso"])
        )

    if (
        val_km != orc_cfg["valor_km"]
        or taxa_min != orc_cfg["taxa_minima"]
        or ida_volta != orc_cfg["retorno_incluso"]
    ):
        orc_cfg["valor_km"] = float(val_km)
        orc_cfg["taxa_minima"] = float(taxa_min)
        orc_cfg["retorno_incluso"] = bool(ida_volta)
        persistir_e_atualizar()

    km_manual = st.number_input(
        "Ou informe a distância de ida manualmente (km)", min_value=0.0, value=0.0, step=0.5
    )

    km_ida_final = 0.0
    duracao_estimada = 0

    if coords_origem and coords_destino:
        rota = calcular_rota_osrm(
            coords_origem["lat"],
            coords_origem["lon"],
            coords_destino["lat"],
            coords_destino["lon"],
        )
        if rota:
            km_ida_final = rota["distancia_km"]
            duracao_estimada = rota["duracao_min"]
            st.success(
                f"Rota calculada: **{km_ida_final:.2f} km** (ida) | Tempo estimado: **{duracao_estimada} min**"
            )
    elif km_manual > 0:
        km_ida_final = km_manual

    if km_ida_final > 0:
        km_cobrado = km_ida_final * 2.0 if ida_volta else km_ida_final
        valor_sugerido = max(taxa_min, round(km_cobrado * val_km, 2))
        custo_corrida = km_cobrado * custos_km["custo_total_km"]
        lucro_corrida = valor_sugerido - custo_corrida

        r1, r2, r3 = st.columns(3)
        r1.metric("Valor a Cobrar", f"R$ {valor_sugerido:.2f}", f"{km_cobrado:.1f} km totais")
        r2.metric("Seu Custo Real", f"R$ {custo_corrida:.2f}")
        r3.metric("Seu Lucro Líquido", f"R$ {lucro_corrida:.2f}")

        origem_txt = label_origem or "Ponto de Coleta"
        destino_txt = coords_destino["label"] if coords_destino else "Endereço de Entrega"
        msg_wpp = gerar_mensagem_whatsapp(
            origem=origem_txt,
            destino=destino_txt,
            km_ida=km_ida_final,
            ida_e_volta=ida_volta,
            valor_cobrado=valor_sugerido,
            custo_operacional=custo_corrida,
            lucro_estimado=lucro_corrida,
        )
        st.text_area("Mensagem pronta para copiar e enviar no WhatsApp:", value=msg_wpp, height=160)


# ==============================================================================
# ABA 2: SAÚDE DA MOTO
# ==============================================================================
with aba2:
    st.subheader(f"🔧 Saúde Preventiva — {moto['apelido']}")

    col_h1, col_h2 = st.columns([2, 1])
    with col_h1:
        novo_hod = st.number_input(
            "Atualizar Hodômetro Atual (km)",
            min_value=0,
            value=int(moto["hodometro"]),
            step=10,
        )
    with col_h2:
        st.write("")
        st.write("")
        if st.button("Atualizar Km", use_container_width=True):
            moto["hodometro"] = int(novo_hod)
            persistir_e_atualizar()
            st.success("Hodômetro atualizado!")
            st.rerun()

    if moto.get("tipo") == "alugada":
        st.info(
            "Esta motocicleta está configurada como **Alugada** (manutenção preventiva inclusa na locação)."
        )
    else:
        hod_atual = int(moto["hodometro"])
        pecas = moto.get("pecas", [])
        if not pecas:
            st.warning("Nenhuma peça preventiva cadastrada para esta moto.")
        else:
            for idx, p in enumerate(pecas):
                km_rodado_peca = max(0, hod_atual - int(p.get("ultima_km", hod_atual)))
                intervalo = max(1, int(p.get("intervalo", 1000)))
                pct_uso = min(1.0, km_rodado_peca / intervalo)
                km_restante = intervalo - km_rodado_peca

                with st.container(border=True):
                    p_c1, p_c2, p_c3 = st.columns([3, 2, 1])
                    with p_c1:
                        status_icon = "🟢" if pct_uso < 0.75 else ("🟡" if pct_uso < 1.0 else "🔴")
                        st.markdown(f"**{status_icon} {p['nome']}**")
                        st.progress(pct_uso)
                        if km_restante >= 0:
                            st.caption(
                                f"Rodados: {km_rodado_peca:,} km / {intervalo:,} km "
                                f"(Faltam **{km_restante:,} km**) | Custo médio: R$ {p['custo']:.2f}"
                            )
                        else:
                            st.caption(
                                f"Vencida há **{abs(km_restante):,} km**! "
                                f"(Troca prevista aos {int(p['ultima_km']) + intervalo:,} km)"
                            )
                    with p_c2:
                        valor_troca_rapida = st.number_input(
                            "Valor pago (R$)",
                            min_value=0.0,
                            value=float(p["custo"]),
                            step=5.0,
                            key=f"val_troca_{moto_id}_{idx}",
                        )
                    with p_c3:
                        st.write("")
                        if st.button(
                            "Troquei Hoje",
                            key=f"btn_troca_{moto_id}_{idx}",
                            use_container_width=True,
                        ):
                            p["ultima_km"] = hod_atual
                            if valor_troca_rapida > 0:
                                p["custo"] = float(valor_troca_rapida)
                            estado["manutencoes"].append(
                                {
                                    "id": f"man_{uuid.uuid4().hex[:8]}",
                                    "data": date.today().isoformat(),
                                    "moto_id": moto_id,
                                    "km": hod_atual,
                                    "peca": p["nome"],
                                    "tipo": "Preventiva",
                                    "oficina": "Troca Rápida",
                                    "valor": float(valor_troca_rapida),
                                    "obs": "Registrado via Saúde da Moto",
                                }
                            )
                            persistir_e_atualizar()
                            st.rerun()

    st.divider()

    # Parâmetros de Combustível e Custos Fixos da Moto Ativa
    with st.expander("⚙️ Configurar Combustível, Seguro, Documentos e Aluguel"):
        cfg_c1, cfg_c2 = st.columns(2)
        with cfg_c1:
            n_gas = st.number_input(
                "Preço Gasolina (R$/L)",
                min_value=1.0,
                value=float(moto.get("preco_gasolina", 5.99)),
                step=0.05,
            )
            n_cons = st.number_input(
                "Consumo Médio (km/L)",
                min_value=5.0,
                value=float(moto.get("consumo_kml", 29.0)),
                step=0.5,
            )
            n_proj = st.number_input(
                "Projeção Km Anual",
                min_value=1000.0,
                value=float(moto.get("projecao_anual_km", 37286.64)),
                step=1000.0,
            )
        with cfg_c2:
            n_seg = st.number_input(
                "Seguro Anual (R$)",
                min_value=0.0,
                value=float(moto.get("seguro_anual", 0.0)),
                step=50.0,
            )
            n_lic = st.number_input(
                "IPVA + Licenciamento Anual (R$)",
                min_value=0.0,
                value=float(moto.get("licenciamento_anual", 0.0)),
                step=20.0,
            )
            n_alug = st.number_input(
                "Aluguel Semanal (se alugada, R$)",
                min_value=0.0,
                value=float(moto.get("aluguel_semanal", 0.0)),
                step=10.0,
            )

        if st.button("Salvar Parâmetros da Moto", type="primary"):
            moto["preco_gasolina"] = float(n_gas)
            moto["consumo_kml"] = float(n_cons)
            moto["projecao_anual_km"] = float(n_proj)
            moto["seguro_anual"] = float(n_seg)
            moto["licenciamento_anual"] = float(n_lic)
            moto["aluguel_semanal"] = float(n_alug)
            persistir_e_atualizar()
            st.success("Parâmetros atualizados!")
            st.rerun()

        st.markdown(
            f"**Resumo do Custo/Km Atual:** Combustível `R$ {custos_km['custo_combustivel_km']:.4f}` + "
            f"Peças `R$ {custos_km['custo_pecas_km']:.4f}` + "
            f"Fixos/Aluguel `R$ {custos_km['custo_fixo_km']:.4f}` = "
            f"**`R$ {custos_km['custo_total_km']:.4f}/km`**"
        )

    # Adicionar Nova Moto via Catálogo Nacional
    with st.expander("➕ Adicionar Nova Moto (Catálogo Nacional)"):
        nm_apelido = st.text_input("Apelido da Moto", placeholder="Ex: CG 160 Trabalho")
        nm_modelo = st.selectbox("Modelo Base do Catálogo", list(CATALOGO_MOTOS.keys()))
        nm_hod = st.number_input("Hodômetro Inicial (km)", min_value=0, value=0, step=100)
        nm_cid = st.text_input("Cidade", value=estado.get("cidade", "Araras"))
        nm_uf = st.text_input("Estado (UF)", value=estado.get("estado", "SP"), max_chars=2)

        if st.button("Cadastrar Moto e Ativar"):
            novo_id = f"moto_{uuid.uuid4().hex[:6]}"
            apelido_final = nm_apelido.strip() or nm_modelo.split("(")[0].strip()
            nova_moto = criar_moto_do_catalogo(
                moto_id=novo_id,
                apelido=apelido_final,
                modelo_catalogo=nm_modelo,
                hodometro_inicial=int(nm_hod),
            )
            estado["motos"][novo_id] = nova_moto
            estado["moto_ativa_id"] = novo_id
            estado["cidade"] = nm_cid.strip() or "Araras"
            estado["estado"] = nm_uf.strip().upper() or "SP"
            persistir_e_atualizar()
            st.success(f"Moto '{apelido_final}' cadastrada e ativada!")
            st.rerun()


# ==============================================================================
# ABA 3: RELATÓRIOS & CLT
# ==============================================================================
with aba3:
    st.subheader("📊 Relatórios Financeiros, Auditoria & Equivalência CLT")

    f_col1, f_col2 = st.columns(2)
    data_ini_padrao = datetime.strptime(DATA_INICIO_CICLO, "%Y-%m-%d").date()
    with f_col1:
        dt_ini = st.date_input("Data Inicial", value=data_ini_padrao, key="rel_ini")
    with f_col2:
        dt_fim = st.date_input("Data Final", value=date.today(), key="rel_fim")

    rel = calcular_resumo_periodo(
        estado, moto_id, dt_ini.isoformat(), dt_fim.isoformat()
    )

    # Bloco 1: Balanço da Caixinha e Resultado Líquido
    st.markdown("#### 1. Balanço Financeiro & Caixinha da Moto")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Faturamento Bruto", f"R$ {rel['bruto_total']:.2f}", f"{rel['km_total']:.1f} km")
    m2.metric("Combustível Previsto", f"R$ {rel['combustivel_previsto']:.2f}")
    m3.metric(
        "Caixinha (Prev. vs Prev. Gasta)",
        f"R$ {rel['saldo_caixinha_preventiva']:.2f}",
        f"Prev: R$ {rel['caixinha_prevista']:.2f} | Gasto: R$ {rel['gasto_preventiva']:.2f}",
    )
    m4.metric(
        "Lucro Líquido Final",
        f"R$ {rel['lucro_liquido_final']:.2f}",
        f"Corretivas: -R$ {rel['gasto_corretiva']:.2f}",
    )

    st.divider()

    # Bloco 2: Termômetro CLT 2026
    st.markdown("#### 2. Termômetro Equivalência CLT 2026 (Piso + 30% Periculosidade)")
    clt1, clt2, clt3 = st.columns(3)
    clt1.metric(
        "Meta CLT do Período",
        f"R$ {rel['meta_clt_periodo']:.2f}",
        f"{rel['dias_trabalhados']} dia(s) x R$ {CLT_META_DIARIA:.2f}",
    )
    clt2.metric(
        "Seu Ganho Hora Líquido",
        f"R$ {rel['ganho_hora_liquido']:.2f}/h",
        f"Piso CLT: R$ {CLT_META_HORA:.2f}/h",
    )
    clt3.metric(
        "Desempenho vs CLT",
        f"{rel['indice_clt_pct']:.1f}%",
        f"Pacote Mensal CLT: R$ {CLT_TOTAL_MENSAL:.2f}",
    )
    st.progress(min(1.0, max(0.0, rel["indice_clt_pct"] / 100.0)))

    st.divider()

    # Bloco 3: Auditoria de Abastecimentos
    st.markdown("#### 3. Auditoria de Combustível (Previsto vs. Bomba)")
    ab1, ab2, ab3 = st.columns(3)
    ab1.metric("Combustível Previsto (Km)", f"R$ {rel['combustivel_previsto']:.2f}")
    ab2.metric(
        "Gasto Real na Bomba",
        f"R$ {rel['gasto_bomba_real']:.2f}",
        f"{rel['litros_bomba_real']:.2f} L abastecidos",
    )
    consumo_txt = (
        f"{rel['consumo_real_kml']:.1f} km/L"
        if rel["consumo_real_kml"] > 0
        else "Sem abastecimentos no período"
    )
    ab3.metric("Consumo Real Apurado", consumo_txt, f"Calibrado: {moto['consumo_kml']:.1f} km/L")

    st.divider()

    # Bloco 4: Histórico Detalhado e Exclusão Direta (sem st.form aninhado)
    st.markdown("#### 4. Extrato e Gerenciamento de Lançamentos")
    tab_t, tab_m, tab_a = st.tabs(["Turnos", "Manutenções", "Abastecimentos"])

    with tab_t:
        if not rel["turnos"]:
            st.info("Nenhum turno registrado neste período.")
        else:
            df_t = pd.DataFrame(rel["turnos"])[
                ["data", "km_inicial", "km_final", "km_rodado", "bruto", "horas", "estabelecimento", "obs"]
            ]
            st.dataframe(df_t, use_container_width=True, hide_index=True)

            opcoes_t = {
                t["id"]: f"{t['data']} | {t['km_rodado']:.0f} km | R$ {t['bruto']:.2f} ({t['estabelecimento']})"
                for t in rel["turnos"]
            }
            del_t = st.selectbox("Selecionar Turno para Excluir", list(opcoes_t.keys()), format_func=lambda x: opcoes_t[x])
            if st.button("🗑️ Excluir Turno Selecionado", key="btn_del_turno"):
                estado["turnos"] = [t for t in estado["turnos"] if t["id"] != del_t]
                persistir_e_atualizar()
                st.rerun()

    with tab_m:
        todas_man = [
            m for m in estado.get("manutencoes", []) if m.get("moto_id") == moto_id
        ]
        if not todas_man:
            st.info("Nenhuma manutenção registrada.")
        else:
            df_m = pd.DataFrame(todas_man)[
                ["data", "km", "tipo", "peca", "oficina", "valor", "obs"]
            ]
            st.dataframe(df_m, use_container_width=True, hide_index=True)

            opcoes_m = {
                m["id"]: f"{m['data']} | [{m['tipo']}] {m['peca']} — R$ {m['valor']:.2f}"
                for m in todas_man
            }
            del_m = st.selectbox("Selecionar Manutenção para Excluir", list(opcoes_m.keys()), format_func=lambda x: opcoes_m[x])
            if st.button("🗑️ Excluir Manutenção Selecionada", key="btn_del_man"):
                estado["manutencoes"] = [m for m in estado["manutencoes"] if m["id"] != del_m]
                persistir_e_atualizar()
                st.rerun()

    with tab_a:
        if not rel["abastecimentos"]:
            st.info("Nenhum abastecimento registrado neste período.")
        else:
            df_a = pd.DataFrame(rel["abastecimentos"])[
                ["data", "km", "litros", "preco_litro", "valor_total", "tanque_cheio"]
            ]
            st.dataframe(df_a, use_container_width=True, hide_index=True)

            opcoes_a = {
                a["id"]: f"{a['data']} | {a['km']} km | {a['litros']:.2f} L — R$ {a['valor_total']:.2f}"
                for a in rel["abastecimentos"]
            }
            del_a = st.selectbox("Selecionar Abastecimento para Excluir", list(opcoes_a.keys()), format_func=lambda x: opcoes_a[x])
            if st.button("🗑️ Excluir Abastecimento Selecionado", key="btn_del_ab"):
                estado["abastecimentos"] = [a for a in estado["abastecimentos"] if a["id"] != del_a]
                persistir_e_atualizar()
                st.rerun()
