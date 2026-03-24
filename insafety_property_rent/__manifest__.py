# -*- coding: utf-8 -*-
{
    'name': "Bomatech",

    'summary': """
        Deals with the accounting aspects of property rentals""",

    'description': """
        Deals with the accounting aspects of property rentals
    """,

    'author': "Insafety GmbH, Zürich, Switzerland",
    'website': "https://odoo.insafety.ch",

    'category': 'Accounting',
    'version': '0.1',

    'depends': ['contacts','account','mail'],

    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/property.xml',
        'views/property_building.xml',
        'views/property_type.xml',
        'views/property_tag.xml',
        'views/property_rent_log.xml',
        'views/property_account_view.xml',
        'views/property_rent_contract.xml',
        'views/property_analytics.xml',
        'views/menu_items.xml',
        'data/ir_cron_data.xml',
        'wizard/landlord_statement_wizard_view.xml',
        'report/landlord_statement_report.xml',
    ],

    'demo': [
        'data/demo.xml', 
    ],
    'auto_install': True,
    'license': "LGPL-3",
    'images': ['static/description/main_screenshot.png','static/description/cost_billing_en.png'],
    'module_type': 'official',
    'assets': {},
}
