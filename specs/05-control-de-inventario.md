# SPEC 05 — App Control de inventario: movimientos con motivo, controles de conteo y auditoría de stock

> **Estado:** Implementado
> **Depende de:** ninguna
> **Fecha:** 2026-10-21
> **Objetivo:** Una app "Control de inventario" (módulo `stock_control`) sobre el Inventario de Odoo que registra entradas y salidas con motivo, arma controles de conteo por depósito y categoría con planilla imprimible, bloquea los controles guardados y da una auditoría completa de los movimientos de stock.

## Por qué existe esta spec

Compras maneja los productos (`/odoo/purchase-products`).
La app Inventario de Odoo ya está activada, pero no da control con motivos, conteos cerrados ni una auditoría en un solo lugar.

En lugar de construir existencias propias, la spec usa el módulo estándar **Inventario (`stock`)**.
Inventario ya resuelve existencias por ubicación, recepciones de compras, entregas de ventas y trazabilidad.
`stock_control` agrega encima lo que falta para tener control y auditoría:

- Movimientos manuales con motivo obligatorio, que no se pueden editar una vez confirmados.
- Controles de inventario con planilla de conteo, carga del conteo y ajuste automático.
- Controles guardados en solo lectura, que solo un administrador puede reabrir.
- Listado de auditoría, ficha por producto (kardex) e informe de diferencias.

Lo que Inventario estándar ya resuelve no se rehace, se reutiliza:

| Necesidad | Qué se usa de Odoo |
| --- | --- |
| Listar productos con stock y filtrar por categoría | Acción estándar `stock.product_template_action_product` (Inventario > Productos) |
| Existencias por ubicación | Acción estándar `stock.action_view_quants` (Inventario > Informes > Stock por ubicación) |
| Mostrar u ocultar el teórico en la planilla | Parámetro estándar `stock.show_expected_quantity_count`, el mismo que usa "Solicitar un conteo" de Inventario |
| Salidas por rotura o desecho | "Desechar" estándar (Inventario > Operaciones > Ajustes > Desechar) sigue disponible. En Odoo 20 es un `stock.move` con `is_scrap = True` y `scrap_reason_tag_ids`, y aparece en la auditoría con origen Desecho |
| Movimientos de compras y ventas | Recepciones y entregas estándar de `purchase_stock` y `sale_stock` |

Lo que Odoo no trae, y por eso hace este módulo:

- El conteo guardado como documento (control de inventario), con su historial, que queda cerrado y solo un administrador reabre.
- El informe de diferencias por control y el kardex con saldo acumulado.
- Las entradas y salidas manuales con un motivo de una lista. En Odoo estándar, las entradas sin compra solo se hacen como ajuste de inventario, con texto libre.
- La auditoría con el origen, el motivo y quién validó en columnas que se pueden filtrar.

Al activar Inventario con Facturación instalada, Odoo instala solo `stock_account`, `purchase_stock` y `sale_stock` (`auto_install`).
En Odoo 20, `purchase_stock` y `sale_stock` dependen de `stock_account`, así que no se puede tener una cosa sin la otra.
La valuación por defecto es **Periódica** (`res.company.inventory_valuation = 'periodic'`): los movimientos de stock no generan asientos automáticos.

Esta spec no cambia esa configuración ni usa los valores de `stock_account`.
Mostrar movimientos y diferencias en pesos, y definir el método de costo y la valuación, queda para la SPEC 06, para no mezclar decisiones contables con esta.

## Alcance

**Incluye:**

*Dependencias estándar (ya activadas con Inventario):*

- `stock` (Inventario), `purchase_stock` (las compras generan recepciones) y `sale_stock` (las ventas generan entregas).
- `stock_account`, que llega como dependencia. Se deja con la configuración de valuación que tenga cada empresa.
- Varios depósitos (`stock.warehouse`) por empresa, con sus ubicaciones internas.

*App "Control de inventario" (módulo nuevo `stock_control`):*

- App en el menú principal, con ícono, visible para los grupos del módulo.
- Menús:
  - **Productos:** abre la acción estándar `stock.product_template_action_product`, con los filtros estándar por categoría y depósito. No se crean vistas nuevas.
  - **Existencias:** abre la acción estándar `stock.action_view_quants` (stock por producto y ubicación), con sus filtros estándar. No se crean vistas nuevas.
  - **Movimientos manuales:** entradas y salidas cargadas a mano.
  - **Controles de inventario:** los conteos.
  - **Auditoría** (solo Administrador): Movimientos, Ficha por producto (kardex) y Diferencias de controles.
  - **Configuración** (solo Administrador): Motivos y Ajustes.

*Grupos:*

- **Control de inventario: Usuario** (`stock_control.group_stock_control_user`). Implica `stock.group_stock_user`. Ve productos y existencias, carga y confirma movimientos manuales, y crea, imprime y carga controles.
- **Control de inventario: Administrador** (`stock_control.group_stock_control_manager`). Implica el grupo Usuario. Además reabre controles, ve la auditoría y mantiene motivos y ajustes.

*Movimientos manuales:*

- Cabecera: número, tipo (Entrada / Salida), depósito, ubicación, fecha, motivo (obligatorio), observación y empresa.
- Líneas: producto (solo `is_storable`), cantidad y unidad.
- Estados: **Borrador** → **Confirmado**. Además, **Cancelado** desde Borrador.
- Al confirmar se crea y se valida un `stock.move` por línea:
  - Entrada: desde la ubicación de ajuste de inventario del producto (`property_stock_inventory`) hacia la ubicación elegida.
  - Salida: desde la ubicación elegida hacia la ubicación de ajuste de inventario.
- Una salida no puede dejar el stock de la ubicación en negativo.
- Confirmado no se edita ni se borra. Se corrige con el botón **"Revertir"**, que crea y confirma un movimiento manual inverso, enlazado al original.
- Numeración por empresa: `MM/AAAA/0001`.

*Motivos:*

