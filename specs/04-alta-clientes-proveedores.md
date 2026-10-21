# SPEC 04 — Alta de clientes y proveedores desde las apps, con control de CUIT repetido

> **Estado:** Aprobado
> **Depende de:** SPEC 02, SPEC 03
> **Fecha:** 2026-10-21
> **Objetivo:** Que las apps Clientes y Proveedores permitan dar de alta clientes y proveedores desde su listado, con valores precargados y un control de CUIT repetido configurable en cada app.

## Por qué existe esta spec

Los listados de las apps Clientes (SPEC 02) y Proveedores (SPEC 03) tienen `create="0"`, así que no hay forma de dar de alta un contacto desde ahí.
La lista de Clientes, además, es editable en línea para cambiar el Vendedor: con el "Nuevo" estándar se agregaría una fila vacía en lugar de abrir la ficha.

Al dar de alta aparece el riesgo de cargar dos veces el mismo CUIT.
El control es compartido por las dos apps, así que vive en un módulo chico propio (`partner_vat_check`), pero cada app tiene su propio ajuste.

`supplier_management` (SPEC 03) está implementado en la rama `spec-03-app-proveedores`.
Esta spec se implementa después de que esa rama esté integrada.

## Alcance

**Incluye:**

*Alta desde las apps:*

- **Clientes:** botón propio **"Nuevo cliente"** en la cabecera del listado, que abre la ficha completa del contacto. La edición en línea de la columna Vendedor (SPEC 02) queda igual.
- **Proveedores:** se habilita el botón **"Nuevo"** estándar del listado (se quita `create="0"`), que abre la ficha completa.
- Valores precargados al crear desde cada app:
  - **Es empresa** (`is_company = True`).
  - **Rango:** `customer_rank = 1` en Clientes, `supplier_rank = 1` en Proveedores.
  - **Empresas en las que participa:** la empresa activa del usuario.
  - **Vendedor** (solo Clientes): el usuario que crea, si tiene `sales_team.group_sale_salesman`. Si no, queda vacío.
- Los valores precargados también aplican al "Nuevo" de la vista kanban de cada app.
- **Permisos:** los estándar de Odoo. Solo crean quienes ya pueden crear contactos (*Creación de contactos*, Gerente de ventas con `sale` instalado, Gerente de compras). Quien no puede, no ve el botón.

*Control de CUIT repetido (`partner_vat_check`, módulo nuevo):*

- Un ajuste **"CUIT repetido"** en Ajustes de cada app, con tres opciones:
  - **Bloquear** (por defecto): no deja guardar.
  - **Avisar:** deja guardar y deja un aviso en el chatter del contacto.
  - **No controlar.**
- Cada app tiene su ajuste independiente: el de Clientes rige en la app Clientes y el de Proveedores en la app Proveedores.
- **Solo rige dentro de las apps:** al crear o editar desde Clientes o Proveedores. En Contactos, Facturación o importaciones no se controla.
- Se controla **al guardar**, al crear y al cambiar el CUIT de un contacto existente.
- Comparación:
  - Contra contactos principales (sin padre), activos, de cualquier empresa, sin contar el propio.
  - En Clientes, solo contra clientes (`customer_rank > 0`); en Proveedores, solo contra proveedores (`supplier_rank > 0`).
  - Se ignoran guiones, puntos, espacios y mayúsculas/minúsculas.
- El mensaje nombra el contacto que ya tiene ese CUIT.

**Fuera de alcance (para futuras specs):**

- Control de CUIT repetido en todo Odoo (Contactos, Facturación, importaciones).
- Aviso en vivo al escribir el CUIT (onchange).
- Validar el formato o el dígito verificador del CUIT.
- Limpiar o fusionar los duplicados que ya existen en la base.
- Dar permiso de alta de contactos a Facturación, vendedores o Compras.
- Ventana de alta rápida (formulario reducido).
- Tests automáticos.

## Modelo de datos

### `partner_vat_check` (nuevo)

Ruta: `C:\Users\Daniel\Archivos\custom_addons\partner_vat_check`.

