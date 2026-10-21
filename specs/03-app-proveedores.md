# SPEC 03 — App Proveedores y estado de cuenta de proveedores

> **Estado:** Aprobado
> **Depende de:** SPEC 01, SPEC 02
> **Fecha:** 2026-10-21
> **Objetivo:** Una app "Proveedores" (módulo `supplier_management`) que reúne listado, estado de cuenta, comprobantes, pagos y órdenes de compra de proveedores, reutilizando el estado de cuenta de clientes generalizado a cuentas a pagar.

## Por qué existe esta spec

La SPEC 01 dejó fuera las cuentas a pagar, y la SPEC 02 armó la app Clientes.
Falta lo mismo para proveedores: ver cuánto se le debe a cada uno, imputar pagos y notas de crédito a sus facturas y mandarle el resumen para conciliar saldos.

El estado de cuenta de clientes ya resuelve casi todo (consolidado multiempresa, casillas que recalculan, pendientes, imputación parcial, PDF y email).
Hoy tiene fijas las cuentas `asset_receivable`, los textos de cliente y los permisos de Facturación y vendedores.
En lugar de copiarlo, esta spec lo generaliza con un tipo de cuenta (cliente / proveedor) y la app nueva lo usa en modo proveedor.

La spec agrupa dos frentes: la generalización (en `customer_account_statement`) y la app nueva (en `supplier_management`).
La carga automatizada de facturas de proveedor tiene su lugar reservado en el menú de la app, pero se define en otra spec.

## Alcance

**Incluye:**

*Estado de cuenta (`customer_account_statement`, generalización):*

- Campo `partner_type` (Cliente / Proveedor) en el estado de cuenta, por defecto Cliente. Todo lo existente sigue funcionando igual en modo Cliente.
- En modo Proveedor:
  - Apuntes en cuentas `liability_payable` en lugar de `asset_receivable`.
  - Signo contable, igual que en clientes: saldo = Debe − Haber. Las facturas del proveedor van al Haber y lo que se le debe sale **negativo**. Los pagos y las NC del proveedor van al Debe.
  - Modo Movimientos y modo Solo pendientes, con las casillas de empresas y el recálculo automático de la SPEC 02.
  - Textos de proveedor en pantalla, PDF y email: "Proveedor" en lugar de "Cliente" y "Pago" en lugar de "Recibo".
  - Imputar: elegir un pago o una NC del proveedor con saldo e imputarlo a una o varias facturas/ND del proveedor, con importe por factura (mismas reglas de moneda que la SPEC 01).
  - Desimputar desde la lista de imputaciones.
  - PDF "Resumen de cuenta de proveedor" y envío por email con plantilla propia, registrado en el chatter del proveedor.
- Los controles de permisos (consultar, imputar, desimputar, enviar) pasan a métodos que otros módulos pueden extender. `customer_account_statement` no depende de Compras.
- Botón "Cuenta proveedor" en la ficha del contacto, visible si `supplier_rank > 0`, separado del botón "Estado de cuenta" (cliente). Cada uno muestra solo su cuenta.
- Menú Facturación > Proveedores > Estado de cuenta.
- En `customer_account_statement`, el modo Proveedor lo usa solo Facturación (`account.group_account_invoice`).

*App Proveedores (`supplier_management`, módulo nuevo):*

- App "Proveedores" en el menú principal, con ícono, visible para Facturación y Compras (`purchase.group_purchase_user`).
- Menús de la app:
  - **Proveedores:** listado de proveedores con filtros.
  - **Estado de cuenta:** abre el asistente en modo Proveedor.
  - **Facturas y notas:** facturas, NC y ND de proveedor.
  - **Pagos realizados:** pagos a proveedores.
  - **Comprobantes vencidos:** facturas y ND de proveedor publicadas, con saldo pendiente y vencidas.
  - **Órdenes de compra:** órdenes de compra estándar de Compras.
  - **Carga automática de facturas:** lugar reservado. No se crea en esta spec (ver Fuera de alcance).
  - **Configuración > Ajustes:** sección de ajustes de la app.
- Listado de Proveedores:
  - Columnas: Nombre, CUIT, Empresas en las que participa, Ciudad, Provincia, Teléfono, Email.
  - Filtros: Proveedores (`supplier_rank > 0`, activo por defecto y quitable), Con deuda, Con vencidos.
  - Búsqueda y agrupación por Empresas en las que participa, Ciudad y Provincia.
  - Sin columna de saldo: puede haber varias monedas, igual que en clientes.
