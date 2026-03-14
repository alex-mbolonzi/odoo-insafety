# -*- coding: utf-8 -*-

import time  
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime

class Property(models.Model):
    _name = 'insafety.property'
    _inherit = "mail.thread"
    _description = 'Real Estate Properties'
    _check_company_auto = True


    name = fields.Char(string="Name", required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True,
        default=lambda self: self.env.company)
    status = fields.Selection([('rented','Rented'),('free','Free')], required=True, default="free", 
                              compute="_compute_status", store=True, tracking=True)
    type_id = fields.Many2one('insafety.property.type', string="Unit Type")
    tag_ids = fields.Many2many('insafety.property.tag', string="Unit Tag"
                               )
    building_id = fields.Many2one('insafety.property.building', string="Building", required=True)
    description = fields.Text(string="Description", tracking=True)
    next_cost_billing = fields.Float(string="Next Cost Billing Amount")
    bedrooms = fields.Integer(string="Bedrooms",tracking=True)
    total_rooms = fields.Float(string="Total Rooms", digits=(3,1),tracking=True)
    living_area = fields.Integer(string="Living Area  (sqm)",tracking=True)
    volume = fields.Float(string="Volume (cm)",tracking=True)
    garage = fields.Boolean(string="Garage", default=False, tracking=True)
    garden = fields.Boolean(string="Garden", default=False, tracking=True)
    garden_area = fields.Integer(string="Garden Area (sqm)", tracking=True)
    total_area = fields.Integer(string="Total Area (sqm)", compute="_compute_total_area", store=True)
    garden_orientation = fields.Selection([("north", "North"),("south", "South"),("east", "East"),("west", "West")], 
                                          string="Garden Orientation", default="north")

    current_rent_contract_id = fields.Many2one('res.partner',
        string="Current Rent Contract", compute='_compute_current_tenant', tracking=True)

    cost_factor_custom = fields.Float(string="Cost Factor Custom", digits=(3,1), default=1, tracking=True)
    
    count = fields.Integer(string="Count", default=1)
    empty_days = fields.Integer("Empty Days",  compute="_compute_empty_days")
    empty_month = fields.Integer("Empty Month",  compute="_compute_empty_days")
    calculated_extra_costs = fields.Integer("Calculated Cost Paid",  compute="_compute_empty_days")
    rent_contract_ids = fields.One2many('insafety.property.rent.contract','property_id', string="Rent Contracts")
    
    _sql_constraints = [('name_uniq', 'unique(name)', 'Property already exists')] 

    
    @api.depends('rent_contract_ids.rent_date_from','rent_contract_ids.rent_date_to')
    def _compute_current_tenant(self):
        for rec in self:
            c = False
            t = datetime.today().date()
            for contract in rec.rent_contract_ids:
                if contract.rent_date_from <= t:
                    if not contract.rent_date_to or contract.rent_date_to >= t:
                        c = contract.tenant_id
            rec.current_rent_contract_id = c
    

    @api.depends('current_rent_contract_id')
    def _compute_status(self):
        for rec in self:
            if rec.current_rent_contract_id:
                rec.status = 'rented'
            else:
                rec.status = 'free'


    
    
    
            

    @api.onchange('garden')
    def _change_garden(self):
        if self.garden ==  False:
            self.garden_area = 0
    
    @api.constrains('garden_area', 'garden')
    def _check_garden_area(self):
        for rec in self:
            if rec.garden and rec.garden_area <= 0:
                raise ValidationError("Garden sqm cannot be zero")
    
    @api.depends('living_area','garden_area')
    def _compute_total_area(self):
        for rec in self:
            rec.total_area = rec.living_area + rec.garden_area

    @api.model_create_multi
    def create(self, vals_list):
        property = super().create(vals_list)
        return property
    
    def unlink(self): 
        for rec in self: 
            if len(rec.rent_contract_ids) > 0:
                raise ValidationError("Cannot delete, property has rent contracts.")
            super(Property, rec).unlink()
 

    def open_property(self):
        return {
            'name': "_insafety_property_form",
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'insafety.property',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': self.id, 
        }
    
    def open_building(self):
        return {
            'name': "_insafety_property_building_form",
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'insafety.property.building',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': self.building_id.id, 
        }

    # def open_rent_contract(self):
    #     self.ensure_one()
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Rent Contracts',
    #         'view_mode': 'tree,form',
    #         'res_model': 'insafety.property.rent.contract',
    #         'domain': [('property_id', '=', self.id)],
    #         'context': {'default_property_id': self.id},
    #         'target': 'current',
    #     }
