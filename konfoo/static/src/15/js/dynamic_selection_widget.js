/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import BasicModel from 'web.BasicModel';
import fieldRegistry from 'web.field_registry';
import relationalFields from 'web.relational_fields';

const FieldSelection = relationalFields.FieldSelection;


BasicModel.include({
    /**
     * @private
     * @param {Object} record
     * @param {string} fieldName
     * @returns {Promise}
     */
    _fetchSpecialDynamicSelection: function (record, fieldName) {
        if (!(fieldName in record.fields)) {
            return Promise.resolve();
        }

        const selection = record.fields[fieldName].selection;
        if (!selection || selection.length !== 1) {
            return Promise.resolve();
        }

        const [ magic, method ] = selection[0];
        if (magic !== 'selection_dynamic') {
            return Promise.resolve();
        }

        return this._rpc({
            model: record.model,
            method: method,
            args: [],
            context: record.context,
        });
    },
});

const DynamicSelectionField = FieldSelection.extend({
    description: _t('Dynamic Selection'),
    specialData: '_fetchSpecialDynamicSelection',
    supportedFieldTypes: ['selection'],

    getDynamicOptions: function () {
        if (!(this.name in this.record.fields)) {
            return null;
        }

        const selection = this.record.fields[this.name].selection;
        if (!selection || selection.length !== 1) {
            return null;
        }

        const [ magic, _ ] = selection[0];
        if (magic !== 'selection_dynamic') {
            return null;
        }

        return this.record.specialData[this.name];
    },

    /**
     * @override
     */
    _setValues: function () {
        const opts = this.getDynamicOptions();
        if (opts) {
            this.values = [[false, this.attrs.placeholder || '']].concat(opts);
            return;
        }

        this._super.apply(this, arguments);
    },
});

fieldRegistry.add('dynamic-selection', DynamicSelectionField);
