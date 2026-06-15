import time 
import locale
import base64
from datetime import datetime, timedelta
from odoo import _
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json

class Property(models.Model):
    _name = 'insafety.property.building'
    _inherit = "mail.thread"
    _description = 'Real Estate Property Building'
    _check_company_auto = True


    name = fields.Char(string="Name", required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True,
        default=lambda self: self.env.company)
    description = fields.Text(string="Description", tracking=True)
    account_receivable_id = fields.Many2one('account.account', string="Default Account Receivable", 
                                            domain=[('deprecated', '=', False)], check_company=True, required=True, tracking=True)
    tax_ids = fields.Many2many('account.tax', string='Taxes', domain=[('active', '=', True)], tracking=True)
    invoice_payment_term_id = fields.Many2one('account.payment.term', string="Rent Payment Term", required=True, tracking=True)
    qr_code_method = fields.Selection(
        string="Rent QR-code", copy=False,
        selection=lambda self: self.env['res.partner.bank'].get_available_qr_methods_in_sequence(),
        help="Type of QR-code to be generated for the payment of this invoice, "
             "when printing it. If left blank, the first available and usable method "
             "will be used.",
    )
    account_payable_id = fields.Many2one('account.account', tracking=True,
                                         string="Account Payable", domain=[('deprecated', '=', False),('account_type','=','expense')], check_company=True)
    administrative_expenses = fields.Float(string="Administrative Expenses Percentage", tracking=True)

    total_area = fields.Integer(string="Total Area (sqm)", compute="_compute_total_area")
    total_volume = fields.Float(string="Total Volume", compute="_compute_total_area")
    total_rooms =fields.Float(string="Total Rooms", compute="_compute_total_area")
    total_cost_factor_custom = fields.Float(string="Total Cost Factor Custom", compute="_compute_total_area")

    property_count = fields.Integer(string="Number of Properties", compute="_compute_total_area")
    property_ids = fields.One2many('insafety.property','building_id', string="Properties")
    distribute_by = fields.Selection([("rooms", "Rooms"),("area", "Area"),("volume", "Volume"),("custom", "Custom"), ("equal", "Equal")], string="Distributed By", default="rooms", required=True)
    billing_period_from = fields.Date(string="Billing Period From", required=True)
    billing_period_to = fields.Date(string="Billing Period To", required=True)
    document = fields.Binary(string="Document", attachment=True )
    document_name = fields.Char(string="File Name")
    notes = fields.Html(string="Notes")

    account_expense_ids = fields.One2many('account.account','building_id', string="Expense", readonly=True, tracking=True)
    account_ids = fields.One2many('account.account','building_id', string="Accounts", tracking=True)
    
    total_expense = fields.Float(string="Total Expense", compute="_compute_total_expense")
    total_income = fields.Float(string="Total Income", compute="_compute_total_income")
    total_vacant_cost = fields.Float(string="Total Vacant Costs", compute="_compute_total")
    total_administrative_expenses = fields.Float(string="Total Administrative Expenses", compute="_compute_total")
    rent_contract_ids = fields.One2many("insafety.property.rent.contract", string="Contracts", compute="_compute_contracts")
    cost_billing_receivable_id = fields.Many2one('account.account', string="Cost Account Receivable", 
                                                 domain=[('deprecated', '=', False)], check_company=True, required=True, tracking=True)
    garbage_collection_income_account_id = fields.Many2one('account.account', string="Garbage Service Fees Account",
                                                           domain=[('deprecated', '=', False), ('account_type', '=', 'income')], check_company=True, tracking=True)
    cost_billing_tax_ids = fields.Many2many('account.tax', string='Taxes Cost Billing', domain=[('active', '=', True)],relation="insafety_cost_billing_tax_ids")
    cost_billing_payment_term_id = fields.Many2one('account.payment.term', string="Cost Billing Payment Term", required=True, tracking=True)
    cost_billing_qr_code_method = fields.Selection(
        string="Payment QR-code", copy=False,
        selection=lambda self: self.env['res.partner.bank'].get_available_qr_methods_in_sequence(),
        help="Type of QR-code to be generated for the payment of this invoice, "
             "when printing it. If left blank, the first available and usable method "
             "will be used.",
    )

    cost_billing_administrative_fees_id = fields.Many2one('account.account', string="Administrative Fees", tracking=True,
                                                 domain=[('deprecated', '=', False)], check_company=True, required=True)
    cost_billing_administrative_tax_ids = fields.Many2many('account.tax', string='Administrative Fees Taxes', check_company=True, tracking=True,
                                                           domain=[('active', '=', True)], relation="insafety_cost_billing_administrative_tax_ids")

    cost_billing_direct_post = fields.Boolean(string="Direct Post", default=True)

    analytic_account_ids = fields.Many2many('account.analytic.account', string='Analytic Accounts', tracking=True)
    
  
    @api.depends('property_ids.rent_contract_ids','distribute_by')
    def _compute_contracts(self):
        for rec in self:    
         rec.rent_contract_ids = rec.property_ids.rent_contract_ids

    def _compute_total(self):
        for rec in self:
            next_cost_billing = 0
            for con in rec.rent_contract_ids:
                next_cost_billing += con.next_cost_billing
            rec.total_vacant_cost = rec.total_expense - next_cost_billing
            rec.total_administrative_expenses = next_cost_billing * rec.administrative_expenses / 100
    
    def _compute_total_expense(self):
        for rec in self:
            domain = [
                ('account_id', 'in', rec.account_expense_ids.ids),
                ('date', '>=', rec.billing_period_from),
                ('date', '<=', rec.billing_period_to),
                ('move_id.state', '=', 'posted'),
                ('company_id', '=', rec.company_id.id)
            ]
            result = self.env['account.move.line'].read_group(domain, ['balance'], [])
            rec.total_expense = result[0]['balance'] if result else 0.0

    def _compute_total_income(self):
        for rec in self:
            total = 0
            # for acc in rec.account_income_ids:
            #     total += acc.current_balance
            for contract in rec.rent_contract_ids:
                total += contract.monthly_rent
            rec.total_income = total

    def _compute_total_area(self):
        for rec in self:
            property_count = 0
            total_area = 0
            total_volume = 0
            total_rooms = 0
            total_cost_factor_custom = 0
            for property in rec.property_ids: 
                total_area += property.total_area
                total_volume += property.volume
                total_rooms += property.total_rooms
                property_count += 1
                total_cost_factor_custom += property.cost_factor_custom
            rec.total_area = total_area
            rec.property_count = property_count
            rec.total_volume = total_volume
            rec.total_rooms = total_rooms
            rec.total_cost_factor_custom = total_cost_factor_custom

    # def create_invoice(self):
    #     self = self.with_company(self.company_id)
    #     building = self
    #     contracts = self.rent_contract_ids
    #     partner = self.env['res.partner'].search([('name', '=', building.name)], limit=1)

    #     analyticAccounts = {}
    #     for a in building.analytic_account_ids:
    #         analyticAccounts[str(a.id)] = 100
        


    #     for contract in contracts:
    #         if True: # contract.cost_billing_total != 0:
    #             move_type = 'out_invoice'
    #             cost_billing_total = contract.cost_billing_total
    #             if contract.cost_billing_total < 0:
    #                 move_type = 'in_invoice'
    #                 cost_billing_total =  0 - contract.cost_billing_total
    #             locale.setlocale(locale.LC_ALL, contract.tenant_id.lang + '.UTF-8')
    #             total_expense = building.total_expense
    #             distribution_base = contract.distribution_base if contract.distribution_base != 0 else 1.0
    #             fraction_expense = total_expense / 365 * contract.rent_days / distribution_base * contract.distribution_key
    #             fraction_text = f"{_('Distribution')}: {building.distribute_by} {distribution_base}/{contract.distribution_key} "
    #             if contract.rent_days != 365:
    #                     fraction_text += f"365/{contract.rent_days}"
    #             administrative_expenses = fraction_expense * building.administrative_expenses / 100
    #             invoice = self.env['account.move'].create([
    #                         {
    #                             'move_type': move_type, 
    #                             'partner_id': partner.id if partner else contract.tenant_id.id,
    #                             'invoice_date': time.strftime('%Y-%m-01'),
    #                             'invoice_payment_term_id': building.cost_billing_payment_term_id.id,
    #                             'qr_code_method': building.cost_billing_qr_code_method,
    #                             'invoice_line_ids': [
    #                                 (0, 0, {'price_unit': cost_billing_total - administrative_expenses, 
    #                                                         'account_id': building.cost_billing_receivable_id.id, 
    #                                                         'tax_ids': building.cost_billing_tax_ids,
    #                                                         'name': _('Balance'),
    #                                                         'analytic_distribution': analyticAccounts}),
    #                                                   (0, 0, {'price_unit': administrative_expenses, 
    #                                                         'account_id': building.cost_billing_administrative_fees_id.id, 
    #                                                         'tax_ids': building.cost_billing_administrative_tax_ids,
    #                                                         'name': _('Administrative Fees'),
    #                                                         'analytic_distribution': analyticAccounts})           
    #                                                 ],
    #                         },
    #                     ])      
    #             text = f'''
    #                 <p style="page-break-before:always;"> </p>
    #                 <h5>{_('Aditional Cost Billing')}, {building.billing_period_from.strftime("%x")} - {building.billing_period_to.strftime("%x")}</h5>
    #                 <h5>{building.name}, {building.description}, {contract.property_id.name}, {contract.property_id.description} </h5>     
    #                 <table>
    #                 <tbody>
    #             '''
    #             cur = self.env.company.currency_id.display_name

    #             total_expense = building.total_expense
    #             # distribution_base = contract.distribution_base if contract.distribution_base != 0 else 1.0
    #             fraction_expense = total_expense / 365 * contract.rent_days / distribution_base * contract.distribution_key
    #             fraction_text = f"{_('share calc')}: {building.distribute_by} {distribution_base}/{contract.distribution_key} "
    #             if contract.rent_days != 365:
    #                     fraction_text += f"365/{contract.rent_days}"
    #             administrative_expenses = fraction_expense  * building.administrative_expenses / 100

    #             if building.cost_billing_direct_post:
    #                 invoice.action_post()

    #             for expense in building.account_expense_ids:
    #                 text += f'''
    #                         <tr>
    #                             <td> {expense.name}&nbsp;</td>
    #                             <td>{expense.currency_id.display_name}&nbsp;</td>
    #                             <td style="text-align:right">{format(expense.current_balance, ".2f")}</td>
    #                         </tr>
    #                 '''        
    #             text += f'''
    #             </tbody>
    #             <tfoot>
    #                 <tr>
    #                     <td>Total</td>
    #                     <td>{cur}</td>
    #                     <td style="text-align:right">{format(total_expense, ".2f")}</td>
    #                 </tr>
    #                 <tr>
    #                     <td>{_('Your share')}*</td>
    #                     <td>{cur}</td>
    #                     <td style="text-align:right">{format(fraction_expense, ".2f")}</td>
    #                 </tr>
    #                 <tr>
    #                 <tr>
    #                     <td>{_('paid')}</td>
    #                     <td>{cur}</td>
    #                     <td style="text-align:right"> - {format(contract.monthly_extra_costs_paid_calc, ".2f")}</td>
    #                 </tr>
    #                 <tr>
    #                     <td>{_('Balance')}</td>
    #                     <td>{cur}</td>
    #                     <td style="text-align:right">{format(fraction_expense - contract.monthly_extra_costs_paid_calc, ".2f")}</td>
    #                 </tr>              
    #             </tfoot>
    #             </table>
    #             <p><br></p>
    #             <table>
    #             <tr>
    #                 <td>+ {_('Administrative Fees')}&nbsp;</td>
    #                 <td>{cur}&nbsp;</td>
    #                 <td style="text-align:right">{format(administrative_expenses, ".2f")}</td>
    #             </tr>
    #             </table>
    #             <div>*{fraction_text}</div>
    #             '''
    #             invoice.narration = text
    
    def calculate(self):
        pass

    def create_demo_invoice(self):
        ref = self.env.ref
        for building in self:
            acc1 = self.env['account.account'].search([('code', '=', "650004")])
            acc2 = self.env['account.account'].search([('code', '=', "650005")])
            acc3 = self.env['account.account'].search([('code', '=', "650006")])
            
            invoice1 = self.env['account.move'].create([
            {
                'move_type': 'in_invoice',
                'partner_id': ref('base.res_partner_12').id,
                'invoice_user_id': ref('base.user_demo').id,
                'invoice_payment_term_id': ref('account.account_payment_term_end_following_month').id,
                'invoice_date': time.strftime('%Y-%m-01'),
                'invoice_line_ids': [
                    (0, 0, {'price_unit': 4000, 
                                            'account_id': acc1.id, 
                                            'tax_ids': building.cost_billing_tax_ids,
                                            'name': _('Salary Care Taker')}),
                    
                                    ],
            },
            ])
            invoice1.action_post()
            invoice2 = self.env['account.move'].create([
            {
                'move_type': 'in_invoice',
                'partner_id': ref('base.res_partner_12').id,
                'invoice_user_id': ref('base.user_demo').id,
                'invoice_payment_term_id': ref('account.account_payment_term_end_following_month').id,
                'invoice_date': time.strftime('%Y-%m-01'),
                'invoice_line_ids': [
                    (0, 0, {'price_unit': 2500, 
                                            'account_id': acc2.id, 
                                            'tax_ids': building.cost_billing_tax_ids,
                                            'name': _('Yearly Engergy')}),
                    
                                    ],
            },
            ])
            invoice2.action_post() 
            invoice3 = self.env['account.move'].create([
            {
                'move_type': 'in_invoice',
                'partner_id': ref('base.res_partner_12').id,
                'invoice_user_id': ref('base.user_demo').id,
                'invoice_payment_term_id': ref('account.account_payment_term_end_following_month').id,
                'invoice_date': time.strftime('%Y-%m-01'),
                'invoice_line_ids': [
                    (0, 0, {'price_unit': 1500, 
                                            'account_id': acc3.id, 
                                            'tax_ids': building.cost_billing_tax_ids,
                                            'name': _('Yearly Water')}),
                    
                                    ],
            },
            ])
            print(invoice3) 
            invoice3.action_post()  

    def open_cron(self):
        rent_cron = self.env["ir.cron"].with_context(active_test=False).search(
            [("model_name", "=", "insafety.property.rent.contract")], limit=1)

        if rent_cron:
            return {
                'name': "Rent Cron Job",
                "view_type": "form",
                "res_model": "ir.cron",
                "res_id": rent_cron.id, 
                'view_id': False,
                'view_mode': "form",
                'type': "ir.actions.act_window"
            }

    def generate_monthly_statement(self, date_from=None, date_to=None):
        import io
        import xlsxwriter

        for rec in self:
            if not date_from or not date_to:
                # Use the billing period dates defined on the record
                start_date = rec.billing_period_from
                end_date = rec.billing_period_to
            else:
                start_date = fields.Date.to_date(date_from)
                end_date = fields.Date.to_date(date_to)

            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet("Monthly Statement")

            title_format = workbook.add_format({
                'bold': True,
                'font_size': 14,
                'font_name': 'Arial',
            })
            meta_format = workbook.add_format({
                'font_size': 10,
                'font_name': 'Arial',
            })
            header_format = workbook.add_format({
                'bold': True,
                'font_name': 'Arial',
                'bg_color': '#EAEAEA',
                'border': 1,
                'align': 'left',
            })
            cell_format = workbook.add_format({
                'font_name': 'Arial',
                'border': 1,
                'align': 'left',
            })
            
            currency_symbol = rec.company_id.currency_id.symbol or rec.company_id.currency_id.name or ""
            currency_format_str = f'#,##0.00 "{currency_symbol}"' if currency_symbol else '#,##0.00'
            
            num_cell_format = workbook.add_format({
                'font_name': 'Arial',
                'border': 1,
                'align': 'right',
                'num_format': currency_format_str
            })

            # Write Title Block
            worksheet.write(0, 0, f"MONTHLY STATEMENT: {rec.name}", title_format)
            worksheet.write(1, 0, f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", meta_format)
            worksheet.write(2, 0, f"Generated on: {fields.Date.today().strftime('%Y-%m-%d')}", meta_format)

            # Invoice journals - tenant invoices may be in either TIJ or INV
            invoice_journals = self.env['account.journal'].search([
                ('type', '=', 'sale'),
                ('company_id', '=', rec.company_id.id),
                ('code', 'in', ['TIJ', 'INV']),
            ])

            # Payment journals - tenant payments may come from any of these banks
            payment_journals = self.env['account.journal'].search([
                ('type', '=', 'bank'),
                ('company_id', '=', rec.company_id.id),
                ('code', 'in', ['PBNK1','LLDP','PBNK2']),
            ])

            # Outstanding receipts account used to identify actual payment lines
            outstanding_receipts_account = self.env['account.account'].search([
                ('code', '=', '120003'),
                ('company_ids', 'in', [rec.company_id.id]),
            ], limit=1)

            # Opening balance journal - carries forward initial tenant balances
            opb_journal = self.env['account.journal'].search([
                ('company_id', '=', rec.company_id.id),
                ('code', '=', 'OPB'),
            ], limit=1)

            import logging
            _logger = logging.getLogger(__name__)
            _logger.info("OPB journal found: %s (id=%s)", opb_journal.name if opb_journal else 'NOT FOUND', opb_journal.id if opb_journal else 0)

            invoice_columns = ['House Deposit', 'Water Deposit', 'Elec Deposit', 'Water', 'Garbage']
            # Map unique keywords found in account.move.line names to statement columns
            keyword_mapping = [
                ('HSE_DPO', 'House Deposit'),
                ('WTR_DPO', 'Water Deposit'),
                ('ELEC_DPO', 'Elec Deposit'),
                ('WATER_SRV_TENANT', 'Water'),
                ('GRB_SRV', 'Garbage'),
            ]

            property_contract_data = []

            for property in rec.property_ids:
                active_contracts = []
                for contract in property.rent_contract_ids:
                    c_start = contract.rent_date_from
                    c_end = contract.rent_date_to
                    if c_start <= end_date and (not c_end or c_end >= start_date):
                        active_contracts.append(contract)

                if active_contracts:
                    for contract in active_contracts:
                        contract_amounts = {col: 0.0 for col in invoice_columns}
                        payment_total = 0.0
                        opening_balance = 0.0
                        if invoice_journals:
                            # Query invoice journal items directly
                            lines = self.env['account.move.line'].search([
                                ('journal_id', 'in', invoice_journals.ids),
                                ('partner_id', '=', contract.tenant_id.id),
                                ('date', '>=', start_date),
                                ('date', '<=', end_date),
                                ('move_id.state', '=', 'posted'),
                                ('move_id.move_type', '=', 'out_invoice'),
                                ('company_id', '=', rec.company_id.id),
                            ])

                            for line in lines:
                                if not line.name or line.display_type in ('line_section', 'line_note', 'tax', 'payment_term'):
                                    continue
                                line_name = line.name.strip()
                                for keyword, col in keyword_mapping:
                                    if keyword in line_name:
                                        contract_amounts[col] += line.credit
                                        break

                            # Opening balance calculation (skip for zero-rent contracts)
                            if contract.monthly_rent != 0:
                                prior_invoiced = self.env['account.move.line'].search([
                                    ('journal_id', 'in', invoice_journals.ids),
                                    ('partner_id', '=', contract.tenant_id.id),
                                    ('date', '<', start_date),
                                    ('move_id.state', '=', 'posted'),
                                    ('company_id', '=', rec.company_id.id),
                                ])
                                # Sum all product-line credits (including rent) for opening balance
                                opening_balance_keywords = ['Monthly Rent', 'HSE_DPO', 'WTR_DPO', 'ELEC_DPO', 'WATER_SRV_TENANT', 'GRB_SRV']
                                total_invoiced = 0.0
                                for pl in prior_invoiced:
                                    if not pl.date or pl.date >= start_date:
                                        continue
                                    if not pl.name or pl.display_type in ('line_section', 'line_note', 'tax', 'payment_term'):
                                        continue
                                    line_name = pl.name.strip()
                                    if any(kw in line_name for kw in opening_balance_keywords):
                                        total_invoiced += pl.credit

                                prior_payments = 0.0
                                if payment_journals and outstanding_receipts_account:
                                    prior_pay_lines = self.env['account.move.line'].search([
                                        ('journal_id', 'in', payment_journals.ids),
                                        ('partner_id', '=', contract.tenant_id.id),
                                        ('account_id', '=', outstanding_receipts_account.id),
                                        ('date', '<', start_date),
                                        ('move_id.state', '=', 'posted'),
                                        ('debit', '>', 0),
                                        ('company_id', '=', rec.company_id.id),
                                    ])
                                    filtered_prior_pay = prior_pay_lines.filtered(
                                        lambda l: l.date and l.date < start_date
                                    )
                                    prior_payments = sum(filtered_prior_pay.mapped('debit'))

                                opening_balance = total_invoiced - prior_payments

                                # Add OPB journal net balance (debit = owes, credit = has credit)
                                # OPB entries are opening balances - no date filter needed
                                opb_net = 0.0
                                if opb_journal:
                                    opb_lines = self.env['account.move.line'].search([
                                        ('journal_id', '=', opb_journal.id),
                                        ('partner_id', '=', contract.tenant_id.id),
                                        ('move_id.state', '=', 'posted'),
                                        ('company_id', '=', rec.company_id.id),
                                    ])
                                    opb_net = sum(opb_lines.mapped('debit')) - sum(opb_lines.mapped('credit'))
                                    opening_balance += opb_net
                                    if opb_lines:
                                        _logger.info("OPB lines tenant=%s: %d lines, debit=%.2f, credit=%.2f, net=%.2f",
                                                     contract.tenant_id.name, len(opb_lines),
                                                     sum(opb_lines.mapped('debit')),
                                                     sum(opb_lines.mapped('credit')), opb_net)

                                # Count distinct invoices for this tenant before the period
                                invoice_count = len(prior_invoiced.mapped('move_id'))

                                import logging
                                _logger = logging.getLogger(__name__)
                                _logger.debug(
                                    "Opening Bal tenant=%s: invoices=%d, invoiced=%.2f, paid=%.2f, opb_net=%.2f, balance=%.2f, period_start=%s",
                                    contract.tenant_id.name, invoice_count, total_invoiced, prior_payments,
                                    opb_net, opening_balance, start_date
                                )

                        # Query payment journal items - sum debit across all 3 bank journals
                        if payment_journals and outstanding_receipts_account:
                            payment_lines = self.env['account.move.line'].search([
                                ('journal_id', 'in', payment_journals.ids),
                                ('partner_id', '=', contract.tenant_id.id),
                                ('account_id', '=', outstanding_receipts_account.id),
                                ('date', '>=', start_date),
                                ('date', '<=', end_date),
                                ('move_id.state', '=', 'posted'),
                                ('debit', '>', 0),
                                ('company_id', '=', rec.company_id.id),
                            ])
                            # Filter to only lines within the period (extra safety)
                            filtered_lines = payment_lines.filtered(
                                lambda l: l.date and start_date <= l.date <= end_date
                            )
                            for pline in filtered_lines:
                                payment_total += pline.debit

                        # Zero out opening balance and payment for contracts with no rent
                        if contract.monthly_rent == 0:
                            opening_balance = 0.0
                            payment_total = 0.0

                        contract_amounts['Opening Bal'] = opening_balance
                        contract_amounts['Payment'] = payment_total

                        property_contract_data.append({
                            'property': property,
                            'contract': contract,
                            'status': 'Occupied',
                            'line_amounts': contract_amounts
                        })
                else:
                    vacant_amounts = {col: 0.0 for col in invoice_columns}
                    vacant_amounts['Opening Bal'] = 0.0
                    vacant_amounts['Payment'] = 0.0
                    property_contract_data.append({
                        'property': property,
                        'contract': None,
                        'status': 'Vacant',
                        'line_amounts': vacant_amounts
                    })

            # Headers
            all_columns = invoice_columns + ['Opening Bal', 'Total Due', 'Payment', 'Balance']
            headers = ["Unit", "Description", "Status", "Tenant", "Rent Amount"] + all_columns
            for col_num, header in enumerate(headers):
                worksheet.write(4, col_num, header, header_format)

            # Set column widths
            worksheet.set_column(0, 0, 15)  # Unit
            worksheet.set_column(1, 1, 30)  # Description
            worksheet.set_column(2, 2, 12)  # Status
            worksheet.set_column(3, 3, 25)  # Tenant
            worksheet.set_column(4, 4, 15)  # Rent Amount
            for i in range(len(all_columns)):
                worksheet.set_column(5 + i, 5 + i, 15)

            # Bold format for totals row
            totals_format = workbook.add_format({
                'bold': True,
                'border': 1,
                'bg_color': '#D9E1F2',
                'num_format': currency_format_str,
                'align': 'right',
            })
            totals_text_format = workbook.add_format({
                'bold': True,
                'border': 1,
                'bg_color': '#D9E1F2',
                'align': 'left',
            })

            # Running totals for numerical columns (Rent Amount + all_columns)
            col_totals = {4: 0.0}  # column index 4 = Rent Amount
            for i in range(len(all_columns)):
                col_totals[5 + i] = 0.0

            row_num = 5
            for data in property_contract_data:
                property = data['property']
                desc = property.description or ""
                worksheet.write(row_num, 0, property.name, cell_format)
                worksheet.write(row_num, 1, desc, cell_format)
                worksheet.write(row_num, 2, data['status'], cell_format)
                
                if data['contract']:
                    contract = data['contract']
                    tenant_name = contract.tenant_id.name or "Unknown Tenant"
                    rent_amount = contract.monthly_rent
                    worksheet.write(row_num, 3, tenant_name, cell_format)
                    worksheet.write_number(row_num, 4, rent_amount, num_cell_format)
                else:
                    contract = None
                    rent_amount = 0
                    worksheet.write(row_num, 3, "", cell_format)
                    worksheet.write_number(row_num, 4, 0, num_cell_format)
                col_totals[4] += rent_amount
                
                # Track Total Due for Balance calculation
                row_total_due = rent_amount
                for sum_col in invoice_columns + ['Opening Bal']:
                    row_total_due += data['line_amounts'].get(sum_col, 0.0)
                
                for i, col in enumerate(all_columns):
                    if col == 'Total Due':
                        amt = row_total_due
                    elif col == 'Balance':
                        amt = row_total_due - data['line_amounts'].get('Payment', 0.0)
                    else:
                        amt = data['line_amounts'].get(col, 0.0)
                    worksheet.write_number(row_num, 5 + i, amt, num_cell_format)
                    # Do not sum Opening Bal; exclude negatives for Total Due and Balance
                    if col == 'Opening Bal':
                        continue
                    if col in ('Total Due', 'Balance') and amt < 0:
                        continue
                    col_totals[5 + i] += amt
                        
                row_num += 1

            # Write totals row
            worksheet.write(row_num, 0, "", totals_text_format)
            worksheet.write(row_num, 1, "", totals_text_format)
            worksheet.write(row_num, 2, "", totals_text_format)
            worksheet.write(row_num, 3, "TOTAL", totals_text_format)
            for col_idx, total_val in col_totals.items():
                worksheet.write_number(row_num, col_idx, total_val, totals_format)

            # --- Income and Expenses Summary Section ---
            summary_header_fmt = workbook.add_format({
                'bold': True, 'font_size': 12, 'border': 1,
                'bg_color': '#4472C4', 'font_color': '#FFFFFF', 'align': 'center',
            })
            summary_label_fmt = workbook.add_format({
                'border': 1, 'align': 'left', 'font_size': 11,
            })
            summary_num_fmt = workbook.add_format({
                'border': 1, 'align': 'right', 'num_format': currency_format_str, 'font_size': 11,
            })
            summary_bold_fmt = workbook.add_format({
                'bold': True, 'border': 1, 'align': 'left', 'font_size': 11,
                'bg_color': '#D9E1F2',
            })
            summary_bold_num_fmt = workbook.add_format({
                'bold': True, 'border': 1, 'align': 'right', 'num_format': currency_format_str,
                'font_size': 11, 'bg_color': '#D9E1F2',
            })
            summary_cat_fmt = workbook.add_format({
                'bold': True, 'border': 1, 'align': 'left', 'font_size': 11,
                'bg_color': '#E2EFDA', 'underline': True,
            })
            summary_cat_num_fmt = workbook.add_format({
                'bold': True, 'border': 1, 'align': 'right', 'num_format': currency_format_str,
                'font_size': 11, 'bg_color': '#E2EFDA',
            })

            # Calculate Vendor Opening Balance (Previous Month Balance)
            vendor_partner = self.env['res.partner'].search([
                ('name', '=', rec.name),
            ], limit=1)

            vendor_opening_balance = 0.0
            if vendor_partner:
                # 1. OPB net balance
                vendor_opb_net = 0.0
                if opb_journal:
                    opb_lines_vendor = self.env['account.move.line'].search([
                        ('journal_id', '=', opb_journal.id),
                        ('partner_id', '=', vendor_partner.id),
                        ('move_id.state', '=', 'posted'),
                        ('company_id', '=', rec.company_id.id),
                    ])
                    vendor_opb_net = sum(opb_lines_vendor.mapped('credit')) - sum(opb_lines_vendor.mapped('debit'))

                # 2. Prior bills (BILL journal)
                vendor_journal = self.env['account.journal'].search([
                    ('type', '=', 'purchase'),
                    ('company_id', '=', rec.company_id.id),
                    ('code', '=', 'BILL'),
                ], limit=1)

                prior_bills_vendor = 0.0
                if vendor_journal:
                    prior_bills_lines = self.env['account.move.line'].search([
                        ('journal_id', '=', vendor_journal.id),
                        ('partner_id', '=', vendor_partner.id),
                        ('date', '<', start_date),
                        ('move_id.state', '=', 'posted'),
                        ('account_id.account_type', '=', 'liability_payable'),
                        ('company_id', '=', rec.company_id.id),
                    ])
                    prior_bills_vendor = sum(prior_bills_lines.mapped('credit')) - sum(prior_bills_lines.mapped('debit'))

                # 3. Prior payments (Bank journals)
                prior_payments_vendor = 0.0
                if payment_journals:
                    prior_payment_lines = self.env['account.move.line'].search([
                        ('journal_id', 'in', payment_journals.ids),
                        ('partner_id', '=', vendor_partner.id),
                        ('date', '<', start_date),
                        ('move_id.state', '=', 'posted'),
                        ('company_id', '=', rec.company_id.id),
                    ])
                    prior_payments_vendor = sum(prior_payment_lines.mapped('debit')) - sum(prior_payment_lines.mapped('credit'))

                vendor_opening_balance = vendor_opb_net + prior_bills_vendor - prior_payments_vendor

            row_num += 2
            # Section header
            worksheet.merge_range(row_num, 0, row_num, 1, "INCOME", summary_header_fmt)
            worksheet.merge_range(row_num, 3, row_num, 4, "DEDUCTIONS", summary_header_fmt)
            row_num += 1

            # INCOME rows
            income_rows = [
                ('Previous Month Balance', vendor_opening_balance),
                ('Rent', col_totals.get(4, 0.0)),
                ('House Deposit', col_totals.get(5, 0.0)),
                ('Water Deposit', col_totals.get(6, 0.0)),
                ('Electricity Deposit', col_totals.get(7, 0.0)),
                ('Water', col_totals.get(8, 0.0)),
            ]
            total_income = 0.0
            for label, amount in income_rows:
                worksheet.write(row_num, 0, label, summary_label_fmt)
                worksheet.write_number(row_num, 1, amount, summary_num_fmt)
                total_income += amount
                row_num += 1
            # Income total
            worksheet.write(row_num, 0, "Total Income", summary_bold_fmt)
            worksheet.write_number(row_num, 1, total_income, summary_bold_num_fmt)
            income_end_row = row_num

            # DEDUCTIONS rows - start aligned with first income row
            deduct_row = income_end_row - len(income_rows)

            # 1. Agency Commission (admin fee % of total rent)
            admin_fee_rate = 0.0
            for tax in rec.cost_billing_administrative_tax_ids:
                if 'admin' in (tax.name or '').lower():
                    admin_fee_rate = tax.amount
                    break
            total_rent = col_totals.get(4, 0.0)
            commission_amount = total_rent * admin_fee_rate / 100.0

            worksheet.write(deduct_row, 3,
                            f"Agency Commission ({admin_fee_rate:.1f}%)", summary_label_fmt)
            worksheet.write_number(deduct_row, 4, commission_amount, summary_num_fmt)
            deduct_row += 1

            # 1b. Payments to Vendor (Landlord) during the current period
            total_vendor_payments = 0.0
            if payment_journals and vendor_partner:
                pay_lines_current = self.env['account.move.line'].search([
                    ('journal_id', 'in', payment_journals.ids),
                    ('partner_id', '=', vendor_partner.id),
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('move_id.state', '=', 'posted'),
                    ('company_id', '=', rec.company_id.id),
                ])
                for line in pay_lines_current:
                    amt = line.debit - line.credit
                    if amt > 0.0:
                        ref = line.move_id.ref or line.move_id.payment_reference or line.name or ""
                        ref_str = f" - Ref: {ref}" if ref else ""
                        date_str = line.date.strftime('%Y-%m-%d') if line.date else ""
                        title = f"Payment to LL ({date_str}{ref_str})"
                        worksheet.write(deduct_row, 3, title, summary_label_fmt)
                        worksheet.write_number(deduct_row, 4, amt, summary_num_fmt)
                        total_vendor_payments += amt
                        deduct_row += 1

            # 2. Expenses grouped by product category and internal reference/tag
            total_expenses = 0.0
            if rec.account_expense_ids:
                expense_lines = self.env['account.move.line'].search([
                    ('account_id', 'in', rec.account_expense_ids.ids),
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('move_id.state', '=', 'posted'),
                    ('company_id', '=', rec.company_id.id),
                    ('product_id', '!=', False),
                ])

                # Group: {category_name: {(ref_key, name): amount}}
                expense_groups = {}
                for line in expense_lines:
                    product = line.product_id
                    categ_name = product.categ_id.name if product.categ_id else 'Other'

                    if categ_name == 'Materials':
                        # Group by Tag for Materials category
                        tag_name = ', '.join(product.product_tag_ids.mapped('name')) if product.product_tag_ids else 'Untagged'
                        ref_key = tag_name
                        display_name = tag_name
                    else:
                        # Group by internal reference for other categories
                        ref_key = product.default_code or product.name or 'Unknown'
                        display_name = product.name or 'Unknown'
                    expense_groups.setdefault(categ_name, {})
                    group_key = (ref_key, display_name)
                    expense_groups[categ_name][group_key] = (
                        expense_groups[categ_name].get(group_key, 0.0) + line.balance
                    )

                # Write expenses by category
                for categ_name in sorted(expense_groups.keys()):
                    # Category header
                    worksheet.write(deduct_row, 3, categ_name, summary_cat_fmt)
                    worksheet.write(deduct_row, 4, '', summary_cat_fmt)
                    deduct_row += 1

                    categ_total = 0.0
                    for (ref_key, display_name), amount in expense_groups[categ_name].items():
                        if ref_key == display_name:
                            label = f"  {display_name}"
                        else:
                            label = f"  {display_name} ({ref_key})"
                        worksheet.write(deduct_row, 3, label, summary_label_fmt)
                        worksheet.write_number(deduct_row, 4, amount, summary_num_fmt)
                        categ_total += amount
                        deduct_row += 1

                    # Category subtotal
                    worksheet.write(deduct_row, 3, f"  Subtotal {categ_name}", summary_bold_fmt)
                    worksheet.write_number(deduct_row, 4, categ_total, summary_bold_num_fmt)
                    total_expenses += categ_total
                    deduct_row += 1

            # Deductions total
            total_deductions = commission_amount + total_vendor_payments + total_expenses
            worksheet.write(deduct_row, 3, "Total Deductions", summary_bold_fmt)
            worksheet.write_number(deduct_row, 4, total_deductions, summary_bold_num_fmt)

            # Payable to Landlord - after both totals
            net_row = max(income_end_row, deduct_row) + 1
            net_amount = total_income - total_deductions
            worksheet.merge_range(net_row, 0, net_row, 3, "Payable to Landlord", summary_bold_fmt)
            worksheet.write_number(net_row, 4, net_amount, summary_bold_num_fmt)

            workbook.close()
            output.seek(0)
            
            rec.document = base64.b64encode(output.read())
            rec.document_name = f"Monthly_Statement_{rec.name}_{start_date.strftime('%Y-%m')}.xlsx"

            # Post to chatter to keep historical records
            attachment = self.env['ir.attachment'].create({
                'name': rec.document_name,
                'type': 'binary',
                'datas': rec.document,
                'res_model': 'insafety.property.building',
                'res_id': rec.id,
            })
            rec.message_post(
                body=f"Monthly Statement generated for period {start_date} to {end_date}.",
                attachment_ids=[attachment.id]
            )

    @api.model
    def _cron_generate_monthly_statements(self):
        today = fields.Date.today()
        # First day of this month
        first_of_this_month = today.replace(day=1)
        # Last day of previous month
        end_date = first_of_this_month - timedelta(days=1)
        # First day of previous month
        start_date = end_date.replace(day=1)
        
        buildings = self.search([])
        buildings.generate_monthly_statement(date_from=start_date, date_to=end_date)