- Usuarios de Compras sin Facturación:
  - Siempre pueden consultar e imprimir el estado de cuenta de **todos** los proveedores.
  - Pueden imputar, desimputar y enviar por email según tres casillas de Ajustes, tildadas por defecto.
  - No ven ni pueden usar el estado de cuenta de clientes por esta app.
- Ajustes (sección "Proveedores", solo administradores), globales para todas las empresas:
  - "Compras puede imputar".
  - "Compras puede desimputar".
  - "Compras puede enviar el estado de cuenta por email".
- Reglas de lectura propias para que Compras pueda abrir los pagos a proveedores y sus asientos desde el estado de cuenta.

**Fuera de alcance (para futuras specs):**

- Carga automatizada de facturas de proveedor (el menú, su acción y todo su comportamiento).
- Comprador asignado al proveedor y ajuste "Compras ve solo sus proveedores".
- Estado de cuenta combinado cliente + proveedor de un mismo contacto.
- Columna de saldo en el listado de Proveedores.
- Ajustes de permisos por empresa.
- Órdenes de pago, retenciones y certificados de retención.
- Antigüedad de saldos por tramos.
- Envío masivo o programado de resúmenes.
- Renombrar `customer_account_statement` o sus modelos.
- Tests automáticos.

## Modelo de datos

### `customer_account_statement` (cambios)

```python
# wizard/account_statement_wizard.py
PARTNER_TYPES = [
    ('customer', 'Cliente'),
    ('supplier', 'Proveedor'),
]

ACCOUNT_TYPES = {
    'customer': 'asset_receivable',
    'supplier': 'liability_payable',
}


class CustomerAccountStatement(models.TransientModel):
    _name = 'customer.account.statement'

    partner_type = fields.Selection(
        PARTNER_TYPES, string='Tipo', required=True, default='customer')
    # partner_id: la etiqueta de la vista cambia según partner_type ("Cliente" / "Proveedor").

    # _get_base_domain usa ACCOUNT_TYPES[self.partner_type].
    # _get_document_type devuelve 'Pago' en lugar de 'Recibo' si partner_type = 'supplier'.

    # Puntos de extensión de permisos (supplier_management los extiende):
    @api.model
    def _check_partner_access(self, partner, partner_type='customer'): ...
    @api.model
    def _can_reconcile(self, partner_type): ...    # hoy: group_account_invoice
    @api.model
    def _can_unreconcile(self, partner_type): ...  # hoy: group_account_invoice
    @api.model
    def _can_send(self, partner_type): ...         # hoy: group_account_invoice

    can_reconcile = fields.Boolean(compute='_compute_permissions')    # para ocultar botones en la vista
    can_unreconcile = fields.Boolean(compute='_compute_permissions')
    can_send = fields.Boolean(compute='_compute_permissions')
```

```python
# wizard/account_statement_reconcile.py
class CustomerAccountStatementReconcile(models.TransientModel):
    _name = 'customer.account.statement.reconcile'

    partner_type = fields.Selection(related='statement_id.partner_type')
    # credit_line_id pasa a ser el "origen" de la imputación:
    #   customer: recibo/NC con amount_residual < 0, cuenta asset_receivable (como hoy).
    #   supplier: pago/NC de proveedor con amount_residual > 0, cuenta liability_payable.
    # available_amount = abs(credit_line_id.amount_residual).
```

```python
# wizard/account_statement_reconcile.py (líneas)
class CustomerAccountStatementReconcileLine(models.TransientModel):
    _name = 'customer.account.statement.reconcile.line'

    # debit_line_id pasa a ser el "destino" de la imputación:
    #   customer: factura/ND con amount_residual > 0 (como hoy).
    #   supplier: factura/ND de proveedor con amount_residual < 0.
    # amount_residual y amount_to_apply se guardan siempre en valor absoluto.
```

`_reconcile_partial_amount` limita el residual del apunte **destino** al importe pedido.
En cliente el destino es el apunte con saldo deudor.
En proveedor es el apunte con saldo acreedor, así que el residual limitado es `-amount`.

Nuevos IDs XML:

- `customer_account_statement.action_supplier_account_statement` (asistente con `context="{'default_partner_type': 'supplier'}"`).
- `customer_account_statement.menu_supplier_account_statement` (bajo `account.menu_finance_payables`).
- `customer_account_statement.mail_template_supplier_account_statement` (modelo `res.partner`).
- Se reutiliza `action_report_customer_account_statement`: el título y los textos del PDF cambian según `partner_type`.

```python
# models/res_partner.py
class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_open_supplier_account_statement(self): ...  # abre el asistente con partner_type='supplier'
```

### `supplier_management` (nuevo)

Ruta: `C:\Users\Daniel\Archivos\custom_addons\supplier_management`.

```python
# __manifest__.py (extracto)
{
    'name': 'Proveedores',
    'version': '1.0',
    'category': 'Purchases',
    'author': 'Daniel',
    'depends': ['customer_account_statement', 'purchase'],
    'application': True,
    'license': 'LGPL-3',
}
```

```python
# models/res_config_settings.py
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    purchase_can_reconcile = fields.Boolean(
        string='Compras puede imputar',
        config_parameter='supplier_management.purchase_can_reconcile')
    purchase_can_unreconcile = fields.Boolean(
        string='Compras puede desimputar',
        config_parameter='supplier_management.purchase_can_unreconcile')
    purchase_can_send = fields.Boolean(
        string='Compras puede enviar el estado de cuenta por email',
        config_parameter='supplier_management.purchase_can_send')
```

```xml
<!-- data/ir_config_parameter_data.xml: casillas tildadas al instalar -->
<odoo noupdate="1">
    <record id="config_purchase_can_reconcile" model="ir.config_parameter">
        <field name="key">supplier_management.purchase_can_reconcile</field>
        <field name="value">True</field>
    </record>
    <!-- ídem purchase_can_unreconcile y purchase_can_send -->
</odoo>
```

```python
# wizard/account_statement_wizard.py
class CustomerAccountStatement(models.TransientModel):
    _inherit = 'customer.account.statement'

    # _check_partner_access: en modo supplier, también deja pasar a purchase.group_purchase_user.
    # _can_reconcile / _can_unreconcile / _can_send: en modo supplier, también True para
    # purchase.group_purchase_user si el ir.config_parameter correspondiente es 'True'.
```

```python
# models/res_partner.py
class ResPartner(models.Model):
    _inherit = 'res.partner'

    has_payable_debt = fields.Boolean(
        string='Con deuda', compute='_compute_payable_flags', search='_search_has_payable_debt')
    has_overdue_payable = fields.Boolean(
        string='Con vencidos', compute='_compute_payable_flags', search='_search_has_overdue_payable')
```

Convenciones:

- **Apuntes de proveedor:** `account.move.line` con `account_id.account_type = 'liability_payable'`, `parent_state = 'posted'`, `partner_id` hijo del `commercial_partner_id` y `company_id` en las empresas permitidas.
- **Empresas permitidas:** la misma regla de la SPEC 02 ("Empresas en las que participa" ∩ empresas habilitadas del usuario; vacío = todas las del usuario).
- **Signo:** saldo = Debe − Haber, en moneda de la empresa. Negativo = se le debe al proveedor. Positivo = saldo a favor (anticipos o NC sin aplicar).
- **Con deuda:** en alguna moneda de empresa, la suma de `amount_residual` de los apuntes a pagar del proveedor es menor que cero.
- **Con vencidos:** el proveedor tiene al menos un apunte a pagar publicado con `amount_residual < 0` y `date_maturity < hoy`. Los pagos y las NC con saldo no cuentan como vencidos.
- **Días de atraso** en modo Solo pendientes: igual que en clientes (`date_to - date_maturity`, 0 si no venció), solo para facturas y ND.
- **Usuario de Compras sin Facturación:** tiene `purchase.group_purchase_user` y no tiene `account.group_account_invoice`.
- Las casillas se leen con `ir.config_parameter.get_param(...) == 'True'`. Si un administrador la destilda, Odoo borra el parámetro y la casilla queda en falso.
- Cuando Compras imputa o desimputa con la casilla tildada, la operación se hace con `sudo()` después de verificar el permiso. Compras no tiene permiso estándar sobre los asientos de pago ni para borrar `account.partial.reconcile`.
- Los menús de la app son acciones de ventana comunes: no hay filtro por usuario, así que no hacen falta acciones de servidor.