- Tabla de motivos (`stock.control.reason`) que mantiene el Administrador: nombre, tipo en el que aplica (Entrada, Salida o Ambos) y activo.
- Al instalar se cargan: Rotura, Vencimiento, Consumo interno, Devolución de cliente, Devolución a proveedor, Muestra, Regalo y Otro.

*Controles de inventario:*

- Cada control es de **un depósito** (todas sus ubicaciones internas) y de **una o varias categorías**, con la opción "Incluir subcategorías".
- Entran todos los productos `is_storable` de esas categorías, aunque tengan stock 0.
- Estados:
  1. **Borrador:** se eligen depósito, categorías y fecha. Se puede editar y borrar.
  2. **En conteo:** el botón **"Iniciar conteo"** genera una línea por producto y ubicación. Las ubicaciones salen de las existencias del producto dentro del depósito. Si el producto no tiene existencias, la línea va a la ubicación principal del depósito (`lot_stock_id`). Se imprime la planilla, se cargan las cantidades y se pueden agregar líneas a mano (un producto que apareció en otra ubicación).
  3. **Guardado:** el botón **"Guardar control"** aplica el ajuste y deja el control en solo lectura.
  4. **Reabierto:** solo el Administrador, con el botón **"Reabrir"**, que pide un motivo de reapertura. Se edita el conteo y se vuelve a guardar.
  5. **Cancelado:** desde Borrador o En conteo, sin tocar el stock.
- Una línea sin cantidad cargada es **No contada**: no se ajusta y queda marcada así. Para indicar que no hay stock, se carga 0.
- **Cantidad teórica**, según el ajuste "Comparar contra":
  - **Al guardar:** se toma la existencia de la ubicación en el momento de guardar. El ajuste lleva el stock exactamente a lo contado.
  - **Al iniciar el conteo:** se congela la existencia al apretar "Iniciar conteo". El ajuste es (contado − congelado), así que los movimientos hechos durante el conteo no se pisan.
  - El modo se copia al control al iniciar el conteo. Cambiar el ajuste después no afecta controles ya iniciados.
- **Ajuste al guardar:** por cada línea contada con diferencia distinta de cero, se crea y se valida un `stock.move` de inventario (`is_inventory = True`) entre la ubicación de la línea y la de ajuste de inventario, con referencia = número del control.
- **Al volver a guardar un control reabierto:** por cada línea se aplica solo la corrección (conteo nuevo − conteo ya aplicado). Los movimientos originales no se tocan. Una línea que antes estaba No contada y ahora tiene cantidad se ajusta como la primera vez.
- Numeración por empresa: `CI/AAAA/0001`. La empresa del control es la del depósito.
- Historial de eventos del control (inicio, guardado, reapertura con motivo, nuevo guardado), con usuario y fecha.

*Planilla de conteo (PDF):*

- Se imprime desde un control En conteo o Reabierto.
- Cabecera: número, empresa, depósito, categorías, fecha y espacio para la firma de quien cuenta.
- Agrupada por ubicación y categoría, ordenada por código y nombre.
- Columnas: Código (`default_code`), Producto, Unidad, Cantidad contada (en blanco) y Observaciones (en blanco).
- La columna **Teórico** se imprime solo si está tildado el ajuste "Mostrar cantidad teórica en la planilla".
  - El ajuste guarda el parámetro estándar `stock.show_expected_quantity_count`. Es el mismo que usan la "Hoja de conteo" y "Solicitar un conteo" de Inventario, así que vale igual en las dos apps.
  - Si el parámetro no existe, no se imprime (conteo ciego).
- La planilla es propia, porque lista las líneas del control. La "Hoja de conteo" estándar lista existencias sueltas y no está atada a un control.

*Auditoría (solo Administrador):*

- **Movimientos:** listado de los `stock.move` hechos (estado `done`), con fecha, referencia, producto, categoría, depósito, ubicación origen y destino, cantidad con signo (entrada + / salida −), unidad, origen, motivo y quién lo validó.
  - **Origen** del movimiento: Compra, Venta, Movimiento manual, Control de inventario, Desecho (el "Desechar" estándar) u Otro (transferencias internas y ajustes hechos desde el Inventario físico estándar).
  - **Motivo:** el motivo del movimiento manual. En los desechos, las etiquetas de motivo estándar (`stock.move.scrap_reason_tag_ids`). En los ajustes estándar, el texto que se cargó al aplicar.
  - Filtros por origen, depósito, categoría, producto, motivo, usuario y fecha. Agrupación por cualquiera de ellos.
  - Exportación con el "Exportar" estándar de la lista.
- **Ficha por producto (kardex):** asistente con producto, depósito (opcional, vacío = todos) y fechas desde y hasta. Muestra en PDF el saldo inicial, cada movimiento (fecha, referencia, origen, motivo, entrada, salida y saldo acumulado) y el saldo final.
- **Diferencias de controles:** listado de líneas de controles guardados, con control, fecha, depósito, producto, teórico, contado, diferencia y estado de la línea, con filtros por control, depósito, categoría y fecha. Desde cada control se imprime el PDF **"Informe de diferencias"**, que incluye su historial de eventos.

*Productos de Compras:*

- En el listado de `/odoo/purchase-products` se agrega la columna **"Stock"** (`qty_available`), visible para los grupos del módulo.
- En la ficha del producto, el botón **"Movimientos"** abre la auditoría filtrada por ese producto, visible solo para el Administrador. El stock disponible ya lo muestra Inventario estándar.

*Ajustes (sección "Control de inventario", solo Administrador), globales:*

- "Comparar contra": Al guardar (por defecto) / Al iniciar el conteo.
- "Mostrar cantidad teórica en la planilla": guarda el parámetro estándar `stock.show_expected_quantity_count`. El módulo no lo crea ni lo cambia al instalar.

*Multiempresa:*

- Movimientos manuales, controles y motivos tienen empresa. Cada usuario ve solo los de sus empresas permitidas.

**Fuera de alcance (para futuras specs):**

