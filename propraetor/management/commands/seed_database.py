"""
seed_database — populate Propraetor with realistic test data.

Usage:
    python manage.py seed_database              # full seed (~2 000 records)
    python manage.py seed_database --flush      # wipe everything first
    python manage.py seed_database --small      # smaller dataset (~500 records)
    python manage.py seed_database --no-activity # suppress activity-log generation
"""

import datetime
import decimal
import random
import string
from itertools import count

from django.contrib.auth.models import User as DjangoUser
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from propraetor.activity import suppress_auto_log
from propraetor.models import (
    Asset,
    AssetAssignment,
    AssetModel,
    Category,
    Company,
    Component,
    ComponentHistory,
    ComponentType,
    InvoiceLineItem,
    Location,
    Department,
    Employee,
    MaintenanceRecord,
    PurchaseInvoice,
    Requisition,
    RequisitionItem,
    SparePartsInventory,
    Vendor,
    ActivityLog,
    sync_all_spare_parts,
)


# ============================================================================
# Realistic data pools
# ============================================================================

COMPANY_DATA = [
    {"name": "Nexus Technologies", "code": "NXT", "city": "Dhaka", "country": "Bangladesh", "phone": "+880-2-9876543"},
    {"name": "Orbital Systems", "code": "ORB", "city": "Chittagong", "country": "Bangladesh", "phone": "+880-31-654321"},
    {"name": "Apex Digital Solutions", "code": "APX", "city": "Sylhet", "country": "Bangladesh", "phone": "+880-821-12345"},
    {"name": "Pinnacle Industries", "code": "PIN", "city": "Rajshahi", "country": "Bangladesh", "phone": "+880-721-98765"},
    {"name": "Cobalt Enterprises", "code": "CBT", "city": "Khulna", "country": "Bangladesh", "phone": "+880-41-55555"},
    {"name": "Vanguard Corp", "code": "VNG", "city": "Gazipur", "country": "Bangladesh", "phone": "+880-2-1234567"},
]

LOCATION_DATA = [
    {"name": "HQ — Tower A", "city": "Dhaka", "address": "45 Gulshan Avenue, Gulshan-2", "zipcode": "1212", "country": "Bangladesh"},
    {"name": "HQ — Tower B", "city": "Dhaka", "address": "47 Gulshan Avenue, Gulshan-2", "zipcode": "1212", "country": "Bangladesh"},
    {"name": "Dhaka Data Center", "city": "Dhaka", "address": "Bashundhara R/A, Block D", "zipcode": "1229", "country": "Bangladesh"},
    {"name": "Uttara Branch Office", "city": "Dhaka", "address": "Sector 7, Uttara", "zipcode": "1230", "country": "Bangladesh"},
    {"name": "Chittagong Office", "city": "Chittagong", "address": "Agrabad C/A", "zipcode": "4100", "country": "Bangladesh"},
    {"name": "Chittagong Warehouse", "city": "Chittagong", "address": "Halishahar, Gate 2", "zipcode": "4216", "country": "Bangladesh"},
    {"name": "Sylhet Branch", "city": "Sylhet", "address": "Zindabazar", "zipcode": "3100", "country": "Bangladesh"},
    {"name": "Rajshahi Campus", "city": "Rajshahi", "address": "Shaheb Bazar", "zipcode": "6000", "country": "Bangladesh"},
    {"name": "Khulna Office", "city": "Khulna", "address": "Shibbari More", "zipcode": "9100", "country": "Bangladesh"},
    {"name": "Gazipur Tech Park", "city": "Gazipur", "address": "Joydebpur, Chowrasta", "zipcode": "1700", "country": "Bangladesh"},
    {"name": "Remote Storage — Mirpur", "city": "Dhaka", "address": "Mirpur DOHS", "zipcode": "1216", "country": "Bangladesh"},
    {"name": "Comilla Sub-Office", "city": "Comilla", "address": "Kandirpar", "zipcode": "3500", "country": "Bangladesh"},
    {"name": "Narayanganj Depot", "city": "Narayanganj", "address": "Shitalakshya Road", "zipcode": "1400", "country": "Bangladesh"},
    {"name": "Server Room — Floor 5", "city": "Dhaka", "address": "45 Gulshan Avenue, Gulshan-2, Floor 5", "zipcode": "1212", "country": "Bangladesh"},
]

DEPARTMENT_NAMES = [
    "Engineering", "Finance", "Human Resources", "IT Operations", "Marketing",
    "Sales", "Legal", "Product", "Customer Support", "Quality Assurance",
    "DevOps", "Data Science", "Security", "Procurement", "Administration",
    "Research & Development", "Design", "Facilities", "Training", "Compliance",
]

FIRST_NAMES = [
    "Liam", "Olivia", "Noah", "Emma", "Oliver", "Charlotte", "James", "Amelia", 
    "Elijah", "Sophia", "William", "Ava", "Henry", "Isabella", "Lucas", "Mia", 
    "Benjamin", "Evelyn", "Theodore", "Harper", "Jack", "Luna", "Levi", "Elizabeth", 
    "Alexander", "Sofia", "Jackson", "Emily", "Mateo", "Avery", "Daniel", "Mila", 
    "Michael", "Scarlett", "Gabriel", "Eleanor", "Logan", "Madison", "Sebastian", "Layla", 
    "Ethan", "Penelope", "Ezra", "Aria", "Elias", "Chloe", "Silas", "Grace", 
    "Wyatt", "Ellie", "Kai", "Nora", "Julian", "Hazel", "Hudson", "Zoey", 
    "Nathan", "Paisley", "Samuel", "Audrey", "Lincoln", "Aurora", "Asher", "Savannah", 
    "Cameron", "Brooklyn", "Christopher", "Bella", "Josiah", "Claire", "David", "Skylar", 
    "Jaxon", "Lucy", "Leo"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", 
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", 
    "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", 
    "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young", 
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", 
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", 
    "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker", 
    "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy", 
    "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson", "Bailey", 
    "Reed", "Kelly", "Howard"
]

POSITIONS = [
    "Software Engineer", "Senior Software Engineer", "Staff Engineer",
    "Junior Developer", "Frontend Developer", "Backend Developer",
    "Full-Stack Developer", "DevOps Engineer", "System Administrator",
    "Network Engineer", "Database Administrator", "QA Engineer",
    "QA Lead", "Product Manager", "Project Manager", "Technical Lead",
    "Engineering Manager", "VP of Engineering", "CTO", "CFO",
    "Accountant", "Senior Accountant", "Financial Analyst",
    "HR Manager", "HR Coordinator", "Recruiter", "Office Manager",
    "Marketing Manager", "Content Writer", "Graphic Designer",
    "UI/UX Designer", "Data Analyst", "Data Engineer", "ML Engineer",
    "Security Analyst", "Compliance Officer", "Legal Counsel",
    "Sales Representative", "Account Manager", "Business Analyst",
    "Customer Support Lead", "Support Agent", "Intern", "Trainee",
    "Procurement Officer", "Facilities Coordinator",
]

