/** @odoo-module **/
// noinspection DuplicatedCode

import { registry } from '@web/core/registry';
import { useBus, useService } from '@web/core/utils/hooks';
import { rpc } from '@web/core/network/rpc';
import { standardWidgetProps } from '@web/views/widgets/standard_widget_props';
import { useEffect } from "@odoo/owl";

// It is quite inconvenient that `odoo.info` is not available at this point.
import { Widget } from '@web/views/widgets/widget';
const isModernComponentInterface = ('props' in Widget && '*' in Widget.props && Widget.props['*'] === true);

const KONFOO_VERBOSE = false;

export class KonfooComponent extends owl.Component {
    static props = {
        ...standardWidgetProps,
        parentModel: { type: String, optional: true },
        lineModel: { type: String, optional: true },
    };
    static template = owl.xml`
        <div t-if="state.isOpen" class="o_konfoo_container">
            <iframe class="o_konfoo_iframe" t-att-src="state.config.url" t-on-load="onLoad"></iframe>
        </div>
    `;

    setup() {
        if (KONFOO_VERBOSE)
            console.log('[odoo-konfoo] component setup');

        super.setup()

        this.notifications = useService('notification');
        this.props.parentModel = this.props.parentModel || 'sale.order';
        this.props.lineModel = this.props.lineModel || 'sale.order.line';

        this.state = owl.useState({
            isOpen: false,
            config: null,
            iframe: null,
            record_id: null,
            session_key: null,
        });

        useBus(this.env.bus, 'KONFOO_OPEN', event => {
            if (!this.state.config || !this.state.config.url) {
                this.notifications.add('Konfoo not configured', {
                    type: 'danger',
                    title: 'Konfoo',
                });
                return;
            }

            const data = event.detail;
            if (data && data.konfoo_session_key) {
                this.state.session_key = data.konfoo_session_key;
                if (KONFOO_VERBOSE)
                    console.log('[odoo-konfoo] set session key: %s', this.state.session_key);
            }
            else {
                this.state.session_key = null;
                if (KONFOO_VERBOSE)
                    console.log('[odoo-konfoo] unset session key')
            }
            this.open();
        });

        useEffect(
            () => {
                const handler = this.onMessage.bind(this);
                if (KONFOO_VERBOSE) console.log('[odoo-konfoo] effect: adding listener');
                window.addEventListener('message', handler);

                // Return a clean-up function
                return () => {
                    if (KONFOO_VERBOSE) console.log('[odoo-konfoo] effect: removing listener');
                    window.removeEventListener('message', handler);
                };
            },
            () => [] // Only run once when the component is mounted
        );

        owl.onWillUnmount(() => {
            if (KONFOO_VERBOSE)
                console.log('[odoo-konfoo] unmounting');
        });

        owl.onWillUpdateProps(() => {
            this.updateState();
        });

        this.updateState();

        owl.onWillStart(async () => {
            if (KONFOO_VERBOSE)
                console.log('[odoo-konfoo] component start');

            const clientConfig = await rpc('/konfoo-client');
            if ('ok' in clientConfig && clientConfig.ok === true) {
                this.state.config = clientConfig;
            }
            else if ('error' in clientConfig) {
                this.notifications.add(clientConfig.error, {
                    type: 'danger',
                    title: 'Konfoo',
                });
            }
        });
    }

