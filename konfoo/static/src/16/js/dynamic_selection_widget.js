/** @odoo-module **/
// noinspection DuplicatedCode

import { registry } from "@web/core/registry";
import { SelectionField } from "@web/views/fields/selection/selection_field";
const { useState } = owl;

export class DynamicSelectionField extends SelectionField {
    async setup() {
        this.state = useState({
            dynamicOptions: [],
        });

        this.type = this.props.record.fields[this.props.name].type;

        const selection = this.props.record.fields[this.props.name].selection;
        if (!selection || selection.length !== 1) {
            return;
        }

        const [ magic, method ] = selection[0];
        if (magic !== 'selection_dynamic') {
            return;
        }

        this.state.dynamicOptions = await this.props.record.model.orm.call(
            this.props.record.resModel,
            method,
            [],
            { context: this.props.record.context },
        );
    }

    get options() {
        return this.state.dynamicOptions;
    }
}

DynamicSelectionField.props = {
    ...SelectionField.props,
};

registry.category("fields").add("dynamic-selection", DynamicSelectionField);