Reglas de lectura nuevas para `purchase.group_purchase_user` (en `supplier_management/security/ir.access.csv`):

- `account.payment` con `[('partner_type', '=', 'supplier')]`.
- `account.move` con `[('origin_payment_id.partner_type', '=', 'supplier')]` (asientos de pagos a proveedores).
- Accesos a los modelos transitorios del estado de cuenta (`customer.account.statement`, `.line`, `.currency`, `.reconcile`, `.reconcile.line`).

Facturas de proveedor, apuntes e imputaciones ya los da Compras estándar (ver `purchase/security/ir.access.csv`).

Archivos del módulo nuevo:

```text
supplier_management/
├── __init__.py
├── __manifest__.py
├── README.md
├── data/
│   └── ir_config_parameter_data.xml
├── models/
│   ├── __init__.py
│   ├── res_config_settings.py
│   └── res_partner.py
├── wizard/
│   ├── __init__.py
│   └── account_statement_wizard.py     # extiende los controles de permisos
├── views/
│   ├── res_partner_views.xml           # lista, búsqueda y acción del listado de Proveedores; botón para Compras
│   ├── account_views.xml               # acciones de Facturas y notas, Pagos realizados, Comprobantes vencidos
│   ├── res_config_settings_views.xml   # sección "Proveedores" en Ajustes
│   └── menus.xml
├── security/
│   └── ir.access.csv
└── static/description/icon.png
```

IDs XML principales:

- `supplier_management.menu_supplier_management_root` (app "Proveedores", con `web_icon`).
- `supplier_management.action_supplier_management_suppliers` (listado de Proveedores).
- `supplier_management.action_supplier_management_invoices`, `..._payments`, `..._overdue`.
- Órdenes de compra: el menú usa `purchase.purchase_form_action`.
- Estado de cuenta: el menú usa `customer_account_statement.action_supplier_account_statement`.
- `supplier_management.action_supplier_management_settings` (Ajustes con `context="{'module': 'supplier_management'}"`).
- **Reservado** para la carga automática de facturas: `supplier_management.menu_supplier_management_bill_import`, entre "Órdenes de compra" y "Configuración". No se crea en esta spec.

## Plan de implementación

1. En `customer_account_statement`, agregar `partner_type` (default `customer`) y usar `ACCOUNT_TYPES` en `_get_base_domain`. Prueba manual: el estado de cuenta de un cliente da las mismas cifras que antes del cambio.
2. Crear `action_supplier_account_statement` y el menú Facturación > Proveedores > Estado de cuenta. Ajustar los textos de la vista según `partner_type` ("Proveedor", "Pago"). Prueba manual: con un proveedor con facturas y pagos, el saldo final es Debe − Haber de sus apuntes a pagar y sale negativo si se le debe.
3. Verificar el modo Solo pendientes y el consolidado en modo Proveedor. Prueba manual: con una empresa ARS y una USD, "Saldos por moneda" muestra dos filas, y el total pendiente coincide con el saldo final de Movimientos.
4. Agregar el botón "Cuenta proveedor" en la ficha del contacto (visible si `supplier_rank > 0`, grupo Facturación) y `action_open_supplier_account_statement`. Prueba manual: un contacto cliente y proveedor muestra los dos botones, y cada uno abre su cuenta.
5. Pasar los controles de permisos a `_check_partner_access(partner, partner_type)`, `_can_reconcile`, `_can_unreconcile` y `_can_send`. Agregar los campos `can_*` y usarlos en la vista para ocultar los botones. Hacer lo mismo en `action_reconcile`, `action_statement_unreconcile` y `action_send`. Prueba manual: en clientes, Facturación y vendedores ven los mismos botones que antes.
6. Generalizar el asistente de imputación al sentido proveedor (origen pago/NC con residual positivo, destino factura/ND con residual negativo, importes en valor absoluto, parcial limitando el residual del destino). Prueba manual: un pago de 1000 a dos facturas de 600 permite aplicar 600 + 400, y la segunda factura queda con 200 pendientes.
7. Adaptar el PDF (título "Resumen de cuenta de proveedor" y textos según `partner_type`). Crear también `mail_template_supplier_account_statement` y elegir la plantilla según el tipo en `_action_send_mail`. Prueba manual: imprimir y enviar el resumen de un proveedor, y ver el mensaje en su chatter.
8. Actualizar `customer_account_statement/README.md`: qué hace, uso, permisos, sección Base de datos (columna `partner_type`, plantilla, acción y menú nuevos) e historial.
9. Crear el esqueleto de `supplier_management` (manifiesto con `application`, ícono, `ir.access.csv`, menú raíz "Proveedores" visible para `account.group_account_invoice` y `purchase.group_purchase_user`). Prueba manual: la app aparece en el menú principal y se instala con `-i supplier_management` sin errores.
10. Agregar los tres ajustes, `data/ir_config_parameter_data.xml` con los valores en `True`, la sección "Proveedores" en Ajustes y el menú Configuración > Ajustes (solo `base.group_system`). Prueba manual: al instalar, las tres casillas vienen tildadas; destildar una y guardar la deja destildada.
11. Crear el listado de Proveedores (vista lista, búsqueda con filtros y agrupaciones, acción) y su menú. Prueba manual: el filtro "Proveedores" viene activo y se puede quitar.
12. Agregar `has_payable_debt` y `has_overdue_payable` con sus métodos de búsqueda, y los filtros "Con deuda" y "Con vencidos". Prueba manual: los filtros coinciden con el estado de cuenta de dos proveedores de prueba.
13. Crear los menús Estado de cuenta, Facturas y notas, Pagos realizados, Comprobantes vencidos y Órdenes de compra.
14. Dar acceso a Compras:
    - Accesos a los modelos transitorios del estado de cuenta y reglas de lectura sobre `account.payment` y `account.move` de pagos a proveedores.
    - Extender `_check_partner_access` y `_can_*` en `supplier_management/wizard/account_statement_wizard.py`.
    - Mostrar el botón "Cuenta proveedor" también a `purchase.group_purchase_user`.

    Prueba manual: un usuario de Compras sin Facturación consulta, imprime, abre un pago e imputa.
