# SPEC 02 — App Clientes y estado de cuenta multiempresa

> **Estado:** Borrador
> **Depende de:** SPEC 01
> **Fecha:** 2026-10-20
> **Objetivo:** Una app "Clientes" (módulo `customer_management`) que reúne listado y asignación de vendedores, estado de cuenta, comprobantes y visitas, con un estado de cuenta que muestra todas las empresas del cliente y se filtra por casillas que recalculan al instante.

## Por qué existe esta spec

Hoy el estado de cuenta solo se encuentra dentro de Facturación, y los vendedores entran únicamente por el botón de la ficha del cliente.
Además, el asistente pide elegir "Empresas" antes de consultar, y por defecto propone solo la empresa activa.
Eso se confunde con "Empresas en las que participa" del cliente, que ya define en qué empresas se puede consultar.

La spec agrupa dos frentes: los cambios al estado de cuenta (en `customer_account_statement`) y la app nueva (en `customer_management`).
Se recomendó separarlos en dos specs y se decidió mantenerlos juntos (ver Decisiones).

Aclaración de los tres campos de empresa, que queda como referencia:

- **Empresa** (estándar de Odoo, en la ficha del cliente): qué empresa puede ver el contacto. No influye en el estado de cuenta.
- **Empresas en las que participa** (`res.partner.company_ids`, SPEC 01): en qué empresas se puede consultar el estado de cuenta del cliente. Vacío = todas las del usuario.
- **Empresas** del asistente (`customer.account.statement.company_ids`): qué empresas se muestran en la consulta. Con esta spec deja de pedirse antes de consultar y pasa a ser el filtro de casillas dentro del estado de cuenta.

## Alcance

**Incluye:**

*Estado de cuenta (`customer_account_statement`):*

- El asistente previo ya no muestra el campo "Empresas". Pide cliente, modo y fechas.
- Al consultar se incluyen **todas las empresas permitidas**: las "Empresas en las que participa" del cliente que el usuario tiene habilitadas. Si el cliente no tiene ninguna, se incluyen todas las empresas habilitadas del usuario.
- La pantalla de resultado pasa a ser un formulario del estado de cuenta:
  - Arriba, editables: casillas de empresas (solo las permitidas), modo y fechas.
  - Al cambiar cualquiera de esos campos se recalcula todo **automáticamente**: saldo inicial, movimientos, saldo acumulado, totales.
  - Un cuadro "Saldos por moneda" con los totales de cada moneda.
  - Abajo, la lista de movimientos, con los mismos botones por línea de hoy (Abrir comprobante, Imputaciones, Imputar).
  - Botones Imprimir y Enviar por email en la cabecera, que usan las empresas, modo y fechas que se ven en pantalla.
- Se mantienen el menú Facturación > Clientes > Estado de cuenta y el botón de la ficha del cliente.

*App Clientes (`customer_management`, módulo nuevo):*

- App "Clientes" en el menú principal, con ícono, visible para Facturación y vendedores.
- Menús de la app:
  - **Clientes:** listado de clientes con filtros y asignación de vendedores.
  - **Estado de cuenta:** abre el asistente de la SPEC 01.
  - **Facturas y notas:** facturas, notas de crédito y notas de débito de clientes.
  - **Pagos recibidos:** pagos de clientes.
  - **Comprobantes vencidos:** facturas y notas de débito publicadas, con saldo pendiente y vencidas.
  - **Visitas:** visitas del módulo `customer_visit`.
  - **Configuración > Ajustes:** sección de ajustes de la app.
- Listado de Clientes:
  - Columnas: Nombre, CUIT, Vendedor, Empresas en las que participa, Ciudad, Provincia, Teléfono, Email.
  - Filtros: Mis clientes (activo por defecto), Sin vendedor, Con deuda, Con vencidos.
  - Búsqueda y agrupación por Vendedor, Empresas en las que participa, Ciudad y Provincia.
- Asignación de vendedor ("Vendedor" estándar, `res.partner.user_id`) de dos formas:
  - Acción masiva "Asignar vendedor" sobre los clientes seleccionados.
  - Columna Vendedor editable en la lista.
  - Ambas solo para Facturación y Gerente de ventas.
