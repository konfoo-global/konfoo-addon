Konfoo
======

Konfoo integration


Configuration
-------------

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


Extending for other models
--------------------------

Currently, this is limited to models that have the parent + lines structure,
for instance `sale.order` and `sale.order.line`.

In the form view of the parent model you can add the konfoo widget like this:

```xml
<widget name="konfoo" parent="my.model" line="my.model.line" />
```

Additionally, you must implement `konfoo_options` API on the line model like this (again `sale.order.line` as example):

```python
@api.model
def konfoo_options(self):
    return dict(
        quantity='product_uom_qty',
        uom='product_uom',
        product_id='product_id',
        parent_id='order_id',
    )
```

If you do not need a parameter to be set then the value can be `None` or the key omitted from this dict.


Changelog
---------

- 1.10.0
    - Ability to receive `meta` product field values as translation dict
- 1.9.0
    - Ability to use Konfoo in other models besides `sale.order`
- 1.8.1
    - Fix regression in tests for 18 / edge
    - Correct import path for `SENTINEL` in `DynamicSelection`
    - Support Odoo `json` -> `jsonrpc` route type change
    - Remove deprecated `inline` target from menu actions
- 1.8.0
    - Added `update_if_exists` option to `meta` block
- 1.7.3
    - Correct view overrides for 15/16 versions
- 1.7.2
    - Add ability to read objects and reference them via Konfoo aggregator rules
    - Remove match case statements for backwards compatibility
- 1.7.1
    - Updates to Estonian translations
    - Fixes a potentially colliding setting title (Client ID)
- 1.7.0
    - Port to 18.0
- 1.6.0
    - Add ability to update objects and make RPC calls via Konfoo aggregator rules
- 1.5.2
    - Make app visible only to Konfoo user & admin groups
- 1.5.1
    - Cron `numbercall` and `doall` fields removed in Odoo >17.0
- 1.5.0
    - Added backwards compatibility support for Odoo 15.0
    - Fix: edit button shown for lines without konfoo session
    - Split KonfooButton and KonfooEditButton components into separate files
    - Forked 16.0 compatibly components from mainline component
- 1.4.3
    - Mitigate record not updated properly in 16.0 when calling `record.load()`
- 1.4.2
    - Minor improvements to legacy settings view layout
- 1.4.1
    - Fix regression in 17.0 where Konfoo button was disabled even after the Sale Order was saved
- 1.4.0
    - Handle Konfoo endpoint connection errors more gracefully
    - Add a very simple configuration import/export system
- 1.3.1
    - Add a Settings shortcut to Konfoo application
    - Clean up deprecated data
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
