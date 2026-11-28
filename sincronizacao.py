"""Sincronização segura do estado (user_states) com o Supabase.

Este módulo NÃO importa o Streamlit de propósito: assim a lógica de versão e de
mesclagem pode ser testada sozinha (python -m unittest).

Como funciona:
- Cada linha de user_states tem uma coluna `version`.
- Ao gravar, só vale se a versão no banco ainda for a que a sessão leu.
- Se outra sessão gravou antes (conflito), buscamos o estado atual do banco e
  fazemos uma mesclagem de 3 vias (base = o que lemos, local = o que temos,
  servidor = o que está lá agora), preservando o trabalho dos dois lados.
"""
import copy
from calculos_moto import migrate_data

LISTAS_ESTADO = ("turnos", "abastecimentos", "manutencoes")
MAX_TENTATIVAS = 4


def _mesclar_motos(base, local, servidor):
    b = {m["id"]: m for m in base.get("motos", [])}
    l = {m["id"]: m for m in local.get("motos", [])}
    s_lista = servidor.get("motos", [])
    resultado = {m["id"]: copy.deepcopy(m) for m in s_lista}

    for mid, m_local in l.items():
        if mid not in b:
            # moto nova criada nesta sessão
            resultado[mid] = copy.deepcopy(m_local)
        elif mid in resultado:
            # campo a campo: o que mudei aqui vence, o resto fica como está no servidor
            m_final = resultado[mid]
            m_base = b[mid]
            for campo in set(m_local) | set(m_base):
                if m_local.get(campo) == m_base.get(campo):
                    continue
                if campo not in m_local:
                    m_final.pop(campo, None)
                elif campo == "hodometro":
                    m_final[campo] = max(m_local[campo], m_final.get(campo, 0))
                else:
                    m_final[campo] = copy.deepcopy(m_local[campo])
        else:
            # alguém removeu a moto no servidor e eu a alterei: mantém a minha
            resultado[mid] = copy.deepcopy(m_local)

    for mid in b:
        if mid not in l:
            # removi esta moto aqui
            resultado.pop(mid, None)
    return list(resultado.values())


def mesclar_estados(base, local, servidor):
    """Mescla o estado local com o do servidor usando `base` como ancestral."""
    base = base or {}
    resultado = copy.deepcopy(servidor)

    # campos simples: o que mudei desde a leitura vence
    for chave in set(local) | set(base):
        if chave in LISTAS_ESTADO or chave == "motos":
            continue
        if local.get(chave) != base.get(chave):
            if chave in local:
                resultado[chave] = copy.deepcopy(local[chave])
            else:
                resultado.pop(chave, None)

    # listas de registros: soma o que adicionei, tira o que removi
    for chave in LISTAS_ESTADO:
        b = base.get(chave, [])
        l = local.get(chave, [])
        s = servidor.get(chave, [])
        adicionados = [x for x in l if x not in b]
        removidos = [x for x in b if x not in l]
        mesclada = [x for x in s if x not in removidos]
        for x in adicionados:
            if x not in mesclada:
                mesclada.append(copy.deepcopy(x))
        resultado[chave] = mesclada

    resultado["motos"] = _mesclar_motos(base, local, servidor)
    return resultado


def _eh_duplicado(exc):
    msg = str(exc).lower()
    return "duplicate" in msg or "23505" in msg or "already exists" in msg


def _ler_linha(sb, user_key):
    res = sb.table("user_states").select("state_json, version").eq("user_key", user_key).execute()
    return next(iter(res.data or []), None)


def salvar_com_versao(sb, user_key, data, versao, base):
    """Grava `data` respeitando a versão.

    Retorna (ok, nova_versao, erro). Em conflito, `data` é atualizado NO LUGAR
    com o resultado da mesclagem antes de tentar de novo.
    """
    try:
        for _ in range(MAX_TENTATIVAS):
            nova = None
            if versao is None:
                # primeira gravação desta conta
                try:
                    sb.table("user_states").insert(
                        {"user_key": user_key, "state_json": data, "version": 1}
                    ).execute()
                    return True, 1, None
                except Exception as e:
                    if not _eh_duplicado(e):
                        raise
            else:
                res = sb.rpc(
                    "salvar_state",
                    {"p_key": user_key, "p_json": data, "p_version": versao},
                ).execute()
                nova = res.data
                if isinstance(nova, list):
                    nova = nova[0] if nova else None
                if nova:
                    return True, int(nova), None

            # conflito: outra sessão gravou antes. Busca o estado atual e mescla.
            linha = _ler_linha(sb, user_key)
            if not linha:
                versao = None
                continue
            servidor = migrate_data(copy.deepcopy(linha["state_json"]))
            mesclado = mesclar_estados(base, data, servidor)
            data.clear()
            data.update(mesclado)
            base = copy.deepcopy(servidor)
            versao = linha.get("version") or 1
        return False, versao, "Muitas alterações simultâneas. Recarregue da nuvem e repita o lançamento."
    except Exception as e:
        return False, versao, str(e)