CATEGORY_DATA = [
    {"name": "Laptop", "description": "Portable computers including ultrabooks, workstations, and business notebooks."},
    {"name": "Desktop", "description": "Tower and small-form-factor desktop workstations."},
    {"name": "All-in-One", "description": "Integrated display-and-computer units."},
    {"name": "Monitor", "description": "External displays and presentation screens."},
    {"name": "Printer", "description": "Inkjet, laser, and multifunction printers."},
    {"name": "Networking", "description": "Routers, switches, access points, and firewalls."},
    {"name": "Server", "description": "Rack-mount and tower servers."},
    {"name": "Phone", "description": "Desk phones, conference phones, and VoIP devices."},
    {"name": "Tablet", "description": "Tablets and convertible devices."},
    {"name": "Peripheral", "description": "Keyboards, mice, headsets, webcams, docking stations."},
    {"name": "Storage", "description": "NAS devices, external drives, tape libraries."},
    {"name": "UPS", "description": "Uninterruptible power supplies and surge protectors."},
]

ASSET_MODEL_DATA = [
    # Laptops
    {"category": "Laptop", "manufacturer": "Apple", "model_name": "MacBook Pro 14\"", "model_number": "MKGR3LL/A"},
    {"category": "Laptop", "manufacturer": "Apple", "model_name": "MacBook Air M2", "model_number": "MLY33LL/A"},
    {"category": "Laptop", "manufacturer": "Lenovo", "model_name": "ThinkPad X1 Carbon Gen 11", "model_number": "21HM002YUS"},
    {"category": "Laptop", "manufacturer": "Lenovo", "model_name": "ThinkPad T14s Gen 4", "model_number": "21F60029US"},
    {"category": "Laptop", "manufacturer": "Dell", "model_name": "Latitude 5540", "model_number": "5540-7890"},
    {"category": "Laptop", "manufacturer": "Dell", "model_name": "XPS 15 9530", "model_number": "XPS9530-7758SLV"},
    {"category": "Laptop", "manufacturer": "HP", "model_name": "EliteBook 840 G10", "model_number": "6T242EA"},
    {"category": "Laptop", "manufacturer": "HP", "model_name": "ProBook 450 G10", "model_number": "86R18EA"},
    {"category": "Laptop", "manufacturer": "Toshiba", "model_name": "Satellite Pro C40-G", "model_number": "PMZ11U-006001"},
    {"category": "Laptop", "manufacturer": "ASUS", "model_name": "ExpertBook B9 OLED", "model_number": "B9403CVA-KM0076X"},
    # Desktops
    {"category": "Desktop", "manufacturer": "Dell", "model_name": "OptiPlex 7010 SFF", "model_number": "7010-SFF-2023"},
    {"category": "Desktop", "manufacturer": "HP", "model_name": "ProDesk 400 G9", "model_number": "6B2B1EA"},
    {"category": "Desktop", "manufacturer": "Lenovo", "model_name": "ThinkCentre M90q Gen 3", "model_number": "11U50010US"},
    {"category": "Desktop", "manufacturer": "", "model_name": "Custom Build (i7-13700K)", "model_number": ""},
    {"category": "Desktop", "manufacturer": "", "model_name": "Custom Build (Ryzen 9 7950X)", "model_number": ""},
    # All-in-Ones
    {"category": "All-in-One", "manufacturer": "Apple", "model_name": "iMac 24\" M3", "model_number": "MQR93LL/A"},
    {"category": "All-in-One", "manufacturer": "Lenovo", "model_name": "IdeaCentre AIO 3i", "model_number": "F0GH00AYUS"},
    {"category": "All-in-One", "manufacturer": "HP", "model_name": "EliteOne 870 G9", "model_number": "5V8H6EA"},
    # Monitors
    {"category": "Monitor", "manufacturer": "Dell", "model_name": "UltraSharp U2723QE 27\"", "model_number": "U2723QE"},
    {"category": "Monitor", "manufacturer": "LG", "model_name": "27UK850-W 27\" 4K", "model_number": "27UK850-W"},
    {"category": "Monitor", "manufacturer": "Samsung", "model_name": "Odyssey G7 32\"", "model_number": "LC32G75TQSNXZA"},
    {"category": "Monitor", "manufacturer": "BenQ", "model_name": "PD2705U 27\" 4K", "model_number": "PD2705U"},
    # Printers
    {"category": "Printer", "manufacturer": "HP", "model_name": "LaserJet Pro M404dn", "model_number": "W1A53A"},
    {"category": "Printer", "manufacturer": "Canon", "model_name": "PIXMA G1010", "model_number": "G1010"},
    {"category": "Printer", "manufacturer": "Brother", "model_name": "MFC-L3770CDW", "model_number": "MFC-L3770CDW"},
    {"category": "Printer", "manufacturer": "Canon", "model_name": "imageCLASS MF455dw", "model_number": "MF455dw"},
    # Networking
    {"category": "Networking", "manufacturer": "Cisco", "model_name": "Catalyst 9200L-24P", "model_number": "C9200L-24P-4G-E"},
    {"category": "Networking", "manufacturer": "Ubiquiti", "model_name": "UniFi Dream Machine Pro", "model_number": "UDM-PRO"},
    {"category": "Networking", "manufacturer": "TP-Link", "model_name": "Archer AX6000", "model_number": "AX6000"},
    {"category": "Networking", "manufacturer": "Cisco", "model_name": "Meraki MR46", "model_number": "MR46-HW"},
    # Servers
    {"category": "Server", "manufacturer": "Dell", "model_name": "PowerEdge R750xs", "model_number": "R750XS-2023"},
    {"category": "Server", "manufacturer": "HP", "model_name": "ProLiant DL380 Gen10 Plus", "model_number": "P55247-B21"},
    {"category": "Server", "manufacturer": "Lenovo", "model_name": "ThinkSystem SR650 V3", "model_number": "7D76A01UNA"},
    # Phones
    {"category": "Phone", "manufacturer": "Cisco", "model_name": "IP Phone 8845", "model_number": "CP-8845-K9"},
    {"category": "Phone", "manufacturer": "Poly", "model_name": "CCX 500", "model_number": "2200-49720-019"},
    {"category": "Phone", "manufacturer": "Yealink", "model_name": "T54W", "model_number": "SIP-T54W"},
    # Tablets
    {"category": "Tablet", "manufacturer": "Apple", "model_name": "iPad Air (5th gen)", "model_number": "MM9C3LL/A"},
    {"category": "Tablet", "manufacturer": "Samsung", "model_name": "Galaxy Tab S9", "model_number": "SM-X710NZAAXAR"},
    # Peripherals
    {"category": "Peripheral", "manufacturer": "Logitech", "model_name": "MX Keys S", "model_number": "920-011406"},
    {"category": "Peripheral", "manufacturer": "Logitech", "model_name": "MX Master 3S", "model_number": "910-006556"},
    {"category": "Peripheral", "manufacturer": "Jabra", "model_name": "Evolve2 85", "model_number": "28599-999-999"},
    {"category": "Peripheral", "manufacturer": "CalDigit", "model_name": "TS4 Thunderbolt 4 Dock", "model_number": "TS4-US"},
    {"category": "Peripheral", "manufacturer": "Logitech", "model_name": "Brio 4K Webcam", "model_number": "960-001105"},
    # Storage
    {"category": "Storage", "manufacturer": "Synology", "model_name": "DiskStation DS923+", "model_number": "DS923+"},
    {"category": "Storage", "manufacturer": "QNAP", "model_name": "TS-464", "model_number": "TS-464-8G-US"},
    # UPS
    {"category": "UPS", "manufacturer": "APC", "model_name": "Smart-UPS 1500VA", "model_number": "SMT1500C"},
    {"category": "UPS", "manufacturer": "CyberPower", "model_name": "CP1500PFCLCD", "model_number": "CP1500PFCLCD"},
]

