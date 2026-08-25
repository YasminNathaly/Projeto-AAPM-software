import bcrypt


def hash_senha(senha: str) -> str:
    senha_bytes = senha.encode("utf-8")[:72]
    hash_bytes = bcrypt.hashpw(senha_bytes, bcrypt.gensalt())
    return hash_bytes.decode("utf-8")


def verificar_senha(senha_plana: str, hash_salvo: str) -> bool:
    try:
        return bcrypt.checkpw(senha_plana.encode("utf-8")[:72], hash_salvo.encode("utf-8"))
    except (ValueError, TypeError):
        return False
