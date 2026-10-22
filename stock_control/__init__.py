from . import models
from . import report
from . import wizard


def _uninstall_hook(env):
    # Al desinstalar, Odoo borra los motivos iniciales antes que las tablas, y los movimientos
    # manuales que los usan lo impiden (clave foránea RESTRICT). Esos movimientos se pierden
    # igual con sus tablas: se vacían antes. Las líneas caen en cascada y stock_move queda
    # con el vínculo en NULL.
    env.cr.execute("DELETE FROM stock_control_manual_move")