    onMessage(e) {
        if (this.__owl__.status < 3 && this.__owl__.status !== 1) {
            console.log('[odoo-konfoo] onMessage: status = ', this.__owl__.status, ' (not 1 or 3), ignoring message');
            return;
        }

        if (!this.state.config) {
            return;
        }

        if (KONFOO_VERBOSE)
            console.log('[odoo-konfoo] recv:', e.origin, e.data, event.origin);

        if (e.origin !== this.state.config.url) {
            return; // ignore other origins
        }

        if (typeof(e.data) !== 'object' || e.data.type !== 'konfoo') {
            return;
        }

        const self = this;

        switch (e.data.cmd) {
            case 'hello':
                e.source.postMessage({
                    type: 'konfoo',
                    cmd: 'auth',
                    params: { key: this.state.config.client_id },
                }, e.origin);
                break;
            case 'start':
                if (KONFOO_VERBOSE)
                    console.log('[odoo-konfoo] start:', e.data.params);
                break;
            case 'discard':
                if (KONFOO_VERBOSE)
                    console.log('[odoo-konfoo] discard');
                this.close();
                break;
            case 'finish':
                if (KONFOO_VERBOSE)
                    console.log('[odoo-konfoo] finish:', e.data.params);

                this.updateState();
                if (!this.state.record_id) {
                    this.notifications.add('Please save the document before clicking Finish in Konfoo.', {
                        type: 'warning',
                        title: 'Konfoo',
                    });
                    return;
                }

                rpc('/konfoo/create', {
                    res_id: this.state.record_id,
                    session: e.data.params.session,
                    parent_model: this.props.parentModel,
                    line_model: this.props.lineModel,
                })
                .then(function (_response) {
                    if (KONFOO_VERBOSE)
                        console.log('[odoo-konfoo] Create OK');

                    self.close();
                    if (self.props && self.props.record) {
                        console.log('calling props.record.load()')
                        return self.props.record.load();
                    }
                    console.log('didnt call props.record.load()')
                })
                .then(function() {
                    console.log('got to here after props.record.load()')
                    if (KONFOO_VERBOSE)
                        console.log('[odoo-konfoo] Update OK');
                })
                .catch(function (err) {
                    if (KONFOO_VERBOSE)
                        console.log('[odoo-konfoo] Error on finish:', JSON.stringify(err));

                    if (typeof(err) === 'object' && err.data) {
                        self.notifications.add(err.data.message, {
                            type: 'danger',
                            title: 'Konfoo',
                            sticky: true,
                        });
                    }
                    else {
                        self.notifications.add(err, {
                            type: 'danger',
                            title: 'Konfoo',
                            sticky: true,
                        });
                    }
                });
                break;
            default:
                break;
        }
    }

    updateState() {
        this.state.record_id = this.getActiveId();
        if (KONFOO_VERBOSE)
            console.log('[odoo-konfoo] update state: record_id = %s', this.state.record_id);
    }

    onLoad(event) {
        this.state.iframe = event.target;
        if (KONFOO_VERBOSE)
            console.log('[odoo-konfoo] iframe loaded: %s', this.state.iframe ? 'OK' : 'NOT OK');

        if (!this.state.iframe) {
            return;
        }

        this.state.iframe.classList.add('o_konfoo_loaded');

        this.state.iframe.contentWindow.postMessage({
            type: 'konfoo',
            cmd: 'hello',
            params: {
                origin: window.origin,
                session: this.state.session_key,
            },
        }, this.state.config.url);
    }

    open() {
        this.state.isOpen = true;
    }

    close() {
        this.state.isOpen = false;
    }

    getActiveId() {
        if (!this.props || !this.props.record) {
            return null;
        }

        // Odoo >= 18.0 (preferred)
        if (this.props.record.evalContext && this.props.record.evalContext.id) {
            return this.props.record.evalContext.id;
        }

        // Odoo <= 16.0
        if (this.props.record.data && 'id' in this.props.record.data && this.props.record.data.id) {
            return this.props.record.data.id;
        }

        // Odoo >= 17.0
        if (this.props.record.evalContext && this.props.record.evalContext.active_id) {
            return this.props.record.evalContext.active_id;
        }
    }
}

if (isModernComponentInterface) {
    registry.category('view_widgets').add('konfoo', {
        component: KonfooComponent,
        extractProps: ({ attrs }) => {
            const { parent, line } = attrs;
            return {
                parentModel: parent,
                lineModel: line,
            };
        }
    });
}
else {
    registry.category("view_widgets").add("konfoo", KonfooComponent);
}
