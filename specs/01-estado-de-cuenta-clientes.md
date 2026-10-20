# SPEC 01 — Estado de cuenta de clientes

> **Estado:** Implementado
> **Depende de:** —
> **Fecha:** 2026-10-20
> **Objetivo:** Un módulo `customer_account_statement` que permite consultar, imprimir, enviar e imputar la cuenta corriente de un cliente, por empresa o consolidada.

## Por qué existe esta spec

Odoo 20.0 Community no trae `account_reports` ni `account_followup`, así que no hay estado de cuenta de clientes nativo.
Hoy la cuenta corriente se arma mirando apuntes sueltos, y la imputación de recibos a facturas solo se puede hacer por el total pendiente desde el widget de la factura.
Además, un mismo cliente opera con varias empresas del grupo, y hay que poder ver su saldo por empresa y consolidado.

La spec agrupa cinco frentes (empresas del cliente, consulta, PDF, email e imputación).
Se evaluó dividirla y se decidió mantenerla junta (ver Decisiones).

## Alcance

**Incluye:**

- Campo `company_ids` ("Empresas en las que participa") en `res.partner`, informativo, que define en qué empresas se puede consultar el estado de cuenta del cliente.
- Asistente de consulta con cliente, empresas, rango de fechas y modo (`Movimientos` / `Solo pendientes`).
- Acceso desde un smart button "Estado de cuenta" en la ficha del cliente y desde el menú Facturación > Clientes > Estado de cuenta.
- Modo **Movimientos**: saldo inicial a la fecha "desde", cada apunte con Debe / Haber / Saldo acumulado, y saldo final.
- Modo **Solo pendientes**: comprobantes con saldo pendiente a la fecha "hasta", con Vencimiento, Importe original, Pendiente y Días de atraso, y total adeudado al pie.
- Consolidado multiempresa: si se eligen varias empresas, los movimientos se agrupan **por moneda de la empresa**, con saldos separados por moneda y una columna "Empresa".
- Filtro por empresa: si se elige una sola empresa, se ve el saldo de esa empresa.
- Detalle del movimiento: clic en una línea abre la factura/NC (`account.move`) o el recibo (`account.payment`).
- Ver imputaciones: para cada comprobante, lista de lo que lo cancela o lo que cancela (fecha, comprobante contraparte, importe imputado).
- Imputar: elegir un crédito (recibo o NC con saldo) e imputarlo a una o varias facturas/ND, con importe por factura.
- Desimputar: botón por línea en la lista de imputaciones.
- Resumen de cuenta en PDF (ambos modos), con datos de la empresa y del cliente.
- Envío del PDF por email al cliente, con plantilla y destinatario editable, registrado en el chatter del cliente.
- Permisos: usuarios de Facturación pueden todo; vendedores solo consultan e imprimen el estado de cuenta de sus clientes.

**Fuera de alcance (para futuras specs):**

- Cuentas a pagar / proveedores.
- Grupo de seguridad "Cobranzas".
- Conversión de monedas en el consolidado (se separa por moneda en lugar de convertir).
- Imputación con importe parcial en moneda extranjera.
- Restringir la visibilidad del cliente según `company_ids` (reglas de registro sobre `res.partner`).
- Antigüedad de saldos (aging por tramos).
- Envío masivo o programado de resúmenes.
- Portal del cliente.
- Tests automáticos.

## Modelo de datos

Ruta del módulo: `C:\Users\Daniel\Archivos\custom_addons\customer_account_statement`.

```python
# __manifest__.py (extracto)
{
    'name': 'Estado de cuenta de clientes',
    'version': '1.0',
    'category': 'Accounting',
    'author': 'Daniel',
    'depends': ['account', 'sales_team'],
    'license': 'LGPL-3',
}
```

```python
# models/res_partner.py
class ResPartner(models.Model):
    _inherit = 'res.partner'

    company_ids = fields.Many2many(
        'res.company', 'res_partner_statement_company_rel',
        'partner_id', 'company_id',
        string='Empresas en las que participa',
    )
```

```python
# wizard/account_statement_wizard.py
class CustomerAccountStatement(models.TransientModel):
    _name = 'customer.account.statement'

    partner_id = fields.Many2one('res.partner', required=True)        # se usa su commercial_partner_id
    company_ids = fields.Many2many('res.company', required=True)      # 1 = por empresa, >1 = consolidado
    date_from = fields.Date()                                         # ignorado en modo pending
    date_to = fields.Date(required=True, default=fields.Date.today)
    mode = fields.Selection([('movements', 'Movimientos'), ('pending', 'Solo pendientes')],
                            default='movements', required=True)
    line_ids = fields.One2many('customer.account.statement.line', 'statement_id')
```

