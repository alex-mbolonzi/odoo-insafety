# -*- coding: utf-8 -*-

from odoo import models, fields, api

class LandlordStatementWizard(models.TransientModel):
    _name = 'insafety.landlord.statement.wizard'
    _description = 'Landlord Statement Wizard'

    building_id = fields.Many2one('insafety.property.building', string='Building', required=True)

    def print_report(self):
        return self.env.ref('insafety_property_rent.action_report_landlord_statement').report_action(self)
