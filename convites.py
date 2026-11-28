"""Convites de piloto: código aleatório, com validade, número de usos e revogação."""
import re
import secrets
from datetime import timedelta

from turnos import agora_utc, parse_iso

ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem I, O, 0 e 1 (evita confusão ao digitar)
TENTATIVAS_CAS = 4


def gerar_codigo():
    bruto = "".join(secrets.choice(ALFABETO) for _ in range(8))
    return f"{bruto[:4]}-{bruto[4:]}"


def normalizar_codigo(texto):
    limpo = re.sub(r"[^A-Z0-9]", "", (texto or "").upper())
    return f"{limpo[:4]}-{limpo[4:]}" if len(limpo) == 8 else limpo


def convite_valido(convite, agora=None):
    """Retorna (ok, motivo)."""
    agora = agora or agora_utc()
    if convite.get("revogado"):
        return False, "Convite revogado. Peça um novo ao gestor."
    if parse_iso(convite["expira_em"]) <= agora:
        return False, "Convite expirado. Peça um novo ao gestor."
    if int(convite.get("usos") or 0) >= int(convite.get("usos_max") or 1):
        return False, "Convite já utilizado. Peça um novo ao gestor."
    return True, None


def _duplicado(exc):
    msg = str(exc).lower()
    return "duplicate" in msg or "23505" in msg or "already exists" in msg


def criar_convite(sb, empresa_id, criado_por, dias=7, usos_max=1):
    """Retorna (linha, erro)."""
    expira = (agora_utc() + timedelta(days=int(dias))).isoformat()
    for _ in range(5):
        try:
            res = sb.table("convites").insert({
                "empresa_id": empresa_id,
                "codigo": gerar_codigo(),
                "criado_por": criado_por,
                "expira_em": expira,
                "usos_max": int(usos_max),
            }).execute()
            return next(iter(res.data or []), None), None
        except Exception as e:
            if not _duplicado(e):
                return None, f"Não consegui criar o convite: {e}"
    return None, "Não consegui gerar um código único. Tente de novo."


def listar_convites(sb, empresa_id):
    try:
        res = sb.table("convites").select("*").eq("empresa_id", empresa_id).execute()
        return sorted(res.data or [], key=lambda c: c.get("criado_em") or "", reverse=True)
    except Exception:
        return []


def revogar_convite(sb, convite_id, empresa_id):
    try:
        res = (sb.table("convites").update({"revogado": True})
               .eq("id", convite_id).eq("empresa_id", empresa_id).execute())
        return bool(res.data)
    except Exception:
        return False


def consumir_convite(sb, codigo, agora=None):
    """Usa uma vez o convite. Retorna (linha, erro).

    O incremento só vale se `usos` ainda for o valor lido (duas pessoas com o mesmo
    convite de uso único nunca passam as duas).
    """
    codigo = normalizar_codigo(codigo)
    if not codigo:
        return None, "Informe o código de convite fornecido pelo gestor."
    try:
        for _ in range(TENTATIVAS_CAS):
            res = sb.table("convites").select("*").eq("codigo", codigo).execute()
            convite = next(iter(res.data or []), None)
            if not convite:
                return None, "Convite inválido. Confira o código com o gestor."
            ok, motivo = convite_valido(convite, agora)
            if not ok:
                return None, motivo
            usos = int(convite.get("usos") or 0)
            upd = (sb.table("convites").update({"usos": usos + 1})
                   .eq("id", convite["id"]).eq("usos", usos).execute())
            if upd.data:
                return upd.data[0], None
        return None, "Convite em uso por outra pessoa agora. Tente de novo."
    except Exception as e:
        return None, f"Não consegui validar o convite: {e}"


def devolver_uso(sb, convite_id):
    """Desfaz um uso (quando o cadastro falha depois de consumir o convite)."""
    try:
        for _ in range(TENTATIVAS_CAS):
            res = sb.table("convites").select("usos").eq("id", convite_id).execute()
            linha = next(iter(res.data or []), None)
            if not linha or int(linha["usos"]) <= 0:
                return False
            upd = (sb.table("convites").update({"usos": int(linha["usos"]) - 1})
                   .eq("id", convite_id).eq("usos", int(linha["usos"])).execute())
            if upd.data:
                return True
        return False
    except Exception:
        return False