```python
# wizard/account_statement_line.py
class CustomerAccountStatementLine(models.TransientModel):
    _name = 'customer.account.statement.line'
    _order = 'currency_id, sequence'

    statement_id = fields.Many2one('customer.account.statement', ondelete='cascade')
    sequence = fields.Integer()
    line_type = fields.Selection([('initial', 'Saldo inicial'), ('move', 'Movimiento')])
    company_id = fields.Many2one('res.company')
    currency_id = fields.Many2one('res.currency')            # moneda de la empresa (agrupador)
    move_line_id = fields.Many2one('account.move.line')
    move_id = fields.Many2one('account.move')
    payment_id = fields.Many2one('account.payment')          # move_id.origin_payment_id
    document_type = fields.Char()                            # 'Factura', 'Nota de crédito', 'Nota de débito', 'Recibo', 'Asiento'
    date = fields.Date()
    date_maturity = fields.Date()
    name = fields.Char()                                     # número de comprobante / referencia
    debit = fields.Monetary()
    credit = fields.Monetary()
    cumulative_balance = fields.Monetary()                   # solo modo movements
    original_currency_id = fields.Many2one('res.currency')   # informativo si difiere de currency_id
    amount_currency = fields.Monetary(currency_field='original_currency_id')
    amount_residual = fields.Monetary()                      # solo modo pending
    days_overdue = fields.Integer()                          # solo modo pending
```

```python
# wizard/account_statement_reconcile.py
class CustomerAccountStatementReconcile(models.TransientModel):
    _name = 'customer.account.statement.reconcile'

    partner_id = fields.Many2one('res.partner', required=True)
    credit_line_id = fields.Many2one('account.move.line', required=True)  # recibo/NC con amount_residual < 0
    company_id = fields.Many2one(related='credit_line_id.company_id')
    available_amount = fields.Monetary()                                  # -credit_line_id.amount_residual
    line_ids = fields.One2many('customer.account.statement.reconcile.line', 'reconcile_id')


class CustomerAccountStatementReconcileLine(models.TransientModel):
    _name = 'customer.account.statement.reconcile.line'

    reconcile_id = fields.Many2one('customer.account.statement.reconcile', ondelete='cascade')
    selected = fields.Boolean()
    debit_line_id = fields.Many2one('account.move.line')   # factura/ND con amount_residual > 0
    amount_residual = fields.Monetary()
    amount_to_apply = fields.Monetary()                    # editable solo si ambos apuntes están en moneda de la empresa
    allow_partial = fields.Boolean()
```

```python
# models/account_partial_reconcile.py
class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    def action_statement_unreconcile(self):
        ...  # verifica group_account_invoice y hace unlink() del parcial
```

Convenciones:

- Apuntes considerados: `account.move.line` con `account_id.account_type = 'asset_receivable'`, `parent_state = 'posted'`, `partner_id` hijo de `partner_id.commercial_partner_id` y `company_id in company_ids`.
- Signo: Debe = aumenta la deuda del cliente (facturas, ND); Haber = la disminuye (recibos, NC). Saldo positivo = el cliente debe.
- Importes en moneda de la empresa (`balance`, `amount_residual`). La moneda original se muestra solo como columna informativa.
- Saldo inicial (modo movements): suma de `balance` con `date < date_from`, una línea `initial` por moneda.
- `cumulative_balance` se reinicia por moneda.
- Si `partner_id.company_ids` está vacío, el asistente ofrece todas las empresas habilitadas del usuario.
- Si no está vacío, ofrece la intersección entre `partner_id.company_ids` y las empresas habilitadas del usuario.
- Default de `company_ids` en el asistente: la empresa activa, si está permitida; si no, la primera permitida.

Archivos del módulo:

```text
customer_account_statement/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── res_partner.py
│   └── account_partial_reconcile.py
├── wizard/
│   ├── __init__.py
│   ├── account_statement_wizard.py
│   ├── account_statement_wizard_views.xml
│   ├── account_statement_line.py
│   ├── account_statement_line_views.xml
│   ├── account_statement_reconcile.py
│   └── account_statement_reconcile_views.xml
├── views/
│   ├── res_partner_views.xml
│   ├── account_partial_reconcile_views.xml
│   └── menus.xml
├── report/
│   ├── account_statement_report.xml
│   └── account_statement_templates.xml
├── data/
│   └── mail_template_data.xml
└── security/
    ├── security.xml
    └── ir.access.csv
```

