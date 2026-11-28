"""Origens do ganho (apps, clientes/estabelecimentos, particular) — regras puras, sem Streamlit.

Os clientes/estabelecimentos ficam em db["locais"] como {"id", "nome", "ativo"}.
Cada turno guarda `origens`: [{"local_id", "local", "valor"}], com o nome copiado no momento
do lançamento (renomear ou arquivar um local nunca altera o histórico) e o id para os relatórios.
"""
import difflib
import unicodedata
import uuid

ID_PARTICULAR = "particular"
ID_OUTRO = "outro"
NOME_PARTICULAR = "Particular"
NOME_OUTRO = "Outro"
LIMITE_PARECIDO = 0.8
RESERVADOS = {"particular", "outro", "apps"}  # já existem como opções próprias


def normalizar_nome(texto):
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.casefold().split())


def locais_ativos(locais):
    return [l for l in locais if l.get("ativo", True)]


def achar_local(locais, nome):
    """Procura por nome ignorando maiúsculas, acentos e espaços (inclui arquivados)."""
    alvo = normalizar_nome(nome)
    if not alvo:
        return None
    return next((l for l in locais if normalizar_nome(l["nome"]) == alvo), None)


def locais_parecidos(locais, nome, limite=LIMITE_PARECIDO):
    """Locais ativos com nome muito parecido (mas não igual) ao informado."""
    alvo = normalizar_nome(nome)
    if not alvo:
        return []
    achados = []
    for l in locais_ativos(locais):
        n = normalizar_nome(l["nome"])
        if n != alvo and difflib.SequenceMatcher(None, alvo, n).ratio() >= limite:
            achados.append(l)
    return achados


def adicionar_local(locais, nome):
    """Retorna (local, criado). Reaproveita um local igual e reativa se estava arquivado."""
    nome = " ".join(str(nome or "").split())
    if not nome or normalizar_nome(nome) in RESERVADOS:
        return None, False
    existente = achar_local(locais, nome)
    if existente:
        existente["ativo"] = True
        return existente, False
    novo = {"id": f"loc_{uuid.uuid4().hex[:8]}", "nome": nome, "ativo": True}
    locais.append(novo)
    return novo, True


def renomear_local(locais, local_id, novo_nome):
    """Retorna (ok, erro)."""
    novo_nome = " ".join(str(novo_nome or "").split())
    if not novo_nome:
        return False, "Informe o nome."
    if normalizar_nome(novo_nome) in RESERVADOS:
        return False, "Esse nome já existe como opção própria (Apps, Particular ou Outro)."
    alvo = next((l for l in locais if l["id"] == local_id), None)
    if alvo is None:
        return False, "Local não encontrado."
    outro = achar_local(locais, novo_nome)
    if outro is not None and outro["id"] != local_id:
        return False, f"Já existe um local chamado “{outro['nome']}”."
    alvo["nome"] = novo_nome
    return True, None


def arquivar_local(locais, local_id):
    alvo = next((l for l in locais if l["id"] == local_id), None)
    if alvo is None:
        return False
    alvo["ativo"] = False
    return True


def montar_origens(linhas):
    """linhas: [(local_dict_ou_None, valor)] -> origens do turno (soma o mesmo local repetido, ignora valor 0)."""
    por_id = {}
    for local, valor in linhas:
        valor = float(valor or 0)
        if local is None or valor <= 0:
            continue
        if local["id"] in por_id:
            por_id[local["id"]]["valor"] = round(por_id[local["id"]]["valor"] + valor, 2)
        else:
            por_id[local["id"]] = {"local_id": local["id"], "local": local["nome"], "valor": round(valor, 2)}
    return list(por_id.values())


def validar_linhas(linhas):
    """Há valor digitado sem origem escolhida? Retorna mensagem de erro ou None."""
    for local, valor in linhas:
        if (valor or 0) > 0 and local is None:
            return "Escolha a origem de cada valor informado."
    return None


def total_origens(origens):
    return round(sum(o["valor"] for o in origens), 2)


def _texto_origem(ganho_app, origens):
    nomes = [o["local"] for o in origens]
    if not nomes:
        return "iFood / Apps"
    extra = len(nomes) - 2
    partes = (["Apps"] if ganho_app > 0 else []) + nomes[:2]
    texto = " + ".join(partes)
    return f"{texto} (+{extra})" if extra > 0 else texto


def campos_de_ganho(ganho_app, origens):
    """Campos do turno que dependem dos ganhos (mantém compatibilidade com turnos antigos)."""
    ganho_app = float(ganho_app or 0)
    soma = total_origens(origens)
    return {
        "ganho_app": ganho_app,
        "ganho_estab": soma,
        "bruto": round(ganho_app + soma, 2),
        "estabelecimento": _texto_origem(ganho_app, origens),
        "origens": origens,
    }


def origens_do_turno(turno):
    """Origens de um turno, inclusive os antigos (que só têm estabelecimento + ganho_estab)."""
    if turno.get("origens"):
        return turno["origens"]
    lista = []
    if turno.get("ganho_app", 0) > 0:
        lista.append({"local_id": "apps", "local": "Apps", "valor": float(turno["ganho_app"])})
    if turno.get("ganho_estab", 0) > 0:
        nome = str(turno.get("estabelecimento", "Outro")).replace("Apps + ", "").strip() or "Outro"
        lista.append({"local_id": None, "local": nome, "valor": float(turno["ganho_estab"])})
    return lista
