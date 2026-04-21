from django import template

register = template.Library()


@register.filter(name='split')
def split(value, sep=','):
    """{{ "a,b,c"|split:"," }} → ['a','b','c']"""
    return value.split(sep)


@register.filter(name='badge_color')
def badge_color(statut):
    colors = {
        'attente':  'warning',
        'confirme': 'success',
        'annule':   'danger',
        'termine':  'secondary',
    }
    return colors.get(statut, 'secondary')