- Ajuste **"Vendedores ven solo sus clientes"** (activado / desactivado, por defecto desactivado):
  - Desactivado: los vendedores ven todos los clientes en la app, con el filtro "Mis clientes" activo y quitable.
  - Activado: en los menús de la app, los vendedores ven solo sus clientes y los comprobantes y visitas de sus clientes.
  - Afecta solo a vendedores sin más permisos: no afecta a Facturación, a "Ventas: todos los documentos" ni a Gerente de ventas.
  - Solo rige dentro de la app Clientes. En el resto de Odoo nada cambia.

**Fuera de alcance (para futuras specs):**

- Ocultar clientes ajenos en todo Odoo (regla de seguridad sobre `res.partner`).
- Columna de saldo adeudado en el listado de Clientes.
- Asignar Equipo de ventas o empleados de RRHH (`hr.employee`).
- Quitar el menú Facturación > Clientes > Estado de cuenta o la app Visitas.
- Tablero o indicadores de la app (gráficos, KPIs).
- Cambios en el modelo o las vistas de `customer_visit`.
- Tests automáticos.

## Modelo de datos

### `customer_account_statement` (cambios)

```python
# wizard/account_statement_wizard.py
class CustomerAccountStatement(models.TransientModel):
    _name = 'customer.account.statement'

    # Sin cambios de definición: partner_id, allowed_company_ids, mode, date_from, date_to.

    company_ids = fields.Many2many(...)   # default = allowed_company_ids completo (antes: solo la empresa activa)

    line_ids = fields.One2many(
        'customer.account.statement.line', 'statement_id',
        compute='_compute_statement', store=True, readonly=True)
    currency_total_ids = fields.One2many(
        'customer.account.statement.currency', 'statement_id',
        compute='_compute_statement', store=True, readonly=True)

    # _compute_statement depende de partner_id, company_ids, mode, date_from, date_to.
    # Si company_ids queda vacío, no genera líneas y la vista muestra un aviso.
```

```python
# wizard/account_statement_currency.py (nuevo)
class CustomerAccountStatementCurrency(models.TransientModel):
    _name = 'customer.account.statement.currency'
    _description = 'Saldo de estado de cuenta por moneda'

    statement_id = fields.Many2one('customer.account.statement', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', required=True)   # moneda de la empresa
    initial_balance = fields.Monetary()   # solo modo movements
    debit = fields.Monetary()             # solo modo movements
    credit = fields.Monetary()            # solo modo movements
    final_balance = fields.Monetary()     # solo modo movements
    amount_residual = fields.Monetary()   # solo modo pending (total adeudado)
```

Vistas:

- `customer_account_statement_view_form`: asistente previo **sin** `company_ids`.
- `customer_account_statement_view_form_result` (nueva): pantalla de resultado (cabecera editable, "Saldos por moneda", movimientos).
- Se elimina `customer_account_statement_line_view_list`: su lista pasa a estar dentro del formulario de resultado. Se eliminan también `action_print_statement` y `action_send_statement` de la línea.

### `customer_management` (nuevo)

Ruta: `C:\Users\Daniel\Archivos\custom_addons\customer_management`.

```python
# __manifest__.py (extracto)
{
    'name': 'Clientes',
    'version': '1.0',
    'category': 'Sales',
    'author': 'Daniel',
    'depends': ['customer_account_statement', 'customer_visit'],
    'application': True,
    'license': 'LGPL-3',
}
```

```python
# models/res_config_settings.py
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    salesman_own_customers_only = fields.Boolean(
        string='Vendedores ven solo sus clientes',
        config_parameter='customer_management.salesman_own_customers_only')
```

