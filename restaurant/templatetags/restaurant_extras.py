from django import template

register = template.Library()

@register.filter
def dict_values_sum(dictionary):
    """Sum all values in a dictionary"""
    if not dictionary:
        return 0
    return sum(int(value) for value in dictionary.values())

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0 