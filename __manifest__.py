# -*- coding: utf-8 -*-
{
    'name': "Prepaid Card",
    'summary': "Manage prepaid cards for N Beauty customers",
    'description': """
        This module handles prepaid card types and customer cards
        with bonus calculations and discount management
    """,
    'author': "My Company",
    'website': "https://www.yourcompany.com",
    'category': 'Sales',
    'version': '0.1',

    'depends': [
        'base',
        'contacts',
        'point_of_sale',
        'account'
    ],

    'data': [
        'data/prepaid_card_sequence.xml',
        # 'data/pos_payment_method.xml',
        'views/prepaid_card_views.xml',
        'views/prepaid_card_type_views.xml',
        'views/prepaid_transaction.xml',
        'views/pos_payment_views.xml',
        'views/prepaid_card_topup_view.xml',
        'views/menus.xml',
        'data/cron.xml',
        'security/ir.model.access.csv',

    ],
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'nbeauty_prepaid_card/static/src/js/PaymentNCard.js',
            # 'nbeauty_prepaid_card/static/src/js/NCardPopup.js',
            'nbeauty_prepaid_card/static/src/xml/NCardPopup.xml',

        ],
    },
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
