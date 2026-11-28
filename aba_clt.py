import streamlit as st
from calculos_moto import PISO_CLT_MENSAL, META_CLT_DIARIA, calc_custos_moto

def render_aba_clt(db, motos_dict, moto_ativa):
    st.subheader("Comparativo Real vs. Piso CLT (+30% Periculosidade)")
    dias_unicos = len(set(t["data"] for t in db["turnos"]))
    bruto_total_clt = sum(t["bruto"] for t in db["turnos"])

    custo_total_periodo = 0.0
    for t in db["turnos"]:
        m_ref = motos_dict.get(t.get("moto_id"), moto_ativa)
        _, _, c_km_ref = calc_custos_moto(m_ref)
        custo_total_periodo += (t["km"] * c_km_ref) + t.get("extras", 0.0)

    liquido_total_clt = bruto_total_clt - custo_total_periodo
    meta_proporcional = dias_unicos * META_CLT_DIARIA
    empate_bruto = meta_proporcional + custo_total_periodo
    indice_clt = (liquido_total_clt / meta_proporcional * 100) if meta_proporcional > 0 else 0

    st.metric(
        "Índice de Remuneração Real (% do Piso CLT)",
        f"{indice_clt:.1f}%",
        delta=f"R$ {liquido_total_clt - meta_proporcional:+.2f} vs CLT ({dias_unicos} dias)"
    )

    c_clt1, c_clt2 = st.columns(2)
    c_clt1.metric("Meta Líquida CLT (Período)", f"R$ {meta_proporcional:.2f}")
    c_clt2.metric("Faturamento Bruto de Empate", f"R$ {empate_bruto:.2f}")

    st.caption(
        f"Base CLT 2026: **R$ {PISO_CLT_MENSAL:.2f}/mês** (Salário Mínimo R$ 1.621 + 30% Periculosidade R$ 486,30 + "
        f"13º + Férias 1/3 + FGTS + INSS MEI + Vale-Alimentação = **R$ {META_CLT_DIARIA:.2f}/dia**)."
    )