15. Hacer que imputar y desimputar desde Compras se ejecuten con `sudo()` después de verificar la casilla. Prueba manual: con "Compras puede desimputar" destildada, el botón Desimputar no aparece para ese usuario, y llamar al método da error de acceso.
16. Crear `supplier_management/README.md` según `AGENTS.md`, con la sección Base de datos y la mención del menú reservado para la carga automática de facturas.

## Criterios de aceptación

Verificación manual sobre `odoo_prueba` con Compras instalado, al menos dos empresas en ARS y una en USD. Hacen falta un usuario de Facturación, un usuario de Compras sin Facturación, un vendedor sin más permisos y proveedores con facturas, NC y pagos en esas empresas. También hace falta un contacto que sea cliente y proveedor.

**Estado de cuenta de clientes (sin regresiones)**

- [ ] El estado de cuenta de un cliente da las mismas cifras, botones y PDF que antes de instalar los cambios.
- [ ] Un vendedor sigue pudiendo consultar a sus clientes y no ve Imputar, Desimputar ni Enviar por email.

**Estado de cuenta de proveedores**

- [ ] Facturación > Proveedores > Estado de cuenta abre el asistente en modo Proveedor.
- [ ] En modo Movimientos, solo aparecen apuntes publicados de cuentas a pagar del proveedor y sus contactos hijos.
- [ ] Una factura de proveedor de 1000 sin pagar deja el saldo final en −1000.
- [ ] El saldo final es igual al saldo inicial más la suma de Debe menos la suma de Haber del período.
- [ ] Los pagos a proveedores se muestran con tipo "Pago".
- [ ] Con una empresa ARS y una USD tildadas, "Saldos por moneda" muestra dos filas.
- [ ] Destildar una empresa recalcula saldos y movimientos sin apretar ningún botón.
- [ ] En modo Solo pendientes, el total pendiente coincide con el saldo final de Movimientos para la misma fecha "hasta".
- [ ] Un contacto cliente y proveedor muestra los botones "Estado de cuenta" y "Cuenta proveedor". El primero no muestra apuntes a pagar y el segundo no muestra apuntes a cobrar.
- [ ] Un contacto con `supplier_rank = 0` no muestra el botón "Cuenta proveedor".
- [ ] "Imputar" sobre un pago de 1000 con dos facturas de 600 permite aplicar 600 + 400 y deja la segunda factura con 200 pendientes.
- [ ] Un importe mayor al pendiente de la factura, o una suma mayor al disponible del pago, muestra un error y no imputa nada.
- [ ] Si el pago o la factura están en moneda extranjera, el importe no es editable y se imputa por el total posible.
- [ ] "Imputaciones" sobre una factura de proveedor lista los pagos y NC aplicados, y "Desimputar" le devuelve ese pendiente.
- [ ] "Imprimir" genera un PDF titulado "Resumen de cuenta de proveedor", con las mismas cifras que la pantalla.
- [ ] "Enviar por email" abre el compositor con la plantilla de proveedor y el PDF adjunto. Tras enviar, el mensaje queda en el chatter del proveedor.

