import re
import secrets
import streamlit as st
from servicos_externos import get_supabase
from seguranca import (
    MSG_LOGIN_GENERICA, pin_formato_valido, hash_pin, verificar_pin, verificar_pin_fantasma,
    proximo_estado_falha, minutos_restantes,
)
from convites import consumir_convite, devolver_uso
from turnos import agora_utc, parse_iso

COLUNAS_LOGIN = "id, email, nome, pin_hash, papel, empresa_id, state_key, tentativas_falhas, bloqueado_ate"
LIMITE_CONVITES_INVALIDOS_POR_SESSAO = 10
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _pepper():
    return str(st.secrets.get("PIN_PEPPER", "")).strip()


def _limpar_perfil(perfil):
    return {k: v for k, v in perfil.items() if k not in ("pin_hash", "tentativas_falhas", "bloqueado_ate")}


def autenticar_usuario(email: str, pin: str):
    sb = get_supabase()
    if not sb:
        return None, "Banco de dados não conectado. Verifique os Secrets."
    email_clean = email.strip().lower()
    pin_clean = pin.strip()
    if not email_clean or not pin_clean:
        return None, "Preencha e-mail e PIN."
    try:
        res = sb.table("profiles").select(COLUNAS_LOGIN).eq("email", email_clean).execute()
        perfil = next(iter(res.data or []), None)
        if not perfil:
            verificar_pin_fantasma(pin_clean)  # mesmo tempo de resposta de uma conta real
            return None, MSG_LOGIN_GENERICA

        agora = agora_utc()
        bloqueado_ate = perfil.get("bloqueado_ate")
        if bloqueado_ate and parse_iso(bloqueado_ate) > agora:
            mins = minutos_restantes(parse_iso(bloqueado_ate), agora)
            return None, f"Muitas tentativas incorretas. Tente de novo em {mins} min."

        ok, atualizar = verificar_pin(perfil.get("pin_hash"), email_clean, pin_clean, _pepper())
        if not ok:
            tentativas, bloquear_ate = proximo_estado_falha(perfil.get("tentativas_falhas"), agora)
            try:
                sb.table("profiles").update({
                    "tentativas_falhas": tentativas,
                    "bloqueado_ate": bloquear_ate.isoformat() if bloquear_ate else None,
                }).eq("id", perfil["id"]).execute()
            except Exception:
                pass
            if bloquear_ate:
                return None, f"Muitas tentativas incorretas. Tente de novo em {minutos_restantes(bloquear_ate, agora)} min."
            return None, MSG_LOGIN_GENERICA

        mudancas = {}
        if perfil.get("tentativas_falhas") or perfil.get("bloqueado_ate"):
            mudancas.update({"tentativas_falhas": 0, "bloqueado_ate": None})
        if atualizar:
            mudancas["pin_hash"] = hash_pin(email_clean, pin_clean, _pepper())
        if mudancas:
            try:
                sb.table("profiles").update(mudancas).eq("id", perfil["id"]).execute()
            except Exception:
                pass

        perfil = _limpar_perfil(perfil)
        empresa_info = None
        if perfil.get("empresa_id"):
            res_emp = sb.table("empresas").select("*").eq("id", perfil["empresa_id"]).execute()
            empresa_info = next(iter(res_emp.data or []), None)
        perfil["empresa"] = empresa_info
        return perfil, None
    except Exception as e:
        return None, f"Erro ao consultar login: {e}"


def cadastrar_usuario(nome: str, email: str, pin: str, papel: str, nome_empresa: str = "", codigo_convite: str = ""):
    sb = get_supabase()
    if not sb:
        return None, "Banco de dados não conectado."
    nome_clean = nome.strip()
    email_clean = email.strip().lower()
    pin_clean = pin.strip()
    if not nome_clean or not _EMAIL_RE.match(email_clean):
        return None, "Informe seu nome e um e-mail válido."
    if not pin_formato_valido(pin_clean):
        return None, "O PIN deve ter de 4 a 6 números."

    convite_usado = None
    empresa_criada_id = None
    try:
        existe = sb.table("profiles").select("id").eq("email", email_clean).execute()
        if existe.data:
            return None, "Este e-mail já está cadastrado. Faça login na aba Entrar."

        empresa_id = None
        empresa_info = None
        state_key = f"user_{email_clean.replace('@', '_').replace('.', '_')}"

        if papel == "gestor":
            if not nome_empresa.strip():
                return None, "Informe o nome da Empresa ou Frota."
            res_emp = sb.table("empresas").insert({
                "nome_empresa": nome_empresa.strip(),
                "codigo_convite": secrets.token_hex(8),  # campo antigo: não serve mais para entrar
                "plano": "beta",
            }).execute()
            empresa_info = next(iter(res_emp.data or []), None)
            if empresa_info:
                empresa_id = empresa_info["id"]
                empresa_criada_id = empresa_id
                state_key = f"empresa_{empresa_id}"

        elif papel == "piloto":
            convite_usado, erro = consumir_convite(sb, codigo_convite)
            if erro:
                return None, erro
            res_emp = sb.table("empresas").select("*").eq("id", convite_usado["empresa_id"]).execute()
            empresa_info = next(iter(res_emp.data or []), None)
            if not empresa_info:
                devolver_uso(sb, convite_usado["id"])
                convite_usado = None
                return None, "Convite inválido. Confira o código com o gestor."
            empresa_id = empresa_info["id"]
            state_key = f"empresa_{empresa_id}"

        novo_perfil = {
            "email": email_clean,
            "nome": nome_clean,
            "pin_hash": hash_pin(email_clean, pin_clean, _pepper()),
            "papel": papel,
            "empresa_id": empresa_id,
            "state_key": state_key,
        }
        res_prof = sb.table("profiles").insert(novo_perfil).execute()
        perfil_criado = _limpar_perfil(next(iter(res_prof.data or []), novo_perfil))
        perfil_criado["empresa"] = empresa_info
        return perfil_criado, None
    except Exception as e:
        # desfaz o que já tinha sido feito para não deixar convite gasto nem empresa solta
        if convite_usado:
            devolver_uso(sb, convite_usado["id"])
        if empresa_criada_id:
            try:
                sb.table("empresas").delete().eq("id", empresa_criada_id).execute()
            except Exception:
                pass
        msg = str(e).lower()
        if "duplicate" in msg or "23505" in msg:
            return None, "Este e-mail já está cadastrado. Faça login na aba Entrar."
        return None, f"Erro ao criar conta: {e}"


