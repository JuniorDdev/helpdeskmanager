from decimal import Decimal, InvalidOperation


class ValidationError(ValueError):
    """Erro de entrada que pode ser mostrado com segurança ao usuário."""


def required_text(form, field, label, max_length=None):
    value = (form.get(field) or "").strip()
    if not value:
        raise ValidationError(f"{label} é obrigatório.")
    if max_length and len(value) > max_length:
        raise ValidationError(f"{label} deve ter no máximo {max_length} caracteres.")
    return value


def optional_text(form, field, max_length=None):
    value = (form.get(field) or "").strip()
    if max_length and len(value) > max_length:
        raise ValidationError(f"O campo {field} deve ter no máximo {max_length} caracteres.")
    return value or None


def choice(form, field, choices, label):
    value = (form.get(field) or "").strip()
    if value not in choices:
        raise ValidationError(f"{label} inválido.")
    return value


def optional_id(form, field):
    value = (form.get(field) or "").strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"Identificador de {field} inválido.")
    if parsed <= 0:
        raise ValidationError(f"Identificador de {field} inválido.")
    return parsed


def integer(form, field, label, minimum=0):
    value = (form.get(field) or "").strip()
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} deve ser um número inteiro válido.")
    if parsed < minimum:
        raise ValidationError(f"{label} deve ser maior ou igual a {minimum}.")
    return parsed


def non_negative_decimal(form, field, label):
    value = (form.get(field) or "").strip()
    if not value:
        return Decimal("0")
    try:
        parsed = Decimal(value.replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValidationError(f"{label} deve ser um valor válido.")
    if parsed < 0:
        raise ValidationError(f"{label} não pode ser negativo.")
    return parsed
