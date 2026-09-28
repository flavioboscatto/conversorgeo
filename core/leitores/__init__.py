# ==============================================================================
# Leitores: arquivo (bytes, em memória) → Projeto (SIRGAS 2000 geodésico).
# ==============================================================================


class ErroLeitura(ValueError):
    """Erro de leitura com mensagem pronta para o usuário (linguagem de agrimensor)."""