```python
# __manifest__.py (extracto)
{
    'name': 'Control de CUIT repetido',
    'version': '1.0',
    'category': 'Hidden',
    'author': 'Daniel',
    'depends': ['mail'],
    'license': 'LGPL-3',
}
```

```python
# models/res_partner.py
VAT_CHECK_CONTEXT_KEY = 'partner_vat_check_scope'   # valores: 'customer' / 'supplier'

VAT_CHECK_POLICIES = [
    ('block', 'Bloquear'),
    ('warn', 'Avisar'),
    ('none', 'No controlar'),
]

VAT_CHECK_SCOPES = {
    # scope: (parámetro del ajuste, campo de rango, etiqueta)
    'customer': ('partner_vat_check.customer_policy', 'customer_rank', 'cliente'),
    'supplier': ('partner_vat_check.supplier_policy', 'supplier_rank', 'proveedor'),
}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _normalize_vat_for_check(self, vat): ...       # quita todo lo que no sea letra o número, en mayúsculas

    def _get_vat_duplicate_partners(self, scope): ...  # SQL con regexp_replace sobre vat, con sudo implícito

    @api.constrains('vat', 'parent_id')
    def _check_vat_duplicate_app(self): ...            # solo si el contexto trae el scope y el ajuste es 'block'

    # create / write: si el ajuste es 'warn' y hay duplicados, message_post en el contacto guardado.
```

```python
# models/res_config_settings.py
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    customer_vat_duplicate_policy = fields.Selection(
        VAT_CHECK_POLICIES, string='CUIT repetido en Clientes',
        config_parameter='partner_vat_check.customer_policy')
    supplier_vat_duplicate_policy = fields.Selection(
        VAT_CHECK_POLICIES, string='CUIT repetido en Proveedores',
        config_parameter='partner_vat_check.supplier_policy')
```

```xml
<!-- data/ir_config_parameter_data.xml: los dos ajustes en Bloquear al instalar -->
<odoo noupdate="1">
    <record id="config_customer_policy" model="ir.config_parameter">
        <field name="key">partner_vat_check.customer_policy</field>
        <field name="value">block</field>
    </record>
    <record id="config_supplier_policy" model="ir.config_parameter">
        <field name="key">partner_vat_check.supplier_policy</field>
        <field name="value">block</field>
    </record>
</odoo>
```

Los campos de Ajustes se definen en `partner_vat_check`, pero cada app los muestra en su propia sección.

### `customer_management` (cambios)

```python
# __manifest__.py
'depends': ['customer_account_statement', 'customer_visit', 'partner_vat_check'],
```

```python
# models/res_partner.py
class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def default_get(self, fields): ...
    # Con partner_vat_check_scope = 'customer' en el contexto:
    #   company_ids = [env.company] y, si el usuario tiene sales_team.group_sale_salesman, user_id = usuario.

    @api.model
    def action_customer_management_new_customer(self): ...
    # check_access('create') y devuelve la acción de la ficha de contacto con el contexto de la app.
```

- `action_customer_management_customers_window`: se agrega `'partner_vat_check_scope': 'customer'` al contexto.
- `res_partner_view_list_customer_management`: se agrega en `<header>` el botón `action_customer_management_new_customer` ("Nuevo cliente", `display="always"`, `groups="base.group_partner_manager,sales_team.group_sale_manager"`). Sigue con `create="0"` y `editable="bottom"`.
- `res_config_settings_view_form`: el campo `customer_vat_duplicate_policy` en la sección Clientes.

### `supplier_management` (cambios)

```python
# __manifest__.py
'depends': ['customer_account_statement', 'purchase', 'partner_vat_check'],
```

```python
# models/res_partner.py
class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def default_get(self, fields): ...
    # Con partner_vat_check_scope = 'supplier' en el contexto: company_ids = [env.company].
```

- `action_supplier_management_suppliers`: se agrega `'partner_vat_check_scope': 'supplier'` al contexto.
- `res_partner_view_list_supplier_management`: se quita `create="0"`.
- `res_config_settings_view_form`: el campo `supplier_vat_duplicate_policy` en la sección Proveedores.

