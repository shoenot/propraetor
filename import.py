import os
import django
import csv
from datetime import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from propraetor.models import Employee, Company, Department, Location, Asset, AssetModel, Category


def import_employees(file_path):
    """
    Import employees from CSV file.
    
    Expected CSV columns:
    - name (required)
    - company (required)
    - department (required)
    - location (required)
    - employee_id (optional)
    - email (optional)
    - phone (optional)
    - extension (optional)
    - position (optional)
    - status (optional, defaults to 'active')
    """
    success_count = 0
    error_count = 0
    
    with open(file_path, 'r') as file:
        reader = csv.DictReader(file)
        for idx, row in enumerate(reader, start=1):
            try:
                # Validate required fields
                if not row.get('name') or not row.get('company') or not row.get('department') or not row.get('location'):
                    raise ValueError("Missing required field(s): name, company, department, or location")
                
                # Normalize whitespace and get or create related objects
                company, _ = Company.objects.get_or_create(
                    name=row['company'].strip()
                )
                department, _ = Department.objects.get_or_create(
                    name=row['department'].strip(),
                    company=company
                )
                location, _ = Location.objects.get_or_create(
                    name=row['location'].strip()
                )
                
                # Create employee
                Employee.objects.create(
                    name=row['name'].strip(),
                    employee_id=row.get('employee_id', '').strip(),
                    email=row.get('email', '').strip(),
                    phone=row.get('phone', '').strip(),
                    extension=row.get('extension', '').strip(),
                    position=row.get('position', '').strip(),
                    status=row.get('status', 'active').strip(),
                    company=company,
                    department=department,
                    location=location
                )
                success_count += 1
                print(f"✓ Row {idx}: Imported {row['name'].strip()}")
                
            except Exception as e:
                error_count += 1
                print(f"✗ Row {idx} ({row.get('name', 'unknown')}): {e}")
                continue
    
    print(f"\n{'='*50}")
    print(f"Employee Import Complete")
    print(f"{'='*50}")
    print(f"Succeeded: {success_count}")
    print(f"Failed: {error_count}")
    print(f"Total: {success_count + error_count}")


