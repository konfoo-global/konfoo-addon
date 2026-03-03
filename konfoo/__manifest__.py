# noinspection PyStatementEffect
{
    'name': 'Konfoo',
    'version': '1.15.1',
    'author': 'Konfoo',
    'website': 'https://konfoo.com',
    'license': 'Other proprietary',
    'data': [
        'data/cron.xml',
        'security/security_legacy.xml',
        'security/ir.model.access.csv',
        'views/konfoo_dataset.xml',
        'views/konfoo_cache.xml',
        'views/konfoo_session.xml',
        'views/konfoo_allowed_model.xml',
        'views/konfoo_menus.xml',
        'views/sale_views.xml',
        'views/res_config_settings_views.xml',
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
            'konfoo/static/src/js/*.js',
            'konfoo/static/src/css/*.css',
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
        '18.0': {
            'data': [
                'data/cron.xml',
                'security/security_legacy.xml',
                'security/ir.model.access.csv',
                'views/konfoo_dataset.xml',
                'views/konfoo_cache.xml',
                'views/konfoo_session.xml',
                'views/konfoo_allowed_model.xml',
                'views/konfoo_menus.xml',
                'views/sale_views.xml',
                'views/res_config_settings_views.xml',
            ],
        },
        '17.0': {
            'data': [
                'data/cron_legacy.xml',
                'security/security_legacy.xml',
                'security/ir.model.access.csv',
                'views/konfoo_dataset_17.xml',
                'views/konfoo_cache_17.xml',
                'views/konfoo_session_17.xml',
                'views/konfoo_allowed_model_17.xml',
                'views/konfoo_menus.xml',
                'views/sale_views_17.xml',
                'views/res_config_settings_views.xml',
            ],
            'assets': {
                'web.assets_backend': [
                    'konfoo/static/src/17/js/*.js',
                    'konfoo/static/src/css/*.css',
                ],
            },
        },
        '16.0': {
            'data': [
                'data/cron_legacy.xml',
                'security/security_legacy.xml',
                'security/ir.model.access.csv',
                'views/konfoo_dataset_legacy.xml',
                'views/konfoo_cache_17.xml',
                'views/konfoo_session_17.xml',
                'views/konfoo_allowed_model_17.xml',
                'views/konfoo_menus.xml',
                'views/sale_views_16.xml',
                'views/res_config_settings_views_legacy.xml',  # settings block for <= 16.0
            ],
            'assets': {
                'web.assets_backend': [
                    'konfoo/static/src/16/js/*.js',
                    'konfoo/static/src/css/*.css',
                ],
            },
        },
        '15.0': {
            'depends': [
                'sale_management',
                'sale_margin',
                'sale_mrp',  # only in 15.0
                'mrp',
                'mrp_account',
                'uom',
            ],
            'data': [
                'data/cron_legacy.xml',
                'security/security_legacy.xml',
                'security/ir.model.access.csv',
                'views/konfoo_dataset_legacy.xml',
                'views/konfoo_cache_17.xml',
                'views/konfoo_session_17.xml',
                'views/konfoo_allowed_model_17.xml',
                'views/konfoo_menus.xml',
                'views/sale_views_16.xml',
                'views/res_config_settings_views_legacy.xml',  # settings block for <= 16.0
            ],
            'assets': {
                'web.assets_backend': [
                    'konfoo/static/src/15/js/*.js',
                    'konfoo/static/src/css/*.css',
                ],
            },
        },
    },
}
