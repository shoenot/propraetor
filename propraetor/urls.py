from django.urls import path
from . import views

app_name = 'propraetor'

urlpatterns = [
    # Search API (searchable-select dropdowns)
    path('api/search/', views.api_search, name='api_search'),

    # Modal inline-create (create FK entries on the fly)
    path('modal/create/<str:model_key>/', views.modal_create, name='modal_create'),

    # Dashboard
    path('', views.dashboard, name='dashboard'),
    # Activity
    path('activity/', views.activity_list, name='activity_list'),

    # Users
    path('users/', views.users_list, name='users_list'),
    path('users/new/', views.user_create, name='user_create'),
    path('users/bulk-deactivate/', views.users_bulk_deactivate, name='users_bulk_deactivate'),
    path('users/bulk-delete/', views.users_bulk_delete, name='users_bulk_delete'),
    path('users/<str:user_id>/', views.user_details, name='user_details'),
    path('users/<str:user_id>/edit/', views.user_edit, name='user_edit'),
    path('users/<str:user_id>/delete/', views.user_delete, name='user_delete'),
    path('users/<str:user_id>/activate/', views.user_activate, name='user_activate'),
    path('users/<str:user_id>/deactivate/', views.user_deactivate, name='user_deactivate'),

    # Assets
    path('assets/', views.assets_list, name='assets_list'),
    path('assets/new/', views.asset_create, name='asset_create'),
    path('assets/bulk-unassign/', views.assets_bulk_unassign, name='assets_bulk_unassign'),
    path('assets/bulk-delete/', views.assets_bulk_delete, name='assets_bulk_delete'),
    path('assets/bulk-status/', views.assets_bulk_status, name='assets_bulk_status'),
    path('assets/<int:asset_id>/', views.asset_details, name='asset_details'),
    path('assets/<int:asset_id>/edit/', views.asset_edit, name='asset_edit'),
    path('assets/<int:asset_id>/delete/', views.asset_delete, name='asset_delete'),
    path('assets/<int:asset_id>/unassign/', views.asset_unassign, name='asset_unassign'),
    path('assets/<int:asset_id>/status/', views.asset_change_status, name='asset_change_status'),
    path('assets/<int:asset_id>/clone/', views.asset_duplicate, name='asset_duplicate'),
    path('assets/<int:asset_id>/transfer-location/', views.asset_transfer_location, name='asset_transfer_location'),
    path('ht/<str:asset_tag>/', views.asset_details_ht, name='asset_details_ht'),

    # Asset Models
    path('asset_models/', views.asset_models_list, name='asset_models_list'),
    path('asset_models/new/', views.asset_model_create, name='asset_model_create'),
    path('asset_models/bulk-delete/', views.asset_models_bulk_delete, name='asset_models_bulk_delete'),
    path('asset_models/<int:asset_model_id>/', views.asset_model_details, name='asset_model_details'),
    path('asset_models/<int:asset_model_id>/edit/', views.asset_model_edit, name='asset_model_edit'),
    path('asset_models/<int:asset_model_id>/delete/', views.asset_model_delete, name='asset_model_delete'),

    # Components
    path('components/', views.components_list, name='components_list'),
    path('components/new/', views.component_create, name='component_create'),
    path('components/bulk-unassign/', views.components_bulk_unassign, name='components_bulk_unassign'),
    path('components/bulk-delete/', views.components_bulk_delete, name='components_bulk_delete'),
    path('components/<int:component_id>/', views.component_details, name='component_details'),
    path('components/<int:component_id>/edit/', views.component_edit, name='component_edit'),
    path('components/<int:component_id>/delete/', views.component_delete, name='component_delete'),
    path('components/<int:component_id>/unassign/', views.component_unassign, name='component_unassign'),
    path('components/<int:component_id>/status/', views.component_change_status, name='component_change_status'),

    # Component Types
    path('component_types/', views.component_types_list, name='component_types_list'),
    path('component_types/new/', views.component_type_create, name='component_type_create'),
    path('component_types/bulk-delete/', views.component_types_bulk_delete, name='component_types_bulk_delete'),
    path('component_types/<int:component_type_id>/', views.component_type_details, name='component_type_details'),
    path('component_types/<int:component_type_id>/edit/', views.component_type_edit, name='component_type_edit'),
    path('component_types/<int:component_type_id>/delete/', views.component_type_delete, name='component_type_delete'),

    # Requisitions
    path('requisitions/', views.requisitions_list, name='requisition_list'),
    path('requisitions/new/', views.requisition_create, name='requisition_create'),
    path('requisitions/bulk-delete/', views.requisitions_bulk_delete, name='requisitions_bulk_delete'),
    path('requisitions/bulk-cancel/', views.requisitions_bulk_cancel, name='requisitions_bulk_cancel'),
    path('requisitions/bulk-fulfill/', views.requisitions_bulk_fulfill, name='requisitions_bulk_fulfill'),
    path('requisitions/<int:requisition_id>/', views.requisition_details, name='requisition_details'),
    path('requisitions/<int:requisition_id>/edit/', views.requisition_edit, name='requisition_edit'),
    path('requisitions/<int:requisition_id>/delete/', views.requisition_delete, name='requisition_delete'),
    path('requisitions/<int:requisition_id>/items/create/', views.requisition_item_create, name='requisition_item_create'),
    path('requisitions/<int:requisition_id>/fulfill/', views.requisition_fulfill, name='requisition_fulfill'),
    path('requisitions/<int:requisition_id>/cancel/', views.requisition_cancel, name='requisition_cancel'),

    # Invoices
    path('invoices/', views.invoices_list, name='invoices_list'),
    path('invoices/new/', views.invoice_create, name='invoice_create'),
    path('invoices/bulk-delete/', views.invoices_bulk_delete, name='invoices_bulk_delete'),
    path('invoices/bulk-mark-paid/', views.invoices_bulk_mark_paid, name='invoices_bulk_mark_paid'),
    path('invoices/<int:invoice_id>/', views.invoice_details, name='invoice_details'),
    path('invoices/<int:invoice_id>/edit/', views.invoice_edit, name='invoice_edit'),
    path('invoices/<int:invoice_id>/delete/', views.invoice_delete, name='invoice_delete'),
    path('invoices/<int:invoice_id>/mark-paid/', views.invoice_mark_paid, name='invoice_mark_paid'),
    path('invoices/<int:invoice_id>/duplicate/', views.invoice_duplicate, name='invoice_duplicate'),
    path('invoices/<int:invoice_id>/receive/', views.receive_invoice_items, name='receive_invoice_items'),
    path('invoices/<int:invoice_id>/line-items/new/', views.invoice_line_item_create, name='invoice_line_item_create'),
    path('invoices/<int:invoice_id>/line-items/<int:line_item_id>/edit/', views.invoice_line_item_edit, name='invoice_line_item_edit'),
    path('invoices/<int:invoice_id>/line-items/<int:line_item_id>/delete/', views.invoice_line_item_delete, name='invoice_line_item_delete'),

    # Locations
    path('locations/', views.locations_list, name='locations_list'),
    path('locations/new/', views.location_create, name='location_create'),
    path('locations/bulk-delete/', views.locations_bulk_delete, name='locations_bulk_delete'),
    path('locations/<int:location_id>/', views.location_details, name='location_details'),
    path('locations/<int:location_id>/edit/', views.location_edit, name='location_edit'),
    path('locations/<int:location_id>/delete/', views.location_delete, name='location_delete'),

    # Departments
    path('departments/', views.departments_list, name='departments_list'),
    path('departments/new/', views.department_create, name='department_create'),
    path('departments/bulk-delete/', views.departments_bulk_delete, name='departments_bulk_delete'),
    path('departments/<int:department_id>/', views.department_details, name='department_details'),
    path('departments/<int:department_id>/edit/', views.department_edit, name='department_edit'),
    path('departments/<int:department_id>/delete/', views.department_delete, name='department_delete'),

    # Vendors
    path('vendors/', views.vendors_list, name='vendors_list'),
    path('vendors/new/', views.vendor_create, name='vendor_create'),
    path('vendors/bulk-delete/', views.vendors_bulk_delete, name='vendors_bulk_delete'),
    path('vendors/<int:vendor_id>/', views.vendor_details, name='vendor_details'),
    path('vendors/<int:vendor_id>/edit/', views.vendor_edit, name='vendor_edit'),
    path('vendors/<int:vendor_id>/delete/', views.vendor_delete, name='vendor_delete'),

    # Companies
    path('companies/', views.companies_list, name='companies_list'),
    path('companies/new/', views.company_create, name='company_create'),
    path('companies/bulk-delete/', views.companies_bulk_delete, name='companies_bulk_delete'),
    path('companies/<int:company_id>/', views.company_details, name='company_details'),
    path('companies/<int:company_id>/edit/', views.company_edit, name='company_edit'),
    path('companies/<int:company_id>/delete/', views.company_delete, name='company_delete'),

    # Categories
    path('categories/', views.categories_list, name='categories_list'),
    path('categories/new/', views.category_create, name='category_create'),
    path('categories/bulk-delete/', views.categories_bulk_delete, name='categories_bulk_delete'),
    path('categories/<int:category_id>/', views.category_details, name='category_details'),
    path('categories/<int:category_id>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:category_id>/delete/', views.category_delete, name='category_delete'),

    # Spare Parts Inventory
    path('spare-parts/', views.spare_parts_list, name='spare_parts_list'),
    path('spare-parts/new/', views.spare_part_create, name='spare_part_create'),
    path('spare-parts/bulk-delete/', views.spare_parts_bulk_delete, name='spare_parts_bulk_delete'),
    path('spare-parts/<int:spare_part_id>/', views.spare_part_details, name='spare_part_details'),
    path('spare-parts/<int:spare_part_id>/edit/', views.spare_part_edit, name='spare_part_edit'),
    path('spare-parts/<int:spare_part_id>/delete/', views.spare_part_delete, name='spare_part_delete'),

    # Maintenance Records
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('maintenance/new/', views.maintenance_create, name='maintenance_create'),
    path('maintenance/bulk-delete/', views.maintenance_bulk_delete, name='maintenance_bulk_delete'),
    path('maintenance/<int:record_id>/', views.maintenance_details, name='maintenance_details'),
    path('maintenance/<int:record_id>/edit/', views.maintenance_edit, name='maintenance_edit'),
    path('maintenance/<int:record_id>/delete/', views.maintenance_delete, name='maintenance_delete'),

    # Requisition Items (delete only — items are managed from the requisition details page)
    path('requisition-items/<int:item_id>/delete/', views.requisition_item_delete, name='requisition_item_delete'),
]
