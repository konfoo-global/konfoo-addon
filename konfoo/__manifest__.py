# noinspection PyStatementEffect
{
    'name': 'Konfoo',
    'version': '1.2.4',
    'author': 'Konfoo',
    'website': 'https://konfoo.com',
    'license': 'Other proprietary',
    'data': [
        # 'data/data.xml',
        'data/cron.xml',

        'security/security.xml',
        'security/ir.model.access.csv',

        'views/konfoo_dataset.xml',
        'views/konfoo_cache.xml',
        'views/konfoo_session.xml',
        'views/konfoo_allowed_model.xml',
        'views/konfoo_menus.xml',
        'views/sale_views.xml',

        'views/res_config_settings_views.xml',  # settings block for master
    ],
    'depends': [
        'sale_management',
        'sale_margin',
        'mrp',
        'mrp_account',
        'uom',
    ],
    'assets': {
        'web.assets_backend': [
            'konfoo/static/src/**/*.js',
            'konfoo/static/src/**/*.css',
            'konfoo/static/src/**/*.xml',
        ],
        # 'web.assets_qweb': [
        #     'konfoo/static/src/**/*.xml',
        # ],
    },

    'installable': True,
    'application': True,

    'cloc_exclude': [
        '**/*',
    ],

    'override': {
        '16.0': {
            'data': [
                # 'data/data.xml',
                'data/cron.xml',

                'security/security.xml',
                'security/ir.model.access.csv',

                'views/konfoo_dataset_legacy.xml',
                'views/konfoo_cache.xml',
                'views/konfoo_session.xml',
                'views/konfoo_allowed_model.xml',
                'views/konfoo_menus.xml',
                'views/sale_views_16.xml',

                'views/res_config_settings_views_legacy.xml',  # settings block for <= 16.0
            ],
        }
    }
}