- Valorización en pesos de movimientos y diferencias, y su impacto contable (`stock_account`): SPEC 06.
- Lotes y números de serie.
- Controles por una sola ubicación (sin el depósito completo).
- Bloquear recepciones o entregas mientras hay un control abierto.
- Ajuste "Comparar contra" por control.
- Aprobación de movimientos manuales por un administrador.
- Carga del conteo desde Excel, lector de código de barras o celular.
- Ocultar o deshabilitar los ajustes de inventario de la app Inventario estándar.
- Transferencias entre depósitos desde la app.
- Reposición automática, stock mínimo y alertas.
- Tests automáticos.

## Modelo de datos

### `stock_control` (nuevo)

Ruta: `C:\Users\Daniel\Archivos\custom_addons\stock_control`.

```python
# __manifest__.py (extracto)
{
    'name': 'Control de inventario',
    'version': '1.0',
    'category': 'Inventory/Inventory',
    'author': 'Daniel',
    'depends': ['stock', 'purchase_stock', 'sale_stock', 'mail'],
    'application': True,
    'license': 'LGPL-3',
}
```

```python
# models/stock_control_reason.py
class StockControlReason(models.Model):
    _name = 'stock.control.reason'
    _description = 'Motivo de movimiento de stock'
    _order = 'sequence, name'

    name = fields.Char('Motivo', required=True, translate=True)
    sequence = fields.Integer(default=10)
    move_type = fields.Selection(
        [('in', 'Entrada'), ('out', 'Salida'), ('both', 'Ambos')],
        string='Aplica en', required=True, default='both')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company')   # vacío = todas las empresas
```

```python
# models/stock_control_manual_move.py
class StockControlManualMove(models.Model):
    _name = 'stock.control.manual.move'
    _description = 'Movimiento manual de stock'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char('Número', readonly=True, copy=False, default='/')   # MM/AAAA/0001
    move_type = fields.Selection([('in', 'Entrada'), ('out', 'Salida')], required=True, tracking=True)
    warehouse_id = fields.Many2one('stock.warehouse', 'Depósito', required=True)
    location_id = fields.Many2one('stock.location', 'Ubicación', required=True)   # interna, del depósito
    date = fields.Datetime('Fecha', required=True, default=fields.Datetime.now)
    reason_id = fields.Many2one('stock.control.reason', 'Motivo', required=True, tracking=True)
    note = fields.Text('Observación')
    state = fields.Selection(
        [('draft', 'Borrador'), ('done', 'Confirmado'), ('cancel', 'Cancelado')],
        default='draft', tracking=True)
    company_id = fields.Many2one(related='warehouse_id.company_id', store=True)
    line_ids = fields.One2many('stock.control.manual.move.line', 'manual_move_id', 'Líneas')
    move_ids = fields.One2many('stock.move', 'stock_control_manual_move_id', 'Movimientos de stock')
    reversed_move_id = fields.Many2one('stock.control.manual.move', 'Revierte a', readonly=True)
    reversal_ids = fields.One2many('stock.control.manual.move', 'reversed_move_id', 'Reversiones')

    def action_confirm(self): ...   # crea y valida un stock.move por línea; controla stock negativo en salidas
    def action_cancel(self): ...    # solo desde Borrador
    def action_reverse(self): ...   # crea y confirma el movimiento inverso, con el mismo motivo


class StockControlManualMoveLine(models.Model):
    _name = 'stock.control.manual.move.line'
    _description = 'Línea de movimiento manual de stock'

    manual_move_id = fields.Many2one('stock.control.manual.move', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', 'Producto', required=True,
                                 domain="[('is_storable', '=', True)]")
    quantity = fields.Float('Cantidad', required=True, digits='Product Unit')
    uom_id = fields.Many2one(related='product_id.uom_id')
```

```python
# models/stock_control_inventory.py
THEORETICAL_MODES = [
    ('on_save', 'Al guardar'),
    ('on_start', 'Al iniciar el conteo'),
]


class StockControlInventory(models.Model):
    _name = 'stock.control.inventory'
    _description = 'Control de inventario'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char('Número', readonly=True, copy=False, default='/')   # CI/AAAA/0001
    warehouse_id = fields.Many2one('stock.warehouse', 'Depósito', required=True)
    category_ids = fields.Many2many('product.category', string='Categorías', required=True)
    include_child_categories = fields.Boolean('Incluir subcategorías', default=True)
    date = fields.Date('Fecha', required=True, default=fields.Date.context_today)
    theoretical_mode = fields.Selection(THEORETICAL_MODES, 'Comparar contra', readonly=True)  # se copia de Ajustes al iniciar
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('in_progress', 'En conteo'),
        ('done', 'Guardado'),
        ('reopened', 'Reabierto'),
        ('cancel', 'Cancelado'),
    ], default='draft', tracking=True)
    company_id = fields.Many2one(related='warehouse_id.company_id', store=True)
    line_ids = fields.One2many('stock.control.inventory.line', 'inventory_id', 'Líneas')
    event_ids = fields.One2many('stock.control.inventory.event', 'inventory_id', 'Historial')
    move_ids = fields.One2many('stock.move', 'stock_control_inventory_id', 'Movimientos de ajuste')
    is_locked = fields.Boolean(compute='_compute_is_locked')   # True en Guardado y Cancelado; la vista lo usa en readonly

    def action_start(self): ...     # genera líneas; en modo on_start congela theoretical_qty
    def action_save(self): ...      # aplica ajustes o correcciones; pasa a Guardado
    def action_reopen(self): ...    # solo Administrador; abre el asistente de motivo
    def action_cancel(self): ...    # solo desde Borrador o En conteo
    def action_print_sheet(self): ...
    def action_print_differences(self): ...
    # write/unlink: en Guardado o Cancelado solo se permite lo que hacen los botones (control en Python, no solo en la vista).


class StockControlInventoryLine(models.Model):
    _name = 'stock.control.inventory.line'
    _description = 'Línea de control de inventario'
    _order = 'location_id, categ_id, default_code, product_id'

    inventory_id = fields.Many2one('stock.control.inventory', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', 'Producto', required=True)
    default_code = fields.Char(related='product_id.default_code', store=True)
    categ_id = fields.Many2one(related='product_id.categ_id', store=True)
    location_id = fields.Many2one('stock.location', 'Ubicación', required=True)
    uom_id = fields.Many2one(related='product_id.uom_id')
    theoretical_qty = fields.Float('Teórico', digits='Product Unit', readonly=True)
    counted_qty = fields.Float('Contado', digits='Product Unit')
    is_counted = fields.Boolean('Contada')   # se tilda al cargar counted_qty; sin tildar = No contada
    applied_counted_qty = fields.Float(digits='Product Unit', readonly=True)  # conteo ya aplicado al stock
    is_applied = fields.Boolean(readonly=True)                                # ya tuvo un ajuste aplicado
    difference_qty = fields.Float('Diferencia', compute='_compute_difference_qty', store=True)
    line_state = fields.Selection(
        [('not_counted', 'No contada'), ('ok', 'Sin diferencia'), ('diff', 'Con diferencia')],
        compute='_compute_difference_qty', store=True)
    move_ids = fields.One2many('stock.move', 'stock_control_inventory_line_id')
    _unique_product_location = models.Constraint(
        'unique(inventory_id, product_id, location_id)',
        'El producto ya está en esa ubicación dentro del control.')


class StockControlInventoryEvent(models.Model):
    _name = 'stock.control.inventory.event'
    _description = 'Evento de control de inventario'
    _order = 'date desc, id desc'

    inventory_id = fields.Many2one('stock.control.inventory', required=True, ondelete='cascade', index=True)
    event_type = fields.Selection([
        ('start', 'Inicio del conteo'),
        ('save', 'Guardado'),
        ('reopen', 'Reapertura'),
        ('resave', 'Guardado después de reabrir'),
        ('cancel', 'Cancelación'),
    ], required=True)
    user_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user)
    date = fields.Datetime(required=True, default=fields.Datetime.now)
    reason = fields.Text('Motivo')   # obligatorio en reopen
    adjusted_line_count = fields.Integer('Líneas ajustadas')
```