```python
# models/res_partner.py
class ResPartner(models.Model):
    _inherit = 'res.partner'

    has_receivable_debt = fields.Boolean(
        string='Con deuda', compute='_compute_receivable_flags', search='_search_has_receivable_debt')
    has_overdue_debt = fields.Boolean(
        string='Con vencidos', compute='_compute_receivable_flags', search='_search_has_overdue_debt')

    @api.model
    def _get_app_salesman_domain(self, partner_field='id'):
        ...  # [] o [(partner_field + '.commercial_partner_id.user_id', '=', uid)] según el ajuste y los grupos

    @api.model
    def action_open_app_customers(self):
        ...  # devuelve la acción del listado con el dominio de _get_app_salesman_domain
```

```python
# wizard/assign_salesman.py
class CustomerManagementAssignSalesman(models.TransientModel):
    _name = 'customer.management.assign.salesman'
    _description = 'Asignar vendedor a clientes'

    partner_ids = fields.Many2many('res.partner', required=True)   # default: active_ids
    user_id = fields.Many2one('res.users', string='Vendedor', domain="[('share', '=', False)]")
    # user_id vacío = quitar el vendedor

    def action_assign(self):
        ...  # verifica grupos y escribe partner_ids.user_id con sudo()
```

Convenciones:

- **Cliente** en el listado: contacto principal (`is_company = True` o `parent_id = False`), con el filtro estándar "Clientes" (`customer_rank > 0`) activo por defecto y quitable, igual que Facturación > Clientes.
- **Con deuda:** el cliente tiene saldo neto positivo (suma de `amount_residual`) en apuntes a cobrar publicados.
- **Con vencidos:** el cliente tiene al menos un apunte a cobrar publicado con `amount_residual > 0` y `date_maturity < hoy`.
- **Empresas** de "Con deuda" y "Con vencidos": la misma regla del estado de cuenta (empresas del cliente ∩ empresas habilitadas del usuario; si el cliente no tiene, todas las del usuario).
- **Vendedor sin más permisos:** tiene `sales_team.group_sale_salesman` y no tiene `account.group_account_invoice`, `sales_team.group_sale_salesman_all_leads` ni `sales_team.group_sale_manager`.
- **Comprobantes del cliente** cuando rige el ajuste: `commercial_partner_id.user_id = usuario` (facturas, notas y pagos) y `partner_id.commercial_partner_id.user_id = usuario` (visitas).
- Los menús de la app que dependen del ajuste usan `ir.actions.server`: el dominio se calcula en el servidor al abrir el menú.

Archivos del módulo nuevo:

```text
customer_management/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── res_config_settings.py
│   └── res_partner.py
├── wizard/
│   ├── __init__.py
│   ├── assign_salesman.py
│   └── assign_salesman_views.xml
├── views/
│   ├── res_partner_views.xml          # lista, búsqueda y acción del listado de Clientes
│   ├── account_views.xml              # acciones de Facturas y notas, Pagos recibidos, Comprobantes vencidos
│   ├── res_config_settings_views.xml  # sección "Clientes" en Ajustes
│   └── menus.xml
├── security/
│   └── ir.access.csv
└── static/description/icon.png
```

IDs XML principales:

- `customer_management.menu_customer_management_root` (app "Clientes", con `web_icon`).
- `customer_management.action_customer_management_customers` (servidor: listado de Clientes).
- `customer_management.action_customer_management_invoices`, `..._payments`, `..._overdue`, `..._visits`.
- `customer_management.action_customer_management_assign_salesman` (acción masiva sobre `res.partner`, vista lista).
- `customer_management.action_customer_management_settings` (Ajustes con `context="{'module': 'customer_management'}"`).

## Plan de implementación