def import_assets(file_path):
    """
    Import assets from CSV file with auto-creation of categories and asset models.
    
    Expected CSV columns:
    - category (required) - e.g., 'Desktop', 'Laptop', 'Printer'
    - manufacturer (optional) - e.g., 'Dell', 'HP', 'Apple'
    - model_name (required) - e.g., 'OptiPlex 7090', 'MacBook Pro'
    - model_number (optional) - manufacturer's part number
    - asset_tag (optional) - will be auto-generated if blank
    - serial_number (optional)
    - company (required)
    - status (optional) - pending/active/in_repair/retired/disposed/inactive
    - assigned_to (optional) - employee_id or name
    - location (optional) - location name (only if not assigned to employee)
    - purchase_date (optional) - YYYY-MM-DD format
    - purchase_cost (optional)
    - warranty_expiry_date (optional) - YYYY-MM-DD format
    - notes (optional)
    """
    success_count = 0
    error_count = 0
    
    with open(file_path, 'r') as file:
        reader = csv.DictReader(file)
        for idx, row in enumerate(reader, start=1):
            try:
                # Validate required fields
                if not row.get('category') or not row.get('model_name') or not row.get('company'):
                    raise ValueError("Missing required field(s): category, model_name, or company")
                
                # Get or create category
                category, created = Category.objects.get_or_create(
                    name=row['category'].strip()
                )
                if created:
                    print(f"  → Created new category: {category.name}")
                
                # Get or create asset model
                manufacturer = row.get('manufacturer', '').strip()
                model_name = row['model_name'].strip()
                model_number = row.get('model_number', '').strip()
                
                asset_model, created = AssetModel.objects.get_or_create(
                    category=category,
                    manufacturer=manufacturer,
                    model_name=model_name,
                    defaults={
                        'model_number': model_number if model_number else None
                    }
                )
                if created:
                    print(f"  → Created new asset model: {asset_model}")
                
                # Get company
                company, _ = Company.objects.get_or_create(
                    name=row['company'].strip()
                )
                
                # Handle assignment (either to employee or location, not both)
                assigned_to = None
                location = None
                
                if row.get('assigned_to', '').strip():
                    assigned_to_value = row['assigned_to'].strip()
                    # Try to find employee by employee_id first, then by name
                    try:
                        assigned_to = Employee.objects.get(employee_id=assigned_to_value)
                    except Employee.DoesNotExist:
                        try:
                            assigned_to = Employee.objects.get(name=assigned_to_value)
                        except Employee.DoesNotExist:
                            print(f"  ⚠ Warning: Employee '{assigned_to_value}' not found, asset will be unassigned")
                        except Employee.MultipleObjectsReturned:
                            print(f"  ⚠ Warning: Multiple employees named '{assigned_to_value}', using employee_id instead")
                
                elif row.get('location', '').strip():
                    location, _ = Location.objects.get_or_create(
                        name=row['location'].strip()
                    )
                
                # Parse dates
                purchase_date = None
                if row.get('purchase_date', '').strip():
                    try:
                        purchase_date = datetime.strptime(row['purchase_date'].strip(), '%Y-%m-%d').date()
                    except ValueError:
                        print(f"  ⚠ Warning: Invalid purchase_date format, expected YYYY-MM-DD")
                
                warranty_expiry_date = None
                if row.get('warranty_expiry_date', '').strip():
                    try:
                        warranty_expiry_date = datetime.strptime(row['warranty_expiry_date'].strip(), '%Y-%m-%d').date()
                    except ValueError:
                        print(f"  ⚠ Warning: Invalid warranty_expiry_date format, expected YYYY-MM-DD")
                
                # Parse purchase cost
                purchase_cost = None
                if row.get('purchase_cost', '').strip():
                    try:
                        purchase_cost = float(row['purchase_cost'].strip())
                    except ValueError:
                        print(f"  ⚠ Warning: Invalid purchase_cost, must be a number")
                
                # Create asset
                asset = Asset.objects.create(
                    asset_tag=row.get('asset_tag', '').strip(),  # Will auto-generate if blank
                    asset_model=asset_model,
                    company=company,
                    serial_number=row.get('serial_number', '').strip(),
                    status=row.get('status', 'pending').strip(),
                    assigned_to=assigned_to,
                    location=location,
                    purchase_date=purchase_date,
                    purchase_cost=purchase_cost,
                    warranty_expiry_date=warranty_expiry_date,
                    notes=row.get('notes', '').strip()
                )
                
                success_count += 1
                assignee_info = f"→ {assigned_to or location}" if (assigned_to or location) else "(unassigned)"
                print(f"✓ Row {idx}: Imported {asset.asset_tag} {assignee_info}")
                
            except Exception as e:
                error_count += 1
                identifier = row.get('asset_tag') or row.get('serial_number') or 'unknown'
                print(f"✗ Row {idx} ({identifier}): {e}")
                continue
    
    print(f"\n{'='*50}")
    print(f"Asset Import Complete")
    print(f"{'='*50}")
    print(f"Succeeded: {success_count}")
    print(f"Failed: {error_count}")
    print(f"Total: {success_count + error_count}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python import.py <employees|assets> <csv_file_path>")
        print("\nExamples:")
        print("  python import.py employees employees.csv")
        print("  python import.py assets assets.csv")
        sys.exit(1)
    
    import_type = sys.argv[1].lower()
    file_path = sys.argv[2]
    
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found")
        sys.exit(1)
    
    if import_type == "employees":
        print(f"Importing employees from {file_path}...\n")
        import_employees(file_path)
    elif import_type == "assets":
        print(f"Importing assets from {file_path}...\n")
        import_assets(file_path)
    else:
        print(f"Error: Unknown import type '{import_type}'")
        print("Must be either 'employees' or 'assets'")
        sys.exit(1)