from django import template

register = template.Library()


@register.filter
def vnd(amount):
    return f"{int(amount):,}".replace(",", ".") + " ₫"