```python
# models/stock_move.py
STOCK_CONTROL_ORIGINS = [
    ('purchase', 'Compra'),
    ('sale', 'Venta'),
    ('manual', 'Movimiento manual'),
    ('inventory', 'Control de inventario'),
    ('scrap', 'Desecho'),
    ('other', 'Otro'),
]


class StockMove(models.Model):
    _inherit = 'stock.move'

    stock_control_manual_move_id = fields.Many2one('stock.control.manual.move', index='btree_not_null', readonly=True)
    stock_control_inventory_id = fields.Many2one('stock.control.inventory', index='btree_not_null', readonly=True)
    stock_control_inventory_line_id = fields.Many2one('stock.control.inventory.line', index='btree_not_null', readonly=True)
    stock_control_reason_id = fields.Many2one('stock.control.reason', 'Motivo', readonly=True)
    stock_control_reason_text = fields.Char('Motivo (texto)', compute=..., store=True)
    # motivo propio, o las etiquetas del desecho (scrap_reason_tag_ids), o inventory_name en ajustes estándar
    stock_control_origin = fields.Selection(STOCK_CONTROL_ORIGINS, 'Origen',
                                            compute='_compute_stock_control_origin', store=True)
    stock_control_done_user_id = fields.Many2one('res.users', 'Validado por', readonly=True)  # se escribe en _action_done
    stock_control_signed_qty = fields.Float('Cantidad (±)', compute=..., store=True)
    # + si el destino es interno y el origen no; − al revés; 0 entre internas.
    stock_control_warehouse_id = fields.Many2one('stock.warehouse', 'Depósito', compute=..., store=True)
    # depósito de la ubicación interna del movimiento (destino en entradas, origen en salidas)
```

```python
# models/res_config_settings.py
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    stock_control_theoretical_mode = fields.Selection(
        THEORETICAL_MODES, string='Comparar contra',
        config_parameter='stock_control.theoretical_mode')
    stock_control_sheet_show_theoretical = fields.Boolean(
        'Mostrar cantidad teórica en la planilla',
        config_parameter='stock.show_expected_quantity_count')   # parámetro estándar de Inventario
```

```python
# wizard/stock_control_reopen_wizard.py
class StockControlReopenWizard(models.TransientModel):
    _name = 'stock.control.reopen.wizard'
    inventory_id = fields.Many2one('stock.control.inventory', required=True)
    reason = fields.Text('Motivo de la reapertura', required=True)

# wizard/stock_control_kardex_wizard.py
class StockControlKardexWizard(models.TransientModel):
    _name = 'stock.control.kardex.wizard'
    product_id = fields.Many2one('product.product', required=True, domain="[('is_storable', '=', True)]")
    warehouse_id = fields.Many2one('stock.warehouse')   # vacío = todos los depósitos de la empresa
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    def action_print(self): ...
```

Convenciones:

- **Ajuste aplicado** (control): `stock.move` con `is_inventory = True`, `inventory_name` = número del control, `stock_control_inventory_id` y `stock_control_inventory_line_id`. Entre `line.location_id` y `product_id.property_stock_inventory` (o la ubicación por defecto de la empresa si falta), según el signo. Se valida con `_action_done()`.
- **Cantidad a ajustar** en una línea contada:
  - Primera vez (`is_applied = False`), modo `on_save`: `counted_qty − existencia actual de la ubicación`.
  - Primera vez, modo `on_start`: `counted_qty − theoretical_qty`.
  - Ya aplicada (`is_applied = True`): `counted_qty − applied_counted_qty`.
  - Después de aplicar: `applied_counted_qty = counted_qty`, `is_applied = True`.
  - En modo `on_save`, `theoretical_qty` se escribe al guardar con la existencia que se usó.
