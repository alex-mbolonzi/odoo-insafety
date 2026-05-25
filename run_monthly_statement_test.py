import sys
import logging
logging.basicConfig(level=logging.ERROR)

env = self.env
building_model = env['insafety.property.building']

print("Searching for buildings...")
buildings = building_model.search([])
if not buildings:
    print("No buildings found to test.")
    sys.exit(0)

print(f"Found {len(buildings)} buildings. Testing generate_monthly_statement...")
try:
    for building in buildings:
        print(f"Generating statement for building: {building.name}")
        building.generate_monthly_statement()
        print(f"Successfully generated: {building.document_name}")
        if building.document:
            import base64
            content = base64.b64decode(building.document).decode('utf-8')
            print("--- STATEMENT CONTENT PREVIEW ---")
            print("\n".join(content.split("\n")[:15]))
            print("---------------------------------")
        else:
            print("WARNING: document field is empty!")
            
    print("Testing cron _cron_generate_monthly_statements...")
    building_model._cron_generate_monthly_statements()
    print("Cron execution successful.")
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)

sys.exit(0)