IDs XML principales:

- `customer_account_statement.action_customer_account_statement` (asistente).
- `customer_account_statement.menu_customer_account_statement` (bajo `account.menu_finance_receivables`).
- `customer_account_statement.action_report_customer_account_statement` (PDF).
- `customer_account_statement.mail_template_customer_account_statement` (modelo `res.partner`).

## Plan de implementación

1. Crear el esqueleto del módulo (`__init__.py`, `__manifest__.py`, `security/ir.access.csv` vacío con cabecera). Prueba manual: el módulo se instala sin errores con `-i customer_account_statement`.
2. Agregar `company_ids` a `res.partner` y mostrarlo en la pestaña "Ventas y compras" de la ficha. Prueba manual: asignar dos empresas a un cliente y guardar.
3. Crear `customer.account.statement` y `customer.account.statement.line` con sus accesos para `account.group_account_invoice`. Crear también la vista formulario del asistente, la acción y el menú Facturación > Clientes > Estado de cuenta. Prueba manual: el asistente abre y valida los campos obligatorios.
4. Implementar la generación de líneas en modo `movements` para una sola empresa (saldo inicial, movimientos, saldo acumulado) y la vista lista de líneas con saldo final al pie. Prueba manual: el saldo final coincide con la suma de `balance` de los apuntes a cobrar del cliente hasta `date_to`.
5. Agregar el smart button "Estado de cuenta" en la ficha del cliente, que abre el asistente con el cliente precargado.
6. Implementar el consolidado: varias empresas, agrupación por `currency_id`, saldo inicial y acumulado por moneda, y columna "Empresa". Prueba manual: con dos empresas ARS se ve un solo bloque; con una ARS y una USD se ven dos bloques.
7. Implementar el modo `pending` (pendientes a `date_to`, vencimiento, importe original, pendiente, días de atraso, total adeudado). Para el pendiente a `date_to`, descontar las imputaciones con `max_date > date_to`.
8. Agregar la acción "Abrir comprobante" en la línea: abre `account.payment` si existe `payment_id`; si no, abre `account.move`.
9. Agregar el botón "Imputaciones" en la línea, que abre una lista de `account.partial.reconcile` del apunte (fecha, comprobante contraparte, importe) con vista propia en `views/account_partial_reconcile_views.xml`.
10. Agregar `action_statement_unreconcile` en `account.partial.reconcile` y el botón "Desimputar" en esa lista, visible solo para `account.group_account_invoice`. Al confirmar, la línea desaparece y el pendiente del comprobante vuelve a subir.
11. Crear el asistente `customer.account.statement.reconcile` con imputación **por el total posible**. Se abre desde el botón "Imputar" en líneas de crédito con pendiente, lista las facturas/ND pendientes de la misma empresa y cuenta, y concilia con `_reconcile_plan` en orden de vencimiento.
12. Habilitar el importe parcial por factura (`amount_to_apply`) cuando crédito y factura están en moneda de la empresa. El parcial se arma con `_prepare_reconciliation_single_partial`, limitando el residual al importe pedido. Validar que cada importe sea ≤ al pendiente de su factura y que la suma sea ≤ `available_amount`.
13. Crear el reporte QWeb PDF (`report/account_statement_report.xml` y `report/account_statement_templates.xml`) con encabezado de la empresa activa, empresas incluidas, cliente (nombre, CUIT, dirección), rango de fechas y modo. Incluir tablas por moneda según el modo. Agregar el botón "Imprimir" en el asistente y en la lista de líneas.
14. Crear la plantilla `mail_template_customer_account_statement` y el botón "Enviar por email". El botón genera el PDF, lo adjunta y abre `mail.compose.message` sobre el cliente con su email como destinatario editable. El envío queda en el chatter del cliente.
15. Permisos para vendedores en `security/security.xml` e `ir.access.csv`:
    - Acceso de lectura al asistente y las líneas para `sales_team.group_sale_salesman`.
    - Lectura de `account.move`, `account.move.line`, `account.payment` y `account.partial.reconcile`, con reglas de registro limitadas a clientes cuyo `commercial_partner_id.user_id` es el usuario.
    - Chequeo en el asistente que impide consultar clientes ajenos.
    - Botones Imputar, Desimputar y Enviar por email ocultos para quien no tenga `account.group_account_invoice`.

