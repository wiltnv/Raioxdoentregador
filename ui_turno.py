import streamlit as st
from servicos_externos import get_supabase, save_state
from calculos_moto import calc_custos_moto
from catalogo_motos import ESTABELECIMENTOS_LISTA
from turnos import (
    FUSO, LIMITE_ALERTA_HORAS, agora_utc, parse_iso, duracao_minutos, formatar_duracao,
    validar_inicio, validar_encerramento, montar_turno, buscar_turno_aberto, iniciar_turno,
    fechar_turno_aberto, reabrir_turno, cancelar_turno, listar_turnos_abertos,
)


def _bloco_iniciar(sb, perfil, user_key, papel, moto_ativa, nome_usuario):
    hodo_moto = int(moto_ativa.get("hodometro", 0))
    st.caption(f"Moto: **{moto_ativa['apelido']}** • último hodômetro registrado: **{hodo_moto:,} km**")
    km_ini = st.number_input(
        "Hodômetro agora (km)", min_value=0, value=hodo_moto, step=1,
        key=f"turno_ini_km_{moto_ativa['id']}_{hodo_moto}",
    )
    if int(km_ini) > hodo_moto:
        st.caption(f"🚶 {int(km_ini) - hodo_moto:,} km desde o último registro serão contados como uso fora de turno.")
    if st.button("▶️ Iniciar turno", type="primary", use_container_width=True, key="btn_iniciar_turno"):
        erro = validar_inicio(km_ini, hodo_moto, papel)
        if erro:
            st.error(erro)
            return
        _, erro = iniciar_turno(sb, perfil["id"], user_key, moto_ativa["id"], km_ini, hodo_moto, nome_usuario)
        if erro:
            st.error(erro)
        else:
            st.rerun()


def _bloco_encerrar(sb, aberto, db, user_key, motos_dict, nome_usuario, email_usuario):
    inicio = parse_iso(aberto["inicio"])
    dur = duracao_minutos(inicio, agora_utc())
    km_ini = int(aberto["hodometro_ini"])
    st.success(
        f"🟢 Turno em andamento desde **{inicio.astimezone(FUSO):%H:%M}** "
        f"({formatar_duracao(dur)}) • Km inicial: **{km_ini:,}**"
    )
    if dur > LIMITE_ALERTA_HORAS * 60:
        st.warning(f"Este turno está aberto há mais de {LIMITE_ALERTA_HORAS} h. Encerre ou cancele se foi esquecido.")

    moto_t = motos_dict.get(aberto["moto_id"])
    if moto_t is None:
        st.error("A moto deste turno não está disponível para você. Cancele o turno abaixo e inicie outro.")
    else:
        with st.form(f"form_encerrar_{aberto['id']}"):
            km_fim = st.number_input("Km Final", min_value=0, value=max(int(moto_t["hodometro"]), km_ini), step=1)
            c1, c2 = st.columns(2)
            ganho_app = c1.number_input("Ganhos Apps / iFood-Bee (R$)", min_value=0.0, step=5.0)
            extras = c2.number_input("Gastos Extras no Dia (R$)", min_value=0.0, step=5.0)
            c3, c4 = st.columns(2)
            estab = c3.selectbox("Estabelecimento", options=ESTABELECIMENTOS_LISTA)
            ganho_fixo = c4.number_input("Ganho no Estabelecimento (R$)", min_value=0.0, step=5.0)
            enviar = st.form_submit_button("⏹️ Encerrar turno", type="primary", use_container_width=True)

        if enviar:
            erro = validar_encerramento(km_ini, km_fim)
            if erro:
                st.error(erro)
            else:
                agora = agora_utc()
                if not fechar_turno_aberto(sb, aberto["id"], agora):
                    st.warning("Este turno já foi encerrado em outra tela. Atualize a página.")
                else:
                    _, _, custo_total_km = calc_custos_moto(moto_t)
                    registro = montar_turno(aberto, km_fim, ganho_app, ganho_fixo, extras, estab,
                                            nome_usuario, email_usuario, custo_total_km, agora)
                    db["turnos"].append(registro)
                    if int(km_fim) > int(moto_t["hodometro"]):
                        moto_t["hodometro"] = int(km_fim)
                    if save_state(user_key, db):
                        st.rerun()
                    else:
                        # não gravou: reabre o turno e recarrega da nuvem para nada se perder
                        reabrir_turno(sb, aberto["id"])
                        st.session_state.pop("db", None)
                        st.rerun()

    with st.expander("Cancelar este turno (descartar)"):
        st.caption("Use se iniciou por engano. Nada será registrado.")
        if st.button("🗑️ Cancelar turno", key="btn_cancelar_turno"):
            cancelar_turno(sb, aberto["id"])
            st.rerun()


def _painel_em_turno(sb, user_key, motos_dict):
    abertos = listar_turnos_abertos(sb, user_key)
    if not abertos:
        return
    partes = []
    for a in abertos:
        apelido = motos_dict.get(a["moto_id"], {}).get("apelido", "moto")
        desde = parse_iso(a["inicio"]).astimezone(FUSO)
        partes.append(f"**{a.get('piloto_nome') or 'Piloto'}** ({apelido}, desde {desde:%H:%M})")
    st.info("🟢 Em turno agora: " + " • ".join(partes))


def render_turno_em_andamento(db, user_key, perfil, papel, motos_dict, moto_ativa, nome_usuario, email_usuario):
    sb = get_supabase()
    if not sb or not perfil.get("id"):
        return
    with st.container(border=True):
        st.markdown("#### 🏁 Turno")
        aberto, ok = buscar_turno_aberto(sb, perfil["id"])
        if not ok:
            st.warning("Não consegui verificar se há turno aberto. Atualize a página.")
        elif aberto is None:
            _bloco_iniciar(sb, perfil, user_key, papel, moto_ativa, nome_usuario)
        else:
            _bloco_encerrar(sb, aberto, db, user_key, motos_dict, nome_usuario, email_usuario)
    if papel == "gestor":
        _painel_em_turno(sb, user_key, motos_dict)
