# AGENTS.md

Instrucciones para agentes (Claude Code, Codex, etc.) que trabajan en `custom_addons`.

## Contexto

- Módulos propios para **Odoo 20.0**. El código de Odoo está en `../odoo` (rama `20.0`).
- Cada carpeta de primer nivel es un módulo (`customer_account_statement`, `customer_visit`, ...). `specs/` guarda las especificaciones.
- Para correr Odoo, este directorio tiene que estar en el addons path:

  ```powershell
  cd ..\odoo
  python odoo-bin -r odoo_user -w <password> --addons-path=addons,..\custom_addons -d <base>
  ```

  Si falta, Odoo muestra `module <nombre>: not installable, skipped` y no carga el módulo.

## Regla obligatoria: README.md en cada módulo

**Todo módulo tiene que tener un `README.md` dentro de su propia carpeta** (`<modulo>/README.md`, nunca en la raíz ni en otro lugar).

- **Módulo nuevo:** el README se crea en la misma tarea que el módulo. Un módulo sin README no está terminado.
- **Cambio en un módulo existente:** en la misma tarea se actualizan las secciones del README que el cambio afecte y se agrega una entrada al historial de cambios.
- **Módulo existente sin README:** se crea antes de darlo por terminado, leyendo el código. No se documenta de memoria.

El README tiene que tener, como mínimo, estas secciones:

1. **Título y ficha:** nombre, nombre técnico, versión de Odoo, dependencias, licencia y una frase sobre qué resuelve.
2. **Qué hace:** las funciones, en lenguaje de usuario.
3. **Qué agrega o modifica en Odoo:** campos, botones, menús, reportes, plantillas, permisos y modelos nuevos, y qué modelos estándar hereda. Si no toca el comportamiento estándar, decirlo.
4. **Cómo funciona:** las reglas de negocio (qué datos toma, cómo calcula, qué valida).
5. **Uso:** paso a paso con la ruta de menú real.
6. **Configuraciones esenciales:** todo lo que hay que configurar para que funcione (campos a cargar, grupos de usuarios, empresas, plantillas, servidores, parámetros), con la ruta exacta en la interfaz.
7. **Permisos:** tabla con cada registro de `ir.access` (ID externo, modelo, grupo, operaciones, filtro y para qué sirve), más los controles hechos en el código y los usos de `sudo()`.
8. **Base de datos:** ver la regla siguiente.
9. **Instalación y actualización:** comandos con `-i` / `-u` y el addons path.
10. **Limitaciones conocidas.**
11. **Historial de cambios:** una entrada por cambio, con fecha absoluta (`AAAA-MM-DD`), qué cambió y por qué. Lo más nuevo arriba.

Antes de escribir algo en el README, verificarlo en el código: nombres de menú, grupos, campos y comportamiento tienen que coincidir con lo que el módulo hace de verdad.

Ejemplo de referencia: [customer_account_statement/README.md](customer_account_statement/README.md).

## Regla obligatoria: README.md principal actualizado

El [README.md](README.md) de la raíz es el índice del repo y **tiene que estar siempre al día** con los módulos que existen. En la misma tarea en que se crea, renombra, borra o cambia un módulo, se revisa y actualiza:

- **Tabla "Módulos":** una fila por módulo, con enlace a su README, nombre, qué resuelve y dependencias (iguales al `depends` del `__manifest__.py`).
- **Diagrama de dependencias** (`mermaid`): una flecha por cada dependencia de cada módulo.
- **Estructura del repositorio:** una línea por carpeta de módulo.
- **Comando de instalación de "Todos"** (`-i ...`): todos los módulos, en orden de dependencias.
- **Párrafo de introducción** y **Requisitos** (por ejemplo, si un módulo empieza a usar librerías de Python externas).

Una tarea que agrega o cambia un módulo no está terminada si el README principal quedó desactualizado.

## Regla obligatoria: cambios en la base de datos

Todo lo que un módulo crea o modifica en la base **se documenta en el `README.md` del módulo**, en la sección **"Base de datos"**, que incluye:

- **Resumen:** cantidad de tablas nuevas, si modifica tablas existentes y qué datos estándar escribe (por ejemplo, conciliaciones o asientos).
- **Esquema relacional:** diagrama `mermaid` `erDiagram` de las tablas nuevas, cómo se relacionan entre sí y con las tablas existentes de Odoo, con el nombre del campo en cada relación.
- **Tablas nuevas:** por tabla, si es permanente o temporal, qué guarda y el detalle `Columna | Tipo | Nulo | Referencia | ON DELETE`, con clave primaria e índices.
- **Tablas existentes:** columnas agregadas, campos calculados sin columna y qué datos escribe el módulo en ellas.
- **Registros de configuración:** cantidad por tabla de metadatos (`ir_access`, `ir_ui_view`, `ir_ui_menu`, ...).
- **Al desinstalar:** qué datos se pierden y cuáles quedan.

Además, **cada entrada del historial de cambios** lleva una línea `Base de datos:` con el impacto exacto del cambio: tablas o columnas creadas, modificadas o borradas, permisos agregados o cambiados, vistas o datos actualizados. Si no hubo impacto, se escribe "sin cambios".

Los datos se sacan **de la base real**, no de memoria: el script `esquema_db.py` de la skill `modulo-odoo` releva tablas, columnas, claves foráneas y permisos de un módulo (solo lectura). Lo que el código escribe en tablas estándar se saca leyendo el código.

## Skill `modulo-odoo`

Claude Code tiene la skill **`modulo-odoo`** (`~/.claude/skills/modulo-odoo/`) con el procedimiento completo: código, actualización en la base, relevamiento con `esquema_db.py`, estructura del README e informe final. Usarla siempre que se cree o cambie un módulo de este directorio.

## Convenciones de código

- Textos visibles en **español rioplatense con voseo** ("Consultá", "Elegí"), igual que los módulos existentes.
- Mensajes de error con `self.env._(...)`.
- **Expresiones de vista** (`invisible`, `readonly`, `required`, `column_invisible`, `domain`, `context`): se evalúan en el navegador con un intérprete reducido ([py_builtin.js](../odoo/addons/web/static/src/core/py_js/py_builtin.js)). Solo hay `bool`, `set`, `max`, `min` y funciones de fecha; **no hay `len`, `any`, `all`, `sum`, etc.** Si hace falta una condición así, crear un campo calculado booleano y usarlo en la vista. En los reportes QWeb (que corren en el servidor) se puede usar Python normal.
- Permisos en `security/ir.access.csv` (formato de Odoo 20, con columna `domain` para filtrar registros).
- Seguir las guías de `../odoo/skills/` (`odoo-guidelines`, `odoo-security`, `odoo-review`).

## Regla obligatoria: dependencias de Python

Si un módulo usa una librería de Python que no viene con Odoo:

1. Se declara en `external_dependencies` del `__manifest__.py` (`{'python': ['<nombre del import>']}`).
2. Se lista en `<modulo>/requirements.txt` (paquete de pip y versión).
3. Se instala en el entorno del proyecto principal antes de instalar el módulo: `..\odoo\.venv\Scripts\python.exe -m pip install -r <modulo>\requirements.txt`.
4. Se documenta en "Instalación y actualización" del README.

Si no usa librerías externas, no se crea `requirements.txt`. No se instalan paquetes desde hooks del módulo. El detalle está en la skill `modulo-odoo`.

## Después de cambiar un módulo

1. Actualizar el módulo en la base con `-u <modulo> --stop-after-init` y revisar que el log no tenga `ERROR` ni `WARNING` nuevos.
2. Actualizar el `README.md` del módulo, incluida la sección "Base de datos" y la línea `Base de datos:` del historial (ver reglas obligatorias).
3. Revisar y actualizar el `README.md` principal (tabla de módulos, dependencias, estructura y comando de instalación).
4. Informar al usuario los archivos cambiados, los comandos corridos contra la base y los cambios en la base.