## Criterios de aceptación

Verificación manual sobre una base Odoo 20.0 con al menos dos empresas en ARS, una en USD y un cliente con facturas, NC y recibos en ellas.

**Instalación y datos del cliente**

- [ ] El módulo se instala y desinstala sin errores ni advertencias en el log.
- [ ] La ficha del cliente muestra "Empresas en las que participa" y permite elegir varias empresas.
- [ ] Con `company_ids` = {A, B}, el selector de empresas del asistente ofrece solo A y B (si el usuario las tiene habilitadas).
- [ ] Con `company_ids` vacío, el selector ofrece todas las empresas habilitadas del usuario.

**Consulta**

- [ ] El smart button "Estado de cuenta" de la ficha abre el asistente con el cliente precargado.
- [ ] El menú Facturación > Clientes > Estado de cuenta abre el mismo asistente.
- [ ] En modo Movimientos con una empresa, el saldo inicial es igual a la suma de `balance` de los apuntes a cobrar publicados con fecha anterior a "desde".
- [ ] El saldo final es igual al saldo inicial más la suma de Debe menos la suma de Haber del período.
- [ ] Cada línea muestra el saldo acumulado correcto respecto de la anterior.
- [ ] Los asientos en borrador o cancelados no aparecen.
- [ ] Los movimientos de contactos hijos del cliente aparecen en su estado de cuenta.
- [ ] Con dos empresas en ARS, se ve un único bloque ARS con columna "Empresa" y el saldo es la suma de ambas.
- [ ] Con una empresa ARS y una USD, se ven dos bloques con saldos separados.
- [ ] Una factura en USD de una empresa ARS muestra el importe en ARS en Debe y el importe en USD en la columna informativa.
- [ ] En modo Solo pendientes, solo aparecen comprobantes con pendiente distinto de cero a "hasta", con Días de atraso = `date_to - date_maturity` (0 si no venció).
- [ ] En modo Solo pendientes, el total adeudado coincide con el saldo final del modo Movimientos para la misma fecha "hasta".

**Detalle e imputaciones**

- [ ] Clic en "Abrir comprobante" sobre una factura abre la factura.
- [ ] Clic en "Abrir comprobante" sobre un recibo abre el pago (`account.payment`).
- [ ] "Imputaciones" sobre una factura parcialmente pagada lista cada recibo/NC aplicado con fecha e importe, y la suma coincide con lo pagado.
- [ ] "Imputaciones" sobre un recibo lista las facturas que cancela.
- [ ] "Desimputar" borra la imputación y la factura vuelve a tener pendiente por ese importe.
- [ ] El asistente Imputar sobre un recibo de 1000 con dos facturas de 600 permite aplicar 600 + 400 y deja la segunda factura con 200 pendientes.
- [ ] Ingresar un importe mayor al pendiente de la factura, o una suma mayor al disponible, muestra un error y no imputa nada.
- [ ] Ingresar un importe parcial menor al pendiente (por ejemplo, 300 sobre una factura de 600 con recibo de 1000) deja la factura con 300 y el recibo con 700 pendientes.
- [ ] Si la factura o el recibo están en moneda extranjera, el campo de importe no es editable y se imputa por el total posible.
- [ ] El asistente Imputar solo lista facturas/ND del mismo cliente, empresa y cuenta contable que el crédito.

**PDF y email**

- [ ] "Imprimir" genera un PDF con datos de empresa y cliente (nombre, CUIT, dirección), rango y modo, y las mismas cifras que la pantalla.
- [ ] El PDF del consolidado muestra un bloque por moneda y la columna "Empresa".
- [ ] "Enviar por email" abre el compositor con la plantilla, el PDF adjunto y el email del cliente como destinatario editable.
- [ ] Tras enviar, el mensaje con el adjunto queda en el chatter del cliente.

**Permisos**

- [ ] Un usuario de Facturación ve y usa todos los botones.
- [ ] Un vendedor sin Facturación puede consultar e imprimir el estado de cuenta de un cliente donde es vendedor (`user_id`).
- [ ] Un vendedor recibe un error de acceso al intentar consultar un cliente de otro vendedor.
- [ ] Un vendedor no ve los botones Imputar, Desimputar ni Enviar por email.

## Decisiones