- **Diferencia mostrada:** `counted_qty − theoretical_qty` en líneas contadas, y 0 en No contadas.
- **Existencia de una ubicación:** suma de `stock.quant.quantity` del producto en esa ubicación exacta (sin hijas, porque cada ubicación tiene su propia línea).
- Una línea agregada a mano en un control en modo `on_start` toma como teórico la existencia en el momento de agregarla.
- **Origen de un `stock.move`:** `inventory` si tiene `stock_control_inventory_id`; `manual` si tiene `stock_control_manual_move_id`; `scrap` si `is_scrap = True`; `purchase` si tiene `purchase_line_id`; `sale` si tiene `sale_line_id`; si no, `other`.
- **Movimiento manual:** `stock.move` con `stock_control_manual_move_id` y `stock_control_reason_id`, `is_inventory = False`, referencia = número del movimiento manual.
- **Mensaje de stock negativo:** *"No hay stock suficiente de [COD] Producto en Depósito/Ubicación: hay 3 y querés sacar 5."*
- **Mensaje de control bloqueado:** *"El control CI/2026/0001 está guardado. Solo un administrador puede reabrirlo."*
- **Ajuste sin parámetro** (borrado a mano o nunca guardado): "Comparar contra" = `on_save`, "Mostrar cantidad teórica" = no.
- `data/ir_config_parameter_data.xml` crea solo `stock_control.theoretical_mode` = `on_save` (`noupdate="1"`). No toca `stock.show_expected_quantity_count`.
- Secuencias `ir.sequence` por empresa: `stock_control.seq_manual_move` (`MM/%(year)s/`, 4 dígitos) y `stock_control.seq_inventory` (`CI/%(year)s/`, 4 dígitos), con `company_id` vacío y `use_date_range` por año.

Permisos (`security/ir.access.csv`, formato Odoo 20):

| Modelo | Usuario | Administrador |
| --- | --- | --- |
| `stock.control.reason` | r | crud |
| `stock.control.manual.move` / `.line` | cru (unlink solo en Borrador, controlado en código) | crud |
| `stock.control.inventory` / `.line` | cru (unlink solo en Borrador, controlado en código) | crud |
| `stock.control.inventory.event` | r (los crea el código) | r |
| Asistentes de reapertura y kardex | — | crud |

Más reglas multiempresa con `[('company_id', 'in', company_ids)]` para los modelos con empresa.
La reapertura se controla en Python (`has_group('stock_control.group_stock_control_manager')`), no solo ocultando el botón.

Archivos del módulo nuevo:

```text
stock_control/
├── __init__.py
├── __manifest__.py
├── README.md
├── data/
│   ├── ir_config_parameter_data.xml
│   ├── ir_sequence_data.xml
│   └── stock_control_reason_data.xml
├── models/
│   ├── __init__.py
│   ├── res_config_settings.py
│   ├── stock_control_inventory.py
│   ├── stock_control_manual_move.py
│   ├── stock_control_reason.py
│   └── stock_move.py
├── report/
│   ├── stock_control_reports.xml
│   ├── report_count_sheet.xml
│   ├── report_differences.xml
│   └── report_kardex.xml
├── security/
│   ├── ir.access.csv
│   └── stock_control_security.xml
├── static/description/icon.png
├── views/
│   ├── menus.xml
│   ├── product_views.xml
│   ├── res_config_settings_views.xml
│   ├── stock_control_inventory_views.xml
│   ├── stock_control_manual_move_views.xml
│   ├── stock_control_reason_views.xml
│   └── stock_move_views.xml
└── wizard/
    ├── __init__.py
    ├── stock_control_kardex_wizard.py
    ├── stock_control_kardex_wizard_views.xml
    ├── stock_control_reopen_wizard.py
    └── stock_control_reopen_wizard_views.xml
```

Tablas nuevas permanentes: `stock_control_reason`, `stock_control_manual_move`, `stock_control_manual_move_line`, `stock_control_inventory`, `stock_control_inventory_line`, `stock_control_inventory_event` y la relación `product_category_stock_control_inventory_rel`.
Columnas nuevas en `stock_move`: las ocho `stock_control_*` de arriba.

## Plan de implementación

1. Verificar en `odoo_prueba` que `stock`, `stock_account`, `purchase_stock` y `sale_stock` están instalados (si falta alguno, instalarlo), que la valuación de cada empresa es Periódica, y crear dos depósitos en una empresa. Prueba manual: una compra confirmada genera una recepción, una venta genera una entrega, y validarlas no crea asientos.
2. Crear el esqueleto de `stock_control` (manifiesto, `__init__.py`, ícono, menú raíz vacío) y los dos grupos con su privilegio. Prueba manual: se instala con `-i stock_control` sin errores y la app aparece para un usuario del grupo.
3. Agregar `stock.control.reason` con vistas, menú Configuración > Motivos, permisos y datos iniciales. Prueba manual: el Administrador ve los ocho motivos y crea uno; el Usuario no ve el menú.
4. Agregar los campos `stock_control_*` en `stock.move`, el cómputo de origen, cantidad con signo y depósito, y `stock_control_done_user_id` en `_action_done`. Prueba manual en `odoo shell`: una recepción validada queda con origen Compra y el usuario que validó.
5. Agregar la vista de auditoría de movimientos (lista y búsqueda sobre `stock.move` con `state = done`) y el menú Auditoría > Movimientos. Prueba manual: la recepción y la entrega del paso 1 aparecen con su origen y su signo.
6. Agregar los menús Productos y Existencias de la app, apuntando a las acciones estándar `stock.product_template_action_product` y `stock.action_view_quants`. Prueba manual: los dos menús abren las mismas pantallas que en Inventario, con el filtro por categoría.
7. Crear `stock.control.manual.move` con sus líneas, la secuencia, las vistas, los permisos y `action_confirm` / `action_cancel`. Prueba manual: una entrada de 10 unidades sube el stock en 10 y aparece en auditoría con origen Movimiento manual y su motivo.
8. Agregar el control de stock negativo en salidas, el bloqueo de edición y borrado en Confirmado, y `action_reverse`. Prueba manual: una salida mayor al stock da error; "Revertir" deja el stock como estaba y enlaza los dos movimientos.
9. Crear `stock.control.inventory`, sus líneas y eventos, la secuencia, las vistas y los permisos, con los estados Borrador y Cancelado. Prueba manual: se crea un control con depósito y categorías, y se cancela.
10. Implementar `action_start`: generar líneas por producto y ubicación y copiar `theoretical_mode` desde Ajustes (y en modo `on_start`, congelar el teórico). Agregar los campos de Ajustes y `data/ir_config_parameter_data.xml`. Prueba manual: un producto con stock en dos ubicaciones genera dos líneas, y uno sin stock genera una línea en `lot_stock_id`.
11. Agregar el PDF de planilla de conteo, con la columna Teórico según `stock.show_expected_quantity_count`. Prueba manual: con el ajuste sin tildar, la planilla no muestra teórico; tildado, sí, y la "Hoja de conteo" estándar de Inventario cambia igual.
12. Implementar `action_save`: calcular la cantidad a ajustar por línea, crear y validar los `stock.move` de inventario, registrar el evento y bloquear el control (también en `write` y `unlink`). Prueba manual: después de guardar, el stock de cada línea contada es igual a lo contado y las No contadas no cambian.
13. Implementar la reapertura (asistente con motivo, solo Administrador) y el nuevo guardado con movimientos de corrección. Prueba manual: cambiar un contado de 8 a 10 en un control reabierto genera un movimiento de +2, y los movimientos originales siguen ahí.
14. Agregar Auditoría > Diferencias de controles y el PDF "Informe de diferencias" con el historial de eventos.
15. Agregar el asistente y el PDF de Ficha por producto (kardex), en Auditoría. Prueba manual: saldo inicial + entradas − salidas = saldo final, y coincide con la existencia a la fecha hasta.
16. Agregar la columna "Stock" al listado de `/odoo/purchase-products` y el botón "Movimientos" en la ficha del producto.
17. Crear `stock_control/README.md` según `AGENTS.md`, con la sección Base de datos relevada con `esquema_db.py` y la línea "Base de datos:" en el historial.

