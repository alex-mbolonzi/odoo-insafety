# -*- coding: utf-8 -*- 
import logging
import locale
from datetime import datetime, timedelta
import time 
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo import _

_logger = logging.getLogger(__name__)

class PropertyRentContract(models.Model):
    _inherit = "mail.thread"
    _name = 'insafety.property.rent.contract'
    _description = 'Property Rent Contracts'
    _check_company_auto = True

    property_id = fields.Many2one('insafety.property', string="Unit", required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True,
        default=lambda self: self.env.company)
    #tenant_id = fields.Many2one('res.partner', string="Tenant", domain="[('is_tenant', '=', True)]", required=True, tracking=True)
    tenant_id = fields.Many2one('res.partner', string="Tenant", required=True, tracking=True)
    name = fields.Many2one(string="Name", related="tenant_id", tracking=True)
    rent_date_from = fields.Date(string="Rent From", required=True, tracking=True)
    rent_date_to = fields.Date(string="Rent To", tracking=True)
    monthly_rent = fields.Float(string="Monthly Rent", required=True, tracking=True)
    monthly_extra_costs = fields.Float(string="Monthly Garbage Fee", required=True, tracking=True)
    monthly_lump_sum_costs = fields.Float(string="Monthly Lump Sum Costs", required=True, tracking=True)

    rent_days = fields.Integer(string="Rent Days", compute="_cal_rent_days")
    rent_month = fields.Float(string="Rent Month", digits=(12,1), compute="_cal_rent_days")
    monthly_extra_costs_paid_calc = fields.Float(string="Paid", compute="_cal_rent_days")
    distribution_key = fields.Float(string="Key", compute="_cal_distribution_key")
    distribution_base = fields.Float(string="Base", compute="_cal_distribution_key")
    next_cost_billing = fields.Float(string="Cost Amount", compute="calc_next_cost_billing")

    building_id = fields.Many2one(string="Building", related="property_id.building_id", store=False)
   

    administrative_expenses = fields.Float(string="Administration", compute="_cal_admin_expens")
    cost_billing_total = fields.Float(string="Invoice", compute="_cal_cost_billing_total")

    account_receivable_id = fields.Many2one('account.account', string="Account Receivable", domain=[('deprecated', '=', False)], 
                                            check_company=True, compute="_compute_default", store=True, readonly=False, tracking=True)
    
    tax_ids = fields.Many2many('account.tax', string='Taxes', domain=[('active', '=', True)],
                               check_company=True, compute="_compute_default", store=True, readonly=False, tracking=True)

    invoice_payment_term_id = fields.Many2one('account.payment.term', string="Rent Payment Term", 
                                              compute="_compute_default", store=True, readonly=False, tracking=True)
    


    qr_code_method = fields.Selection(
        string="Payment QR-code", copy=False,
        selection=lambda self: self.env['res.partner.bank'].get_available_qr_methods_in_sequence(),
        help="Type of QR-code to be generated for the payment of this invoice, "
             "when printing it. If left blank, the first available and usable method "
             "will be used.", compute="_compute_default", store=True, readonly=False
    )

    rent_direct_post = fields.Boolean(string="Direct Post", default=True)


    @api.depends('building_id.account_receivable_id','building_id.tax_ids')
    def _compute_default(self):
        for rec in self:    
            rec.account_receivable_id = rec.building_id.account_receivable_id
            rec.tax_ids = rec.building_id.tax_ids
            rec.invoice_payment_term_id = rec.building_id.invoice_payment_term_id
            rec.qr_code_method = rec.building_id.qr_code_method

    @api.depends('building_id.total_expense','distribution_base','distribution_key','rent_days')
    def calc_next_cost_billing(self):
        for rec in self:
            distribution_base = 1
            if rec.distribution_base != 0:
                distribution_base = rec.distribution_base
            rec.next_cost_billing = rec.building_id.total_expense / distribution_base * rec.distribution_key / 365 * rec.rent_days


    @api.depends('next_cost_billing','administrative_expenses','monthly_extra_costs_paid_calc')
    def _cal_cost_billing_total(self):
        for rec in self:
            rec.cost_billing_total = rec.next_cost_billing + rec.administrative_expenses - rec.monthly_extra_costs_paid_calc
    
    @api.depends('building_id.administrative_expenses', 'next_cost_billing')
    def _cal_admin_expens(self):
        for rec in self:
            rec.administrative_expenses = rec.next_cost_billing * rec.building_id.administrative_expenses / 100
  
    @api.depends('building_id.billing_period_from','building_id.billing_period_to', 'rent_date_from', 'rent_date_to')
    def _cal_rent_days(self):
        for rec in self:
            if rec.building_id.billing_period_from and rec.building_id.billing_period_to:
                if rec.rent_date_from <= rec.building_id.billing_period_from:
                    startDate = rec.building_id.billing_period_from 
                else:
                    startDate = rec.rent_date_from      
                if rec.rent_date_to == False:
                    endDate = rec.building_id.billing_period_to
                else:
                    if rec.rent_date_to > rec.building_id.billing_period_to:
                        endDate = rec.building_id.billing_period_to
                    else:
                        endDate = rec.rent_date_to
                days = (endDate - startDate).days + 1
                if days > 0:
                    rec.rent_days = days
                    rec.rent_month = rec.rent_days / 30.4167
                    rec.monthly_extra_costs_paid_calc = rec.monthly_extra_costs * rec.rent_month
                else:
                    rec.rent_days = 0
                    rec.rent_month = 0
                    rec.monthly_extra_costs_paid_calc = 0
            else:
                rec.rent_days = 0
                rec.rent_month = 0
                rec.monthly_extra_costs_paid_calc = 0


            
    @api.constrains('rent_date_from','rent_date_to')
    def _validate_date_id(self):
        errorMessage = ""
        for rec in self:
            if(rec.rent_date_to):
                if(rec.rent_date_from >= rec.rent_date_to):
                    errorMessage = "From cannot be after to"
            for contract in rec.property_id.rent_contract_ids:
                if rec.id != contract.id:
                    if rec.rent_date_to == False and contract.rent_date_to == False:
                        errorMessage = "Can only have one open contract"
                        break

                    if contract.rent_date_to:
                        if rec.rent_date_to:
                            if contract.rent_date_from <= rec.rent_date_to and rec.rent_date_from <= contract.rent_date_to:
                                errorMessage = "Date To in range of other contract"
                                break
                    
                    if contract.rent_date_to == False:
                        if rec.rent_date_to:
                            if contract.rent_date_from <= rec.rent_date_to:
                                errorMessage = "Date To in range of other contract"
                                break


                    if rec.rent_date_to == False:
                        if rec.rent_date_from <= contract.rent_date_to:
                            errorMessage = "Date To in range of other contract"
                            break

            if errorMessage != "":    
                raise ValidationError(errorMessage)
            # else:
            #    rec.rent_contract_id.current_rent_contract = rec.tenant_id
    def open_contract(self): 
        return {
        'name': "_insafety_property_rent_contract_form",
        'view_type': 'form',
        'view_mode': 'form',
        'res_model': 'insafety.property.rent.contract',
        'type': 'ir.actions.act_window',
        'target': 'current',
        'res_id': self.id, 
        }
    
    def _create_invoices(self, target_date=None):
        """Generate monthly rent invoices.
        
        Args:
            target_date: Optional date (e.g. date(2026, 5, 1)) to generate invoices for 
                         a specific month. If not provided, defaults to next month.
        """
        if target_date:
            if isinstance(target_date, str):
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            iDay = target_date
        else:
            iDay = datetime.today() + timedelta(days=31)
            iDay = iDay.date() if isinstance(iDay, datetime) else iDay

        rec = self.env['insafety.property.rent.log'].search([
            ('year','=', iDay.year),
            ('month','=', iDay.month),
            ('status','=', 'ok')
        ])
        if rec:
            self.env['insafety.property.rent.log'].create(
            {
                'date_time': datetime.today(),
                'month': iDay.month,
                'year': iDay.year,
                'status': 'error'
            })
            return

        buildings = self.env['insafety.property.building'].search([])
        for building in buildings:  
            for property in building.property_ids:
                for rent_contract in property.rent_contract_ids:     
                    c = False
                    t =  datetime.date(datetime.today())    
                    for contract in rent_contract:
                        if contract.rent_date_from < t:
                            if contract.rent_date_to == False:
                                c = contract 
                            else:
                                if contract.rent_date_to >= t:
                                    c = contract 
                    if c:
                        self.create_invoice(c, target_date=iDay)
                    
         
        self.env['insafety.property.rent.log'].create(
            {
                'date_time': datetime.today(),
                'month': iDay.month,
                'year': iDay.year
            })

    def create_invoice(self, contract, target_date=None):
        """Create a single rent invoice for a contract.
        
        Args:
            contract: The rent contract record.
            target_date: Optional date for the invoice month. 
                         If not provided, defaults to next month.
        """
        self = self.with_company(contract.company_id)
        locale.setlocale(locale.LC_ALL, contract.tenant_id.lang + '.UTF-8')

        # Determine the invoice date (1st of target month)
        if target_date:
            if isinstance(target_date, str):
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            invoice_date = target_date.replace(day=1)
        else:
            iDay = datetime.today() - timedelta(days=-34)
            invoice_date = iDay.replace(day=1) if hasattr(iDay, 'replace') else iDay
            invoice_date = invoice_date.date() if isinstance(invoice_date, datetime) else invoice_date

        # Validate required configuration before creating invoice
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', contract.company_id.id),
            ('code', '=', 'TIJ'),
        ], limit=1)
        if not journal:
            _logger.error(
                "Journal TIJ not found for company %s (id=%s). Skipping invoice for contract %s.",
                contract.company_id.name, contract.company_id.id, contract.tenant_id.name
            )
            return
        if not contract.account_receivable_id:
            _logger.error(
                "No receivable account set on contract for tenant %s. Skipping.",
                contract.tenant_id.name
            )
            return

        analyticAccounts = {}
        for a in contract.building_id.analytic_account_ids:
            analyticAccounts[str(a.id)] = 100

        # Build invoice lines dynamically
        invoice_lines = [
            (0, 0, {
                'price_unit': contract.monthly_rent,
                'account_id': contract.account_receivable_id.id,
                'tax_ids': [(6, 0, contract.tax_ids.ids)],
                'name': _('Monthly Rent'),
                'analytic_distribution': analyticAccounts,
                'quantity': 1.0,
            }),
        ]

        # Add garbage collection line only if amount > 0
        # if contract.monthly_extra_costs > 0:
        #     if not contract.building_id.garbage_collection_income_account_id:
        #         _logger.warning(
        #             "Garbage collection account not set on building %s. Skipping garbage line for tenant %s.",
        #             contract.building_id.name, contract.tenant_id.name
        #         )
        #     else:
        #         invoice_lines.append((0, 0, {
        #             'price_unit': contract.monthly_extra_costs,
        #             'account_id': contract.building_id.garbage_collection_income_account_id.id,
        #             'tax_ids': [(6, 0, contract.building_id.cost_billing_tax_ids.ids)],
        #             'name': _('[GRB_SRV] Garbage Collection'),
        #             'analytic_distribution': analyticAccounts,
        #             'quantity': 1.0,
        #         }))

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': contract.tenant_id.id,
            'invoice_date': invoice_date.strftime('%Y-%m-%d'),
            'invoice_payment_term_id': contract.invoice_payment_term_id.id,
            'qr_code_method': contract.qr_code_method,
            'journal_id': journal.id,
            'invoice_line_ids': invoice_lines,
        })

        if contract.rent_direct_post:
            invoice.action_post()

        month = invoice_date.strftime('%B')
        year = invoice_date.strftime('%Y')

        unit = contract.property_id.display_name + ", " + contract.property_id.description

        cur = self.env.company.currency_id.display_name
        text = f'''
            <p style="page-break-before:always;"> </p>  
            <table>
                <tr>
                    <strong><td>{_('Rent Invoice') } </td><td> {month} - {year}</td></strong>
                </tr>
                <tr>
                    <td>{contract.building_id.display_name} </td><td></td>
                </tr>
                <tr>
                    <td>{unit} </td><td></td>
                </tr>
                <tr>
                    <td>{_('Monthly Rent')} </td><td style="text-align:right"> {cur} {format(contract.monthly_rent, ".2f")  }</td>
                </tr>
                <tr>
                    <td>{_('Monthly Garbage Fee')} </td><td style="text-align:right"> {cur} {format(contract.monthly_extra_costs, ".2f")  }</td>
                </tr>
            </table>
        '''
        invoice.narration = text
            
    @api.depends('building_id.distribute_by', 'property_id.total_rooms', 'property_id.living_area', 'property_id.volume', 'property_id.cost_factor_custom', 'building_id.total_rooms', 'building_id.total_area', 'building_id.total_volume', 'building_id.total_cost_factor_custom', 'building_id.property_count')
    def _cal_distribution_key(self):
        for rec in self:
            dist = 1
            base = 1
            if rec.building_id.distribute_by == "rooms":
                dist = rec.property_id.total_rooms
                base = rec.building_id.total_rooms
            if rec.building_id.distribute_by == "area":
                dist = rec.property_id.living_area
                base = rec.building_id.total_area
            if rec.building_id.distribute_by == "volume":
                dist = rec.property_id.volume
                base = rec.building_id.total_volume
            if rec.building_id.distribute_by == "custom":
                dist = rec.property_id.cost_factor_custom
                base = rec.building_id.total_cost_factor_custom
            if rec.building_id.distribute_by == "equal":
                dist = 1
                base = rec.building_id.property_count
            
            rec.distribution_key = dist
            rec.distribution_base = base