- **Sí:** fuente de datos = `account.move.line` en cuentas `asset_receivable`, publicados. Incluye asientos manuales y cuadra con contabilidad.
- **No:** unir `account.move` y `account.payment` por separado. Pierde asientos manuales y puede no cuadrar.
- **Sí:** solo clientes (cuentas a cobrar). Proveedores, si llegan, van en otra spec.
- **Sí:** `company_ids` en `res.partner` como Many2many informativo. Permite "varias pero no todas" sin tocar la regla multiempresa del core.
- **No:** usar solo `company_id` estándar. No permite elegir varias empresas puntuales.
- **No:** regla de registro que oculte el cliente según `company_ids`. Es invasiva y pisa la regla de `res.partner`.
- **Sí:** `company_ids` vacío = todas las empresas habilitadas del usuario. Evita tener que cargar el campo en todos los clientes existentes al instalar.
- **Sí:** consolidado separado por moneda de la empresa, con columna "Empresa". Una sola empresa = filtro por empresa.
- **No:** convertir el consolidado a una moneda. Los saldos no cuadrarían con cada contabilidad.
- **Sí:** importes en moneda de la empresa; la moneda original solo es informativa.
- **Sí:** líneas en un `TransientModel` (`customer.account.statement.line`) calculadas al consultar. Permite saldo acumulado ordenado y el vacuum de Odoo las limpia.
- **No:** vista SQL (`_auto = False`). El saldo acumulado depende de los filtros del asistente y complica la consulta.
- **Sí:** modo Solo pendientes con vencimiento, pendiente y días de atraso, sin saldo inicial.
- **Sí:** imputación incluida en esta spec, aunque se recomendó separarla. Decisión del usuario.
- **Sí:** importe parcial por factura solo si crédito y factura están en moneda de la empresa. En moneda extranjera se imputa por el total posible, con diferencia de cambio automática de Odoo.
- **Sí:** el parcial se arma con `_prepare_reconciliation_single_partial`, porque Odoo 20 no tiene API pública para imputar un importe menor al pendiente de ambos apuntes.
- **Sí:** desimputar desde la lista de imputaciones (unlink del `account.partial.reconcile`).
- **Sí:** imputar, desimputar y enviar email solo para `account.group_account_invoice`.
- **Sí:** vendedores (`sales_team.group_sale_salesman`) en lectura, solo sobre clientes donde son `user_id`. Se agregan reglas de lectura propias porque `account` no les da acceso a esos modelos sin el módulo `sale`.
- **No:** depender de `sale`. Las reglas propias evitan instalar Ventas solo para dar acceso.
- **No:** grupo "Cobranzas". Se omite por ahora.
- **Sí:** menú bajo Facturación > Clientes. Los vendedores, que no ven ese menú, entran por el smart button de la ficha.
- **Sí:** PDF con membrete de la empresa activa y lista de empresas incluidas.
- **Sí:** email al cliente con destinatario editable, plantilla sobre `res.partner` y registro en el chatter.
- **No:** tests automáticos. La verificación es manual con los criterios de aceptación.

## Riesgos

| Riesgo | Mitigación |
| --- | --- |
| La imputación parcial usa un método interno (`_prepare_reconciliation_single_partial`) que puede cambiar entre versiones de Odoo. | Se encapsula en un único método del asistente de imputación. Se limita a moneda de la empresa. Se revisa al migrar de versión. |
| Una imputación mal hecha descuadra la cuenta corriente. | Validaciones previas (importe ≤ pendiente, suma ≤ disponible, misma empresa, cuenta y cliente). Desimputar disponible desde el detalle. |
| Las reglas de lectura para vendedores pueden ampliar accesos si `sale` también está instalado (las reglas del mismo grupo se combinan con OR). | Las reglas propias solo cubren clientes con `user_id` = usuario. Se verifica con el criterio de acceso denegado a clientes ajenos. |
| Clientes con muchos movimientos hacen lento el cálculo del saldo acumulado. | Saldo inicial con una sola consulta agregada (`_read_group`). Solo se generan líneas del período. |
| Consulta consolidada de empresas que el usuario no tiene activas en el selector. | Se lee con `with_context(allowed_company_ids=...)` limitado a las empresas permitidas del usuario. |

## Qué **no** incluye esta spec

- Cuentas a pagar / proveedores.
- Grupo de seguridad "Cobranzas".
- Conversión de monedas en el consolidado.
- Imputación parcial en moneda extranjera.
- Ocultar clientes según "Empresas en las que participa".
- Antigüedad de saldos por tramos.
- Envío masivo o programado de resúmenes.
- Portal del cliente.
- Tests automáticos.

Cada uno de estos, si se hace, va en su propia spec.