## Criterios de aceptación

Verificación manual sobre `odoo_prueba` con dos empresas, al menos dos depósitos en una de ellas, un usuario con *Control de inventario: Usuario*, un usuario con *Control de inventario: Administrador* y un usuario de Compras sin grupos del módulo.

**Instalación y acceso**

- [x] `stock_control` se instala y se desinstala sin errores ni advertencias en el log.
- [x] La app "Control de inventario" aparece para Usuario y Administrador, y no aparece para el usuario de Compras sin grupos del módulo.
- [x] El Usuario no ve los menús Auditoría ni Configuración.
- [x] Un usuario solo ve movimientos manuales, controles y motivos de sus empresas permitidas.

**Productos y existencias**

- [x] Los menús Productos y Existencias de la app abren las mismas pantallas que Inventario > Productos e Inventario > Informes > Stock por ubicación.
- [x] Productos y Existencias se filtran por categoría.
- [x] El listado de `/odoo/purchase-products` muestra la columna "Stock" a un usuario del módulo.
- [x] El botón "Movimientos" de la ficha de producto abre la auditoría filtrada por ese producto, y el Usuario no lo ve.

**Movimientos manuales**

- [x] No se puede confirmar un movimiento manual sin motivo.
- [x] Una entrada confirmada sube el stock de la ubicación elegida en la cantidad cargada.
- [x] Una salida confirmada baja el stock de la ubicación elegida en la cantidad cargada.
- [x] Una salida mayor al stock de la ubicación da el error de stock insuficiente y no se confirma.
- [x] Un movimiento manual Confirmado no se puede editar ni borrar, tampoco desde `odoo shell` sin `sudo`.
- [x] "Revertir" crea un movimiento inverso confirmado, enlazado al original, y el stock vuelve a la cantidad previa.
- [x] Los números siguen `MM/2026/0001` con numeración separada por empresa.

**Controles de inventario**

- [x] "Iniciar conteo" genera una línea por cada producto `is_storable` de las categorías elegidas y por cada ubicación interna del depósito donde tiene existencias.
- [x] Con "Incluir subcategorías" tildado, entran los productos de las subcategorías. Sin tildar, no entran.
- [x] Un producto sin existencias en el depósito genera una línea en la ubicación principal del depósito.
- [x] La planilla PDF agrupa por ubicación y categoría y tiene en blanco las columnas Cantidad contada y Observaciones.
- [x] Con "Mostrar cantidad teórica en la planilla" sin tildar, la planilla no muestra la columna Teórico. Tildado, la muestra.
- [x] Tildar o destildar "Mostrar cantidad teórica en la planilla" cambia también la "Hoja de conteo" estándar de Inventario.
- [x] Instalar `stock_control` no cambia el valor de `stock.show_expected_quantity_count`.
- [x] Con "Comparar contra = Al guardar", si entra una recepción de 5 unidades durante el conteo y se carga lo contado, después de guardar el stock es igual a lo contado.
- [x] Con "Comparar contra = Al iniciar el conteo", si entra una recepción de 5 unidades durante el conteo, después de guardar el stock es igual a lo contado + 5.
- [x] Cambiar "Comparar contra" en Ajustes no cambia el modo de un control ya iniciado.
- [x] Una línea sin cantidad cargada queda como "No contada" y su stock no cambia.
- [x] Una línea con 0 cargado deja el stock de esa ubicación en 0.
- [x] Cada ajuste aparece en auditoría con origen Control de inventario y el número del control como referencia.
- [x] Un control Guardado se ve en solo lectura para el Usuario y el Administrador.
- [x] El Usuario no ve el botón "Reabrir", y llamar a `action_reopen` con su usuario da error de acceso.
- [x] El Administrador no puede reabrir sin escribir un motivo.
- [x] En un control reabierto, cambiar un contado de 8 a 10 y guardar genera un único movimiento de corrección de +2, y los movimientos del primer guardado siguen sin cambios.
- [x] El historial del control muestra inicio, guardado, reapertura con motivo y nuevo guardado, cada uno con usuario y fecha.
- [x] Los números siguen `CI/2026/0001` con numeración separada por empresa.