Convenciones:

- **CUIT normalizado:** `re.sub(r'[^0-9A-Za-z]', '', vat).upper()`. En SQL: `regexp_replace(upper(vat), '[^0-9A-Z]', '', 'g')`.
- **Contacto comparable:** `parent_id IS NULL`, `active = True`, rango del scope `> 0`, `id` distinto del contacto que se guarda, cualquier empresa (`company_id` no se filtra).
- Un contacto hijo (con padre) no se controla: hereda el CUIT de su empresa padre.
- Un contacto sin CUIT no se controla.
- El contacto que se guarda se controla aunque todavía no tenga el rango del scope (por ejemplo, un cliente editado desde la app Proveedores).
- **Ajuste sin parámetro** (borrado a mano): se toma `block`.
- **Mensaje de bloqueo** (`ValidationError`): *"El CUIT 30-12345678-9 ya está cargado en el cliente Ejemplo S.A."* (o "proveedor" según la app).
- **Aviso** (`message_post` como nota en el chatter del contacto guardado): *"Atención: el CUIT 30-12345678-9 también está cargado en el cliente Ejemplo S.A."*
- El scope llega por contexto. La ficha abierta desde el listado de la app, o con "Nuevo" / "Nuevo cliente", hereda el contexto de la acción.

Archivos del módulo nuevo:

```text
partner_vat_check/
├── __init__.py
├── __manifest__.py
├── README.md
├── data/
│   └── ir_config_parameter_data.xml
└── models/
    ├── __init__.py
    ├── res_config_settings.py
    └── res_partner.py
```

No crea tablas ni columnas en tablas permanentes.

## Plan de implementación

1. Crear el esqueleto de `partner_vat_check` (manifiesto, `__init__.py`, modelos vacíos). Prueba manual: se instala con `-i partner_vat_check` sin errores.
2. Agregar `VAT_CHECK_POLICIES`, `VAT_CHECK_SCOPES`, los dos campos de Ajustes y `data/ir_config_parameter_data.xml`. Prueba manual: después de instalar, `ir_config_parameter` tiene los dos parámetros en `block`.
3. Implementar `_normalize_vat_for_check` y `_get_vat_duplicate_partners(scope)` con la consulta SQL. Prueba manual en `odoo shell`: dos clientes con "30-12345678-9" y "30123456789" se detectan como duplicados.
4. Implementar el bloqueo (`_check_vat_duplicate_app`, solo con el scope en el contexto y el ajuste en `block`). Prueba manual en `odoo shell`: con el contexto, crear un cliente con CUIT repetido da `ValidationError`; sin el contexto, se crea.
5. Implementar el aviso en `create` y `write` (ajuste en `warn`: `message_post` en el contacto guardado). Prueba manual: el contacto se guarda y el chatter muestra el aviso.
6. En `customer_management`, agregar la dependencia, el scope en el contexto de la acción del listado y `default_get` (empresa activa y vendedor). Prueba manual: "Nuevo" en la vista kanban de Clientes abre la ficha con Es empresa, cliente, empresa activa y vendedor precargados.
7. Agregar el botón "Nuevo cliente" en la cabecera del listado y `action_customer_management_new_customer`. Prueba manual: el botón abre la ficha completa, y la columna Vendedor se sigue editando en línea.
8. Agregar `customer_vat_duplicate_policy` en la sección Clientes de Ajustes.
9. En `supplier_management`, agregar la dependencia, quitar `create="0"`, sumar el scope al contexto de la acción, `default_get` (empresa activa) y `supplier_vat_duplicate_policy` en la sección Proveedores de Ajustes. Prueba manual: "Nuevo" abre la ficha con Es empresa, proveedor y empresa activa precargados.
10. Crear `partner_vat_check/README.md` y actualizar `customer_management/README.md` y `supplier_management/README.md` según `AGENTS.md`, con la sección Base de datos y la línea "Base de datos:" en el historial.

