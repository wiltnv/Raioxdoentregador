# -*- coding: utf-8 -*-
"""
Módulo de Persistência e Estado Inicial (Supabase)
Raio-X do Entregador
"""

import copy
from datetime import datetime, timezone
import streamlit as st
from supabase import create_client, Client
from catalogo_motos import criar_moto_do_catalogo

DATA_INICIO_CICLO = "2026-11-21"


def _limpar_url_supabase(raw_url: str) -> str:
    url = str(raw_url or "").strip().rstrip("/")
    for sufixo in ("/rest/v1", "/auth/v1", "/storage/v1"):
        if url.endswith(sufixo):
            url = url[: -len(sufixo)]
    return url.rstrip("/")


def get_supabase_client() -> Client | None:
    try:
        url = _limpar_url_supabase(st.secrets.get("SUPABASE_URL", ""))
        key = str(st.secrets.get("SUPABASE_KEY", "")).strip()
        if url and key:
            return create_client(url, key)
    except Exception as e:
        st.session_state["sb_erro_conexao"] = str(e)
    return None


def get_default_user_key() -> str:
    try:
        return str(st.secrets.get("DEFAULT_USER_KEY", "wil_bros150")).strip() or "wil_bros150"
    except Exception:
        return "wil_bros150"


def criar_estado_inicial() -> dict:
    moto_padrao = criar_moto_do_catalogo(
        moto_id="moto_bros_2008",
        apelido="Bros 150 ESD 2008",
        modelo_catalogo="Honda NXR 150 Bros ESD 2008 (Carburada)",
        hodometro_inicial=81260,
    )

    ultimas_km = {
        "Troca de Óleo": 80346,
        "Limpeza/Regulagem Carburador": 70050,
        "Filtro de Ar + Vela": 51560,
        "Pastilha Freio Dianteiro (ESD)": 74545,
        "Lona Freio Traseiro": 74545,
        "Cabos + Lubrificação": 70050,
        "Kit Relação / Transmissão": 75056,
        "Par de Pneus": 68824,
        "Bateria (Partida Elétrica)": 58098,
    }

    for peca in moto_padrao.get("pecas", []):
        if peca["nome"] in ultimas_km:
            peca["ultima_km"] = ultimas_km[peca["nome"]]

    turnos_iniciais = [
        {
            "id": "turno_init_1",
            "data": "2026-11-21",
            "moto_id": "moto_bros_2008",
            "km_inicial": 81011,
            "km_final": 81185,
            "km_rodado": 174.0,
            "bruto": 348.00,
            "horas": 10.0,
            "estabelecimento": "Sta. Efigênia / Golden",
            "obs": "Turno inicial calibrado",
        },
        {
            "id": "turno_init_2",
            "data": "2026-11-22",
            "moto_id": "moto_bros_2008",
            "km_inicial": 81185,
            "km_final": 81260,
            "km_rodado": 75.0,
            "bruto": 136.00,
            "horas": 6.0,
            "estabelecimento": "Nenhum (Apenas Apps)",
            "obs": "Turno inicial calibrado",
        },
    ]

    manutencoes_iniciais = [
        {"id": "man_hist_1", "data": "2026-04-10", "moto_id": "moto_bros_2008", "km": 58098, "peca": "Bateria (Partida Elétrica)", "tipo": "Preventiva", "oficina": "Poty", "valor": 180.00, "obs": "Histórico pré-ciclo"},
        {"id": "man_hist_2", "data": "2026-07-24", "moto_id": "moto_bros_2008", "km": 68824, "peca": "Par de Pneus", "tipo": "Preventiva", "oficina": "Amaral", "valor": 308.00, "obs": "Histórico pré-ciclo"},
        {"id": "man_hist_3", "data": "2026-08-05", "moto_id": "moto_bros_2008", "km": 70050, "peca": "Limpeza/Regulagem Carburador", "tipo": "Preventiva", "oficina": "Mineiro", "valor": 120.00, "obs": "Histórico pré-ciclo"},
        {"id": "man_hist_4", "data": "2026-08-05", "moto_id": "moto_bros_2008", "km": 70050, "peca": "Cabos + Lubrificação", "tipo": "Preventiva", "oficina": "Mineiro", "valor": 45.00, "obs": "Histórico pré-ciclo"},
        {"id": "man_hist_5", "data": "2026-09-18", "moto_id": "moto_bros_2008", "km": 74545, "peca": "Pastilha Freio Dianteiro (ESD)", "tipo": "Preventiva", "oficina": "Amaral", "valor": 60.00, "obs": "Histórico pré-ciclo"},
        {"id": "man_hist_6", "data": "2026-09-18", "moto_id": "moto_bros_2008", "km": 74545, "peca": "Lona Freio Traseiro", "tipo": "Preventiva", "oficina": "Amaral", "valor": 40.00, "obs": "Histórico pré-ciclo"},
        {"id": "man_hist_7", "data": "2026-09-23", "moto_id": "moto_bros_2008", "km": 75056, "peca": "Kit Relação / Transmissão", "tipo": "Preventiva", "oficina": "Amaral", "valor": 225.00, "obs": "Histórico pré-ciclo"},
        {"id": "man_hist_8", "data": "2026-11-14", "moto_id": "moto_bros_2008", "km": 80346, "peca": "Troca de Óleo", "tipo": "Preventiva", "oficina": "Amaral", "valor": 34.00, "obs": "Histórico pré-ciclo"},
    ]

    return {
        "data_inicio_ciclo": DATA_INICIO_CICLO,
        "cidade": "Araras",
        "estado": "SP",
        "moto_ativa_id": "moto_bros_2008",
        "motos": {
            "moto_bros_2008": moto_padrao,
        },
        "turnos": turnos_iniciais,
        "abastecimentos": [],
        "manutencoes": manutencoes_iniciais,
        "orcamento_config": {
            "valor_km": 2.00,
            "taxa_minima": 8.00,
            "retorno_incluso": True,
        },
    }


def carregar_estado(user_key: str) -> dict:
    sb = get_supabase_client()
    if sb:
        try:
            resp = sb.table("user_states").select("state_json").eq("user_key", user_key).execute()
            if resp.data and len(resp.data) > 0:
                registro = resp.data
                estado = registro.get("state_json")
                if isinstance(estado, dict) and "motos" in estado and estado["motos"]:
                    st.session_state["sb_conectado"] = True
                    return estado
        except Exception as e:
            st.warning(f"Aviso ao carregar dados do banco: {e}")

    estado_inicial = criar_estado_inicial()
    if sb:
        salvar_estado(user_key, estado_inicial)
    return estado_inicial


def salvar_estado(user_key: str, estado: dict) -> bool:
    sb = get_supabase_client()
    if not sb:
        return False
    try:
        payload = {
            "user_key": user_key,
            "state_json": copy.deepcopy(estado),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        sb.table("user_states").upsert(payload, on_conflict="user_key").execute()
        st.session_state["sb_conectado"] = True
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no Supabase: {e}")
        return False


def registrar_metrica_observatorio(cidade: str, estado_uf: str, categoria_moto: str, custo_km: float, indice_clt: float) -> None:
    sb = get_supabase_client()
    if not sb:
        return
    try:
        sb.table("observatory_metrics").insert({
            "cidade": cidade.strip() or "Não informada",
            "estado": estado_uf.strip().upper() or "SP",
            "categoria_moto": categoria_moto,
            "custo_real_km": round(float(custo_km), 4),
            "indice_clt": round(float(indice_clt), 2),
        }).execute()
    except Exception:
        pass
