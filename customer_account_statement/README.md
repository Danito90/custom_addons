# Estado de cuenta de clientes y proveedores

Módulo técnico: `customer_account_statement` · Odoo 20.0 · Dependencias: `account`, `sales_team` · Licencia LGPL-3

Permite consultar, imprimir, enviar por email e imputar la cuenta corriente de un cliente o de un proveedor, por empresa o consolidada entre varias empresas del grupo.

El nombre técnico conserva `customer_` por compatibilidad: desde la versión 1.2 el mismo estado de cuenta sirve para **clientes** (cuentas a cobrar) y **proveedores** (cuentas a pagar).

## Qué hace

- **Dos tipos de cuenta:**
  - **Cliente:** cuentas a cobrar. Es el estado de cuenta de siempre.
  - **Proveedor:** cuentas a pagar, con las mismas funciones (modos, consolidado, imputación, PDF y email).
- **Consulta de cuenta corriente** en dos modos:
  - **Movimientos:** saldo inicial (si hay fecha "Desde"), todos los movimientos del período y saldo acumulado línea por línea.
  - **Solo pendientes:** comprobantes con saldo pendiente a la fecha "Hasta", con días de atraso. Los vencidos se resaltan en rojo.
- **Todas las empresas del cliente, con filtro en pantalla:** la consulta abre con todas las empresas en las que participa el cliente. Arriba hay casillas para elegir cuáles mostrar, y al tildar o destildar se recalcula todo al instante. Con varias empresas aparece la columna "Empresa" y los saldos se separan **por moneda de la empresa**.
- **Detalle de imputaciones:** desde cada línea se ve con qué comprobantes está conciliada, y se puede **desimputar**.
- **Imputación de créditos:** desde un recibo, un pago o una nota de crédito con saldo, se eligen las facturas o notas de débito pendientes a las que se aplica.
- **Resumen en PDF** (ambos modos) con los datos de la empresa y del cliente o proveedor.
- **Envío por email** del PDF al cliente o proveedor, con una plantilla editable para cada uno.

## Qué agrega o modifica en Odoo

