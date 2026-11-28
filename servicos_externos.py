import streamlit as st
import json
import os
import re
import math
import urllib.request
import urllib.parse
import urllib.error
import base64
import copy
from calculos_moto import get_default_data, migrate_data
from sincronizacao import salvar_com_versao

try:
    from supabase import create_client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

DATA_FILE = "dados_entregador.json"

def get_supabase():
    if not HAS_SUPABASE:
        return None
    try:
        url = str(st.secrets.get("SUPABASE_URL", "")).strip().rstrip("/")
        key = str(st.secrets.get("SUPABASE_KEY", "")).strip()
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None

def _k_ver(user_key):
    return f"_ver_{user_key}"

def _k_base(user_key):
    return f"_base_{user_key}"

def load_state(user_key):
    """Carrega o estado da nuvem. Retorna (estado, ok).

    Se a leitura falhar, devolve (None, False): quem chama NÃO deve seguir nem
    gravar nada, para nunca sobrescrever dados reais com dados padrão.
    """
    sb = get_supabase()
    if not sb:
        return None, False
    try:
        res = sb.table("user_states").select("state_json, version").eq("user_key", user_key).execute()
        primeiro = next(iter(res.data or []), None)
        if primeiro:
            estado = migrate_data(primeiro["state_json"])
            st.session_state[_k_ver(user_key)] = primeiro.get("version") or 1
        else:
            estado = get_default_data()
            moto_inicial = next(iter(estado["motos"]))
            moto_inicial["apelido"] = "Moto Principal"
            moto_inicial["hodometro"] = 0
            estado["turnos"] = []
            estado["abastecimentos"] = []
            estado["manutencoes"] = []
            st.session_state[_k_ver(user_key)] = None  # primeira gravação cria a linha
        st.session_state[_k_base(user_key)] = copy.deepcopy(estado)
        return estado, True
    except Exception:
        return None, False

def save_state(user_key, data):
    """Grava o estado com controle de versão. Em conflito, mescla com o que outra sessão salvou."""
    sb = get_supabase()
    if not sb or not st.session_state.get("cloud_ok"):
        st.session_state["_aviso_persistencia"] = (
            "⚠️ Sem conexão com a nuvem: o último lançamento NÃO foi salvo. "
            "Toque em 🔄 Recarregar da Nuvem e repita."
        )
        return False
    ok, nova, erro = salvar_com_versao(
        sb, user_key, data,
        st.session_state.get(_k_ver(user_key)),
        st.session_state.get(_k_base(user_key)) or {},
    )
    if not ok:
        st.session_state["_aviso_persistencia"] = (
            f"⚠️ O último lançamento NÃO foi salvo ({erro}). "
            "Toque em 🔄 Recarregar da Nuvem e repita."
        )
        return False
    st.session_state[_k_ver(user_key)] = nova
    st.session_state[_k_base(user_key)] = copy.deepcopy(data)
    return True

PRECOS_PADRAO = {"valor_km_cobrar": 2.0, "taxa_minima": 8.0}

def carregar_config_precos(empresa_id):
    """Tabela de preços da empresa (fonte única, lida a cada execução). Retorna (config, ok)."""
    sb = get_supabase()
    if not sb or not empresa_id:
        return dict(PRECOS_PADRAO), False
    try:
        res = sb.table("empresas").select("config_precos").eq("id", empresa_id).execute()
        linha = next(iter(res.data or []), None)
        if linha is None:
            return dict(PRECOS_PADRAO), False
        salvo = linha.get("config_precos") or {}
        cfg = dict(PRECOS_PADRAO)
        for k in PRECOS_PADRAO:
            if k in salvo:
                cfg[k] = float(salvo[k])
        return cfg, True
    except Exception:
        return dict(PRECOS_PADRAO), False