COMPONENT_TYPE_DATA = [
    {"type_name": "CPU", "attributes": {"socket_types": ["LGA1700", "AM5", "LGA4677"]}},
    {"type_name": "RAM", "attributes": {"form_factors": ["DIMM", "SO-DIMM"], "generations": ["DDR4", "DDR5"]}},
    {"type_name": "SSD", "attributes": {"interfaces": ["NVMe M.2", "SATA 2.5\"", "U.2"]}},
    {"type_name": "HDD", "attributes": {"interfaces": ["SATA", "SAS"], "form_factors": ["3.5\"", "2.5\""]}},
    {"type_name": "GPU", "attributes": {"interfaces": ["PCIe x16"]}},
    {"type_name": "Power Supply", "attributes": {"form_factors": ["ATX", "SFX"]}},
    {"type_name": "Motherboard", "attributes": {"form_factors": ["ATX", "Micro-ATX", "Mini-ITX"]}},
    {"type_name": "Network Card", "attributes": {"speeds": ["1GbE", "10GbE", "25GbE"]}},
    {"type_name": "RAID Controller", "attributes": {"interfaces": ["PCIe", "Onboard"]}},
    {"type_name": "Battery", "attributes": {"types": ["Laptop", "UPS", "CMOS"]}},
    {"type_name": "Display Panel", "attributes": {"types": ["LCD", "OLED", "LED"]}},
    {"type_name": "Cooling Fan", "attributes": {"sizes": ["80mm", "120mm", "140mm"]}},
]

COMPONENT_SPECS = {
    "CPU": [
        ("Intel", "Core i5-13400", "10C/16T, 2.5 GHz base, 4.6 GHz boost"),
        ("Intel", "Core i7-13700K", "16C/24T, 3.4 GHz base, 5.4 GHz boost"),
        ("Intel", "Core i9-13900K", "24C/32T, 3.0 GHz base, 5.8 GHz boost"),
        ("Intel", "Xeon w5-3435X", "16C/32T, 3.1 GHz base, 4.7 GHz boost"),
        ("AMD", "Ryzen 5 7600X", "6C/12T, 4.7 GHz base, 5.3 GHz boost"),
        ("AMD", "Ryzen 7 7700X", "8C/16T, 4.5 GHz base, 5.4 GHz boost"),
        ("AMD", "Ryzen 9 7950X", "16C/32T, 4.5 GHz base, 5.7 GHz boost"),
        ("AMD", "EPYC 9354", "32C/64T, 3.25 GHz base, 3.8 GHz boost"),
        ("Apple", "M2", "8C CPU, 10C GPU"),
        ("Apple", "M3 Pro", "11C CPU, 14C GPU"),
    ],
    "RAM": [
        ("Samsung", "M471A2K43EB1-CWE", "16GB DDR4-3200 SO-DIMM"),
        ("Samsung", "M378A4G43AB2-CWE", "32GB DDR4-3200 DIMM"),
        ("Crucial", "CT16G48C40S5", "16GB DDR5-4800 SO-DIMM"),
        ("Crucial", "CT32G48C40U5", "32GB DDR5-4800 DIMM"),
        ("Kingston", "KF556C36-16", "16GB DDR5-5600 DIMM"),
        ("Kingston", "KVR48S40BS8-16", "16GB DDR5-4800 SO-DIMM"),
        ("Corsair", "CMK32GX5M2B5600C36", "32GB (2x16) DDR5-5600"),
        ("SK Hynix", "HMCG78AGBSA092N", "16GB DDR5-4800 SO-DIMM"),
        ("SK Hynix", "HMCG88AGBUA084N", "32GB DDR5-4800 DIMM"),
        ("G.Skill", "F5-6000J3038F16GX2-TZ5N", "32GB (2x16) DDR5-6000"),
    ],
    "SSD": [
        ("Samsung", "980 PRO 1TB", "1TB NVMe M.2, 7000/5000 MB/s"),
        ("Samsung", "990 PRO 2TB", "2TB NVMe M.2, 7450/6900 MB/s"),
        ("Samsung", "870 EVO 500GB", "500GB SATA 2.5\", 560/530 MB/s"),
        ("WD", "Black SN850X 1TB", "1TB NVMe M.2, 7300/6300 MB/s"),
        ("WD", "Red SA500 1TB", "1TB SATA 2.5\" NAS"),
        ("SK Hynix", "Platinum P41 1TB", "1TB NVMe M.2, 7000/6500 MB/s"),
        ("Crucial", "T700 2TB", "2TB NVMe M.2, 12400/11800 MB/s"),
        ("Crucial", "MX500 1TB", "1TB SATA 2.5\", 560/510 MB/s"),
        ("Intel", "Optane 905P 960GB", "960GB U.2 NVMe"),
        ("Kingston", "A2000 500GB", "500GB NVMe M.2, 2200/2000 MB/s"),
    ],
    "HDD": [
        ("Seagate", "Barracuda 2TB", "2TB 7200RPM SATA 3.5\""),
        ("Seagate", "IronWolf 4TB", "4TB 5400RPM SATA 3.5\" NAS"),
        ("WD", "Red Plus 4TB", "4TB 5400RPM SATA 3.5\" NAS"),
        ("WD", "Ultrastar HC550 16TB", "16TB 7200RPM SAS 3.5\""),
        ("Toshiba", "X300 6TB", "6TB 7200RPM SATA 3.5\""),
    ],
    "GPU": [
        ("NVIDIA", "RTX 4090", "24GB GDDR6X"),
        ("NVIDIA", "RTX 4080", "16GB GDDR6X"),
        ("NVIDIA", "RTX A4000", "16GB GDDR6 Professional"),
        ("NVIDIA", "A100 80GB", "80GB HBM2e Data Center"),
        ("AMD", "Radeon Pro W6800", "32GB GDDR6 Professional"),
        ("AMD", "Radeon RX 7900 XTX", "24GB GDDR6"),
    ],
    "Power Supply": [
        ("Corsair", "RM850x", "850W 80+ Gold ATX"),
        ("Corsair", "HX1200", "1200W 80+ Platinum ATX"),
        ("Seasonic", "Focus GX-750", "750W 80+ Gold ATX"),
        ("EVGA", "SuperNOVA 1000 G6", "1000W 80+ Gold ATX"),
    ],
    "Motherboard": [
        ("ASUS", "ProArt Z790-CREATOR", "LGA1700 ATX DDR5"),
        ("MSI", "MAG B550 TOMAHAWK", "AM4 ATX DDR4"),
        ("Gigabyte", "X670E AORUS MASTER", "AM5 ATX DDR5"),
        ("ASRock", "Z790 Pro RS", "LGA1700 ATX DDR5"),
        ("Supermicro", "X12SPi-TF", "LGA4189 ATX Server"),
    ],
    "Network Card": [
        ("Intel", "X710-DA2", "Dual 10GbE SFP+ PCIe"),
        ("Mellanox", "ConnectX-6 Dx", "Dual 25GbE SFP28 PCIe"),
        ("Broadcom", "P210TP", "Dual 10GbE RJ45 PCIe"),
        ("Intel", "I350-T4", "Quad 1GbE RJ45 PCIe"),
    ],
    "RAID Controller": [
        ("Broadcom", "MegaRAID 9460-8i", "8-port 12Gb/s SAS/SATA PCIe"),
        ("Broadcom", "MegaRAID 9560-16i", "16-port 12Gb/s SAS/SATA/NVMe"),
    ],
    "Battery": [
        ("Apple", "A2519", "Laptop battery 66.5Wh"),
        ("Lenovo", "5B10W51828", "Laptop battery 57Wh ThinkPad"),
        ("Dell", "7FMXV", "Laptop battery 54Wh Latitude"),
        ("APC", "APCRBC124", "UPS replacement battery cartridge"),
    ],
    "Display Panel": [
        ("LG Display", "LP140WF9-SPF1", "14\" FHD IPS 1920x1080"),
        ("BOE", "NE135FBM-N41", "13.5\" 2K IPS 2256x1504"),
        ("Samsung", "ATNA56WR06-0", "15.6\" 4K OLED 3840x2160"),
    ],
    "Cooling Fan": [
        ("Noctua", "NF-A12x25 PWM", "120mm premium fan"),
        ("be quiet!", "Silent Wings 4", "140mm low-noise fan"),
        ("Delta", "AFB1212SHE", "120mm server fan high-CFM"),
    ],
}

