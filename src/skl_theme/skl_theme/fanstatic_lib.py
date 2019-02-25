from fanstatic import Library
from fanstatic import Resource
from js.bootstrap import bootstrap_css
from voteit.core.fanstaticlib import voteit_main_css


library = Library('skl_theme', 'static')


skl_custom_bootstrap_css = Resource(library, 'css/bootstrap.css', supersedes=(bootstrap_css,))
skl_theme_css = Resource(library, 'css/main.css', depends = (skl_custom_bootstrap_css, voteit_main_css))


def includeme(config):
    pass