**App Proveedores**

- [ ] `supplier_management` se instala y desinstala sin errores ni advertencias en el log.
- [ ] La app "Proveedores" aparece para un usuario de Facturación y para uno de Compras, y no aparece para un vendedor sin más permisos.
- [ ] La app tiene los menús Proveedores, Estado de cuenta, Facturas y notas, Pagos realizados, Comprobantes vencidos, Órdenes de compra y Configuración > Ajustes.
- [ ] La app no tiene un menú "Carga automática de facturas".
- [ ] Configuración > Ajustes solo la ve un administrador.
- [ ] El listado muestra las columnas Nombre, CUIT, Empresas en las que participa, Ciudad, Provincia, Teléfono y Email.
- [ ] El filtro "Proveedores" viene activo y se puede quitar.
- [ ] "Con deuda" lista exactamente los proveedores cuyo estado de cuenta (Solo pendientes, todas las empresas permitidas) tiene pendiente negativo en alguna moneda.
- [ ] "Con vencidos" lista exactamente los proveedores con alguna factura o ND con días de atraso mayor a cero en ese estado de cuenta.
- [ ] Se puede agrupar por Empresas en las que participa, Ciudad y Provincia.
- [ ] "Comprobantes vencidos" lista solo facturas y ND de proveedor publicadas con saldo pendiente y vencimiento anterior a hoy.
- [ ] "Pagos realizados" lista solo pagos a proveedores.
- [ ] "Órdenes de compra" abre las órdenes de compra estándar.

**Permisos de Compras**

- [ ] Al instalar, las tres casillas de Ajustes vienen tildadas.
- [ ] Un usuario de Compras sin Facturación consulta e imprime el estado de cuenta de cualquier proveedor.
- [ ] Ese usuario abre un pago a proveedor desde "Abrir comprobante" sin error de acceso.
- [ ] Con las tres casillas tildadas, ese usuario ve y usa Imputar, Desimputar y Enviar por email.
- [ ] Con "Compras puede imputar" destildada, no ve el botón Imputar. Desimputar y Enviar siguen según sus casillas.
- [ ] Con "Compras puede desimputar" destildada, no ve el botón Desimputar.
- [ ] Con "Compras puede enviar el estado de cuenta por email" destildada, no ve el botón Enviar por email.
- [ ] Llamar a imputar, desimputar o enviar con la casilla destildada da error de acceso, aunque el botón esté oculto.
- [ ] Ese usuario recibe un error de acceso si intenta abrir el estado de cuenta de un cliente en modo Cliente.
- [ ] Después de instalar `supplier_management`, ese usuario no puede leer pagos de clientes (`account.payment` con `partner_type = 'customer'`).

**Documentación**

- [ ] `customer_account_statement/README.md` y `supplier_management/README.md` cumplen `AGENTS.md`, con la sección Base de datos y la línea "Base de datos:" en el historial.

## Decisiones