1. En `customer_account_statement`, quitar `company_ids` del asistente previo (y el aviso de consolidado). Cambiar el default de `company_ids` a todas las empresas permitidas. Prueba manual: con un cliente con dos empresas tildadas, "Consultar" muestra movimientos de ambas.
2. Crear `customer.account.statement.currency` con su acceso en `ir.access.csv`, y calcular sus totales junto con las líneas. Prueba manual: con una empresa ARS y una USD hay dos filas de totales.
3. Crear `customer_account_statement_view_form_result` con cabecera de solo lectura, "Saldos por moneda" y lista de movimientos con sus botones. Hacer que `action_view` abra ese formulario. Mover Imprimir y Enviar por email a la cabecera. Eliminar la vista lista de líneas y sus acciones. Prueba manual: consultar, abrir un comprobante e imprimir funcionan como antes.
4. Convertir `line_ids` y `currency_total_ids` en calculados (`_compute_statement`) y hacer editables en la cabecera las casillas de empresas (`many2many_checkboxes`, dominio `allowed_company_ids`), el modo y las fechas. Prueba manual: destildar una empresa recalcula saldo inicial, acumulado y totales sin apretar ningún botón.
5. Verificar los botones por línea después de recalcular: Abrir comprobante, Imputaciones e Imputar actúan sobre el comprobante que se ve. Con cero empresas tildadas, la lista queda vacía con un aviso, e Imprimir o Enviar muestran un error.
6. Actualizar `customer_account_statement/README.md`: uso, sección Base de datos (tabla nueva, vista eliminada) e historial.
7. Crear el esqueleto de `customer_management` (manifiesto con `application`, ícono, `ir.access.csv`, menú raíz "Clientes" visible para `account.group_account_invoice` y `sales_team.group_sale_salesman`). Prueba manual: la app aparece en el menú principal y se instala con `-i customer_management` sin errores.
8. Agregar el ajuste `salesman_own_customers_only`, la sección "Clientes" en Ajustes y el menú Configuración > Ajustes (solo `base.group_system`). Prueba manual: activar, guardar y ver el valor persistido.
9. Crear el listado de Clientes (vista lista, búsqueda con filtros y agrupaciones, acción de servidor) y el menú Clientes. Prueba manual: "Mis clientes" viene activo y se puede quitar.
10. Agregar `has_receivable_debt` y `has_overdue_debt` con sus métodos de búsqueda, y los filtros "Con deuda" y "Con vencidos". Prueba manual: los filtros coinciden con los saldos del estado de cuenta de dos clientes de prueba.
11. Agregar la asignación de vendedor: asistente `customer.management.assign.salesman` con acción masiva, y columna Vendedor editable en la lista, ambas solo para Facturación y Gerente de ventas. Prueba manual: asignar un vendedor a tres clientes a la vez.
12. Crear los menús Estado de cuenta, Facturas y notas, Pagos recibidos, Comprobantes vencidos y Visitas.
13. Aplicar el ajuste en las acciones de servidor de los menús de la app (`_get_app_salesman_domain`). Prueba manual: con el ajuste activado, un vendedor ve solo sus clientes; un usuario de Facturación ve todos.
14. Crear `customer_management/README.md` según `AGENTS.md`, con la sección Base de datos.

## Criterios de aceptación

Verificación manual sobre `odoo_prueba` con al menos dos empresas en ARS, una en USD, un usuario de Facturación, un vendedor sin más permisos y clientes con y sin vendedor.

**Estado de cuenta**

- [ ] El asistente previo no muestra el campo "Empresas".
- [ ] Con "Empresas en las que participa" = {A, B}, el estado de cuenta abre con A y B tildadas y muestra movimientos de ambas.
- [ ] Con "Empresas en las que participa" vacío, abre con todas las empresas habilitadas del usuario tildadas.
- [ ] Las casillas ofrecen solo las empresas permitidas para el cliente y el usuario.
- [ ] Destildar una empresa quita sus movimientos y recalcula saldo inicial, saldo acumulado y "Saldos por moneda" sin apretar ningún botón.
- [ ] Cambiar el modo o las fechas en la cabecera recalcula el estado de cuenta.
- [ ] Con una empresa ARS y una USD tildadas, "Saldos por moneda" muestra dos filas.
- [ ] Después de recalcular, "Abrir comprobante" abre el comprobante de esa línea.
- [ ] Imprimir genera un PDF solo con las empresas tildadas, con las mismas cifras que la pantalla.
- [ ] Con ninguna empresa tildada, la lista queda vacía con un aviso, e Imprimir o Enviar por email muestran un error.
- [ ] Facturación > Clientes > Estado de cuenta y el botón de la ficha siguen funcionando.

