# -*- coding: utf-8 -*-
{
    'name': "Prepaid Card",
    'summary': "Manage prepaid cards for N Beauty customers",
    'description': """
        This module handles prepaid card types and customer cards
        with bonus calculations and discount management.
    """,
    'author': "My Company",
    'website': "https://www.yourcompany.com",
    'category': 'Sales',
    'version': '0.1',
    'license': 'LGPL-3',
    'application': True,
    'installable': True,

    'depends': [
        'base',
        'contacts',
        'point_of_sale',
        'account',
        'web',
    ],

    'data': [
        'data/prepaid_card_sequence.xml',
        'data/account_data.xml',
        # 'data/pos_payment_method.xml',
        'data/cron.xml',
        'data/voucher_sequence.xml',
        'views/prepaid_card_views.xml',
        'views/prepaid_card_type_views.xml',
        'views/prepaid_transaction.xml',
        'views/pos_payment_views.xml',
        'views/prepaid_card_topup_view.xml',
        'views/prepaid_voucher_views.xml',
        'views/menus.xml',
        'security/ir.model.access.csv',
        'reports/prepaid_card_reports.xml',
        'reports/prepaid_card_topup_report.xml',
    ],

    'demo': [
        'demo/demo.xml',
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            'nbeauty_prepaid_card/static/src/js/PaymentNCard.js',
            'nbeauty_prepaid_card/static/src/xml/NCardPopup.xml',
            'nbeauty_prepaid_card/static/src/xml/ncard_receipt.xml',
            # 'nbeauty_prepaid_card/static/src/js/ncard_order_patch.js',
        ],
    },
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
