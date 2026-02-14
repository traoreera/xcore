from configurations import core
from hooks import HookManager

xcfg = core.Xcorecfg(conf=core.Configure())

# Global hook manager instance
xhooks = HookManager()