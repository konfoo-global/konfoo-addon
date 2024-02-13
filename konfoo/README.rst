======
Konfoo
======

Konfoo integration


Configuration
=============

- Configuration parameters can be accessed from Settings -> Konfoo
- The configuration parameters are different for STAGING and LIVE environments.
    - Live parameters are only used in the odoo.sh production branch.
    - An environment is considered production if `ODOO_STAGE` environment variable has the value `production`.
- The configuration parameters:
    - Konfoo URL - URL to the Konfoo environment **without trailing slash**
    - Client ID - the shared secret used for Konfoo embed widget
    - Sync Host - the URL for the Konfoo data store
    - Sync Key - key for the Konfoo data store
    - Default UOM - (optional) Default UoM if it differs from "Units".
    - Product lookup field - (optional) Field used for product lookup. Defaults to `default_code`.
    - Sync batch size - The maximum number of records synced in one batch. If not specified 100 is used.


Changelog
=========

- 1.3.0
    - Improved dynamic selection widget implementation. Previous approach no longer worked due to optimizations in 17.0.
- 1.2.4
    - Re-hide invisible columns in 17.0
- 1.2.3
    - Fixes more compatibility issues in 17.0
- 1.2.2
    - Fix issue in 17.0/edge where Konfoo did not pass `record_id` correctly
- 1.2.1
    - Fix issue in 17.0/edge where Konfoo button widget was always in a disabled state
- 1.2.0
    - Metadata: added `product_name_delimiter` option to control the string used to concatenate sale order name and product name. Defaults is a single space (`' '`).
- 1.1.1
    - 16.0 to LTS
- 1.1.0
    - Odoo edge overrides development harness
    - Metadata: `use_parent_name_prefix` option - when false the SO name is not prepended to product name
    - Metadata: adds `line` (just like `parent`) for setting parameters on the `sale.order.line` object
- 1.0.4
    - Fixes an issue where newly created sale order was reloaded incorrectly after finishing configuration
- 1.0.3
    - Fixes an issue where previously edited configuration ID in some cases remained active when starting a new session
- 1.0.2
    - Handle OWL props weirdness when button widget is used inside a tree view line
- 1.0.1
    - Make Konfoo widgets work with both Odoo 16.0 and 16.3 (master) Widgets
- 1.0.0
    - Rewrite of client using OWL 2 Components
- 0.11.1
    - Update dataset reload URL
- 0.11.0
    - Automatic remote datasets reload upon sync
- 0.10.0
    - Multi-company support
- 0.9.3
    - Autofill dataset field name when selecting model field from dropdown
    - Parent properties test to be compatible with version 14.0
    - Add sale order line as a default allowed model
    - Clean up KonfooWidget to make backporting to version 14.0 simpler
- 0.9.2
    - More logging for troubleshooting failed record lookups
- 0.9.1
    - Restore default UOM setting
    - Update translations
- 0.9.0
    - Support setting parent object properties and referencing parent object fields when creating objects
- 0.8.9
    - Product supplier info is copied with template products
- 0.8.8
    - Port to Odoo 16
- 14.0.0.5.0 (2022-05-13)
    - Add: option to configure staging and production credentials independently
- 14.0.0.4.2 (2022-04-25)
    - Fix: optional static fields not handled correctly
- 14.0.0.4.1 (2022-03-03)
    - Fix: regression in setting the configured products name
- 14.0.0.4.0 (2022-03-03)
    - Add: BOM system that can directly reference odoo fields
    - Add: creating operations from BOM rules
- 14.0.0.3.0 (2022-03-03)
    - Add: duplicating existing configured product
- 14.0.0.2.1 (2022-03-02)
    - Fix: Missing translations
    - Fix: Invalid access to field in _compute_konfoo_session_id
- 14.0.0.2.0 (2022-03-02)
    - Add: Reconfiguring existing configured products
- 14.0.0.1.2 (2022-03-01)
    - Fix: update BOM cost and purchase price automatically
- 14.0.0.1.1 (2022-02-26)
    - Sale order and BOM creation from Konfoo
- 14.0.0.0.0 (2022-02-01)
    - Initial version
