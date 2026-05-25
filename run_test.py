import sys
import logging
logging.basicConfig(level=logging.ERROR)

env = self.env
rent_model = env['insafety.property.rent.contract']
print("Searching for contract...")
contract = rent_model.search([], limit=1)
if not contract:
    print("No contract found")
    sys.exit(0)

print(f"Testing with contract: {contract.id} company {contract.company_id.id}")
journal = env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', contract.company_id.id), ('code', '=', 'TIJ')], limit=1)
print(f"TIJ Journal found: {journal}")

try:
    contract._create_invoices()
    print("Cron execution completely successful without error.")
except Exception as e:
    import traceback
    traceback.print_exc()

sys.exit(0)
