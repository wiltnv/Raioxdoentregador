import streamlit as st
from servicos_externos import save_state
from origens import (
    ID_PARTICULAR, ID_OUTRO, NOME_PARTICULAR, NOME_OUTRO, RESERVADOS,
    normalizar_nome, locais_ativos, achar_local, locais_parecidos, adicionar_local,
    renomear_local, arquivar_local, montar_origens, validar_linhas,
)

PLACEHOLDER = "— escolha a origem —"
ADD_NOVO = "➕ Adicionar novo local…"
OUTRO_LABEL = "Outro (não está na lista)"


def limpar_prefixo(prefixo):
    for k in [k for k in st.session_state.keys() if str(k).startswith(f"{prefixo}_")]:
        del st.session_state[k]


def _resolver(db, escolha):
    if escolha == NOME_PARTICULAR:
        return {"id": ID_PARTICULAR, "nome": NOME_PARTICULAR}
    if escolha == OUTRO_LABEL:
        return {"id": ID_OUTRO, "nome": NOME_OUTRO}
    return next((l for l in locais_ativos(db["locais"]) if l["nome"] == escolha), None)


# ---------- callbacks (rodam antes do próximo desenho da tela, então podem mexer nos widgets) ----------
def _cb_mais(n_key):
    st.session_state[n_key] = st.session_state.get(n_key, 1) + 1


def _cb_menos(n_key):
    st.session_state[n_key] = max(1, st.session_state.get(n_key, 1) - 1)


def _cb_salvar_local(user_key, nk, aviso_key, conf_key, loc_key):
    """Cria um local novo (ou reaproveita um igual). Se for parecido com outro, pede confirmação."""
    db = st.session_state.db
    nome = " ".join(str(st.session_state.get(nk, "")).split())
    st.session_state.pop(aviso_key, None)
    if not nome:
        st.session_state[aviso_key] = "Digite o nome do local."
        return
    norm = normalizar_nome(nome)
    if norm in RESERVADOS:
        st.session_state[aviso_key] = "“Apps”, “Particular” e “Outro” já existem como opções próprias."
        if loc_key and norm == "particular":
            st.session_state[loc_key] = NOME_PARTICULAR
        return
    parecidos = locais_parecidos(db["locais"], nome)
    if parecidos and st.session_state.get(conf_key) != norm:
        st.session_state[conf_key] = norm
        st.session_state[aviso_key] = (
            f"Parece com “{parecidos[0]['nome']}”. Escolha esse na lista, "
            "ou toque em Salvar local de novo para criar mesmo assim."
        )
        return
    local, _ = adicionar_local(db["locais"], nome)
    if local is None:
        st.session_state[aviso_key] = "Nome inválido."
        return
    save_state(user_key, db)
    if loc_key:
        st.session_state[loc_key] = local["nome"]
    st.session_state.pop(nk, None)
    st.session_state.pop(conf_key, None)


def _cb_renomear(user_key, local_id, campo):
    db = st.session_state.db
    ok, erro = renomear_local(db["locais"], local_id, st.session_state.get(campo, ""))
    if not ok:
        st.session_state["_loc_msg"] = erro
        return
    st.session_state.pop("_loc_msg", None)
    save_state(user_key, db)


def _cb_arquivar(user_key, local_id):
    db = st.session_state.db
    arquivar_local(db["locais"], local_id)
    save_state(user_key, db)


# ---------- telas ----------
def render_origens(db, papel, user_key, prefixo):
    """Campos de ganho: Apps + uma ou mais origens. Retorna (ganho_app, origens, erro)."""
    ganho_app = st.number_input("Ganhos Apps / iFood-Bee (R$)", min_value=0.0, step=5.0, key=f"{prefixo}_app")

    n_key = f"{prefixo}_n"
    n = st.session_state.setdefault(n_key, 1)
    nomes = [l["nome"] for l in locais_ativos(db["locais"])]
    ultima = OUTRO_LABEL if papel == "piloto" else ADD_NOVO
    opcoes = [PLACEHOLDER] + nomes + [NOME_PARTICULAR, ultima]

    linhas = []
    for i in range(n):
        loc_key = f"{prefixo}_loc_{i}"
        if st.session_state.get(loc_key) not in opcoes:
            st.session_state[loc_key] = PLACEHOLDER
        c1, c2 = st.columns([3, 2])
        escolha = c1.selectbox("Origem do ganho", options=opcoes, key=loc_key,
                               label_visibility="visible" if i == 0 else "collapsed")
        valor = c2.number_input("Valor (R$)", min_value=0.0, step=5.0, key=f"{prefixo}_val_{i}",
                                label_visibility="visible" if i == 0 else "collapsed")
        if escolha == ADD_NOVO:
            nk = f"{prefixo}_novo_{i}"
            aviso_key, conf_key = f"{prefixo}_aviso_{i}", f"{prefixo}_conf_{i}"
            st.text_input("Nome do novo local", key=nk)
            st.button("💾 Salvar local", key=f"{prefixo}_salvar_{i}", on_click=_cb_salvar_local,
                      args=(user_key, nk, aviso_key, conf_key, loc_key))
            if st.session_state.get(aviso_key):
                st.warning(st.session_state[aviso_key])
        linhas.append((_resolver(db, escolha), valor))

    if papel == "piloto":
        st.caption("Não achou o cliente? Escolha “Outro” e avise o gestor. Se ele acabou de cadastrar, toque em 🔄 Recarregar da Nuvem (barra lateral).")
    b1, b2 = st.columns(2)
    b1.button("➕ Outra origem", key=f"{prefixo}_mais", on_click=_cb_mais, args=(n_key,), use_container_width=True)
    if n > 1:
        b2.button("➖ Remover última", key=f"{prefixo}_menos", on_click=_cb_menos, args=(n_key,), use_container_width=True)

    erro = validar_linhas(linhas)
    return ganho_app, montar_origens(linhas), erro


def render_gerenciar_locais(db, user_key):
    """Só autônomo e gestor: cria, renomeia e arquiva os locais/clientes."""
    ativos = locais_ativos(db["locais"])
    with st.expander(f"📍 Meus locais / Clientes ({len(ativos)})", expanded=False):
        st.caption("Os pilotos só podem escolher destes locais. Renomear ou arquivar não muda os turnos já lançados.")
        if st.session_state.get("_loc_msg"):
            st.error(st.session_state["_loc_msg"])
        for l in ativos:
            campo = f"locnome_{l['id']}"
            c1, c2, c3 = st.columns([4, 1.4, 1.6])
            c1.text_input("Nome", value=l["nome"], key=campo, label_visibility="collapsed")
            c2.button("Salvar", key=f"locsalvar_{l['id']}", on_click=_cb_renomear, args=(user_key, l["id"], campo), use_container_width=True)
            c3.button("Arquivar", key=f"locarq_{l['id']}", on_click=_cb_arquivar, args=(user_key, l["id"]), use_container_width=True)
        st.markdown("**Adicionar local**")
        nk, aviso_key, conf_key = "mgr_novo", "mgr_aviso", "mgr_conf"
        st.text_input("Nome do novo local", key=nk, label_visibility="collapsed", placeholder="Ex.: Pizzaria do Zé")
        st.button("➕ Adicionar", key="mgr_add", on_click=_cb_salvar_local, args=(user_key, nk, aviso_key, conf_key, None))
        if st.session_state.get(aviso_key):
            st.warning(st.session_state[aviso_key])
