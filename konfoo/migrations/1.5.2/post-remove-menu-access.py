def migrate(cr, version):
    cr.execute("""
    DELETE FROM ir_ui_menu_group_rel
    WHERE
        menu_id IN (
            SELECT res_id
            FROM ir_model_data
            WHERE
                model = 'ir.ui.menu'
            AND name = 'konfoo_datasets_menu'
            AND module = 'konfoo'
        )
    AND gid IN (
            SELECT res_id
            FROM ir_model_data
            WHERE
                model = 'res.groups'
            AND name = 'group_user'
            AND module = 'base'
        )
    """)
