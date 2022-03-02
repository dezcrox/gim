# -*- coding: utf-8 -*-
{
    'name': 'Mercado Pago - website - odoo - Latam',
    'description': "Addon para recibir pagos a través del sitio web de comercio electrónico",
    'author': "ROCKSCRIPTS",
    'website': "https://instagram.com/rockscripts",
    'summary': "Mercado Pago para sitio web de comercio electrónico",
    'version': '0.1',
    "license": "OPL-1",
    'price':'60',
    'currency':'USD',
    'support': 'rockscripts@gmail.com',
    'category': 'Website',
    "images": ["images/banner.png"],
    'depends': ['base','website_sale','payment','account'],
    'data': [
                'views/templates.xml',
                'views/payment_acquirer.xml',
                'views/sale_order.xml',
                'views/payment_transaction.xml',
                'views/ir_cron.xml',
                'data/mercadopago.xml',
            ],
    'external_dependencies': {
                                'python' : ['mercadopago'],
                             },
    'qweb': [
              
            ],
    'installable': True,
}