def salvar_config_precos(empresa_id, valor_km_cobrar, taxa_minima):
    sb = get_supabase()
    if not sb or not empresa_id:
        return False
    try:
        sb.table("empresas").update({
            "config_precos": {
                "valor_km_cobrar": float(valor_km_cobrar),
                "taxa_minima": float(taxa_minima),
            }
        }).eq("id", empresa_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar a tabela de preços: {e}")
        return False

def obter_moto_ativa_id(db, papel, motos_dict):
    """Gestor e piloto escolhem a moto só na própria sessão (não gravam no JSON compartilhado)."""
    if papel in ("gestor", "piloto"):
        atual = st.session_state.get("moto_ativa_sessao")
    else:
        atual = db.get("moto_ativa_id")
    if atual not in motos_dict:
        atual = next(iter(motos_dict))
    return atual

def definir_moto_ativa(db, moto_id, papel):
    if papel in ("gestor", "piloto"):
        st.session_state["moto_ativa_sessao"] = moto_id
    else:
        db["moto_ativa_id"] = moto_id

def buscar_enderecos_online(query):
    if not query or len(query.strip()) < 3:
        return []
    q_clean = query.strip()
    resultados = []
    vistos = set()

    def add_item(label, lat, lon):
        chave = label.lower()
        if label and chave not in vistos:
            vistos.add(chave)
            resultados.append((label, {"lat": float(lat), "lon": float(lon), "label": label}))

    cep_digits = re.sub(r"\D", "", q_clean)
    if len(cep_digits) == 8:
        try:
            url_cep = "https://viacep.com.br" + "/ws/" + cep_digits + "/json/"
            req = urllib.request.Request(url_cep, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                d_cep = json.loads(resp.read().decode("utf-8"))
                if not d_cep.get("erro"):
                    q_clean = f"{d_cep.get('logradouro', '')}, {d_cep.get('bairro', '')}, {d_cep.get('localidade', '')} - {d_cep.get('uf', '')}".strip(", ")
        except Exception:
            pass

    q_busca = q_clean if ("," in q_clean or "-" in q_clean or "araras" in q_clean.lower()) else f"{q_clean}, Araras, SP"

    try:
        params_arc = urllib.parse.urlencode({
            "SingleLine": q_busca,
            "outSR": "4326",
            "maxLocations": "6",
            "f": "pjson"
        })
        url_arc = "https://geocode.arcgis.com" + "/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?" + params_arc
        req = urllib.request.Request(url_arc, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data_arc = json.loads(resp.read().decode("utf-8"))
            for cand in data_arc.get("candidates", []):
                addr = cand.get("address", "").strip()
                loc = cand.get("location", {})
                if addr and loc.get("y") is not None and loc.get("x") is not None:
                    add_item(addr, loc["y"], loc["x"])
    except Exception:
        pass

    if len(resultados) < 4:
        try:
            q_enc = urllib.parse.quote(q_clean)
            url_ph = "https://photon.komoot.io" + "/api/?q=" + q_enc + "&limit=5&lat=-22.357&lon=-47.384"
            req = urllib.request.Request(url_ph, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for feat in data.get("features", []):
                    props = feat.get("properties", {})
                    coords = feat.get("geometry", {}).get("coordinates", [])
                    rua = props.get("street") or props.get("name") or ""
                    numero = props.get("housenumber") or ""
                    bairro = props.get("district") or props.get("suburb") or ""
                    cidade = props.get("city") or props.get("town") or ""
                    label = ", ".join([p for p in [f"{rua}, {numero}" if numero else rua, bairro, cidade] if p])
                    if label and len(coords) == 2:
                        lon_v, lat_v = coords
                        add_item(label, lat_v, lon_v)
        except Exception:
            pass

    return resultados[:6]

def calcular_rota_osrm(coord1, coord2):
    lat1 = float(coord1["lat"] if isinstance(coord1, dict) else coord1)
    lon1 = float(coord1["lon"] if isinstance(coord1, dict) else coord1)
    lat2 = float(coord2["lat"] if isinstance(coord2, dict) else coord2)
    lon2 = float(coord2["lon"] if isinstance(coord2, dict) else coord2)

    urls = [
        "https://router.project-osrm.org" + f"/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false",
        "https://routing.openstreetmap.de" + f"/routed-car/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                rota = next(iter(data.get("routes") or []), None)
                if data.get("code") == "Ok" and rota:
                    return round(rota["distance"] / 1000.0, 2), max(1, round(rota["duration"] / 60.0))
        except Exception:
            continue

    r_terra = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    dist_est = round(2 * r_terra * math.asin(math.sqrt(a)) * 1.32, 2)
    tempo_est = max(2, round((dist_est / 35.0) * 60))
    return dist_est, tempo_est
    
def interpretar_audio_gemini(audio_bytes, mime_type="audio/wav", hodometro_atual=0):
    api_key = ""
    try:
        api_key = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
    except Exception:
        pass
    if not api_key:
        return {"erro": "Chave GEMINI_API_KEY não configurada nos Secrets do Streamlit."}

    prompt = (
        f"Você é o assistente de voz de um motoboy. Hodômetro atual da moto: {hodometro_atual} km. "
        "Ouça o áudio e identifique qual lançamento ele quer fazer: 'abastecimento', 'turno' ou 'manutencao'. "
        "Responda APENAS com um JSON válido (sem markdown) no formato: "
        '{"tipo": "abastecimento|turno|manutencao", "hodometro": int, "litros": float, "valor_total": float, '
        '"posto_ou_oficina": str, "ganho_app": float, "ganho_estab": float, "estabelecimento": str, "componente": str, "resumo": str}. '
        "Se algum número não foi dito, use 0."
    )

    b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type or "audio/wav", "data": b64_audio}}
            ]
        }],
        "generationConfig": {"temperature": 0.1}
    }

    dominio = ".".join(["generativelanguage", "googleapis", "com"])
    modelos = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]

    try:
        url_list = f"https://{dominio}/v1beta/models?key={api_key}"
        with urllib.request.urlopen(urllib.request.Request(url_list), timeout=8) as r_list:
            m_data = json.loads(r_list.read().decode("utf-8"))
            dinamicos = [
                m["name"].replace("models/", "")
                for m in m_data.get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", []) and "flash" in m.get("name", "")
            ]
            if dinamicos:
                modelos = dinamicos + modelos
    except Exception:
        pass

    erros = []
    for mod in dict.fromkeys(modelos):
        url = f"https://{dominio}/v1beta/models/{mod}:generateContent?key={api_key}"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                cand = next(iter(data.get("candidates") or []), {})
                part = next(iter(cand.get("content", {}).get("parts") or []), {})
                txt = part.get("text", "").strip()
                txt = txt.replace("```json", "").replace("```", "").strip()
                return json.loads(txt)
        except urllib.error.HTTPError as he:
            detalhe = he.read().decode("utf-8", errors="ignore")
            erros.append(f"{mod} -> HTTP {he.code}: {detalhe[:120]}")
            continue
        except Exception as e:
            erros.append(f"{mod} -> {e}")
            continue

    return {"erro": " | ".join(erros[:2])}
