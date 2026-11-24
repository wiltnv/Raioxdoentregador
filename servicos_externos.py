import streamlit as st
import json
import os
import re
import urllib.request
import urllib.parse
from calculos_moto import get_default_data, migrate_data

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

def load_state(user_key):
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("user_states").select("state_json").eq("user_key", user_key).execute()
            primeiro = next(iter(res.data or []), None)
            if primeiro:
                return migrate_data(primeiro["state_json"]), True
        except Exception:
            pass
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return migrate_data(json.load(f)), False
        except Exception:
            pass
    return get_default_data(), bool(sb)

def save_state(user_key, data):
    sb = get_supabase()
    ok_cloud = False
    if sb:
        try:
            sb.table("user_states").upsert({"user_key": user_key, "state_json": data}).execute()
            ok_cloud = True
        except Exception as e:
            st.error(f"Erro ao salvar na nuvem (Supabase): {e}")
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return ok_cloud

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
            url_cep = f"https://viacep.com.br{cep_digits}/json/"
            req = urllib.request.Request(url_cep, headers={"User-Agent": "RaioXEntregadorApp/1.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                d_cep = json.loads(resp.read().decode("utf-8"))
                if not d_cep.get("erro"):
                    q_clean = f"{d_cep.get('logradouro', '')}, {d_cep.get('bairro', '')}, {d_cep.get('localidade', '')} - {d_cep.get('uf', '')}".strip(", ")
        except Exception:
            pass

    try:
        params_arc = urllib.parse.urlencode({
            "SingleLine": q_clean,
            "f": "json",
            "countryCode": "BRA",
            "location": "-47.384,-22.357",
            "maxLocations": 6,
            "outFields": "Match_addr,PlaceName"
        })
        url_arc = f"https://arcgis.com?{params_arc}"
        req = urllib.request.Request(url_arc, headers={"User-Agent": "RaioXEntregadorApp/1.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data_arc = json.loads(resp.read().decode("utf-8"))
            for cand in data_arc.get("candidates", []):
                attrs = cand.get("attributes", {})
                loc = cand.get("location", {})
                place = attrs.get("PlaceName", "").strip()
                addr = attrs.get("Match_addr", "").strip()
                label = f"{place} — {addr}" if (place and place.lower() not in addr.lower()) else addr
                if label and loc.get("y") and loc.get("x"):
                    add_item(label, loc["y"], loc["x"])
    except Exception:
        pass

    if len(resultados) < 5:
        try:
            q_enc = urllib.parse.quote(q_clean)
            url_ph = f"https://komoot.io{q_enc}&limit=6&lat=-22.357&lon=-47.384"
            req = urllib.request.Request(url_ph, headers={"User-Agent": "RaioXEntregadorApp/1.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for feat in data.get("features", []):
                    props = feat.get("properties", {})
                    if props.get("countrycode", "BR").upper() not in ["BR", ""]:
                        continue
                    coords = feat.get("geometry", {}).get("coordinates", [])
                    rua = props.get("street") or props.get("name") or ""
                    numero = props.get("housenumber") or ""
                    bairro = props.get("district") or props.get("suburb") or ""
                    cidade = props.get("city") or props.get("town") or props.get("municipality") or ""
                    estado = props.get("state") or ""
                    partes = [p for p in [f"{rua}, {numero}" if (rua and numero) else rua, bairro, f"{cidade} - {estado}" if (cidade and estado) else cidade] if p]
                    label = ", ".join(partes) if partes else props.get("name", "")
                    if label and len(coords) == 2:
                        lon_v, lat_v = coords
                        add_item(label, lat_v, lon_v)
        except Exception:
            pass

    return resultados[:6]

def calcular_rota_osrm(coord1, coord2):
    try:
        lat1 = coord1["lat"] if isinstance(coord1, dict) else coord1
        lon1 = coord1["lon"] if isinstance(coord1, dict) else coord1
        lat2 = coord2["lat"] if isinstance(coord2, dict) else coord2
        lon2 = coord2["lon"] if isinstance(coord2, dict) else coord2
        url = f"http://project-osrm.org{lon1},{lat1};{lon2},{lat2}?overview=false"
        req = urllib.request.Request(url, headers={"User-Agent": "RaioXEntregadorApp/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rota = next(iter(data.get("routes") or []), None)
            if data.get("code") == "Ok" and rota:
                return round(rota["distance"] / 1000.0, 2), round(rota["duration"] / 60.0)
    except Exception:
        pass
    return None, None