- **Sí:** generalizar `customer_account_statement` con `partner_type` en lugar de copiarlo. Evita duplicar el asistente, la imputación parcial, el PDF y el email.
- **No:** módulos espejo (`supplier_account_statement`) ni copia dentro de `supplier_management`. Habría que mantener dos veces el mismo código, incluido el método interno de imputación parcial.
- **Sí:** conservar los nombres `customer_account_statement` y `customer.account.statement`. Renombrar rompe datos, accesos y vistas existentes por un beneficio solo estético.
- **Sí:** `customer_account_statement` sigue sin depender de Compras. Los permisos de Compras los agrega `supplier_management` extendiendo los métodos de control.
- **Sí:** `supplier_management` depende de `customer_account_statement` y `purchase`, no de `customer_management`. Se puede instalar sin la app Clientes.
- **Sí:** los filtros "Con deuda" y "Con vencidos" se implementan de nuevo en `supplier_management`, siguiendo el de `customer_management`. Se acepta esa duplicación chica a cambio de no depender de la app Clientes.
- **Sí:** signo contable (Debe − Haber), aunque se ofreció mostrar la deuda en positivo. Decisión del usuario: es lo que muestra contabilidad.
- **Sí:** usuarios: Facturación y Compras (`purchase.group_purchase_user`).
- **No:** comprador asignado ni ajuste "ven solo sus proveedores". Es mucho alcance y no hay un campo estándar de comprador en `res.partner`.
- **Sí:** Compras puede hacer todo, pero imputar, desimputar y enviar se habilitan con tres casillas separadas. Decisión del usuario, aunque se recomendó juntar imputar y desimputar.
- **Sí:** consultar e imprimir siempre habilitados para Compras. Sin eso la app no tiene sentido para ellos.
- **Sí:** casillas tildadas al instalar y globales (`ir.config_parameter`). Coincide con "que puedan hacer todo" y con el ajuste de la app Clientes.
- **No:** casillas por empresa. En el consolidado se mezclarían empresas con permisos distintos en la misma pantalla.
- **Sí:** imputar y desimputar desde Compras con `sudo()` después de verificar la casilla. Compras no tiene permiso estándar sobre asientos de pago ni para borrar imputaciones.
- **Sí:** reglas de lectura propias sobre `account.payment` y `account.move` limitadas a pagos a proveedores. Compras estándar no puede leer pagos.
- **Sí:** dos botones en la ficha ("Estado de cuenta" y "Cuenta proveedor"), cada uno con su cuenta.
- **No:** estado de cuenta combinado cliente + proveedor. Mezcla cuentas distintas; si hace falta, va en otra spec.
- **Sí:** menú Facturación > Proveedores > Estado de cuenta, simétrico con clientes.
- **Sí:** menú Órdenes de compra en la app, con la acción estándar `purchase.purchase_form_action`.
- **Sí:** el menú "Carga automática de facturas" solo se reserva (ID y posición) y lo crea su propia spec. Así no queda un menú vacío en producción.
- **No:** columna de saldo en el listado. Con varias monedas no hay un único importe correcto, igual que en clientes.
- **No:** tests automáticos. La verificación es manual con los criterios de aceptación.

## Riesgos

| Riesgo | Mitigación |
| --- | --- |
| Generalizar el estado de cuenta rompe el de clientes, que ya está en uso. | `partner_type` vale `customer` por defecto y el paso 1 verifica cifras iguales. Hay un bloque de criterios de no regresión. |
| La imputación parcial en sentido proveedor invierte signos dentro de `_prepare_reconciliation_single_partial`, un método interno. | Se encapsula en `_reconcile_partial_amount`, se limita a moneda de la empresa y hay criterio de aceptación con importes concretos. Se revisa al migrar de versión. |
| `sudo()` en imputar y desimputar desde Compras saltea los permisos estándar. | Se verifica antes la casilla, el grupo y que los apuntes sean del proveedor, de la misma empresa y cuenta a pagar. Hay criterio de error de acceso con la casilla destildada. |
| Las reglas de lectura nuevas amplían lo que Compras ve fuera de la app (pagos a proveedores en cualquier menú). | Se limitan a `partner_type = 'supplier'` y se documentan en Permisos del README. Hay criterio de que no ve pagos de clientes. |
| Las casillas vienen de datos `noupdate`: si se borran a mano, al actualizar el módulo no vuelven. | Comportamiento esperado: el valor lo decide el administrador. Se documenta en Configuraciones esenciales. |
| La regla de lectura de `account.move` por `origin_payment_id.partner_type` puede ser lenta con muchos asientos. | Se mide en `odoo_prueba` al abrir pagos. Si es lenta, se cambia por un dominio sobre `journal_id` de pagos. |

## Qué **no** incluye esta spec

- Carga automatizada de facturas de proveedor (solo queda reservado su menú).
- Comprador asignado y "Compras ve solo sus proveedores".
- Estado de cuenta combinado cliente + proveedor.
- Columna de saldo en el listado de Proveedores.
- Ajustes de permisos por empresa.
- Órdenes de pago y retenciones.
- Antigüedad de saldos por tramos.
- Envío masivo o programado de resúmenes.
- Renombrar `customer_account_statement`.
- Tests automáticos.

Cada uno de estos, si se hace, va en su propia spec.
