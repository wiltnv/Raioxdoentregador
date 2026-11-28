"""PIN e bloqueio de tentativas (sem Streamlit, para poder testar).

- PIN guardado com PBKDF2-HMAC-SHA256 e sal aleatório por usuário.
- Opcional: segredo PIN_PEPPER nos Secrets do Streamlit. Com ele, um vazamento só do
  banco não permite descobrir os PINs. Defina uma vez e NUNCA mais troque.
- Hashes antigos (SHA-256 simples) ainda entram e são atualizados no primeiro login.
- Bloqueio progressivo por conta depois de 5 erros seguidos.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

ITERACOES = 200_000
TENTATIVAS_ANTES_DE_BLOQUEAR = 5
MSG_LOGIN_GENERICA = "E-mail ou PIN incorretos."


def pin_formato_valido(pin):
    pin = (pin or "").strip()
    return pin.isdigit() and 4 <= len(pin) <= 6


def _derivar(email, pin, salt, iteracoes, pepper):
    material = f"{email.strip().lower()}:{pin.strip()}".encode("utf-8")
    if pepper:
        material = hmac.new(pepper.encode("utf-8"), material, hashlib.sha256).digest()
    return hashlib.pbkdf2_hmac("sha256", material, salt, iteracoes)


def hash_pin(email, pin, pepper=""):
    salt = secrets.token_bytes(16)
    chave = _derivar(email, pin, salt, ITERACOES, pepper)
    prefixo = "pbkdf2p" if pepper else "pbkdf2"
    return f"{prefixo}${ITERACOES}${salt.hex()}${chave.hex()}"


def _hash_legado(email, pin):
    sal = f"raiox_v3_{email.strip().lower()}_{pin.strip()}"
    return hashlib.sha256(sal.encode("utf-8")).hexdigest()


def verificar_pin(pin_hash, email, pin, pepper=""):
    """Retorna (ok, precisa_atualizar_hash)."""
    pin_hash = pin_hash or ""
    if pin_hash.startswith("pbkdf2"):
        try:
            prefixo, iteracoes, salt_hex, chave_hex = pin_hash.split("$")
            iteracoes = int(iteracoes)
            salt = bytes.fromhex(salt_hex)
        except Exception:
            return False, False
        usa_pepper = prefixo == "pbkdf2p"
        if usa_pepper and not pepper:
            return False, False  # hash feito com pepper, mas o segredo não está configurado
        calculado = _derivar(email, pin, salt, iteracoes, pepper if usa_pepper else "").hex()
        if not hmac.compare_digest(calculado, chave_hex):
            return False, False
        precisa = iteracoes < ITERACOES or (bool(pepper) and not usa_pepper)
        return True, precisa
    # formato antigo (SHA-256 com sal fixo): aceita e pede atualização
    ok = hmac.compare_digest(_hash_legado(email, pin), pin_hash)
    return ok, ok


def verificar_pin_fantasma(pin):
    """Gasta o mesmo tempo de uma verificação real quando o e-mail não existe."""
    _derivar("fantasma@raiox", pin or "0000", b"\x00" * 16, ITERACOES, "")


def proximo_estado_falha(tentativas, agora):
    """Após mais um erro: devolve (novas_tentativas, bloqueado_ate ou None).

    Do 5º erro em diante cada novo erro bloqueia: 15 min (5 a 9), 1 h (10 a 14), 24 h (15+).
    Só um acerto zera o contador.
    """
    tentativas = int(tentativas or 0) + 1
    if tentativas < TENTATIVAS_ANTES_DE_BLOQUEAR:
        return tentativas, None
    if tentativas >= 15:
        espera = timedelta(hours=24)
    elif tentativas >= 10:
        espera = timedelta(hours=1)
    else:
        espera = timedelta(minutes=15)
    return tentativas, agora + espera


def minutos_restantes(bloqueado_ate, agora):
    segundos = (bloqueado_ate - agora).total_seconds()
    return max(1, int(-(-segundos // 60)))
