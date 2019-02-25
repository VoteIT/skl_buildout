
def includeme(config):
    config.include('.fanstatic_lib')
    #Static dir
    config.add_static_view('static_skl_theme', 'static', cache_max_age=3600)