**Auditoría**

- [x] Auditoría > Movimientos muestra recepciones de compra, entregas de venta, movimientos manuales, ajustes de control y desechos estándar, cada uno con el origen que le corresponde.
- [x] Un desecho estándar con etiqueta de motivo muestra esa etiqueta en la columna Motivo.
- [x] Cada movimiento muestra quién lo validó.
- [x] Las entradas a ubicaciones internas tienen cantidad positiva, y las salidas, negativa.
- [x] El listado se puede filtrar por origen, depósito, categoría, producto, motivo, usuario y fecha, y exportar.
- [x] La Ficha por producto muestra saldo inicial, movimientos con saldo acumulado y saldo final, y el saldo final coincide con la existencia del producto a la fecha hasta.
- [x] Diferencias de controles lista las líneas de controles guardados con teórico, contado y diferencia.
- [x] El "Informe de diferencias" de un control incluye sus líneas y su historial de eventos.

**Documentación**

- [x] `stock_control/README.md` cumple `AGENTS.md`, con la sección Base de datos y la línea "Base de datos:" en el historial.

## Decisiones

- **Sí:** construir sobre `stock` de Odoo. Existencias, ubicaciones, recepciones, entregas y trazabilidad ya están resueltas y probadas.
- **No:** existencias propias sin `stock`. Es mucho más trabajo y queda desconectado de compras y ventas.
- **Sí:** app propia "Control de inventario", decisión del usuario, aunque se recomendó un menú dentro de Compras.
- **Sí:** nombre técnico `stock_control`. Es corto y no choca con módulos de Odoo.
- **Sí:** instalar `purchase_stock` y `sale_stock`. Las compras y las ventas mueven stock, y la auditoría las muestra.
- **Sí:** varios depósitos. Cada control es de un depósito completo con todas sus ubicaciones internas.
- **No:** controles por una sola ubicación. Queda para otra spec si hace falta.
- **Sí:** dos grupos propios (Usuario y Administrador). Usuario implica `stock.group_stock_user` para poder crear movimientos de stock con los permisos estándar.
- **No:** usar `stock.group_stock_manager` como administrador. Daría permisos de configuración de Inventario que no hacen falta para reabrir controles.
- **Sí:** el ajuste se aplica al guardar el control, en un solo paso.
- **No:** aprobación separada del ajuste por un administrador, ni dejar el control solo como registro.
- **Sí:** "abierto" quiere decir "reabierto para editar". Todos ven el control guardado en solo lectura, y solo el Administrador lo reabre.
- **Sí:** la reapertura pide un motivo y queda en el historial. Sin motivo, la reapertura no se puede auditar.
- **Sí:** al volver a guardar se generan movimientos de corrección por la diferencia con lo ya aplicado. Los movimientos originales no se tocan, así la auditoría muestra todo.
- **No:** revertir y rehacer el ajuste completo. Duplica movimientos y confunde la auditoría.
- **Sí:** "Comparar contra" con dos modos (al guardar / al iniciar), elegido en Ajustes. Decisión del usuario, aunque se recomendó solo "al guardar".
- **No:** "Comparar contra" por control. Decisión del usuario.
- **Sí:** el modo se copia al control al iniciar el conteo. Cambiar el ajuste a mitad de un conteo no altera ese conteo.
- **No:** bloquear recepciones y entregas durante un conteo. Frena la operación; el modo "al iniciar" cubre ese caso.
- **Sí:** columna Teórico de la planilla configurable. Decisión del usuario.
- **Sí:** ese ajuste usa el parámetro estándar `stock.show_expected_quantity_count`. Odoo ya lo tiene para su "Hoja de conteo", y dos ajustes para lo mismo confundirían.
- **No:** un parámetro propio para la planilla. Duplicaría el estándar.
- **Sí:** menús Productos y Existencias con las acciones estándar de Inventario. Ya tienen los filtros por categoría y depósito.
- **No:** vistas propias de productos y existencias. Duplicarían lo estándar.
- **Sí:** planilla de conteo propia. La "Hoja de conteo" estándar no está atada a un documento de control.
- **No:** usar el Inventario físico estándar como control. Al aplicar no queda un documento guardado que se pueda cerrar y reabrir.
- **Sí:** una línea sin cantidad es No contada y no ajusta. Para poner stock en 0 se carga 0. Evita poner stock en cero por olvido.
- **Sí:** entran todos los productos `is_storable` de las categorías, aunque tengan stock 0. Así aparecen los faltantes que en realidad están.
- **Sí:** motivos en una tabla propia (`stock.control.reason`), obligatorios en movimientos manuales. Cubre entradas y salidas en un solo lugar, como se acordó.
- **No:** reutilizar las etiquetas de motivo de Desechar (`stock.scrap.reason.tag`) para los movimientos manuales. Son solo para salidas y no indican si un motivo aplica a entradas o salidas.
- **Sí:** el "Desechar" estándar sigue disponible, y la auditoría lo muestra con origen Desecho y sus etiquetas como motivo.
- **Sí:** el Usuario carga y confirma movimientos manuales. Confirmado no se edita: se corrige con "Revertir".
- **No:** aprobación de movimientos manuales por un administrador.
- **Sí:** movimientos manuales como `stock.move` contra la ubicación de ajuste de inventario, con `is_inventory = False`. Se distinguen de los ajustes por conteo en la auditoría.
- **No:** usar `stock.quant.action_apply_inventory` para aplicar el control. Siempre lleva el stock al valor absoluto y no sirve para el modo "al iniciar" ni para las correcciones. El módulo crea los `stock.move` con los mismos valores que `_get_inventory_move_values`.
- **Sí:** auditoría sobre `stock.move` con campos guardados (origen, cantidad con signo, depósito, validado por), para poder filtrar y agrupar en la lista.
- **Sí:** la auditoría la ve solo el Administrador, como se definió para el grupo.
- **Sí:** numeración por empresa (`MM/AAAA/0001`, `CI/AAAA/0001`).
- **Sí:** en Compras, columna "Stock" en el listado y botón "Movimientos" en la ficha.
- **No:** valorización en pesos en esta spec. `stock_account` ya está instalado como dependencia, pero definir el método de costo, la valuación (Periódica o Perpetua) y los asientos son decisiones contables: van en la SPEC 06.
- **Sí:** `stock_control` no depende de `stock_account` en el manifiesto ni lee sus campos. Se instala igual porque lo traen `purchase_stock` y `sale_stock`.
- **No:** lotes y números de serie.
- **No:** tests automáticos. La verificación es manual con los criterios de aceptación.

