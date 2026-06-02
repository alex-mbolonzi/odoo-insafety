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
            import zipfile
            import io
            content_bytes = base64.b64decode(building.document)
            print(f"Successfully generated Excel file: {building.document_name} ({len(content_bytes)} bytes)")
            try:
                with zipfile.ZipFile(io.BytesIO(content_bytes)) as zf:
                    print("--- EXCEL FILE STRUCTURE VERIFIED ---")
                    print("File list in zip archive:")
                    for f in zf.namelist()[:10]:
                        print(f"  {f}")
                    print("-------------------------------------")
            except zipfile.BadZipFile:
                print("WARNING: The generated document is not a valid Excel (.xlsx) file!")
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