VENDOR_DATA = [
    {"vendor_name": "Ryans Computers", "contact_person": "Md. Iqbal Hossain", "email": "corporate@ryans.com.bd", "phone": "+880-2-9123456", "website": "https://ryanscomputers.com", "address": "IDB Bhaban, Agargaon, Dhaka"},
    {"vendor_name": "Star Tech", "contact_person": "Tanvir Rahman", "email": "sales@startech.com.bd", "phone": "+880-2-8234567", "website": "https://startech.com.bd", "address": "Elephant Road, Dhaka"},
    {"vendor_name": "UCC", "contact_person": "Sakib Ahmed", "email": "info@ucc.com.bd", "phone": "+880-2-7345678", "website": "https://ucc.com.bd", "address": "Multiplan Center, Gulshan"},
    {"vendor_name": "Techland BD", "contact_person": "Rifat Karim", "email": "sales@techlandbd.com", "phone": "+880-2-6456789", "website": "https://techlandbd.com", "address": "BCS Computer City, Agargaon"},
    {"vendor_name": "Global Brand Pvt Ltd", "contact_person": "Nabila Sheikh", "email": "corporate@globalbrand.com.bd", "phone": "+880-2-5567890", "website": "https://globalbrand.com.bd", "address": "Banani, Dhaka"},
    {"vendor_name": "Computer Source", "contact_person": "Wasim Khan", "email": "info@computersource.com.bd", "phone": "+880-2-4678901", "website": "https://computersource.com.bd", "address": "Eastern Mollika, Elephant Road"},
    {"vendor_name": "Binary Logic", "contact_person": "Arif Hasan", "email": "sales@binarylogic.com.bd", "phone": "+880-2-3789012", "website": "https://binarylogic.com.bd", "address": "IDB Bhaban, Agargaon"},
    {"vendor_name": "Cisco Systems (BD)", "contact_person": "Regional Sales", "email": "bd-sales@cisco.com", "phone": "+880-2-2890123", "website": "https://cisco.com", "address": "Gulshan-1, Dhaka"},
    {"vendor_name": "Dell Technologies (BD)", "contact_person": "Enterprise Sales", "email": "bd-enterprise@dell.com", "phone": "+880-2-1901234", "website": "https://dell.com", "address": "Banani DOHS, Dhaka"},
    {"vendor_name": "Lenovo Bangladesh", "contact_person": "Channel Sales", "email": "bd-channel@lenovo.com", "phone": "+880-2-0012345", "website": "https://lenovo.com", "address": "Uttara, Dhaka"},
    {"vendor_name": "Datapath Ltd", "contact_person": "Faisal Mahmud", "email": "sales@datapath.com.bd", "phone": "+880-2-9988776", "website": "https://datapath.com.bd", "address": "Motijheel, Dhaka"},
    {"vendor_name": "NetSol Technologies", "contact_person": "Sharif Uddin", "email": "info@netsol.com.bd", "phone": "+880-31-556677", "website": "https://netsol.com.bd", "address": "Agrabad, Chittagong"},
]

MAINTENANCE_DESCRIPTIONS = {
    "repair": [
        "Replaced faulty keyboard — multiple keys unresponsive.",
        "Fixed screen flickering issue — reseated display cable.",
        "Repaired power jack — intermittent charging resolved.",
        "Replaced cracked display panel.",
        "Fixed overheating — cleaned thermal paste and replaced fan.",
        "Resolved boot loop — repaired corrupted BIOS.",
        "Replaced swollen battery pack.",
        "Fixed USB port — resoldered loose connector.",
        "Repaired trackpad — replaced flex cable.",
        "Fixed speaker buzzing — replaced audio board.",
        "Resolved intermittent Wi-Fi — replaced wireless card.",
        "Replaced failed SSD under warranty.",
        "Fixed paper jam mechanism in printer.",
        "Replaced fuser unit in laser printer.",
        "Repaired network switch — replaced failed module.",
    ],
    "upgrade": [
        "Upgraded RAM from 8GB to 16GB DDR4.",
        "Upgraded RAM from 16GB to 32GB DDR5.",
        "Replaced 256GB SSD with 1TB NVMe.",
        "Upgraded OS from Windows 10 to Windows 11.",
        "Added secondary 2TB HDD for data storage.",
        "Upgraded network card to 10GbE.",
        "Replaced GPU with RTX 4080 for ML workloads.",
        "Upgraded BIOS/firmware to latest version.",
        "Installed additional cooling fan for server.",
        "Replaced 1GbE switch module with 10GbE.",
        "Upgraded UPS batteries for extended runtime.",
        "Replaced CPU with higher-core-count model.",
    ],
}


# ============================================================================
# Helpers
# ============================================================================

_serial_counter = count(1)


def _serial(prefix="SN"):
    """Generate a unique serial number."""
    n = next(_serial_counter)
    chars = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}{n:04d}{chars}"


def _past_date(days_back_min=30, days_back_max=1200):
    """Random date in the past."""
    days = random.randint(days_back_min, days_back_max)
    return (timezone.now() - datetime.timedelta(days=days)).date()


def _past_datetime(days_back_min=30, days_back_max=1200):
    """Random datetime in the past (timezone-aware)."""
    seconds = random.randint(days_back_min * 86400, days_back_max * 86400)
    return timezone.now() - datetime.timedelta(seconds=seconds)


def _cost(low=50, high=5000):
    """Random cost as Decimal."""
    return decimal.Decimal(str(round(random.uniform(low, high), 2)))


def _warranty_from_purchase(purchase_date, years_min=1, years_max=3):
    """Generate a warranty date from a purchase date."""
    years = random.randint(years_min, years_max)
    return purchase_date + datetime.timedelta(days=years * 365)


def _pick(lst, n=1):
    """Pick n random items from a list."""
    return random.sample(lst, min(n, len(lst)))


def _coin(probability=0.5):
    return random.random() < probability