**App Clientes**

- [ ] `customer_management` se instala y desinstala sin errores ni advertencias en el log.
- [ ] La app "Clientes" aparece en el menú principal para un usuario de Facturación y para un vendedor.
- [ ] La app tiene los menús Clientes, Estado de cuenta, Facturas y notas, Pagos recibidos, Comprobantes vencidos, Visitas y Configuración > Ajustes.
- [ ] Configuración > Ajustes solo la ve un administrador.
- [ ] El listado de Clientes muestra las columnas Nombre, CUIT, Vendedor, Empresas en las que participa, Ciudad, Provincia, Teléfono y Email.
- [ ] El filtro "Mis clientes" viene activo y se puede quitar.
- [ ] "Sin vendedor" lista solo clientes sin vendedor.
- [ ] "Con deuda" lista exactamente los clientes cuyo estado de cuenta (modo Solo pendientes, todas las empresas permitidas) tiene total adeudado positivo.
- [ ] "Con vencidos" lista exactamente los clientes con algún comprobante con días de atraso mayor a cero en ese estado de cuenta.
- [ ] Se puede agrupar por Vendedor, Empresas en las que participa, Ciudad y Provincia.
- [ ] "Asignar vendedor" sobre tres clientes seleccionados les asigna el vendedor elegido.
- [ ] "Asignar vendedor" con el vendedor vacío les quita el vendedor.
- [ ] Un usuario de Facturación puede editar la columna Vendedor en la lista.
- [ ] Un vendedor sin más permisos no ve la acción "Asignar vendedor" y la columna Vendedor es de solo lectura para él.
- [ ] "Comprobantes vencidos" lista solo facturas y notas de débito publicadas con saldo pendiente y vencimiento anterior a hoy.

**Ajuste "Vendedores ven solo sus clientes"**

- [ ] Por defecto está desactivado.
- [ ] Desactivado: un vendedor sin más permisos ve todos los clientes en el listado al quitar "Mis clientes".
- [ ] Activado: ese vendedor ve en el listado solo clientes donde es Vendedor, aunque quite el filtro.
- [ ] Activado: en Facturas y notas, Pagos recibidos, Comprobantes vencidos y Visitas, ese vendedor ve solo los de sus clientes.
- [ ] Activado: un usuario de Facturación y un Gerente de ventas siguen viendo todo.
- [ ] Activado: en Contactos y en Facturación > Clientes ese vendedor sigue viendo todos los clientes.

**Documentación**

- [ ] `customer_account_statement/README.md` y `customer_management/README.md` cumplen `AGENTS.md`, con la sección Base de datos y la línea "Base de datos:" en el historial.

## Decisiones

