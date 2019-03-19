from fanstatic import Library
from fanstatic import Resource


library = Library('skl_og_static', 'static')

#main_css = Resource(library, 'main.css', depends = (bootstrap_css,))


def includeme(config):
    pass