## Criterios de aceptación

Verificación manual sobre `odoo_prueba` con al menos dos empresas, un usuario administrador, un usuario de Facturación sin *Creación de contactos*, un vendedor y un usuario con *Creación de contactos* y Ventas: Usuario.

**Alta desde Clientes**

- [ ] `partner_vat_check` se instala y desinstala sin errores ni advertencias en el log.
- [ ] El listado de Clientes muestra el botón "Nuevo cliente" a un usuario con *Creación de contactos*.
- [ ] Un usuario sin permiso para crear contactos no ve el botón "Nuevo cliente".
- [ ] "Nuevo cliente" abre la ficha completa del contacto, no una fila en la lista.
- [ ] La ficha nueva viene con Es empresa tildado, la empresa activa tildada en "Empresas en las que participa" y, al guardar, el contacto tiene `customer_rank = 1`.
- [ ] Si quien crea tiene Ventas: Usuario, el Vendedor viene con su usuario y se puede cambiar.
- [ ] Si quien crea no tiene Ventas: Usuario, el Vendedor viene vacío.
- [ ] El cliente nuevo aparece en el listado con el filtro "Clientes" activo.
- [ ] La columna Vendedor del listado se sigue editando en línea como en la SPEC 02.

**Alta desde Proveedores**

- [ ] El listado de Proveedores muestra el botón "Nuevo" estándar a un usuario con *Creación de contactos*.
- [ ] Un usuario sin permiso para crear contactos no ve el botón "Nuevo".
- [ ] La ficha nueva viene con Es empresa tildado y la empresa activa tildada; al guardar, el contacto tiene `supplier_rank = 1`.
- [ ] La ficha nueva de proveedor no precarga Vendedor.
- [ ] El proveedor nuevo aparece en el listado con el filtro "Proveedores" activo.

**CUIT repetido**

- [ ] Al instalar, los ajustes "CUIT repetido" de Clientes y de Proveedores están en Bloquear.
- [ ] La sección Clientes de Ajustes muestra "CUIT repetido en Clientes", y la sección Proveedores muestra "CUIT repetido en Proveedores".
- [ ] Con Bloquear en Clientes, guardar un cliente nuevo con el CUIT de otro cliente activo muestra un error que nombra a ese cliente, y no se guarda.
- [ ] Con Bloquear, "30-12345678-9" y "30123456789" se consideran el mismo CUIT.
- [ ] Con Bloquear, cambiar el CUIT de un cliente existente al de otro cliente también da error.
- [ ] Con Bloquear en Clientes, un CUIT que solo tiene un proveedor (que no es cliente) no da error.
- [ ] Con Bloquear, un CUIT que solo tiene un cliente archivado no da error.
- [ ] Con Avisar, el cliente se guarda y su chatter muestra el aviso con el nombre del otro cliente.
- [ ] Con No controlar, se guarda sin error ni aviso.
- [ ] El ajuste de Proveedores se aplica igual en la app Proveedores, comparando solo contra proveedores.
- [ ] Cambiar el ajuste de Clientes no cambia el comportamiento en Proveedores, y viceversa.
- [ ] Crear un contacto con CUIT repetido desde Contactos o desde Facturación → Clientes se guarda sin error ni aviso.
- [ ] Un contacto hijo (persona dentro de una empresa) no dispara el control.

**Documentación**

- [ ] `partner_vat_check/README.md`, `customer_management/README.md` y `supplier_management/README.md` cumplen `AGENTS.md`, con la sección Base de datos y la línea "Base de datos:" en el historial.

## Decisiones