| Dónde | Cambio |
|---|---|
| Contacto (`res.partner`) | Campo nuevo **"Empresas en las que participa"** (`company_ids`) en la pestaña *Ventas y compras → Varios*. Botones **"Estado de cuenta"** (cliente) y **"Cuenta proveedor"** (solo si el contacto es proveedor, `supplier_rank > 0`) arriba de la ficha. |
| Conciliaciones (`account.partial.reconcile`) | Campos calculados de contraparte y de permiso, y botón **"Desimputar"**, usados en la lista de imputaciones. No cambia el comportamiento estándar. |
| Menú | **Contabilidad / Facturación → Clientes → Estado de cuenta** y **Contabilidad / Facturación → Proveedores → Estado de cuenta**. |
| Reporte | **"Resumen de cuenta"** (PDF QWeb). En proveedores se titula **"Resumen de cuenta de proveedor"**. |
| Plantillas de email | **"Estado de cuenta: envío de resumen al cliente"** y **"Estado de cuenta: envío de resumen al proveedor"**. |
| Permisos | Acceso de lectura para **vendedores** a asientos, apuntes, pagos y conciliaciones **de sus propios clientes** (ver [Permisos](#permisos)). |

Modelos nuevos, todos transitorios (no guardan datos de forma permanente):

- `customer.account.statement`: asistente de consulta y pantalla de resultado. El campo `partner_type` (Cliente / Proveedor) elige la cuenta.
- `customer.account.statement.line`: líneas calculadas del estado de cuenta.
- `customer.account.statement.currency`: totales por moneda ("Saldos por moneda").
- `customer.account.statement.reconcile` y `.reconcile.line`: asistente de imputación.

No crea asientos ni modifica importes. Las imputaciones usan la conciliación estándar de Odoo.

## Cómo funciona

### Qué movimientos entran

Se toman los apuntes contables (`account.move.line`) que cumplen todo esto:

- Cuenta de tipo **A cobrar** (`asset_receivable`) en clientes, o **A pagar** (`liability_payable`) en proveedores.
- Asiento **publicado**.
- Partner igual al cliente/proveedor o a cualquiera de sus contactos hijos (se usa siempre la empresa principal del contacto).
- Empresa dentro de las tildadas en el estado de cuenta.

Un contacto que es cliente y proveedor tiene dos cuentas separadas: "Estado de cuenta" muestra solo lo a cobrar y "Cuenta proveedor" solo lo a pagar.

Los importes están en la **moneda de la empresa**. Si el comprobante fue en otra moneda, la moneda y el importe originales se muestran en columnas informativas.

### Signo del saldo

En los dos tipos el saldo es **contable: Debe − Haber**.

- **Cliente:** positivo = el cliente debe. Facturas y ND van al Debe; recibos y NC, al Haber.
- **Proveedor:** **negativo = se le debe al proveedor**. Las facturas y ND del proveedor van al Haber; los pagos y las NC, al Debe. Un saldo positivo es un saldo a favor (anticipos o NC sin aplicar).

En proveedores, los pagos se muestran con tipo **"Pago"** (en clientes, "Recibo"). En el modo Solo pendientes, los días de atraso de un proveedor se cuentan solo en facturas y ND (pendiente negativo); los pagos y NC con saldo muestran 0.

### Qué empresas se muestran

Las **empresas permitidas** salen de esta regla:

- Si el cliente **no tiene** empresas cargadas en "Empresas en las que participa", son todas las empresas habilitadas del usuario.
- Si **tiene** empresas cargadas, son las que están cargadas en el cliente **y** habilitadas para el usuario.

El asistente previo no pide empresas: la consulta abre con **todas las empresas permitidas tildadas**. En la pantalla de resultado, las casillas ofrecen solo las permitidas.

### Recálculo en pantalla

Al cambiar las empresas, el modo o las fechas en la pantalla de resultado, Odoo recalcula al instante el saldo inicial, los movimientos, el saldo acumulado y "Saldos por moneda". Lo mismo pasa al imputar o desimputar.

- Sin ninguna empresa tildada no hay movimientos, se muestra un aviso, y Imprimir o Enviar por email dan error.
- Si "Desde" es posterior a "Hasta", Odoo avisa y no muestra movimientos.
- Imprimir y Enviar por email usan las empresas, el modo y las fechas que se ven en pantalla.

### Pendiente a una fecha

En el modo "Solo pendientes", el saldo se calcula **a la fecha "Hasta"**. Las imputaciones posteriores a esa fecha se ignoran, así que un comprobante cobrado después vuelve a aparecer como pendiente.

### Imputación

- Botón **"Imputar"** en las líneas que todavía tienen saldo y pueden cancelar comprobantes:
  - **Cliente:** recibos y notas de crédito (saldo acreedor).
  - **Proveedor:** pagos y notas de crédito del proveedor (saldo deudor).
- Lista las facturas y notas de débito pendientes del mismo cliente/proveedor, **misma empresa y misma cuenta**, ordenadas por vencimiento. Los importes se muestran en valor absoluto.
- Se marcan los comprobantes. Para cada uno se propone el menor importe entre su pendiente y lo que queda disponible del crédito.
- **Importe parcial editable** solo si el crédito y la factura están en la moneda de la empresa. En otra moneda se imputa por el total posible.
- Antes de imputar se valida que el crédito y cada comprobante sean del mismo cliente/proveedor, empresa y cuenta, estén publicados y tengan el signo esperado.
- Al terminar, el estado de cuenta se recalcula solo.

El importe parcial se arma con el método interno de Odoo `_prepare_reconciliation_single_partial`, limitando el pendiente del comprobante destino al importe pedido (en proveedores, el destino es el apunte acreedor).

## Uso

1. Entrar por cualquiera de estos caminos:
   - **Clientes:**
     - Menú Contabilidad / Facturación → Clientes → **Estado de cuenta**.
     - App Clientes → **Estado de cuenta** (si está instalado `customer_management`).
     - Ficha del cliente → botón **"Estado de cuenta"**.
   - **Proveedores:**
     - Menú Contabilidad / Facturación → Proveedores → **Estado de cuenta**.
     - App Proveedores → **Estado de cuenta** (si está instalado `supplier_management`).
     - Ficha del proveedor → botón **"Cuenta proveedor"**.
2. Elegir cliente o proveedor, modo y fechas.
3. Usar uno de estos botones:
   - **Consultar:** abre la pantalla de resultado.
   - **Imprimir:** descarga el PDF con todas las empresas permitidas.
   - **Enviar por email:** abre el redactor de correo con el PDF adjunto.

La pantalla de resultado tiene:

- **Arriba:** casillas de empresas, modo y fechas. Al cambiarlos se recalcula todo.
- **Cabecera:** botones **Imprimir** y **Enviar por email**.
- **"Saldos por moneda":** saldo inicial, debe, haber y saldo final de cada moneda (modo Movimientos), o total adeudado / total pendiente en proveedores (modo Solo pendientes).
- **"Movimientos":** una línea por comprobante.

Cada movimiento tiene tres botones:

- **Abrir comprobante:** abre la factura, la nota o el pago.
- **Imputaciones:** muestra con qué comprobantes está conciliado. Desde ahí se puede **desimputar**.
- **Imputar:** solo en créditos con saldo (recibos, pagos o NC) y si el usuario tiene permiso.

## Configuraciones esenciales

### 1. Cargar las empresas del cliente

1. Abrir el cliente (Contactos o Facturación → Clientes).
2. Ir a la pestaña **Ventas y compras** → bloque **Varios** → **"Empresas en las que participa"**.
3. Tildar las casillas de las empresas en las que opera el cliente y guardar.

Si no se tilda ninguna, el cliente se puede consultar en todas las empresas del usuario.

El campo **no aparece** en estos casos:
- El usuario no tiene permisos de Facturación.
- El contacto es un hijo (una persona dentro de una empresa). En ese caso se carga en la empresa padre.

### 2. Dar permisos a los usuarios

Ajustes → Usuarios y compañías → Usuarios → elegir el usuario.

| Perfil | Grupo en Odoo | Qué puede hacer |
|---|---|---|
| Facturación / Contabilidad | *Facturación* o superior (`account.group_account_invoice`) | Todo: consultar cualquier cliente, imprimir, enviar, imputar y desimputar. Ve el menú. |
| Vendedor | *Ventas: Usuario: solo sus documentos* o superior (`sales_team.group_sale_salesman`) | Consultar e imprimir **solo clientes donde figura como vendedor** (campo "Vendedor" del cliente). Entra por el botón de la ficha del cliente o por la app Clientes; no ve el menú de Facturación. No puede enviar ni imputar. No accede a cuentas de proveedores. |
| Compras | *Compras: Usuario* (`purchase.group_purchase_user`), con `supplier_management` instalado | Consultar e imprimir la cuenta de **todos los proveedores**. Imputar, desimputar y enviar según los ajustes de la app Proveedores. Lo agrega `supplier_management`, no este módulo. |

Para que un vendedor vea el estado de cuenta de un cliente, en la ficha del cliente → **Ventas y compras → Vendedor** tiene que figurar ese usuario.

### 3. Empresas habilitadas del usuario

Solo se pueden consultar empresas que el usuario tiene en **Empresas permitidas** (en la ficha del usuario). Para un consolidado, el usuario tiene que tener habilitadas todas las empresas que quiere sumar.

### 4. Plantillas de email

Ajustes → Técnico → Email → Plantillas (requiere el modo desarrollador):

- **"Estado de cuenta: envío de resumen al cliente"**.
- **"Estado de cuenta: envío de resumen al proveedor"**: le pide al proveedor que concilie saldos e informe diferencias.

En las dos:

- El asunto y el remitente usan la empresa y el email del usuario que envía.
- El cliente o proveedor tiene que tener **email** cargado.
- Se cargan con `noupdate`: los cambios que se les hagan **no se pisan** al actualizar el módulo.

### 5. Servidor de correo saliente

Para que el envío funcione, tiene que haber un servidor de correo saliente configurado en Ajustes → Técnico → Servidores de correo saliente.

### 6. Motor de PDF (wkhtmltopdf)

El resumen en PDF y el adjunto del email necesitan **wkhtmltopdf 0.12.6 (with patched qt)** instalado en el servidor, con el módulo estándar `base_report_wkhtmltox` (se instala solo).

Odoo busca el ejecutable en el `PATH`. Si no lo encuentra, al imprimir muestra *"No encontramos el motor de PDF en este sistema. El reporte aparecerá en formato HTML."* y el envío por email falla.

En Windows:
1. Agregar `C:\Program Files\wkhtmltopdf\bin` al `PATH` del usuario o del sistema.
2. Cerrar **todas** las ventanas de VS Code y las terminales, y volver a arrancar Odoo.

Para verificarlo, el log de arranque tiene que mostrar `Will use the Wkhtmltopdf binary at ...`.

Como alternativa, se puede indicar la carpeta con `bin_path = C:\Program Files\wkhtmltopdf\bin` en el archivo de configuración de Odoo (`-c odoo.conf`). Es una opción que solo se lee del archivo, no de la línea de comandos.

## Permisos

Definidos en [security/ir.access.csv](security/ir.access.csv) con el modelo `ir.access` de Odoo 20. Todos llevan grupo, así que son **permisos que suman**: si un usuario tiene varios, se combinan con OR. El módulo no agrega restricciones (permisos sin grupo).

| ID externo | Modelo | Grupo | Operaciones | Filtro (`domain`) | Para qué |
|---|---|---|---|---|---|
| `access_customer_account_statement_invoice` | `customer.account.statement` | Facturación | CRUD | — | Usar el asistente de consulta |
| `access_customer_account_statement_salesman` | `customer.account.statement` | Vendedor | CRUD | — | Ídem, para vendedores |
| `access_customer_account_statement_line_invoice` | `customer.account.statement.line` | Facturación | CRUD | — | Ver y generar las líneas |
| `access_customer_account_statement_line_salesman` | `customer.account.statement.line` | Vendedor | CRUD | — | Ídem, para vendedores |
| `access_customer_account_statement_currency_invoice` | `customer.account.statement.currency` | Facturación | CRUD | — | Ver y generar "Saldos por moneda" |
| `access_customer_account_statement_currency_salesman` | `customer.account.statement.currency` | Vendedor | CRUD | — | Ídem, para vendedores |
| `access_customer_account_statement_reconcile_invoice` | `customer.account.statement.reconcile` | Facturación | CRUD | — | Asistente de imputación |
| `access_customer_account_statement_reconcile_line_invoice` | `customer.account.statement.reconcile.line` | Facturación | CRUD | — | Comprobantes del asistente de imputación |
| `customer_account_statement_move_salesman` | `account.move` | Vendedor | Lectura | `commercial_partner_id.user_id = usuario` | Abrir facturas y notas de sus clientes |
| `customer_account_statement_move_line_salesman` | `account.move.line` | Vendedor | Lectura | `partner_id.commercial_partner_id.user_id = usuario` | Leer los apuntes de sus clientes |
| `customer_account_statement_payment_salesman` | `account.payment` | Vendedor | Lectura | `partner_id.commercial_partner_id.user_id = usuario` | Abrir los pagos de sus clientes |
| `customer_account_statement_partial_salesman` | `account.partial.reconcile` | Vendedor | Lectura | Débito **o** crédito de un cliente propio | Ver las imputaciones de sus clientes |

"Facturación" es `account.group_account_invoice`; "Vendedor" es `sales_team.group_sale_salesman` (*Ventas: Usuario: solo sus documentos*).

Los cuatro últimos amplían permisos sobre modelos **estándar**. Por eso los vendedores, además del estado de cuenta, pueden ver los asientos, apuntes y pagos de sus clientes en otras pantallas de Odoo. Es solo lectura: no pueden modificar nada.

Controles adicionales en el código (no dependen de `ir.access`):

| Acción | Método | Control en este módulo |
|---|---|---|
| Consultar, imprimir | `_check_partner_access(partner, partner_type)` | Facturación, o vendedor del cliente (solo tipo Cliente) |
| Enviar por email | `_can_send(partner_type)` | Solo Facturación |
| Imputar | `_can_reconcile(partner_type)` | Solo Facturación |
| Desimputar | `_can_unreconcile(partner_type)` | Solo Facturación. El tipo sale de la cuenta de la imputación (a pagar = proveedor) |
| Empresas | — | Solo las permitidas para el cliente/proveedor **y** habilitadas para el usuario |

Esos cuatro métodos son **puntos de extensión**: otros módulos los heredan para dar más permisos (por ejemplo, `supplier_management` habilita a Compras en la cuenta de proveedores). La vista usa los campos calculados `can_reconcile`, `can_unreconcile`, `can_send` y `statement_can_unreconcile` para mostrar u ocultar los botones, y cada acción vuelve a verificar el permiso en el servidor.

El cálculo de líneas lee los apuntes con `sudo()` **después** de validar el acceso al cliente y a las empresas. Así los vendedores y Compras no dependen de tener permisos contables completos.

## Base de datos

### Resumen

- **Tablas nuevas:** 7 (1 permanente, 6 temporales).
- **Tablas existentes modificadas:** ninguna. El módulo **no agrega columnas** a tablas estándar.
- **Datos estándar que escribe:** registros en `account_partial_reconcile` (y `account_full_reconcile`, asientos de diferencia de cambio o de caja si corresponde), creados por la conciliación estándar de Odoo al **imputar**. Al **desimputar** se borra el registro de `account_partial_reconcile`.

### Esquema relacional

Las tablas del módulo aparecen en mayúsculas y las estándar de Odoo en minúsculas. La línea punteada es una relación que no está en una tabla del módulo: el asistente de imputación crea conciliaciones estándar.

```mermaid
erDiagram
    res_partner ||--o{ RES_PARTNER_STATEMENT_COMPANY_REL : "company_ids"
    res_company ||--o{ RES_PARTNER_STATEMENT_COMPANY_REL : "company_id"

    res_partner ||--o{ CUSTOMER_ACCOUNT_STATEMENT : "partner_id"
    CUSTOMER_ACCOUNT_STATEMENT ||--o{ CUSTOMER_ACCOUNT_STATEMENT_COMPANY_REL : "company_ids"
    res_company ||--o{ CUSTOMER_ACCOUNT_STATEMENT_COMPANY_REL : "company_id"

    CUSTOMER_ACCOUNT_STATEMENT ||--o{ CUSTOMER_ACCOUNT_STATEMENT_CURRENCY : "currency_total_ids"
    res_currency ||--o{ CUSTOMER_ACCOUNT_STATEMENT_CURRENCY : "currency_id"

    CUSTOMER_ACCOUNT_STATEMENT ||--o{ CUSTOMER_ACCOUNT_STATEMENT_LINE : "line_ids"
    res_company |o--o{ CUSTOMER_ACCOUNT_STATEMENT_LINE : "company_id"
    res_currency |o--o{ CUSTOMER_ACCOUNT_STATEMENT_LINE : "currency_id, original_currency_id"
    account_move_line |o--o{ CUSTOMER_ACCOUNT_STATEMENT_LINE : "move_line_id"
    account_move |o--o{ CUSTOMER_ACCOUNT_STATEMENT_LINE : "move_id"
    account_payment |o--o{ CUSTOMER_ACCOUNT_STATEMENT_LINE : "payment_id"

    CUSTOMER_ACCOUNT_STATEMENT |o--o{ CUSTOMER_ACCOUNT_STATEMENT_RECONCILE : "statement_id"
    account_move_line ||--o{ CUSTOMER_ACCOUNT_STATEMENT_RECONCILE : "credit_line_id"
    res_partner ||--o{ CUSTOMER_ACCOUNT_STATEMENT_RECONCILE : "partner_id"
    CUSTOMER_ACCOUNT_STATEMENT_RECONCILE ||--o{ CUSTOMER_ACCOUNT_STATEMENT_RECONCILE_LINE : "line_ids"
    account_move_line ||--o{ CUSTOMER_ACCOUNT_STATEMENT_RECONCILE_LINE : "debit_line_id"

    account_move_line ||--o{ account_partial_reconcile : "debit_move_id, credit_move_id"
    CUSTOMER_ACCOUNT_STATEMENT_RECONCILE }o..o{ account_partial_reconcile : "crea al imputar"
```

### Tablas nuevas

`ON DELETE` indica qué pasa con la fila si se borra el registro referenciado. Todas las tablas con `id` tienen además las columnas estándar `create_uid`, `write_uid` (→ `res_users`, SET NULL), `create_date` y `write_date`.

#### `res_partner_statement_company_rel` — permanente

Empresas en las que participa cada cliente (campo `res.partner.company_ids`). Es la **única tabla con datos de negocio** del módulo.

| Columna | Tipo | Nulo | Referencia | ON DELETE |
|---|---|---|---|---|
| `partner_id` | integer | no | `res_partner.id` | CASCADE |
| `company_id` | integer | no | `res_company.id` | CASCADE |

Clave primaria `(partner_id, company_id)`; índice `(company_id, partner_id)`.

#### `customer_account_statement` — temporal

Cada consulta del asistente y su pantalla de resultado (`customer.account.statement`).

| Columna | Tipo | Nulo | Referencia | ON DELETE |
|---|---|---|---|---|
| `id` | integer | no | — | — |
| `partner_id` | integer | no | `res_partner.id` | CASCADE |
| `mode` | varchar | no | `movements` / `pending` | — |
| `date_from` | date | sí | — | — |
| `date_to` | date | no | — | — |
| `is_result` | boolean | sí | `True` una vez consultado: recién ahí se calculan líneas y totales | — |
| `partner_type` | varchar | no | `customer` / `supplier` (por defecto `customer`) | — |

`allowed_company_ids`, `is_consolidated`, `can_reconcile`, `can_unreconcile` y `can_send` son calculados y no se guardan. `line_ids` y `currency_total_ids` son calculados y se guardan en sus propias tablas.

#### `customer_account_statement_company_rel` — temporal

Empresas tildadas en cada consulta (campo `company_ids`). Por defecto, todas las permitidas.

| Columna | Tipo | Nulo | Referencia | ON DELETE |
|---|---|---|---|---|
| `statement_id` | integer | no | `customer_account_statement.id` | CASCADE |
| `company_id` | integer | no | `res_company.id` | CASCADE |

Clave primaria `(statement_id, company_id)`; índice `(company_id, statement_id)`.

#### `customer_account_statement_line` — temporal

Líneas calculadas del estado de cuenta. Es una **copia** de los datos al momento de consultar: se recalcula al cambiar empresas, modo o fechas, al imputar y al desimputar, pero no si un comprobante cambia desde otra pantalla.

| Columna | Tipo | Nulo | Referencia | ON DELETE |
|---|---|---|---|---|
| `id` | integer | no | — | — |
| `statement_id` | integer | no | `customer_account_statement.id` | CASCADE |
| `sequence` | integer | sí | — | — |
| `line_type` | varchar | no | `initial` / `move` | — |
| `company_id` | integer | sí | `res_company.id` | SET NULL |
| `currency_id` | integer | sí | `res_currency.id` (moneda de la empresa) | SET NULL |
| `move_line_id` | integer | sí | `account_move_line.id` | SET NULL |
| `move_id` | integer | sí | `account_move.id` | SET NULL |
| `payment_id` | integer | sí | `account_payment.id` | SET NULL |
| `document_type` | varchar | sí | — | — |
| `name` | varchar | sí | — | — |
| `date`, `date_maturity` | date | sí | — | — |
| `debit`, `credit`, `balance`, `cumulative_balance` | numeric | sí | — | — |
| `original_currency_id` | integer | sí | `res_currency.id` | SET NULL |
| `amount_currency` | numeric | sí | — | — |
| `amount_residual` | numeric | sí | — | — |
| `days_overdue` | integer | sí | — | — |
| `is_reconciled` | boolean | sí | — | — |
| `is_reconcile_source` | boolean | sí | `True` si la línea puede imputarse (recibo/pago/NC con saldo del lado del crédito) | — |

#### `customer_account_statement_currency` — temporal

Totales por moneda de cada consulta ("Saldos por moneda"). Se calcula junto con las líneas.

| Columna | Tipo | Nulo | Referencia | ON DELETE |
|---|---|---|---|---|
| `id` | integer | no | — | — |
| `statement_id` | integer | no | `customer_account_statement.id` | CASCADE |
| `currency_id` | integer | no | `res_currency.id` (moneda de la empresa) | CASCADE |
| `initial_balance` | numeric | sí | — | — |
| `debit`, `credit` | numeric | sí | — (solo movimientos, sin el saldo inicial) | — |
| `final_balance` | numeric | sí | — | — |
| `amount_residual` | numeric | sí | — (total adeudado o pendiente, modo Solo pendientes) | — |

#### `customer_account_statement_reconcile` — temporal

Asistente de imputación (`customer.account.statement.reconcile`).

| Columna | Tipo | Nulo | Referencia | ON DELETE |
|---|---|---|---|---|
| `id` | integer | no | — | — |
| `statement_id` | integer | sí | `customer_account_statement.id` | SET NULL |
| `credit_line_id` | integer | no | `account_move_line.id` (el crédito a imputar: recibo, pago o NC) | CASCADE |
| `partner_id` | integer | no | `res_partner.id` | CASCADE |
| `available_amount` | numeric | sí | — (valor absoluto del pendiente del crédito) | — |
| `partner_type` | varchar | sí | `customer` / `supplier`: el del estado de cuenta o, sin él, según la cuenta del crédito | — |

#### `customer_account_statement_reconcile_line` — temporal

Comprobantes ofrecidos para imputar.

| Columna | Tipo | Nulo | Referencia | ON DELETE |
|---|---|---|---|---|
| `id` | integer | no | — | — |
| `reconcile_id` | integer | no | `customer_account_statement_reconcile.id` | CASCADE |
| `debit_line_id` | integer | no | `account_move_line.id` (la factura o ND, de cliente o de proveedor) | CASCADE |
| `selected` | boolean | sí | — | — |
| `amount_residual` | numeric | sí | — (valor absoluto) | — |
| `amount_to_apply` | numeric | sí | — (valor absoluto) | — |
| `allow_partial` | boolean | sí | — | — |

Las tablas temporales son de modelos `TransientModel`: Odoo borra solo las filas viejas.

### Tablas existentes

| Tabla | Cambio de estructura | Escritura de datos |
|---|---|---|
| `res_partner` | Ninguno. `company_ids` vive en la tabla de relación. | No |
| `account_partial_reconcile` | Ninguno. `statement_counterpart_line_id`, `statement_counterpart_move_id` y `statement_can_unreconcile` son calculados, sin columna. | Sí: altas al imputar, bajas al desimputar (clientes y proveedores) |
| `account_move_line`, `account_move` | Ninguno | Solo lo que actualiza la conciliación estándar (`amount_residual`, `reconciled`, estado de pago) |

### Registros de configuración

Se guardan en las tablas estándar de metadatos de Odoo y se identifican en `ir_model_data` con `module = 'customer_account_statement'`.

| Tabla | Registros |
|---|---|
| `ir_access` | 12 (ver [Permisos](#permisos)) |
| `ir_ui_view` | 7: asistente previo, pantalla de resultado, asistente de imputación, lista de imputaciones, herencia de la ficha de contacto y 2 plantillas QWeb del reporte |
| `ir_act_window` | 2: `action_customer_account_statement` y `action_supplier_account_statement` |
| `ir_act_report_xml` | 1: `action_report_customer_account_statement` |
| `ir_ui_menu` | 2: `menu_customer_account_statement` (Clientes) y `menu_supplier_account_statement` (Proveedores) |
| `mail_template` | 2: `mail_template_customer_account_statement` y `mail_template_supplier_account_statement` (`noupdate`) |
| `ir_model` / `ir_model_fields` / `ir_model_fields_selection` | 7 / 100 / 8, generados por Odoo a partir de los modelos |

### Al desinstalar

Se borran las 7 tablas nuevas, incluidas **las empresas cargadas en los clientes**, y todos los registros de configuración. Las conciliaciones creadas al imputar **quedan**: son datos contables estándar.

## Instalación y actualización

El módulo vive en `custom_addons`, que tiene que estar en el addons path:

```powershell
# Instalar
python odoo-bin -r odoo_user -w <password> --addons-path=addons,..\custom_addons -d <base> -i customer_account_statement

# Actualizar después de cambiar XML, CSV o campos
python odoo-bin -r odoo_user -w <password> --addons-path=addons,..\custom_addons -d <base> -u customer_account_statement
```

Si se arranca Odoo sin `..\custom_addons`, el log muestra `module customer_account_statement: not installable, skipped` y el módulo no se carga.

## Limitaciones conocidas

- Cliente y proveedor son cuentas separadas: no hay un estado de cuenta combinado de un contacto que es las dos cosas.
- Los nombres técnicos (`customer_account_statement`, `customer.account.statement`) se conservan aunque el módulo también sirva para proveedores.
- El consolidado **no convierte monedas**: cada moneda tiene su fila en "Saldos por moneda" (y su bloque en el PDF).
- La lista de movimientos de la pantalla no tiene totales al pie, porque mezclarían monedas. Los totales están en "Saldos por moneda".
- El recálculo es automático en cada cambio: con clientes de muchísimos movimientos cada casilla puede tardar unos segundos.
- La imputación es entre comprobantes de la **misma empresa y la misma cuenta**.
- En moneda extranjera la imputación es por el total posible, no por un importe parcial.
- Las líneas son temporales: Odoo borra solas las consultas viejas. Para guardar un estado de cuenta, imprimir el PDF o enviarlo.

## Historial de cambios

### 2026-10-21 — versión 1.2 ([SPEC 03](../specs/03-app-proveedores.md))
- **Nuevo:** estado de cuenta de **proveedores** (cuentas a pagar) con el campo `partner_type` (Cliente / Proveedor), saldo contable (lo que se le debe al proveedor sale negativo), tipo "Pago" y textos de proveedor en pantalla, PDF y email.
  - Base de datos: columna nueva `partner_type` (varchar, no nula, por defecto `customer`) en `customer_account_statement`; columna nueva `is_reconcile_source` en `customer_account_statement_line`; acción nueva `action_supplier_account_statement` en `ir_act_window`; se actualizan `arch_db` de las dos vistas del asistente y las plantillas QWeb del reporte en `ir_ui_view`, y `print_report_name` de `action_report_customer_account_statement`.
- **Nuevo:** menú Contabilidad / Facturación → Proveedores → Estado de cuenta y botón **"Cuenta proveedor"** en la ficha del contacto (solo proveedores).
  - Base de datos: menú nuevo `menu_supplier_account_statement` en `ir_ui_menu`; se actualiza `arch_db` de `res_partner_view_form_inherit_account_statement`.
- **Nuevo:** imputación en sentido proveedor (pago o NC del proveedor contra sus facturas/ND, con importe parcial en moneda de la empresa) y validación de cliente/proveedor, empresa, cuenta, estado y signo antes de imputar.
  - Base de datos: columna nueva `partner_type` en `customer_account_statement_reconcile`; se actualiza `arch_db` de `customer_account_statement_reconcile_view_form`. Al imputar o desimputar proveedores se escriben y borran filas de `account_partial_reconcile`, igual que con clientes.
- **Nuevo:** plantilla de email "Estado de cuenta: envío de resumen al proveedor".
  - Base de datos: registro nuevo `mail_template_supplier_account_statement` en `mail_template` (`noupdate`).
- **Cambio:** los controles de permisos pasan a los métodos `_check_partner_access(partner, partner_type)`, `_can_reconcile`, `_can_unreconcile` y `_can_send`, que otros módulos pueden extender. Los botones Imputar, Desimputar y Enviar por email se muestran según campos calculados en lugar de `groups`. Para clientes, los permisos no cambian.
  - Base de datos: campos calculados nuevos sin columna (`can_reconcile`, `can_unreconcile`, `can_send` y `account_partial_reconcile.statement_can_unreconcile`); se actualiza `arch_db` de `account_partial_reconcile_view_list_statement`. Sin cambios en `ir_access`.
- **Corrección:** el PDF adjunto al enviar por email salía vacío. Odoo 20 ignora el campo `datas` de `ir.attachment`, y ahora el contenido se guarda con `raw`.
  - Base de datos: sin cambios de estructura. Los adjuntos nuevos de `ir_attachment` guardan el PDF.

### 2026-10-20 — versión 1.1 ([SPEC 02](../specs/02-app-clientes.md))
- **Cambio:** el asistente previo ya no pide "Empresas". La consulta abre con todas las empresas permitidas del cliente tildadas.
  - Base de datos: se actualiza `arch_db` de `customer_account_statement_view_form`. `company_ids` deja de ser obligatorio (no tiene columna: sin cambio de estructura).
- **Nuevo:** pantalla de resultado (formulario) con casillas de empresas, modo y fechas editables y recálculo automático, cuadro "Saldos por moneda" y lista de movimientos con sus botones. Imprimir y Enviar por email pasan a la cabecera.
  - Base de datos: tabla nueva `customer_account_statement_currency`; columna nueva `is_result` en `customer_account_statement`; 2 permisos nuevos en `ir_access` (`access_customer_account_statement_currency_invoice` y `_salesman`); vista nueva `customer_account_statement_view_form_result` en `ir_ui_view`; la acción `action_customer_account_statement` fija su vista (`view_id`).
- **Eliminado:** la lista de líneas como pantalla aparte (`customer_account_statement_line_view_list`) y sus botones Imprimir/Enviar por email.
  - Base de datos: Odoo borra la vista `customer_account_statement_line_view_list` de `ir_ui_view` al actualizar.
- **Documentación:** se agrega el requisito del motor de PDF (wkhtmltopdf en el `PATH`) a las configuraciones esenciales.
  - Base de datos: sin cambios.
- **Cambio:** en la ficha del cliente, "Empresas en las que participa" pasa de etiquetas (`many2many_tags`) a casillas para tildar (`many2many_checkboxes`).
  - Base de datos: se actualiza `arch_db` de la vista `res_partner_view_form_inherit_account_statement` en `ir_ui_view`. Sin cambios de tablas ni de datos.
- **Corrección:** el asistente fallaba al abrirse con `EvalError: Name 'len' is not defined`. La vista usaba `len(company_ids)` en un `invisible`, y el evaluador del navegador no tiene `len`. Ahora usa el campo calculado `is_consolidated`.
  - Base de datos: se actualiza `arch_db` de la vista `customer_account_statement_view_form` en `ir_ui_view`. Sin cambios de tablas ni de datos.
- Se agrega este README, con el detalle de base de datos y permisos.
  - Base de datos: sin cambios.

### 1.0
- Versión inicial según [specs/01-estado-de-cuenta-clientes.md](../specs/01-estado-de-cuenta-clientes.md).
  - Base de datos: crea las 6 tablas de [Tablas nuevas](#tablas-nuevas), los 10 permisos de `ir_access` y los registros de configuración. No modifica tablas existentes.
