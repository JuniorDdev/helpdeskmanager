def excel_safe(value):
    """Evita que conteúdo fornecido pelo usuário seja interpretado como fórmula."""
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value