- **Sí:** una sola spec para estado de cuenta y app, aunque se recomendó separarlas. Decisión del usuario.
- **Sí:** la app vive en un módulo nuevo `customer_management`. `customer_account_statement` sigue siendo solo el estado de cuenta.
- **No:** convertir `customer_account_statement` en la app. Mezclaría el estado de cuenta con listado, asignación y visitas.
- **Sí:** `customer_management` depende de `customer_visit` para el menú Visitas.
- **Sí:** "todas las seleccionadas" = empresas del cliente ∩ empresas habilitadas del usuario. Es la regla de la SPEC 01, sin el paso de elegir.
- **No:** usar las empresas activas en el selector superior de Odoo. Cambian según lo que el usuario tenga tildado en ese momento.
- **Sí:** el filtro de empresas son casillas dentro del estado de cuenta que recalculan todo.
- **No:** un filtro de búsqueda sobre la lista. No recalcula saldo inicial ni acumulado, que seguirían sumando empresas ocultas.
- **Sí:** recálculo automático al cambiar empresas, modo o fechas. Decisión del usuario, aunque se recomendó un botón "Actualizar" por rendimiento.
- **Sí:** la pantalla de resultado es un formulario con la lista de movimientos embebida. Hace falta para tener casillas editables arriba de los movimientos.
- **Sí:** cuadro "Saldos por moneda" (modelo `customer.account.statement.currency`). Una lista embebida en un formulario no se puede agrupar por moneda, y sus totales al pie mezclarían monedas.
- **No:** totales al pie de la lista de movimientos. Mezclarían monedas en el consolidado.
- **Sí:** eliminar la vista lista de líneas y sus botones Imprimir/Enviar. Queda reemplazada por el formulario de resultado.
- **Sí:** mantener Facturación > Clientes > Estado de cuenta y la app Visitas. La app Clientes suma accesos sin quitar los actuales.
- **Sí:** "Vendedor" = `res.partner.user_id` (usuario de Odoo). Es el mismo campo que usan los permisos del estado de cuenta.
- **No:** empleados de RRHH ni Equipo de ventas. No dan acceso al estado de cuenta.
- **Sí:** asignar por acción masiva y por columna editable, solo Facturación y Gerente de ventas.
- **Sí:** el asistente de asignación escribe con `sudo()` después de verificar los grupos. Facturación y Gerente de ventas no siempre tienen permiso estándar para editar contactos.
- **Sí:** la columna editable usa los permisos estándar de contactos ("Creación de contactos", `base.group_partner_manager`). Si el usuario no lo tiene, usa la acción masiva.
- **Sí:** ajuste "Vendedores ven solo sus clientes", por defecto desactivado, guardado como `ir.config_parameter`.
- **Sí:** el ajuste rige solo dentro de la app Clientes, con dominios en acciones de servidor. No es una barrera de seguridad, pero no afecta al resto de Odoo.
- **No:** regla de seguridad sobre `res.partner`. La SPEC 01 ya la descartó por invasiva: `res.partner` incluye empresas, usuarios y proveedores.
- **Sí:** el ajuste afecta solo a vendedores sin Facturación, "Ventas: todos los documentos" ni Gerente de ventas.
- **Sí:** "Con deuda" y "Con vencidos" con la misma regla de empresas y apuntes que el estado de cuenta, para que el filtro y el estado de cuenta coincidan.
- **No:** columna de saldo en el listado. Con varias monedas no hay un único importe correcto.
- **No:** tests automáticos. La verificación es manual con los criterios de aceptación.

## Riesgos

| Riesgo | Mitigación |
| --- | --- |
| El recálculo automático es lento con clientes de muchos movimientos: cada casilla recalcula todo. | Saldo inicial con `_read_group` y solo líneas del período, como en la SPEC 01. Si en la prueba con el cliente de más movimientos tarda más de 2 segundos, se reabre la decisión del botón "Actualizar". |
| Después de un recálculo en pantalla, las líneas son registros nuevos sin guardar; los botones por línea podrían actuar sobre una línea que ya no existe. | Las líneas se guardan con `force_save`. Los botones usan `move_line_id` y no el id de la línea. Hay criterio de aceptación específico (paso 5 del plan). |
| `has_receivable_debt` / `has_overdue_debt` con método de búsqueda pueden ser lentos con muchos clientes. | Una sola consulta agregada por búsqueda, agrupando apuntes por cliente y empresa. |
| El ajuste da la falsa sensación de seguridad: un vendedor puede ver clientes ajenos desde Contactos. | Queda explícito en la etiqueta del ajuste, en el README y en Decisiones. Ocultarlos en todo Odoo es otra spec. |
| La columna Vendedor editable falla para usuarios sin "Creación de contactos". | Se documenta en Configuraciones esenciales del README. La acción masiva funciona igual. |
| Eliminar `customer_account_statement_line_view_list` rompe accesos guardados (favoritos o enlaces) a la lista vieja. | Las líneas son temporales: no hay enlaces útiles para conservar. Se anota en el historial del README. |

## Qué **no** incluye esta spec

- Ocultar clientes ajenos en todo Odoo.
- Columna de saldo adeudado en el listado de Clientes.
- Asignar Equipo de ventas o empleados de RRHH.
- Quitar el menú de Facturación o la app Visitas.
- Tablero o indicadores de la app.
- Cambios en `customer_visit`.
- Tests automáticos.

Cada uno de estos, si se hace, va en su propia spec.