## Riesgos

| Riesgo | Mitigación |
| --- | --- |
| Los usuarios con `stock.group_stock_user` pueden entrar a la app Inventario estándar y hacer transferencias, desechos o conteos por fuera del módulo, salteando el control cerrado. | Esos movimientos aparecen igual en la auditoría con su origen (Desecho u Otro), su motivo y el usuario que los validó. Restringir Inventario estándar va en otra spec. |
| Cambiar "Mostrar cantidad teórica en la planilla" desde "Solicitar un conteo" de Inventario cambia también la planilla del módulo. | Es buscado: es el mismo parámetro. Se documenta en Configuraciones esenciales del README. |
| Instalar `sale_stock` cambia el comportamiento de Ventas: las ventas confirmadas generan entregas y los productos almacenables pueden quedar con stock negativo si se entregan sin stock. | Se instala y se prueba primero en `odoo_prueba` (paso 1). Se documenta en Configuraciones esenciales del README. |
| Si una empresa tiene la valuación en Perpetua, los ajustes de control y los movimientos manuales generan asientos contables contra las cuentas de la categoría. | El paso 1 verifica que la valuación sea Periódica. Pasar a Perpetua es una decisión de la SPEC 06. Se documenta en Configuraciones esenciales del README. |
| Con Inventario ya activo puede haber movimientos y ajustes previos a `stock_control`, sin origen ni motivo propio. | La auditoría los muestra con el origen que se deduce (Compra, Venta u Otro). El campo "Validado por" queda vacío en los movimientos anteriores a la instalación. |
| Con "Comparar contra = Al guardar", si hubo recepciones o entregas entre el conteo físico y la carga, el ajuste las absorbe y queda una diferencia falsa. | Se documenta que en ese modo hay que cargar el conteo el mismo día. Para conteos largos, usar "Al iniciar el conteo". |
| Con "Al iniciar el conteo", un movimiento entre ubicaciones del mismo depósito durante el conteo deja el teórico de cada línea desactualizado. | Se documenta como limitación. El informe de diferencias muestra el teórico usado en cada línea. |
| Productos sin `property_stock_inventory` en una empresa. | Se usa la ubicación por defecto de la empresa, igual que `stock.quant._apply_inventory`. |
| El kardex recorre todos los movimientos del producto para calcular el saldo inicial. | Se calcula con `read_group` sobre `stock_control_signed_qty` antes de la fecha desde. Si con la base más grande tarda más de 2 segundos, se agrega un índice en otra spec. |
| Un administrador con `sudo` en `odoo shell` puede saltear el bloqueo. | El bloqueo es para la interfaz y los usuarios normales. Todo cambio queda en `stock.move` y en el historial. |

## Ajustes durante la implementación

Diferencias entre lo escrito arriba y lo implementado (2026-10-22), por detalles que la spec no resolvía:

- **`stock_move.stock_control_categ_id`** (categoría, relacionado y guardado): columna extra para poder agrupar la auditoría por categoría. Son 10 columnas nuevas en `stock_move`, no 8.
- **Campos relacionados guardados en `stock.control.inventory.line`:** `inventory_state`, `warehouse_id`, `date` y `company_id`, para filtrar y agrupar Diferencias de controles.
- **`report/stock_control_report.py`:** tres modelos abstractos que calculan los datos de los PDF. QWeb no puede llamar métodos privados del modelo.
- **"Contada" se puede tildar a mano:** cargar 0 sobre un 0 no dispara ningún cambio en la pantalla, así que para indicar "no hay stock" se carga 0 y se tilda "Contada".
- **Teórico, Diferencia y Estado en pantalla:** se muestran solo con el control Guardado o Reabierto, para no romper el conteo ciego mientras se cuenta.
- **Auditoría "solo Administrador":** es a nivel de menú. En Odoo 20, los grupos de una acción no impiden abrirla por su dirección, y los `stock.move` los lee cualquier usuario de Inventario. Restringir la lectura de movimientos va en otra spec si hace falta.
- **Una reversión conserva el motivo del original,** aunque el motivo no aplique al tipo inverso (por ejemplo, "Devolución de cliente" en la salida que revierte una entrada).
- **Columna "Stock" de Compras:** en Odoo 20 el listado ya tenía la existencia ("En existencia", `qty_available`). Se le cambia la etiqueta a "Stock" y se deja visible.
- **Menú Ajustes:** además del grupo Administrador del módulo, pide `base.group_system`, porque solo ese grupo puede abrir Ajustes en Odoo.
- **Borrado:** los movimientos manuales en Borrador o Cancelado se pueden borrar (el Usuario solo en Borrador). Los controles, solo en Borrador.
- **`uninstall_hook`:** vacía los movimientos manuales antes de desinstalar, para que Odoo pueda borrar los motivos iniciales sin errores en el log.
- **"Validado por":** se completa en los movimientos validados después de instalar el módulo. Los anteriores quedan vacíos.

## Qué **no** incluye esta spec

- Valorización en pesos e impacto contable (SPEC 06).
- Lotes y números de serie.
- Controles por una sola ubicación.
- Bloqueo de recepciones y entregas durante un conteo.
- "Comparar contra" por control.
- Aprobación de movimientos manuales.
- Carga del conteo desde Excel, código de barras o celular.
- Restricción de la app Inventario estándar.
- Transferencias entre depósitos desde la app.
- Reposición, stock mínimo y alertas.
- Tests automáticos.

Cada uno de estos, si se hace, va en su propia spec.
