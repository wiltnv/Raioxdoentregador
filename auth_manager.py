import streamlit as st
import hashlib
import random
import string
from servicos_externos import get_supabase

def _hash_pin(email: str, pin: str) -> str:
    sal = f"raiox_v3_{email.strip().lower()}_{pin.strip()}"
    return hashlib.sha256(sal.encode("utf-8")).hexdigest()

def _gerar_codigo_convite(nome_empresa: str) -> str:
    prefixo = "".join(c for c in nome_empresa.upper() if c.isalpha())[:5] or "FROTA"
    sufixo = "".join(random.choices(string.digits, k=4))
    return f"{prefixo}-{sufixo}"

def autenticar_usuario(email: str, pin: str):
    sb = get_supabase()
    if not sb:
        return None, "Banco de dados não conectado. Verifique os Secrets."
    email_clean = email.strip().lower()
    if not email_clean or not pin.strip():
        return None, "Preencha e-mail e PIN."
    try:
        res = sb.table("profiles").select("*").eq("email", email_clean).execute()
        perfil = next(iter(res.data or []), None)
        if not perfil:
            return None, "E-mail não encontrado. Crie uma conta na aba ao lado."
        if perfil.get("pin_hash") != _hash_pin(email_clean, pin):
            return None, "PIN incorreto."
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
    if not nome_clean or "@" not in email_clean or len(pin_clean) < 4:
        return None, "Informe nome, e-mail válido e um PIN de pelo menos 4 números."

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
            cod = _gerar_codigo_convite(nome_empresa)
            res_emp = sb.table("empresas").insert({
                "nome_empresa": nome_empresa.strip(),
                "codigo_convite": cod,
                "plano": "beta"
            }).execute()
            empresa_info = next(iter(res_emp.data or []), None)
            if empresa_info:
                empresa_id = empresa_info["id"]
                state_key = f"empresa_{empresa_id}"

        elif papel == "piloto":
            cod_clean = codigo_convite.strip().upper()
            if not cod_clean:
                return None, "Informe o Código de Convite fornecido pelo gestor da empresa."
            res_emp = sb.table("empresas").select("*").eq("codigo_convite", cod_clean).execute()
            empresa_info = next(iter(res_emp.data or []), None)
            if not empresa_info:
                return None, "Código de convite inválido. Verifique com o gestor."
            empresa_id = empresa_info["id"]
            state_key = f"empresa_{empresa_id}"

        novo_perfil = {
            "email": email_clean,
            "nome": nome_clean,
            "pin_hash": _hash_pin(email_clean, pin_clean),
            "papel": papel,
            "empresa_id": empresa_id,
            "state_key": state_key
        }
        res_prof = sb.table("profiles").insert(novo_perfil).execute()
        perfil_criado = next(iter(res_prof.data or []), novo_perfil)
        perfil_criado["empresa"] = empresa_info
        return perfil_criado, None
    except Exception as e:
        return None, f"Erro ao criar conta: {e}"
      
def render_tela_login():
    amb = st.secrets.get("APP_ENV", "prod")
    if amb == "staging":
        st.warning("🧪 **AMBIENTE DE TESTES (BETA V3.0)** — Dados isolados da produção.")

    st.title("🏍️ Raio-X do Entregador")
    st.caption("Gestão inteligente de ganhos, custos reais por km e frotas.")

    modo_tela = st.session_state.get("auth_modo", "login")

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

        col_b1, col_b2 = st.columns(2)
        if col_b1.button("✨ Não tem conta? Criar Cadastro", use_container_width=True):
            st.session_state["auth_modo"] = "cadastro"
            st.rerun()
        if col_b2.button("⚡ Acesso Rápido (Teste)", use_container_width=True):
            st.session_state["auth_modo"] = "rapido"
            st.rerun()

    elif modo_tela == "cadastro":
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

            c_empresa = ""
            c_convite = ""
            if papel_cod == "gestor":
                c_empresa = st.text_input("Nome da Empresa / Frota / Estabelecimento:")
            elif papel_cod == "piloto":
                c_convite = st.text_input("Código de Convite da Empresa (ex: FROTA-1234):")

            if st.form_submit_button("Finalizar Cadastro e Entrar", type="primary", use_container_width=True):
                perfil, erro = cadastrar_usuario(c_nome, c_email, c_pin, papel_cod, c_empresa, c_convite)
                if erro:
                    st.error(erro)
                else:
                    st.session_state["perfil_logado"] = perfil
                    st.session_state["auth_modo"] = "login"
                    st.session_state.pop("db", None)
                    st.rerun()

        if st.button("⬅️ Já tenho conta (Voltar para Login)", use_container_width=True):
            st.session_state["auth_modo"] = "login"
            st.rerun()

    else:
        st.subheader("⚡ Acesso Rápido sem Cadastro")
        cod_legado = st.text_input("Código da Conta de Teste:", value="beta_teste")
        if st.button("Entrar no Modo Rápido", type="primary", use_container_width=True):
            st.session_state["perfil_logado"] = {
                "id": "modo_rapido",
                "nome": cod_legado.strip() or "Visitante",
                "email": "",
                "papel": "autonomo",
                "empresa": None,
                "state_key": cod_legado.strip() or "beta_teste"
            }
            st.session_state.pop("db", None)
            st.rerun()
        if st.button("⬅️ Voltar para Login", use_container_width=True):
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
