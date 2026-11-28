"""Iniciar / Encerrar turno: regras e acesso ao banco (sem Streamlit, para poder testar)."""
import re
from datetime import datetime, timezone, timedelta

from origens import campos_de_ganho

try:
    from zoneinfo import ZoneInfo
    FUSO = ZoneInfo("America/Sao_Paulo")
except Exception:  # sem base de fusos no servidor: Brasília = UTC-3 (sem horário de verão desde 2019)
    FUSO = timezone(timedelta(hours=-3))

LIMITE_ALERTA_HORAS = 12
LIMITE_KM_TURNO = 1000


# ---------- tempo ----------
def agora_utc():
    return datetime.now(timezone.utc)


def parse_iso(valor):
    """Lê o timestamp que o Supabase devolve (aceita 'Z' e frações com 1 a 6 dígitos)."""
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    s = str(valor).strip().replace("Z", "+00:00").replace(" ", "T", 1)
    m = re.match(r"^(.*?T\d{2}:\d{2}:\d{2})(\.\d+)?(.*)$", s)
    if m:
        base, frac, resto = m.groups()
        frac = (frac or ".0")[1:7].ljust(6, "0")
        s = f"{base}.{frac}{resto}"
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def duracao_minutos(inicio, fim):
    return max(0, int((parse_iso(fim) - parse_iso(inicio)).total_seconds() // 60))


def formatar_duracao(minutos):
    minutos = int(minutos or 0)
    h, m = divmod(minutos, 60)
    return f"{h}h{m:02d}" if h else f"{m} min"


# ---------- regras ----------
def km_particular(hodometro_ini, hodometro_anterior):
    """Km rodados entre o fim do último turno e o início deste (uso fora de turno)."""
    if hodometro_anterior is None:
        return 0
    return max(0, int(hodometro_ini) - int(hodometro_anterior))


def validar_inicio(km_ini, hodometro_moto, papel="autonomo"):
    if int(km_ini) < int(hodometro_moto):
        dica = ("Peça ao gestor para corrigir o hodômetro da moto."
                if papel == "piloto" else
                "Se o valor registrado estiver errado, corrija em Garagem → Configurar Moto.")
        return (f"O hodômetro informado ({int(km_ini):,} km) é menor que o último registrado "
                f"({int(hodometro_moto):,} km). {dica}")
    return None


def validar_encerramento(km_ini, km_fim):
    dist = int(km_fim) - int(km_ini)
    if dist <= 0:
        return "O Km Final deve ser maior que o Km Inicial do turno."
    if dist > LIMITE_KM_TURNO:
        return f"{dist:,} km em um turno parece erro de digitação. Confira o Km Final."
    return None


def montar_turno(aberto, km_fim, ganho_app, origens, extras, observacao,
                 nome, email, custo_km, fim_utc):
    """Monta o registro de turno no mesmo formato do fechamento manual, com campos de tempo."""
    km_ini = int(aberto["hodometro_ini"])
    km_fim = int(km_fim)
    inicio = parse_iso(aberto["inicio"])
    registro = {
        "data": inicio.astimezone(FUSO).date().isoformat(),
        "moto_id": aberto["moto_id"],
        "piloto": nome,
        "piloto_email": email,
        "km_ini": km_ini,
        "km_fim": km_fim,
        "km": km_fim - km_ini,
        "extras": float(extras),
        "observacao": (observacao or "").strip(),
        "custo_km": round(float(custo_km), 4),
        "inicio": inicio.isoformat(),
        "fim": parse_iso(fim_utc).isoformat(),
        "duracao_min": duracao_minutos(inicio, fim_utc),
        "km_particular_antes": km_particular(km_ini, aberto.get("hodometro_anterior")),
    }
    registro.update(campos_de_ganho(ganho_app, origens))
    return registro


# ---------- banco (tabela turnos_abertos) ----------
def _eh_duplicado(exc):
    msg = str(exc).lower()
    return "duplicate" in msg or "23505" in msg or "already exists" in msg


def buscar_turno_aberto(sb, profile_id):
    """Retorna (linha_ou_None, ok). ok=False se não foi possível consultar."""
    try:
        res = (sb.table("turnos_abertos").select("*")
               .eq("profile_id", profile_id).is_("encerrado_em", "null").execute())
        return next(iter(res.data or []), None), True
    except Exception:
        return None, False


def iniciar_turno(sb, profile_id, state_key, moto_id, hodometro_ini, hodometro_anterior, nome):
    """Retorna (linha, erro)."""
    try:
        res = sb.table("turnos_abertos").insert({
            "profile_id": profile_id,
            "state_key": state_key,
            "moto_id": moto_id,
            "hodometro_ini": int(hodometro_ini),
            "hodometro_anterior": int(hodometro_anterior),
            "piloto_nome": nome,
        }).execute()
        return next(iter(res.data or []), None), None
    except Exception as e:
        if _eh_duplicado(e):
            return None, "Você já tem um turno aberto. Atualize a página."
        return None, f"Não consegui iniciar o turno: {e}"


def fechar_turno_aberto(sb, turno_id, quando_utc):
    """True só para quem de fato fechou (protege contra duplo clique e duas telas abertas)."""
    try:
        res = (sb.table("turnos_abertos")
               .update({"encerrado_em": parse_iso(quando_utc).isoformat()})
               .eq("id", turno_id).is_("encerrado_em", "null").execute())
        return bool(res.data)
    except Exception:
        return False


def reabrir_turno(sb, turno_id):
    try:
        sb.table("turnos_abertos").update({"encerrado_em": None}).eq("id", turno_id).execute()
        return True
    except Exception:
        return False


def cancelar_turno(sb, turno_id):
    try:
        sb.table("turnos_abertos").delete().eq("id", turno_id).is_("encerrado_em", "null").execute()
        return True
    except Exception:
        return False


def listar_turnos_abertos(sb, state_key):
    try:
        res = (sb.table("turnos_abertos").select("*")
               .eq("state_key", state_key).is_("encerrado_em", "null").execute())
        return res.data or []
    except Exception:
        return []