class Command(BaseCommand):
    help = "Seed the database with realistic test data (~2 000 records)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete ALL existing data before seeding (irreversible).",
        )
        parser.add_argument(
            "--small",
            action="store_true",
            help="Generate a smaller dataset (~500 records).",
        )
        parser.add_argument(
            "--no-activity",
            action="store_true",
            help="Suppress all activity log entries during seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.small = options["small"]
        self.no_activity = options["no_activity"]
        self.stdout.write("")

        if options["flush"]:
            self._flush()

        # Determine counts
        if self.small:
            self.n_employees = 40
            self.n_assets = 120
            self.n_components = 80
            self.n_invoices = 15
            self.n_requisitions = 10
            self.n_maintenance = 25
            self.n_assignments = 40
        else:
            self.n_employees = 150
            self.n_assets = 500
            self.n_components = 350
            self.n_invoices = 55
            self.n_requisitions = 40
            self.n_maintenance = 80
            self.n_assignments = 120

        with suppress_auto_log():
            self._create_companies()
            self._create_locations()
            self._create_departments()
            self._create_employees()
            self._create_categories()
            self._create_asset_models()
            self._create_component_types()
            self._create_vendors()
            self._create_assets()
            self._create_components()
            self._create_component_history()
            self._create_spare_parts()
            self._create_asset_assignments()
            self._create_maintenance_records()
            self._create_invoices()
            self._create_requisitions()

        if not self.no_activity:
            self._create_activity_log()

        total = self._count_all()
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"  Done. {total:,} records created across all models."))
        self.stdout.write("")

    # ------------------------------------------------------------------
    # Flush
    # ------------------------------------------------------------------

    def _flush(self):
        self.stdout.write(self.style.WARNING("  Flushing all data..."))
        models_to_flush = [
            ActivityLog, ComponentHistory, RequisitionItem, Requisition,
            InvoiceLineItem, PurchaseInvoice, MaintenanceRecord,
            AssetAssignment, SparePartsInventory, Component, Asset,
            AssetModel, Category, ComponentType, Employee, Department,
            Location, Company, Vendor,
        ]
        for m in models_to_flush:
            deleted, _ = m.objects.all().delete()
            if deleted:
                self.stdout.write(f"    Deleted {deleted:>6} {m.__name__}")
        self.stdout.write("")

    # ------------------------------------------------------------------
    # Companies
    # ------------------------------------------------------------------

    def _create_companies(self):
        self.companies = []
        for data in COMPANY_DATA:
            obj, created = Company.objects.get_or_create(
                code=data["code"],
                defaults={
                    "name": data["name"],
                    "city": data["city"],
                    "country": data["country"],
                    "phone": data["phone"],
                    "address": f"{data['city']} Office, {data['country']}",
                    "is_active": True,
                },
            )
            self.companies.append(obj)
        self._log("Company", len(self.companies))

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------

    def _create_locations(self):
        self.locations = []
        for data in LOCATION_DATA:
            obj, created = Location.objects.get_or_create(
                name=data["name"],
                defaults={
                    "city": data["city"],
                    "address": data["address"],
                    "zipcode": data.get("zipcode", ""),
                    "country": data.get("country", ""),
                },
            )
            self.locations.append(obj)
        self._log("Location", len(self.locations))

    # ------------------------------------------------------------------
    # Departments
    # ------------------------------------------------------------------

    def _create_departments(self):
        self.departments = []
        dept_names_shuffled = list(DEPARTMENT_NAMES)
        for company in self.companies:
            # Each company gets 4–8 departments
            n = random.randint(4, min(8, len(dept_names_shuffled)))
            chosen = random.sample(dept_names_shuffled, n)
            for name in chosen:
                loc = random.choice(self.locations) if _coin(0.7) else None
                obj, created = Department.objects.get_or_create(
                    company=company,
                    name=name,
                    defaults={"default_location": loc},
                )
                self.departments.append(obj)
        self._log("Department", len(self.departments))

    # ------------------------------------------------------------------
    # Employees
    # ------------------------------------------------------------------

    def _create_employees(self):
        self.employees = []
        used_ids = set(Employee.objects.values_list("employee_id", flat=True))
        used_emails = set()
        emp_counter = count(1)

        for _ in range(self.n_employees):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            name = f"{first} {last}"

            dept = random.choice(self.departments)
            company = dept.company
            loc = dept.default_location or random.choice(self.locations)
            position = random.choice(POSITIONS)

            # Unique employee ID
            while True:
                eid = f"{company.code}-{next(emp_counter):04d}"
                if eid not in used_ids:
                    used_ids.add(eid)
                    break

            # Unique-ish email
            email_base = f"{first.lower()}.{last.lower()}"
            email = f"{email_base}@{company.code.lower()}.local"
            suffix = 1
            while email in used_emails:
                email = f"{email_base}{suffix}@{company.code.lower()}.local"
                suffix += 1
            used_emails.add(email)

            status = "active" if _coin(0.9) else "inactive"
            phone_ext = f"x{random.randint(100, 999)}"

            obj = Employee.objects.create(
                employee_id=eid,
                name=name,
                email=email,
                phone=f"+880-{random.randint(1000000000, 1999999999)}",
                extension=phone_ext,
                company=company,
                department=dept,
                location=loc,
                position=position,
                status=status,
            )
            self.employees.append(obj)

        self._log("Employee", len(self.employees))

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    def _create_categories(self):
        self.categories = {}
        for data in CATEGORY_DATA:
            obj, _ = Category.objects.get_or_create(
                name=data["name"],
                defaults={"description": data["description"]},
            )
            self.categories[data["name"]] = obj
        self._log("Category", len(self.categories))

    # ------------------------------------------------------------------
    # Asset Models
    # ------------------------------------------------------------------

    def _create_asset_models(self):
        self.asset_models = []
        for data in ASSET_MODEL_DATA:
            cat = self.categories.get(data["category"])
            if not cat:
                continue
            obj, _ = AssetModel.objects.get_or_create(
                category=cat,
                manufacturer=data["manufacturer"],
                model_name=data["model_name"],
                defaults={
                    "model_number": data.get("model_number", ""),
                },
            )
            self.asset_models.append(obj)
        self._log("AssetModel", len(self.asset_models))

    # ------------------------------------------------------------------
    # Component Types
    # ------------------------------------------------------------------

    def _create_component_types(self):
        self.component_types = {}
        for data in COMPONENT_TYPE_DATA:
            obj, _ = ComponentType.objects.get_or_create(
                type_name=data["type_name"],
                defaults={"attributes": data.get("attributes")},
            )
            self.component_types[data["type_name"]] = obj
        self._log("ComponentType", len(self.component_types))

    # ------------------------------------------------------------------
    # Vendors
    # ------------------------------------------------------------------

    def _create_vendors(self):
        self.vendors = []
        for data in VENDOR_DATA:
            obj, _ = Vendor.objects.get_or_create(
                vendor_name=data["vendor_name"],
                defaults={
                    "contact_person": data.get("contact_person", ""),
                    "email": data.get("email"),
                    "phone": data.get("phone", ""),
                    "address": data.get("address"),
                    "website": data.get("website"),
                },
            )
            self.vendors.append(obj)
        self._log("Vendor", len(self.vendors))

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    def _create_assets(self):
        self.assets = []
        active_employees = [e for e in self.employees if e.status == "active"]
        status_weights = {
            "active": 55,
            "pending": 10,
            "in_repair": 8,
            "retired": 12,
            "disposed": 10,
            "inactive": 5,
        }
        statuses = list(status_weights.keys())
        weights = list(status_weights.values())

        for i in range(self.n_assets):
            model = random.choice(self.asset_models)
            company = random.choice(self.companies)
            status = random.choices(statuses, weights=weights, k=1)[0]

            purchase_date = _past_date(60, 1500)
            warranty = _warranty_from_purchase(purchase_date) if _coin(0.8) else None

            # Determine assignment (only for active/in_repair)
            assigned_to = None
            location = None
            if status in ("active", "in_repair"):
                if _coin(0.7) and active_employees:
                    assigned_to = random.choice(active_employees)
                elif self.locations:
                    location = random.choice(self.locations)
            elif status == "pending":
                # Pending assets might be at a location (e.g. warehouse)
                if _coin(0.5) and self.locations:
                    location = random.choice(self.locations)

            # Determine cost based on category
            cat_name = model.category.name
            if cat_name in ("Server",):
                cost = _cost(3000, 25000)
            elif cat_name in ("Laptop", "Desktop", "All-in-One"):
                cost = _cost(400, 3500)
            elif cat_name in ("Monitor",):
                cost = _cost(150, 1200)
            elif cat_name in ("Printer",):
                cost = _cost(100, 800)
            elif cat_name in ("Networking",):
                cost = _cost(200, 5000)
            elif cat_name in ("Phone", "Tablet"):
                cost = _cost(100, 1500)
            elif cat_name in ("Peripheral",):
                cost = _cost(20, 400)
            elif cat_name in ("Storage",):
                cost = _cost(300, 3000)
            elif cat_name in ("UPS",):
                cost = _cost(100, 1500)
            else:
                cost = _cost(50, 2000)

            serial = _serial()

            obj = Asset(
                company=company,
                asset_model=model,
                serial_number=serial,
                purchase_date=purchase_date,
                purchase_cost=cost,
                warranty_expiry_date=warranty,
                status=status,
                assigned_to=assigned_to,
                location=location,
                notes=f"Seeded test asset #{i + 1}" if _coin(0.1) else "",
            )
            obj.save()
            self.assets.append(obj)

        self._log("Asset", len(self.assets))

    # ------------------------------------------------------------------
    # Components
    # ------------------------------------------------------------------

    def _create_components(self):
        self.components = []
        # Only assign components to assets that are laptops, desktops,
        # servers, all-in-ones, storage, or networking
        assignable_categories = {"Laptop", "Desktop", "All-in-One", "Server", "Storage", "Networking"}
        assignable_assets = [
            a for a in self.assets
            if a.asset_model.category.name in assignable_categories
            and a.status in ("active", "in_repair", "pending")
        ]

        status_weights = {
            "installed": 60,
            "spare": 20,
            "failed": 8,
            "removed": 8,
            "disposed": 4,
        }
        statuses = list(status_weights.keys())
        weights = list(status_weights.values())

        for i in range(self.n_components):
            ct_name = random.choice(list(COMPONENT_SPECS.keys()))
            ct = self.component_types.get(ct_name)
            if not ct:
                continue

            spec_data = random.choice(COMPONENT_SPECS[ct_name])
            manufacturer, model_name, specifications = spec_data

            status = random.choices(statuses, weights=weights, k=1)[0]

            parent_asset = None
            if status == "installed" and assignable_assets:
                parent_asset = random.choice(assignable_assets)
            elif status in ("removed", "failed") and _coin(0.3) and assignable_assets:
                # Some removed/failed components still reference their last parent
                parent_asset = random.choice(assignable_assets)

            purchase_date = _past_date(30, 1200)
            warranty = _warranty_from_purchase(purchase_date, 1, 5) if _coin(0.6) else None
            install_date = purchase_date + datetime.timedelta(days=random.randint(0, 30)) if status == "installed" else None
            removal_date = None
            if status in ("removed", "failed", "disposed"):
                removal_date = _past_date(1, 180)

            obj = Component(
                component_type=ct,
                parent_asset=parent_asset,
                manufacturer=manufacturer,
                model=model_name,
                serial_number=_serial("CMP"),
                specifications=specifications,
                status=status,
                purchase_date=purchase_date,
                warranty_expiry_date=warranty,
                installation_date=install_date,
                removal_date=removal_date,
                notes=f"Seeded component #{i + 1}" if _coin(0.05) else "",
            )
            obj.save()
            self.components.append(obj)

        self._log("Component", len(self.components))

    # ------------------------------------------------------------------
    # Spare Parts Inventory (auto-sync from components)
    # ------------------------------------------------------------------

    def _create_spare_parts(self):
        sync_all_spare_parts()

        # Set realistic minimum thresholds on existing entries
        entries = SparePartsInventory.objects.all()
        for entry in entries:
            entry.quantity_minimum = random.randint(1, 5)
            if _coin(0.5):
                entry.location = random.choice(self.locations)
            entry.last_restocked = _past_date(1, 90) if _coin(0.6) else None
            entry.save(update_fields=[
                "quantity_minimum", "location", "last_restocked", "updated_at",
            ])

        count_ = entries.count()
        self._log("SparePartsInventory", count_)

    # ------------------------------------------------------------------
    # Asset Assignments (historical)
    # ------------------------------------------------------------------

    def _create_asset_assignments(self):
        assignments = []
        active_employees = [e for e in self.employees if e.status == "active"]

        # Create historical assignments for a subset of assets
        assignable = [a for a in self.assets if a.status in ("active", "in_repair", "retired")]
        chosen = _pick(assignable, self.n_assignments)

        for asset in chosen:
            n_history = random.randint(1, 4)
            current_date = _past_datetime(365, 1400)

            for j in range(n_history):
                if _coin(0.8) and active_employees:
                    user = random.choice(active_employees)
                    loc = None
                else:
                    user = None
                    loc = random.choice(self.locations)

                assigned_date = current_date
                # All but the last entry have a return date
                if j < n_history - 1:
                    returned_date = assigned_date + datetime.timedelta(
                        days=random.randint(30, 300)
                    )
                else:
                    returned_date = None if asset.status == "active" else (
                        assigned_date + datetime.timedelta(days=random.randint(30, 300))
                    )

                conditions = ["New", "Good", "Fair", "Worn", "Minor scratches", "Excellent"]
                obj = AssetAssignment(
                    asset=asset,
                    user=user,
                    location=loc,
                    assigned_date=assigned_date,
                    returned_date=returned_date,
                    condition_on_assignment=random.choice(conditions),
                    condition_on_return=random.choice(conditions) if returned_date else "",
                )
                assignments.append(obj)

                if returned_date:
                    current_date = returned_date + datetime.timedelta(days=random.randint(1, 30))
                else:
                    break

        AssetAssignment.objects.bulk_create(assignments)
        self._log("AssetAssignment", len(assignments))

    # ------------------------------------------------------------------
    # Maintenance Records
    # ------------------------------------------------------------------

    def _create_maintenance_records(self):
        records = []
        maintainable = [a for a in self.assets if a.status in ("active", "in_repair", "retired")]
        chosen = _pick(maintainable, self.n_maintenance)
        technicians = [
            "Md. Rafiq Islam", "Kamal Hossain", "Tanvir Ahmed", "Shariful Alam",
            "Nayeem Uddin", "Abir Sarker", "Farhan Chowdhury", "Javed Khan",
            "External Vendor — Ryans", "External Vendor — Star Tech",
            "In-house IT", "Warranty Service",
        ]

        for asset in chosen:
            mtype = random.choice(["repair", "upgrade"])
            desc = random.choice(MAINTENANCE_DESCRIPTIONS[mtype])
            m_date = _past_date(5, 600)
            next_date = m_date + datetime.timedelta(days=random.randint(90, 365)) if _coin(0.3) else None

            if mtype == "repair":
                cost = _cost(20, 800)
            else:
                cost = _cost(50, 3000)

            records.append(MaintenanceRecord(
                asset=asset,
                maintenance_type=mtype,
                performed_by=random.choice(technicians),
                maintenance_date=m_date,
                cost=cost,
                description=desc,
                next_maintenance_date=next_date,
            ))

        MaintenanceRecord.objects.bulk_create(records)
        self._log("MaintenanceRecord", len(records))

    # ------------------------------------------------------------------
    # Purchase Invoices + Line Items
    # ------------------------------------------------------------------

    def _create_invoices(self):
        self.invoices = []
        self.line_items = []
        inv_counter = count(1)

        payment_statuses_weights = {"paid": 55, "unpaid": 30, "partially_paid": 15}
        p_statuses = list(payment_statuses_weights.keys())
        p_weights = list(payment_statuses_weights.values())

        payment_methods = ["Cash", "Bank Transfer", "Bkash", "Nagad", "Credit Card", "Cheque"]

        for _ in range(self.n_invoices):
            vendor = random.choice(self.vendors)
            company = random.choice(self.companies)
            inv_date = _past_date(10, 800)
            inv_num = f"INV-{next(inv_counter):05d}"

            payment_status = random.choices(p_statuses, p_weights, k=1)[0]
            payment_date = inv_date + datetime.timedelta(days=random.randint(1, 60)) if payment_status in ("paid", "partially_paid") else None
            payment_method = random.choice(payment_methods) if payment_date else None
            payment_ref = f"TXN-{random.randint(100000, 999999)}" if payment_date else None

            received_by = random.choice(self.employees) if _coin(0.7) else None
            received_date = inv_date + datetime.timedelta(days=random.randint(1, 14)) if _coin(0.6) else None

            invoice = PurchaseInvoice(
                invoice_number=inv_num,
                company=company,
                vendor=vendor,
                invoice_date=inv_date,
                total_amount=decimal.Decimal("0.00"),  # will be updated from line items
                payment_status=payment_status,
                payment_date=payment_date,
                payment_method=payment_method or "",
                payment_reference=payment_ref or "",
                received_by=received_by,
                received_date=received_date,
            )
            invoice.save()
            self.invoices.append(invoice)

            # Create 1–6 line items per invoice
            n_items = random.randint(1, 6)
            total = decimal.Decimal("0.00")
            company_depts = list(Department.objects.filter(company=company))
            if not company_depts:
                company_depts = [random.choice(self.departments)]

            for line_num in range(1, n_items + 1):
                item_type = random.choices(
                    ["asset", "component", "service", "other"],
                    weights=[40, 30, 20, 10],
                    k=1,
                )[0]

                dept = random.choice(company_depts)
                qty = random.randint(1, 10)

                if item_type == "asset":
                    am = random.choice(self.asset_models)
                    desc = f"{am.manufacturer} {am.model_name}" if am.manufacturer else am.model_name
                    unit_cost = _cost(200, 5000)
                    ct_fk = None
                    am_fk = am
                elif item_type == "component":
                    ct_name = random.choice(list(self.component_types.keys()))
                    ct_obj = self.component_types[ct_name]
                    spec_data = random.choice(COMPONENT_SPECS.get(ct_name, [("Generic", "Part", "N/A")]))
                    desc = f"{spec_data[0]} {spec_data[1]} — {spec_data[2]}"
                    unit_cost = _cost(30, 2000)
                    ct_fk = ct_obj
                    am_fk = None
                elif item_type == "service":
                    services = [
                        "Annual maintenance contract", "On-site repair service",
                        "Software licensing (annual)", "Cloud hosting (quarterly)",
                        "Network cabling installation", "Security audit",
                        "Data migration service", "Training session",
                    ]
                    desc = random.choice(services)
                    unit_cost = _cost(100, 10000)
                    ct_fk = None
                    am_fk = None
                else:
                    others = [
                        "Shipping and handling", "Import duty", "Insurance premium",
                        "Extended warranty", "Accessories bundle",
                        "Cable management kit", "Rack mounting hardware",
                    ]
                    desc = random.choice(others)
                    unit_cost = _cost(10, 500)
                    ct_fk = None
                    am_fk = None

                line_total = unit_cost * qty
                total += line_total

                li = InvoiceLineItem(
                    invoice=invoice,
                    line_number=line_num,
                    company=company,
                    department=dept,
                    item_type=item_type,
                    description=desc,
                    quantity=qty,
                    item_cost=unit_cost,
                    asset_model=am_fk,
                    component_type=ct_fk,
                )
                li.save()
                self.line_items.append(li)

            # Update invoice total
            invoice.total_amount = total
            invoice.save(update_fields=["total_amount", "updated_at"])

        self._log("PurchaseInvoice", len(self.invoices))
        self._log("InvoiceLineItem", len(self.line_items))

    # ------------------------------------------------------------------
    # Requisitions + Requisition Items
    # ------------------------------------------------------------------

    def _create_requisitions(self):
        self.requisitions = []
        req_items_created = 0
        req_counter = count(1)

        status_weights = {"pending": 35, "fulfilled": 50, "cancelled": 15}
        r_statuses = list(status_weights.keys())
        r_weights = list(status_weights.values())

        priority_weights = {"low": 15, "normal": 50, "high": 25, "urgent": 10}
        priorities = list(priority_weights.keys())
        pri_weights = list(priority_weights.values())

        cancellation_reasons = [
            "Budget constraints — deferred to next quarter.",
            "Duplicate request — already fulfilled via REQ-00012.",
            "Requirements changed — new specifications needed.",
            "Vendor discontinued the product.",
            "Department reorganization — request no longer applicable.",
        ]

        for _ in range(self.n_requisitions):
            dept = random.choice(self.departments)
            company = dept.company
            dept_employees = [e for e in self.employees if e.department_id == dept.id]
            if not dept_employees:
                dept_employees = self.employees[:5]

            requested_by = random.choice(dept_employees)
            approved_by = random.choice(dept_employees) if _coin(0.6) else None

            req_date = _past_date(5, 600)
            status = random.choices(r_statuses, r_weights, k=1)[0]
            priority = random.choices(priorities, pri_weights, k=1)[0]

            fulfilled_date = req_date + datetime.timedelta(days=random.randint(3, 45)) if status == "fulfilled" else None
            cancel_reason = random.choice(cancellation_reasons) if status == "cancelled" else ""

            req_num = f"REQ-{next(req_counter):05d}"
            req = Requisition(
                requisition_number=req_num,
                company=company,
                department=dept,
                requested_by=requested_by,
                approved_by=approved_by,
                requisition_date=req_date,
                priority=priority,
                status="pending",  # save as pending first, then update
                notes=f"Auto-generated requisition" if _coin(0.1) else "",
                fulfilled_date=fulfilled_date,
                cancellation_reason=cancel_reason,
            )
            req.save()
            self.requisitions.append(req)

            # Add 1–5 requisition items (only for fulfilled requisitions)
            if status == "fulfilled":
                n_items = random.randint(1, 5)
                for _ in range(n_items):
                    if _coin(0.6) and self.assets:
                        # Asset item
                        asset = random.choice(self.assets)
                        try:
                            RequisitionItem.objects.create(
                                requisition=req,
                                item_type="asset",
                                asset=asset,
                                component=None,
                            )
                            req_items_created += 1
                        except Exception:
                            pass
                    elif self.components:
                        # Component item
                        comp = random.choice(self.components)
                        try:
                            RequisitionItem.objects.create(
                                requisition=req,
                                item_type="component",
                                asset=None,
                                component=comp,
                            )
                            req_items_created += 1
                        except Exception:
                            pass

            # Now update status (fulfilled needs items to exist first)
            if status != "pending":
                Requisition.objects.filter(pk=req.pk).update(status=status)
                req.status = status

        self._log("Requisition", len(self.requisitions))
        self._log("RequisitionItem", req_items_created)

    # ------------------------------------------------------------------
    # Component History
    # ------------------------------------------------------------------

    def _create_component_history(self):
        """Create component history entries for installed/removed components."""
        histories = []
        relevant = [
            c for c in self.components
            if c.status in ("installed", "removed", "failed", "replaced")
            and c.parent_asset is not None
        ]

        tech_employees = _pick(self.employees, min(20, len(self.employees)))

        for comp in relevant:
            action = {
                "installed": "installed",
                "removed": "removed",
                "failed": "failed",
            }.get(comp.status, "installed")

            histories.append(ComponentHistory(
                component=comp,
                parent_asset=comp.parent_asset,
                action=action,
                action_date=_past_datetime(1, 600),
                performed_by=random.choice(tech_employees) if _coin(0.7) else None,
                reason=random.choice([
                    "Initial installation",
                    "Replacement for failed unit",
                    "Upgrade requested by user",
                    "Preventive maintenance",
                    "Performance issue reported",
                    "Warranty replacement",
                    "",
                ]),
            ))

        ComponentHistory.objects.bulk_create(histories)
        self._log("ComponentHistory", len(histories))

    # ------------------------------------------------------------------
    # Activity Log (synthetic — realistic recent entries)
    # ------------------------------------------------------------------

    def _create_activity_log(self):
        from django.contrib.contenttypes.models import ContentType

        entries = []

        # Try to get or create a system user for the actor
        admin_user = DjangoUser.objects.filter(is_superuser=True).first()
        actor_name = ""
        if admin_user:
            emp = getattr(admin_user, "employee", None)
            actor_name = emp.name if emp else (admin_user.get_full_name() or admin_user.username)

        # Generate realistic activity from assets
        asset_ct = ContentType.objects.get_for_model(Asset)
        sample_assets = _pick(self.assets, min(80, len(self.assets)))
        for asset in sample_assets:
            action = random.choice(["created", "updated", "assigned", "status_changed"])
            detail = asset.get_status_display() if hasattr(asset, "get_status_display") else ""
            entries.append(ActivityLog(
                timestamp=_past_datetime(1, 400),
                event_type="asset",
                action=action,
                message=f"Asset {asset.asset_tag} {action}",
                detail=detail,
                actor=admin_user,
                actor_name=actor_name,
                content_type=asset_ct,
                object_id=asset.pk,
                object_repr=str(asset)[:512],
                url=f"/assets/{asset.pk}/",
            ))

        # Component activity
        comp_ct = ContentType.objects.get_for_model(Component)
        sample_comps = _pick(self.components, min(40, len(self.components)))
        for comp in sample_comps:
            action = random.choice(["created", "updated", "status_changed"])
            entries.append(ActivityLog(
                timestamp=_past_datetime(1, 400),
                event_type="component",
                action=action,
                message=f"Component {comp.component_tag} {action}",
                detail=comp.get_status_display() if hasattr(comp, "get_status_display") else "",
                actor=admin_user,
                actor_name=actor_name,
                content_type=comp_ct,
                object_id=comp.pk,
                object_repr=str(comp)[:512],
                url=f"/components/{comp.pk}/",
            ))

        # Employee activity
        emp_ct = ContentType.objects.get_for_model(Employee)
        sample_emps = _pick(self.employees, min(25, len(self.employees)))
        for emp in sample_emps:
            action = random.choice(["created", "updated"])
            entries.append(ActivityLog(
                timestamp=_past_datetime(1, 400),
                event_type="user",
                action=action,
                message=f"User {emp.name} {action}",
                detail=emp.get_status_display() if hasattr(emp, "get_status_display") else "",
                actor=admin_user,
                actor_name=actor_name,
                content_type=emp_ct,
                object_id=emp.pk,
                object_repr=str(emp)[:512],
                url=f"/users/{emp.employee_id}/",
            ))

        # Invoice activity
        inv_ct = ContentType.objects.get_for_model(PurchaseInvoice)
        sample_invs = _pick(self.invoices, min(20, len(self.invoices)))
        for inv in sample_invs:
            action = random.choice(["created", "updated", "paid"])
            entries.append(ActivityLog(
                timestamp=_past_datetime(1, 400),
                event_type="invoice",
                action=action,
                message=f"Invoice {inv.invoice_number} {action}",
                detail=inv.get_payment_status_display() if hasattr(inv, "get_payment_status_display") else "",
                actor=admin_user,
                actor_name=actor_name,
                content_type=inv_ct,
                object_id=inv.pk,
                object_repr=str(inv)[:512],
                url=f"/invoices/{inv.pk}/",
            ))

        # Requisition activity
        req_ct = ContentType.objects.get_for_model(Requisition)
        sample_reqs = _pick(self.requisitions, min(20, len(self.requisitions)))
        for req in sample_reqs:
            action = random.choice(["created", "fulfilled", "cancelled", "updated"])
            entries.append(ActivityLog(
                timestamp=_past_datetime(1, 400),
                event_type="requisition",
                action=action,
                message=f"Requisition {req.requisition_number} {action}",
                detail=req.get_status_display() if hasattr(req, "get_status_display") else "",
                actor=admin_user,
                actor_name=actor_name,
                content_type=req_ct,
                object_id=req.pk,
                object_repr=str(req)[:512],
                url=f"/requisitions/{req.pk}/",
            ))

        # Maintenance activity
        maint_ct = ContentType.objects.get_for_model(MaintenanceRecord)
        sample_maints = list(MaintenanceRecord.objects.all()[:15])
        for rec in sample_maints:
            entries.append(ActivityLog(
                timestamp=_past_datetime(1, 300),
                event_type="maintenance",
                action="created",
                message=f"Maintenance record for {rec.asset.asset_tag} created",
                detail=rec.get_maintenance_type_display(),
                actor=admin_user,
                actor_name=actor_name,
                content_type=maint_ct,
                object_id=rec.pk,
                object_repr=str(rec)[:512],
                url=f"/maintenance/{rec.pk}/",
            ))

        # Vendor / Company / Location / Department / Category misc activity
        misc_models = [
            ("vendor", Vendor, self.vendors, "/vendors/", 8),
            ("company", Company, self.companies, "/companies/", 5),
            ("location", Location, self.locations, "/locations/", 6),
            ("department", Department, self.departments[:10], "/departments/", 5),
            ("category", Category, list(self.categories.values()), "/categories/", 4),
        ]
        for event_type, model_cls, pool, base_url, n in misc_models:
            ct = ContentType.objects.get_for_model(model_cls)
            for obj in _pick(pool, min(n, len(pool))):
                entries.append(ActivityLog(
                    timestamp=_past_datetime(30, 500),
                    event_type=event_type,
                    action="created",
                    message=f"{event_type.replace('_', ' ').title()} {obj} created",
                    detail="",
                    actor=admin_user,
                    actor_name=actor_name,
                    content_type=ct,
                    object_id=obj.pk,
                    object_repr=str(obj)[:512],
                    url=f"{base_url}{obj.pk}/",
                ))

        ActivityLog.objects.bulk_create(entries)
        self._log("ActivityLog", len(entries))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log(self, model_name, count_):
        label = f"  {model_name}"
        self.stdout.write(f"{label:<30} {count_:>6}")

    def _count_all(self):
        models = [
            Company, Location, Department, Employee, Category, AssetModel,
            ComponentType, Asset, Component, ComponentHistory,
            SparePartsInventory, AssetAssignment, MaintenanceRecord,
            Vendor, Requisition, RequisitionItem, PurchaseInvoice,
            InvoiceLineItem, ActivityLog,
        ]
        return sum(m.objects.count() for m in models)