- **Sí:** el alta abre la ficha completa del contacto. Permite cargar CUIT, dirección y datos fiscales.
- **No:** fila nueva en la lista ni ventana rápida. No alcanzan para cargar los datos fiscales.
- **Sí:** en Clientes, botón propio "Nuevo cliente" en la cabecera. Así la edición en línea del Vendedor de la SPEC 02 queda igual.
- **No:** quitar la edición en línea de Clientes para usar el "Nuevo" estándar. Cambia un comportamiento ya acordado en la SPEC 02.
- **Sí:** en Proveedores, el "Nuevo" estándar, porque su lista no es editable.
- **Sí:** permisos estándar de Odoo para crear contactos. No se toca la seguridad de `res.partner`.
- **No:** dar alta de contactos a Facturación, vendedores o Compras. Ampliaría permisos en todo Odoo.
- **Sí:** precargar Es empresa, el rango, la empresa activa y, en Clientes, el Vendedor.
- **Sí:** Vendedor = usuario que crea si tiene `sales_team.group_sale_salesman`, aunque además sea de Facturación o gerente. Decisión del usuario, aunque se recomendó limitarlo a vendedores sin más permisos.
- **Sí:** precarga con `default_get` según el scope del contexto. Cubre el botón "Nuevo cliente" y el "Nuevo" del kanban con una sola regla.
- **Sí:** control de CUIT en un módulo nuevo `partner_vat_check`, del que dependen las dos apps. No mezcla el estado de cuenta con validaciones de contactos y evita duplicar código.
- **No:** ponerlo en `customer_account_statement` o duplicarlo en cada app.
- **Sí:** un ajuste por app, aunque se recomendó uno compartido. Decisión del usuario.
- **Sí:** selector con tres opciones (Bloquear / Avisar / No controlar), Bloquear por defecto. Decisión del usuario, aunque se recomendó una casilla.
- **Sí:** el control rige solo dentro de las apps, con el scope en el contexto. Decisión del usuario, aunque se recomendó en todo Odoo.
- **Sí:** se controla solo al guardar. Avisar deja una nota en el chatter. Decisión del usuario, aunque se recomendó además un aviso en vivo.
- **Sí:** se controla al crear y al cambiar el CUIT.
- **Sí:** comparación solo contra clientes en Clientes y solo contra proveedores en Proveedores, activos, de cualquier empresa, con el CUIT normalizado. Decisión del usuario.
- **Sí:** la comparación se hace en SQL con `regexp_replace`, sin columna nueva. Evita guardar un CUIT normalizado aparte.
- **No:** validar el formato o el dígito verificador del CUIT. Es otra regla; va en otra spec si hace falta.
- **No:** tests automáticos. La verificación es manual con los criterios de aceptación.

## Riesgos

| Riesgo | Mitigación |
| --- | --- |
| El control depende del contexto: si la ficha se abre desde otro lado (por ejemplo, un enlace del chatter), no se controla. | Es el alcance acordado ("solo en las apps"). Queda escrito en el README de `partner_vat_check`. Controlarlo en todo Odoo es otra spec. |
| El contexto `partner_vat_check_scope` se propaga a registros que se crean desde la ficha (por ejemplo, contactos hijos). | El control ignora contactos con padre. Los registros de otros modelos no leen esa clave. |
| La consulta con `regexp_replace` recorre todos los contactos con CUIT en cada guardado. | Filtra antes por `parent_id IS NULL`, `active` y rango. Si en la prueba con la base más grande tarda más de 1 segundo, se agrega un índice funcional en otra spec. |
| Duplicados que ya existen en la base bloquean la edición del CUIT de esos contactos desde la app. | Solo se controla cuando cambia `vat` o `parent_id`. Editar otros campos no dispara el control. Limpiar duplicados va en otra spec. |
| El Gerente de ventas solo puede crear contactos si `sale` está instalado. Sin `sale`, ve el botón "Nuevo cliente" y recibe error de acceso. | `action_customer_management_new_customer` llama a `check_access('create')` y muestra un mensaje claro. Se documenta en Configuraciones esenciales. |

## Qué **no** incluye esta spec

- Control de CUIT en todo Odoo.
- Aviso en vivo al escribir el CUIT.
- Validación de formato o dígito verificador.
- Limpieza o fusión de duplicados existentes.
- Permisos de alta para Facturación, vendedores o Compras.
- Ventana de alta rápida.
- Tests automáticos.

Cada uno de estos, si se hace, va en su propia spec.