def render_tela_login():
    amb = st.secrets.get("APP_ENV", "prod")
    if amb == "staging":
        st.warning("🧪 **AMBIENTE DE TESTES (BETA V3.0)** — Dados isolados da produção.")

    st.title("🏍️ Raio-X do Entregador")
    st.caption("Gestão inteligente de ganhos, custos reais por km e frotas.")

    modo_tela = st.session_state.get("auth_modo", "login")
    if modo_tela not in ("login", "cadastro"):
        modo_tela = "login"

    if modo_tela == "login":
        st.subheader("🔑 Entrar na sua conta")
        with st.form("form_login_v3"):
            l_email = st.text_input("E-mail:", placeholder="seuemail@exemplo.com")
            l_pin = st.text_input("PIN de Acesso (4 a 6 números):", type="password", max_chars=6)
            if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                perfil, erro = autenticar_usuario(l_email, l_pin)
                if erro:
                    st.error(erro)
                else:
                    st.session_state["perfil_logado"] = perfil
                    st.session_state.pop("db", None)
                    st.rerun()

        if st.button("✨ Não tem conta? Criar Cadastro", use_container_width=True):
            st.session_state["auth_modo"] = "cadastro"
            st.rerun()

    else:
        st.subheader("✨ Criar Nova Conta")
        papel_esc = st.radio(
            "Perfil de acesso:",
            [
                "🏍️ Entregador Autônomo (Individual)",
                "🏢 Gestor / Empresa (Frota ou Loja)",
                "🛵 Piloto de Empresa (Código de Convite)"
            ],
            key="radio_papel_cadastro"
        )
        papel_cod = "autonomo" if papel_esc.startswith("🏍️") else ("gestor" if papel_esc.startswith("🏢") else "piloto")

        with st.form("form_cadastro_v3"):
            c_nome = st.text_input("Seu Nome Completo:")
            c_email = st.text_input("Seu E-mail:")
            c_pin = st.text_input("Crie um PIN numérico (4 a 6 dígitos):", type="password", max_chars=6)
            c_pin2 = st.text_input("Repita o PIN:", type="password", max_chars=6)

            c_empresa = ""
            c_convite = ""
            if papel_cod == "gestor":
                c_empresa = st.text_input("Nome da Empresa / Frota / Estabelecimento:")
            elif papel_cod == "piloto":
                c_convite = st.text_input("Código de Convite da Empresa (ex: K7QM-4XPD):")

            if st.form_submit_button("Finalizar Cadastro e Entrar", type="primary", use_container_width=True):
                if c_pin != c_pin2:
                    st.error("Os dois PINs não são iguais.")
                elif papel_cod == "piloto" and st.session_state.get("convites_invalidos", 0) >= LIMITE_CONVITES_INVALIDOS_POR_SESSAO:
                    st.error("Muitas tentativas de convite inválidas. Recarregue a página e peça um novo convite ao gestor.")
                else:
                    perfil, erro = cadastrar_usuario(c_nome, c_email, c_pin, papel_cod, c_empresa, c_convite)
                    if erro:
                        if papel_cod == "piloto" and erro.startswith("Convite"):
                            st.session_state["convites_invalidos"] = st.session_state.get("convites_invalidos", 0) + 1
                        st.error(erro)
                    else:
                        st.session_state["perfil_logado"] = perfil
                        st.session_state["auth_modo"] = "login"
                        st.session_state.pop("db", None)
                        st.rerun()

        if st.button("⬅️ Já tenho conta (Voltar para Login)", use_container_width=True):
            st.session_state["auth_modo"] = "login"
            st.rerun()


def listar_pilotos_empresa(empresa_id):
    if not empresa_id:
        return []
    sb = get_supabase()
    if not sb:
        return []
    try:
        res = sb.table("profiles").select("id, nome, email").eq("empresa_id", empresa_id).eq("papel", "piloto").execute()
        return res.data or []
    except Exception:
        return []
