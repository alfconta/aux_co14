# Author: NICA-CREATOR desde Nicaragua 
# Copyright 2021 

{
    'name': 'Auxiliary Accounts',
    'version': '14.0.1.1.1',
    'price': 50.00,
    'currency':'USD',
    'support':'gtnorw@yahoo.com',   
    'category': 'Reporting',
    'summary': 'Auxiliary Accounts report in Excel and  pdf Format, so display the records of Account movement in a table,It also shows a report in excel grouping account',   
    'author': 'NICA-CREATOR', 
    "depends": ['base','account',],
    'images': ['static/description/main_screenshot.png'],
    'data': ['auxiliar_cuentas.xml','auxiliar_cuentas_report.xml',"security/ir.model.access.csv",'views.xml',],
    'installable': True,
    'application': True,
    'auto_install': True,
    'license': 'OPL-1',
}
