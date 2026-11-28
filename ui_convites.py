import streamlit as st
from servicos_externos import get_supabase
from convites import criar_convite, listar_convites, revogar_convite, convite_valido
from turnos import parse_iso, FUSO


def render_convites_gestor(perfil, empresa_info):
    sb = get_supabase()
    empresa_id = (empresa_info or {}).get("id")
    if not sb or not empresa_id:
        return
    with st.expander("👥 Convites para pilotos", expanded=False):
        c1, c2 = st.columns(2)
        dias = c1.selectbox("Validade", [1, 7, 30], index=1, format_func=lambda d: f"{d} dia" if d == 1 else f"{d} dias", key="conv_dias")
        usos = c2.selectbox("Quantas pessoas", [1, 5, 10], index=0, format_func=lambda u: f"{u} pessoa" if u == 1 else f"{u} pessoas", key="conv_usos")
        if st.button("➕ Gerar novo convite", use_container_width=True, key="btn_gerar_convite"):
            _, erro = criar_convite(sb, empresa_id, perfil.get("id"), dias, usos)
            if erro:
                st.error(erro)
            else:
                st.rerun()

        lista = listar_convites(sb, empresa_id)
        ativos = [c for c in lista if convite_valido(c)[0]]
        if not ativos:
            st.caption("Nenhum convite ativo. Gere um e envie o código ao piloto.")
        for c in ativos:
            st.code(c["codigo"], language=None)
            expira = parse_iso(c["expira_em"]).astimezone(FUSO)
            st.caption(f"Vale até {expira:%d/%m %H:%M} • usado {int(c.get('usos') or 0)} de {int(c.get('usos_max') or 1)}")
            if st.button("🚫 Revogar este convite", key=f"rev_{c['id']}"):
                revogar_convite(sb, c["id"], empresa_id)
                st.rerun()
        if len(lista) > len(ativos):
            st.caption(f"{len(lista) - len(ativos)} convite(s) já usado(s), vencido(s) ou revogado(s).")
